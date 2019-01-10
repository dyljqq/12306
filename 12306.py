# coding: utf-8

import random
import requests
import urllib
import json
import time
import damatu

from urllib3 import disable_warnings
from collections import namedtuple
from urllib3.exceptions import InsecureRequestWarning

disable_warnings(InsecureRequestWarning)

BASE_URL = 'https://kyfw.12306.cn/'


State = namedtuple('State', ['abbr', 'name', 'code', 'pinyin', 'pyabbr'])

USER_NAME = '18868814424'
PASSWORD = 'dyljqq21'

FROM = '杭州'
TO = '丽水'

TYPE_VERIFY_CAPTCHA_FAILURE = 0
TYPE_VERIFY_CAPTCHA_SUCCESS = 1

TYPE_LOGIN_FAILURE = 0
TYPE_LOGIN_SUCCESS = 1


MAX_TRY_NUM = 3


class Passenger(object):
    def __init__(self, name, id_number):
        self.name = name
        self.id_number = id_number


class BaseTicket(object):
    def __init__(self):
        self.init_session()

    def init_session(self):
        self.session = requests.Session()
        self.session.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13) AppleWebKit/604.1.38 (KHTML, like Gecko) Version/11.0 Safari/604.1.38',            
            'Referer': 'https://kyfw.12306.cn/otn/',
            'Host': 'kyfw.12306.cn',
            'Connection': 'Keep-Alive',
            'refer': 'https://kyfw.12306.cn/otn/leftTicket/init'
        }

    def get(self, url):
        try:
            r = self.session.get(url, verify=False, timeout=5)
            return r
        except Exception as e:
            print e

    def post(self, url, data):
        try:
            r = self.session.post(url, data=data, headers=self.session.headers, verify=False, timeout=16)
            status_code = r.status_code
            if status_code != 200:
                print 'request url: %s, fail: %s' % (url, status_code)
            return r
        except Exception as e:
            print 'error: %s' % e


class Station(BaseTicket):

    def __init__(self):
        super(Station, self).__init__()

        self.states = self.init_station()

    def init_station(self):
        url = BASE_URL + 'otn/resources/js/framework/station_name.js'
        r = self.get(url)
        if not r:
            print u'初始化站牌地址失败~'

        data = r.content

        states = []
        stations = data.split('@')
        for station in stations[:2]:
            items = station.split('|')
            if len(items) < 5:
                continue

            state = State(
                abbr=items[0],
                name=items[1],
                code=items[2],
                pinyin=items[3],
                pyabbr=items[4]
            )
            states.append(state)
        return states


class User(BaseTicket):
    def __init__(self, user_name, password):
        super(User, self).__init__()

        self.user_name = user_name
        self.password = password

        self.uamtk = ''
        self.captcha_location = [
            '44,44',
            '114,44',
            '185,44',
            '254,44',
            '44,124',
            '114,124',
            '185,124',
            '254,124',
        ]

        ret = self.login()
        if ret:
            self.check_uam()
            self.get_real_name()
            self.init_my_12306()
            self.get_passenger_dtos()

    def init_login(self):
        url = BASE_URL + 'otn/login/init'
        self.session.headers.update({
            'Referer': BASE_URL + 'otn',
            'method': 'GET'
        })
        self.get(url)

    def login(self):
        self.init_login()

        if self.session.cookies:
            cookies = requests.utils.dict_from_cookiejar(self.session.cookies)
            self.jessionid = cookies.get('JSESSIONID', '')

        code = self.check_rand_code('login')
        if code == TYPE_VERIFY_CAPTCHA_SUCCESS:
            url = BASE_URL + 'passport/web/login'
            params = {
                'username': self.user_name,
                'password': self.password,
                'appid': 'otn'
            }
            r = self.session.post(url, data=params)
            r = r.json()
            code = r.get('result_code', '')
            if code == 0:
                self.uamtk = r.get('uamtk', '')
                return TYPE_LOGIN_SUCCESS
        return TYPE_LOGIN_FAILURE

    def check_rand_code(self, module):
        rand = 'sjrand'

        captcha_url = self._get_passcode_url(module, rand)
        
        num = 1
        while num < MAX_TRY_NUM:
            if num > 1:
                captcha_url += str(random.random())

            self.captcha = self._get_capcha(captcha_url)
            if not self.captcha:
                continue

            url = self.check_rand_code_url
            params = {
                'answer': self.captcha,
                'rand': rand,
                'login_site': 'E',
                '_': int(time.time() * 1000)
            }

            self.session.headers.update({
                'method': 'POST',
                'Referer': self.login_url,
                'X-Requested-With': 'XMLHttpRequest'
            })
            r = self.post(url, params)
            d = r.json()
            if d.get('result_code', '') == '4':
                return TYPE_VERIFY_CAPTCHA_SUCCESS
            else:
                print 'fail to get captcha: %s' % d

            num += 1
        return TYPE_VERIFY_CAPTCHA_FAILURE

    def get_passenger_dtos(self):
        url = BASE_URL + 'otn/confirmPassenger/getPassengerDTOs'
        data = {
            '_json_att': '',
            'REPEAT_SUBMIT_TOKEN': ''
        }
        r = self.post(url, data=data)
        d = r.json()
        passengers = r.get('data', {}).get('normal_passengers', [])
        self.passengers = [Passenger(name=passenger['passenger_name'], id_number=passenger['passenger_id_no']) for passenger in passengers]

    def check_uam(self):
        url = BASE_URL + 'passport/web/auth/uamtk'
        data = {
            'appid': 'otn'
        }
        r = self.post(url, data=data)

        d = r.json()

        self.app_tk = ''
        code = d.get('result_code', -1)
        if code == 0:
            self.app_tk = d.get('newapptk', '') or d.get('apptk', '')
            return True
        return False

    def get_real_name(self):
        if not self.app_tk:
            print 'apptk为空~'
        
        url = BASE_URL + 'otn/uamauthclient'
        data = {
            'tk': self.app_tk
        }
        r = self.post(url, data=data)
        d = r.json()
        code = d.get('result_code', 0)
        if code == 0:
            self.name = d.get('username', '')
            return True
        return False

    def init_my_12306(self):
        url = BASE_URL + 'otn/index/initMy12306'
        r = self.get(url)
        return r.content

    def _get_capcha(self, url):
        self.session.headers.update({
            'method': 'GET',
            'Referer': self.login_url
        })
        try:
            r = self.session.get(url, verify=False, stream=True, timeout=15)
            with open('captcha.gif', 'wb') as fd:
                for chunk in r.iter_content():
                    fd.write(chunk)

            print(u'请输入4位图片验证码(回车刷新验证码):')
            pos = raw_input()
            code = self._get_rand_code(pos)
            return code
        except Exception as e:
            print 'captch error: %s' % e

    def _get_rand_code(self, pos):
        ps = pos.split(',')
        return ','.join([self.captcha_location[int(p)] for p in ps])

    def _get_passcode_url(self, module, rand):
        return BASE_URL + 'passport/captcha/captcha-image?login_site=E&module=login&rand=sjrand&'

    @property
    def login_url(self):
        return 'https://kyfw.12306.cn/otn/login/init'

    @property
    def check_rand_code_url(self):
        return BASE_URL + 'passport/captcha/captcha-check'


def main():
    # station = Station()
    user = User(user_name=USER_NAME, password=PASSWORD)


if __name__ == '__main__':
    main()
    

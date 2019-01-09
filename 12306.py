# coding: utf-8

import random
import requests
import urllib
import json
import time

from collections import namedtuple

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

DEFAULT_HEADER = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13) AppleWebKit/604.1.38 (KHTML, like Gecko) Version/11.0 Safari/604.1.38',
    'Referer': 'https://kyfw.12306.cn/otn/',
    'Host': 'kyfw.12306.cn',
    'Connection': 'Keep-Alive',
    'refer': 'https://kyfw.12306.cn/otn/leftTicket/init'
}


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

    def post(self, url, data, headers=DEFAULT_HEADER):
        try:
            r = self.session.post(url, data=data, headers=headers, verify=False, timeout=16)
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

        self.login()

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
            r = self.session.post(url, data=params, headers=self.session.headers)
            r = r.json()
            code = r.get('result_code', '')
            if code == 0:
                self.uamtk = r.get('uamtk', '')
                return TYPE_LOGIN_SUCCESS
        return TYPE_LOGIN_FAILURE

    def check_rand_code(self, module):
        rand = 'sjrand'

        url = self._get_passcode_url(module, rand)
        
        num = 1
        while num < MAX_TRY_NUM:
            if num > 1:
                url = url + str(random.random())

            self.captcha = self._get_capcha(url)
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
            r = self.post(url, params, headers=self.session.headers)
            d = r.json()
            if d.get('result_code', '') == '4':
                return TYPE_VERIFY_CAPTCHA_SUCCESS
            else:
                print 'fail to get captcha: %s' % d

            num += 1
        return TYPE_VERIFY_CAPTCHA_FAILURE

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
    

# coding: utf-8

import random
import requests
import urllib
import json
import time
import re

from datetime import datetime
from urllib3 import disable_warnings
from collections import namedtuple
from urllib3.exceptions import InsecureRequestWarning

disable_warnings(InsecureRequestWarning)

BASE_URL = 'https://kyfw.12306.cn/'


USER_NAME = '18868814424'
PASSWORD = 'dyljqq21'

TYPE_VERIFY_CAPTCHA_FAILURE = 0
TYPE_VERIFY_CAPTCHA_SUCCESS = 1

TYPE_LOGIN_FAILURE = 0
TYPE_LOGIN_SUCCESS = 1

FROM_STATE_NAME = '杭州'
TO_STATE_NAME = '丽水'


MAX_TRY_NUM = 3


class RequestManage(object):
    def __init__(self):
        self.cookie_filename = 'cookies.txt'
        self.session = requests.session()
        self.refer = 'https://kyfw.12306.cn/otn/leftTicket/init'
        self.session.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13) AppleWebKit/604.1.38 (KHTML, like Gecko) Version/11.0 Safari/604.1.38',
            'Referer': 'https://kyfw.12306.cn/otn/',
            'Host': 'kyfw.12306.cn',
            'Connection': 'Keep-Alive',
            'refer': self.refer
        }

    def get(self, url):
        try:
            r = self.session.get(url, verify=False, timeout=5)
            return r
        except Exception as e:
            print e

    def post(self, url, data={}):
        try:
            self.session.headers.update({
                'refer': self.refer
            })
            r = self.session.post(
                url, data=data, headers=self.session.headers, verify=False, timeout=16)
            status_code = r.status_code
            if status_code != 200:
                print 'request url: %s, fail: %s' % (url, status_code)
            return r
        except Exception as e:
            print 'error: %s' % e

    def save_cookie(self):
        cookies = requests.utils.dict_from_cookiejar(self.session.cookies)
        with open(self.cookie_filename, 'w') as f:
            f.write(json.dumps(cookies))

    def get_cookie(self):
        try:
            with open(self.cookie_filename, 'r') as f:
                load_cookies = json.load(f)
            if load_cookies:
                self.session.cookie = requests.utils.cookiejar_from_dict(load_cookies)
            return bool(load_cookies)
        except Exception:
            pass
        return False

request_manage = RequestManage()


class State(object):
    def __init__(self, abbr, name, code, pinyin, pyabbr):
        self.abbr = abbr
        self.name = name
        self.code = code
        self.pinyin = pinyin
        self.pyabbr = pyabbr


class Passenger(object):
    def __init__(self, name, id_number):
        self.name = name
        self.id_number = id_number


class TicketParams(object):
    def __init__(self, fr, to, date, purpose_code='ADULT'):
        self.fr = fr
        self.to = to
        self.date = date
        self.purpose_code = purpose_code

    def to_param(self):
        arr = [
            'leftTicketDTO.train_date=%s' % self.date,
            'leftTicketDTO.from_station=%s' % self.fr.code,
            'leftTicketDTO.to_station=%s' % self.to.code,
            'purpose_codes=%s' % self.purpose_code
        ]
        return '&'.join(arr)


class OrderParam(object):
    def __init__(self, ticket, train_date='', purpose_code='ADULT'):
        self.ticket = ticket
        self.purpose_code = purpose_code
        self.train_date = train_date
        self.tour_flag = 'dc'  # 单程dc，往返wf

    def to_params(self):
        return {
            'secretStr': self.ticket.secret_str,
            'train_date': self.train_date,
            'back_train_date': self.train_date,
            'purpose_codes': self.purpose_code,
            'query_from_station_name': self.ticket.from_station_name,
            'query_to_station_name': self.ticket.to_station_name,
            'undefined': '',
            'tour_flag': self.tour_flag
        }


class TicketInfo(object):
    def __init__(self, secret_str, button_text, train_no, train_code, start_station_tel_code, end_station_code,
                 from_station_code, to_station_code, start_time, arrive_time, cost_time, can_web_buy,
                 yp_info, start_train_date, train_seat_type, location_code, from_station_no,
                 to_station_no, is_support_card, controlled_train_flag, swt, ydz, erdz, gjrw,
                 rwy, dw, ywer, rz, yz, wz, other, _map={}):
        self.secret_str = urllib.unquote(secret_str)
        self.button_text = button_text
        self.train_no = train_no
        self.train_code = train_code
        self.start_station_tel_code = start_station_tel_code
        self.end_station_code = end_station_code
        self.from_station_code = from_station_code
        self.to_station_code = to_station_code
        self.start_time = start_time
        self.arrive_time = arrive_time
        self.cost_time = cost_time  # 历时多久
        self.can_web_buy = can_web_buy
        self.yp_info = yp_info
        self.start_train_date = start_train_date
        self.train_seat_type = train_seat_type
        self.location_code = location_code
        self.from_station_code = from_station_code
        self.to_station_code = to_station_code
        self.is_support_card = is_support_card
        self.controlled_train_flag = controlled_train_flag
        self.swt = swt  # 商务特等座
        self.ydz = ydz  # 一等座
        self.erdz = erdz  # 二等座
        self.gjrw = gjrw  # 高级软卧
        self.rwy = rwy  # 软卧一等座
        self.dw = dw  # 动卧
        self.ywer = ywer  # 硬卧二等座
        self.rz = rz  # 软座
        self.yz = yz  # 硬座
        self.wz = wz  # 无座
        self.other = other  # 其他

        self.from_station_name = _map[from_station_code]
        self.to_station_name = _map[to_station_code]

    def is_high_train(self):
        return self.train_code[0] == 'G'


class Train(object):
    def __init__(self, ticket_params=None):
        self.ticket_params = ticket_params
        self.param_str = self.ticket_params.to_param()
        
        self.setup()

    def setup(self):
        self.init_query_ticket()
        self.query_http_zf()
        self.query_ticket_log()

        self.tickets = []
        
        _map, tks = self.query_tickets()
        for tk in tks:
            rs = tk.split('|')
            if not rs:
                continue
            ticket = TicketInfo(*rs[:31], _map=_map)
            self.tickets.append(ticket)

    def init_query_ticket(self):
        url = BASE_URL + 'otn/leftTicket/init?linktypeid=dc&fs=%s,HZH&ts=%s,USH&date=%s&flag=N,N,Y' % (
            self.ticket_params.fr.name, self.ticket_params.to.name, self.ticket_params.date
        )
        return request_manage.get(url)

    def query_http_zf(self):
        url = BASE_URL + 'otn/HttpZF/GetJS'
        r = request_manage.get(url)
        return r.content

    def query_ticket_log(self):
        url = BASE_URL + 'otn/leftTicket/log?' + self.param_str
        r = request_manage.get(url)
        return r.json()

    def query_tickets(self):
        url = BASE_URL + 'otn/leftTicket/queryZ?' + self.param_str
        r = request_manage.get(url)
        try:
            data = r.json()
            data = data.get('data', {})
            if not data:
                return []
            
            flag = data.get('flag', 0)
            if int(flag) != 1:
                return []
            return data.get('map', {}), data.get('result', [])
        except Exception as e:
            print 'query ticket error: %s' % e
        
        return {}, []

    def query_ticket_price(self, ticket_info):
        params = {
            'train_no': ticket_info.train_no,
            'from_station': ticket_info.from_station_no,
            'to_station_no': ticket_info.to_station_no,
            'seat_types': ticket_info.seat_types,
            'train_date': ticket_info.train_date
        }
        url = BASE_URL + '/otn/leftTicket/queryTicketPrice?' + urllib.urlencode(params)
        print 'query ticket price: %s' % url
        r = request_manage.get(url)
        print r.content

    # 搜索特定条件的车票
    def get_tickets(self, is_high_train=True, start_time=''):
        for ticket in self.tickets:
            if is_high_train and not ticket.is_high_train:
                continue


class Station(object):

    def __init__(self):
        self.state_dict = {}
        self.states = self.init_station()

    def init_station(self):
        url = BASE_URL + 'otn/resources/js/framework/station_name.js'
        r = request_manage.get(url)
        if not r:
            print u'初始化站牌地址失败~'

        data = r.content

        states = []
        stations = data.split('@')
        for station in stations:
            items = station.split('|')
            if len(items) < 5:
                continue

            name = items[1]
            state = State(
                abbr=items[0],
                name=name,
                code=items[2],
                pinyin=items[3],
                pyabbr=items[4]
            )
            self.state_dict[name] = state
            states.append(state)
        return states

    def get_state_by_name(self, state_name):
        return self.state_dict.get(state_name, '')


class User(object):
    def __init__(self, user_name, password):
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
            if self.passengers:
                print 'login success...'

    def init_login(self):
        url = BASE_URL + 'otn/login/init'
        request_manage.session.headers.update({
            'Referer': BASE_URL + 'otn',
            'method': 'GET'
        })
        request_manage.get(url)

    def login(self):
        self.init_login()

        if request_manage.session.cookies:
            cookies = requests.utils.dict_from_cookiejar(request_manage.session.cookies)
            self.jessionid = cookies.get('JSESSIONID', '')

        code = self.check_rand_code('login')
        if code == TYPE_VERIFY_CAPTCHA_SUCCESS:
            url = BASE_URL + 'passport/web/login'
            params = {
                'username': self.user_name,
                'password': self.password,
                'appid': 'otn'
            }
            r = request_manage.session.post(url, data=params)
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

            request_manage.session.headers.update({
                'method': 'POST',
                'Referer': self.login_url,
                'X-Requested-With': 'XMLHttpRequest'
            })
            r = request_manage.post(url, params)
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
        try:
            r = request_manage.post(url, data=data)
            d = r.json()
            passengers = d.get('data', {}).get('normal_passengers', [])
            self.passengers = [Passenger(name=passenger['passenger_name'], id_number=passenger['passenger_id_no']) for passenger in passengers]
        except Exception as e:
            print 'get passengers error: %s' % e

    def check_uam(self):
        url = BASE_URL + 'passport/web/auth/uamtk'
        data = {
            'appid': 'otn'
        }
        r = request_manage.post(url, data=data)

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
        r = request_manage.post(url, data=data)
        d = r.json()
        code = d.get('result_code', 0)
        if code == 0:
            self.name = d.get('username', '')
            return True
        return False

    def init_my_12306(self):
        url = BASE_URL + 'otn/index/initMy12306'
        r = request_manage.get(url)
        return r.content

    def _get_capcha(self, url):
        request_manage.session.headers.update({
            'method': 'GET',
            'Referer': self.login_url
        })
        try:
            r = request_manage.session.get(url, verify=False, stream=True, timeout=15)
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


class Order(object):
    def __init__(self, order_param):
        self.order_param = order_param

        self.setup()

    def setup(self):
        self.check_user()
        self.submit_order()
        self.init_dc()
        self.request_dynamic_js()

    def check_user(self):
        url = BASE_URL + 'otn/login/checkUser'
        params = {
            '_json_att': ''
        }
        r = request_manage.post(url, data=params)
        flag = r.json()['data']['flag']
        return flag

    def submit_order(self):
        url = 'https://kyfw.12306.cn/otn/leftTicket/submitOrderRequest'
        r = request_manage.post(url, data=self.order_param.to_params())
        r = r.json()
        status = r['status']
        if not status:
            print 'submit order error: %s' % r['messages']
        return status

    def init_dc(self):
        url = BASE_URL + 'otn/confirmPassenger/initDc'
        params = {
            '_json_att': ''
        }
        r = request_manage.post(url, data=params)
        if not r:
            return

        content = r.content
        self.submit_token = self._get_submit_token(content)
        self.dynamic_js = self._get_dynamic_js(content)
        self.key_check = self._get_key_check_is_change(content)
        self.train_location = self._get_train_location(content)

    def request_dynamic_js(self):
        url = BASE_URL + 'otn/dynamicJs/%s' % self.dynamic_js
        request_manage.refer = 'https://kyfw.12306.cn/otn/confirmPassenger/initDc'
        print 'dynamicJs: %s' % url
        r = request_manage.get(url)
        print r.content

    def pre_order(self):
        def _get_passenger_dtos(token):
            url = BASE_URL + 'otn/confirmPassenger/getPassengerDTOs'
            params = {
                '_json_att': '',
                'REPEAT_SUBMIT_TOKEN': token
            }
            r = request_manage.post(url, data=params)
            data = r.json()['data']
            passengers = data['normal_passengers']
            return [Passenger(name=passenger['passenger_name'], id_number=passenger['passenger_id_no']) for passenger in passengers]

        def get_passcode():
            url = BASE_URL + 'otn/passcodeNew/getPassCodeNew?module=passenger&rand=randp&' % (random.random())
            r = request_manage.get(url)

        self.passengers = _get_passenger_dtos(self.submit_token)

    def _get_submit_token(self, content):
        # var globalRepeatSubmitToken = 'dd589b01b7cf3dc403d05802b8ac5bdc';
        regex = 'var globalRepeatSubmitToken = \'[a-zA-Z0-9]+'
        r = self._parse(regex, content)
        return r.split('= \'')[1] if r else ''

    def _get_dynamic_js(self, content):
        # /otn/dynamicJs/ovvpnjg
        regex = '"/otn/dynamicJs/[a-zA-z0-9]+'
        r = self._parse(regex, content)
        return r.split('/')[3] if r else ''

    def _get_key_check_is_change(self, content):
        # 'key_check_isChange':'4631B83132BFE9C54D666BA79ABA34CE59DBCF5A6704A7A61DD272F9
        regex = '\'key_check_isChange\':\'[a-zA-Z0-9]+'
        r = self._parse(regex, content)
        return r.split(':')[1] if r else ''

    def _get_train_location(self, content):
        regex = '\'train_location\': \'[A-Za-z0-9]+'
        r = self._parse(regex, content)
        return r.split(':\'')[1] if r else ''

    def _parse(self, regex, content):
        r = re.search(regex, content)
        if r:
            return r.group()


def main():
    global request_manage
    _ = User(user_name=USER_NAME, password=PASSWORD)

    station = Station()
    fr = station.get_state_by_name(FROM_STATE_NAME)
    to = station.get_state_by_name(TO_STATE_NAME)
    date = datetime.now().strftime('%Y-%m-%d %H:%M:%S').split(' ')[0]
    ticket_param = TicketParams(fr=fr, to=to, date=date)
    train = Train(ticket_params=ticket_param)

    if train.tickets:
        for tk in train.tickets:
            if tk.secret_str:
                order_param = OrderParam(tk, train_date=date)
                order = Order(order_param=order_param)
                break


if __name__ == '__main__':
    main()

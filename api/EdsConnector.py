#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests, pickle, json, os, math
from bs4 import BeautifulSoup
from urllib.parse import urlparse, unquote
import logging
from datetime import datetime, timedelta
from dateutil.tz import tzutc

UTC = tzutc()

_LOGGER = logging.getLogger(__name__)

class EdisError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)

class UrlError(EdisError):
    def __init__(self, status_code, message, request):
        self.status_code = status_code
        self.request = request
        super().__init__(message)
    pass

def serialize_date(dt):
    """
    Serialize a date/time value into an ISO8601 text representation
    adjusted (if needed) to UTC timezone.

    For instance:
    >>> serialize_date(datetime(2012, 4, 10, 22, 38, 20, 604391))
    '2012-04-10T22:38:20.604391Z'
    """
    if dt.tzinfo:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt.isoformat() 

class EdsConnector():
    __session = None
    SESSION_FILE = '/tmp/edistribucion.session'
    ACCESS_FILE = '/tmp/edistribucion.access'
    __token = 'undefined'
    __credentials = {}
    __dashboard = 'https://zonaprivada.edistribucion.com/areaprivada/s/sfsites/aura?'
    __command_index = 0
    __identities = {}
    __appInfo = None
    __context = None
    __access_date = datetime.now()
    __do_save_session = False
    
    def __init__(self, user, password, do_save_session=False, debug_level=_LOGGER.debug):
        self.__session = requests.Session()
        self.__credentials['user'] = user
        self.__credentials['password'] = password
        self.__do_save_session=do_save_session
        if self.__do_save_session:
            try:
                with open(EdsConnector.SESSION_FILE, 'rb') as f:
                    self.__session.cookies.update(pickle.load(f))
            except FileNotFoundError:
                _LOGGER.warning('Session file not found')
            try:
                with open(EdsConnector.ACCESS_FILE, 'rb') as f:
                    d = json.load(f)
                    self.__token = d['token']
                    self.__identities = d['identities']
                    self.__context = d['context']
                    self.__access_date = datetime.fromisoformat(d['date'])
            except FileNotFoundError:
                _LOGGER.warning('Access file not found')
        
    def __get_url(self, url,get=None,post=None,json=None,cookies=None,headers=None):
        __headers = {
            'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:77.0) Gecko/20100101 Firefox/77.0',
        }
        if (headers):
            __headers.update(headers)
        if (post == None and json == None):
            r = self.__session.get(url, params=get, headers=__headers, cookies=cookies)
        else:
            r = self.__session.post(url, data=post, json=json, params=get, headers=__headers, cookies=cookies)
        _LOGGER.debug('Sending %s request to %s', r.request.method, r.url)
        _LOGGER.debug('Parameters: %s', r.request.url)
        _LOGGER.debug('Headers: %s', r.request.headers)
        _LOGGER.debug('Response with code: %d', r.status_code)
        _LOGGER.debug('Headers: %s', r.headers)
        _LOGGER.debug('History: %s', r.history)
        if r.status_code >= 400:
            try:
                e = r.json()
                msg = 'Error {}'.format(r.status_code)
                _LOGGER.debug('Response error in JSON format')
                if ('error' in e):
                    msg += ':'
                    if ('errorCode' in e['error']):
                        msg += ' [{}]'.format(e['error']['errorCode'])
                    if ('description' in e['error']):
                        msg += ' '+e['error']['description']
            except ValueError:
                _LOGGER.debug('Response error is not JSON format')
                msg = "Error: status code {}".format(r.status_code)
            raise UrlError(r.status_code, msg, r)
        return r
    
    def __command(self, command, post=None, dashboard=None, accept='*/*', content_type=None, recursive=True):
        if (not dashboard):
            dashboard = self.__dashboard
        if (self.__command_index):
            command = 'r='+self.__command_index+'&'
            self.__command_index += 1
        _LOGGER.debug('Preparing command: %s', command)
        if (post):
            post['aura.context'] = self.__context
            post['aura.pageURI'] = '/areaprivada/s/wp-online-access'
            post['aura.token'] = self.__token
            _LOGGER.debug('POST data: %s', post)
        _LOGGER.debug('Dashboard: %s', dashboard)
        if (accept):
            _LOGGER.debug('Accept: %s', accept)
        if (content_type):
            _LOGGER.debug('Content-tpye: %s', content_type)
        headers = {}
        if (content_type):
            headers['Content-Type'] = content_type
        if (accept):
            headers['Accept'] = accept
        r = self.__get_url(dashboard+command, post=post, headers=headers)
        if ('window.location.href' in r.text or 'clientOutOfSync' in r.text):
            if (not recursive):
                _LOGGER.debug('Redirection received. Fetching credentials again.')
                self.__session = requests.Session()
                self.__force_login()
                self.__command(command=command, post=post, dashboard=dashboard, accept=accept, content_type=content_type, recursive=True)
            else:
                _LOGGER.warning('Redirection received twice. Aborting command.')
        elif ('json' in r.headers['Content-Type']):
            jr = r.json()
            if (jr['actions'][0]['state'] != 'SUCCESS'):
                if (not recursive):
                    _LOGGER.debug('Got an error. Fetching credentials again.')
                    self.__session = requests.Session()
                    self.__force_login()
                    self.__command(command=command, post=post, dashboard=dashboard, accept=accept, content_type=content_type, recursive=True)
                else:
                    _LOGGER.warning('Got an error. Aborting command.')
                    raise EdisError('Error processing command: {}'.format(jr['actions'][0]['error'][0]['message']['message']))
            return jr['actions'][0]['returnValue']
        return r
    
    def __check_tokens(self):
        _LOGGER.debug('Checking tokens')
        return self.__token != 'undefined' and self.__access_date+timedelta(minutes=10) > datetime.now()
        
    def __save_access(self):
        t = {}
        t['token'] = self.__token
        t['identities'] = self.__identities
        t['context'] = self.__context
        t['date'] = datetime.now()
        if self.__do_save_session:
            with open(EdsConnector.ACCESS_FILE, 'w') as f:
                json.dump(t, f, default=serialize_date)
            _LOGGER.debug('Saving access to file')
        
    def login(self):
        _LOGGER.debug('Login')
        if (not self.__check_tokens()):
            self.__session = requests.Session()
            return self.__force_login()
        return True
    
    def __force_login(self, recursive=True):
        _LOGGER.debug('Forcing login')
        r = self.__get_url('https://zonaprivada.edistribucion.com/areaprivada/s/login?ec=302&startURL=%2Fareaprivada%2Fs%2F')
        ix = r.text.find('auraConfig')
        if (ix == -1):
            raise EdisError('auraConfig not found. Cannot continue')
        
        soup = BeautifulSoup(r.text, 'html.parser')
        scripts = soup.find_all('script')
        _LOGGER.debug('Loading scripts')
        for s in scripts:
            src = s.get('src')
            if (not src):
                continue
            #print(s)
            upr = urlparse(r.url)
            r = self.__get_url(upr.scheme+'://'+upr.netloc+src)
            if ('resources.js' in src):
                unq = unquote(src)
                self.__context = unq[unq.find('{'):unq.rindex('}')+1]
                self.__appInfo = json.loads(self.__context)
        _LOGGER.debug('Performing login routine')
        data = {
                'message':'{"actions":[{"id":"91;a","descriptor":"apex://LightningLoginFormController/ACTION$login","callingDescriptor":"markup://c:WP_LoginForm","params":{"username":"'+self.__credentials['user']+'","password":"'+self.__credentials['password']+'","startUrl":"/areaprivada/s/"}}]}',
                'aura.context':self.__context,
                'aura.pageURI':'/areaprivada/s/login/?language=es&startURL=%2Fareaprivada%2Fs%2F&ec=302',
                'aura.token':'undefined',
                }
        r = self.__get_url(self.__dashboard+'other.LightningLoginForm.login=1',post=data)
        #print(r.text)
        if ('/*ERROR*/' in r.text):
            if ('invalidSession' in r.text and not recursive):
                self.__session = requests.Session()
                self.__force_login(recursive=True)
            raise EdisError('Unexpected error in loginForm. Cannot continue')
        jr = r.json()
        if ('events' not in jr):
            raise EdisError('Wrong login response. Cannot continue')
        _LOGGER.debug('Accessing to frontdoor')
        r = self.__get_url(jr['events'][0]['attributes']['values']['url'])
        _LOGGER.debug('Accessing to landing page')
        r = self.__get_url('https://zonaprivada.edistribucion.com/areaprivada/s/')
        ix = r.text.find('auraConfig')
        if (ix == -1):
            raise EdisError('auraConfig not found. Cannot continue')
        ix = r.text.find('{',ix)
        ed = r.text.find(';',ix)
        jr = json.loads(r.text[ix:ed])
        if ('token' not in jr):
            raise EdisError('token not found. Cannot continue')
        self.__token = jr['token']
        _LOGGER.debug('Token received!')
        _LOGGER.debug(self.__token)
        _LOGGER.debug('Retreiving account info')
        r = self.get_login_info()
        self.__identities['account_id'] = r['visibility']['Id']
        self.__identities['name'] = r['Name']
        _LOGGER.info('Received name: %s (%s)',r['Name'],r['visibility']['Visible_Account__r']['Identity_number__c'])
        _LOGGER.debug('Account_id: %s', self.__identities['account_id'])
        if self.__do_save_session:
            with open(EdsConnector.SESSION_FILE, 'wb') as f:
                pickle.dump(self.__session.cookies, f)
            _LOGGER.debug('Saving session')
        self.__save_access()

    def get_login_info(self):
        data = {
            'message': '{"actions":[{"id":"215;a","descriptor":"apex://WP_Monitor_CTRL/ACTION$getLoginInfo","callingDescriptor":"markup://c:WP_Monitor","params":{"serviceNumber":"S011"}}]}',
            }
        r = self.__command('other.WP_Monitor_CTRL.getLoginInfo=1', post=data)
        return r
        
    def get_cups(self):
        data = {
            'message': '{"actions":[{"id":"270;a","descriptor":"apex://WP_ContadorICP_CTRL/ACTION$getCUPSReconectarICP","callingDescriptor":"markup://c:WP_Reconnect_ICP","params":{"visSelected":"'+self.__identities['account_id']+'"}}]}',
            }
        r = self.__command('other.WP_ContadorICP_CTRL.getCUPSReconectarICP=1', post=data)
        return r
    
    def get_cups_info(self, cups):
        data = {
            'message': '{"actions":[{"id":"489;a","descriptor":"apex://WP_ContadorICP_CTRL/ACTION$getCupsInfo","callingDescriptor":"markup://c:WP_Reconnect_Detail","params":{"cupsId":"'+cups+'"}}]}',
            }
        r = self.__command('other.WP_ContadorICP_CTRL.getCupsInfo=1', post=data)
        return r
    
    def get_meter(self, cups):
        data = {
            'message': '{"actions":[{"id":"522;a","descriptor":"apex://WP_ContadorICP_CTRL/ACTION$consultarContador","callingDescriptor":"markup://c:WP_Reconnect_Detail","params":{"cupsId":"'+cups+'"}}]}',
            }
        r = self.__command('other.WP_ContadorICP_CTRL.consultarContador=1', post=data)
        return r.get('data', None)
    
    def get_all_cups(self):
        data = {
            'message': '{"actions":[{"id":"294;a","descriptor":"apex://WP_ConsultaSuministros/ACTION$getAllCUPS","callingDescriptor":"markup://c:WP_MySuppliesForm","params":{"visSelected":"'+self.__identities['account_id']+'"}}]}',
            }
        r = self.__command('other.WP_ConsultaSuministros.getAllCUPS=1', post=data)
        return r
    
    def get_cups_detail(self, cups):
        data = {
            'message': '{"actions":[{"id":"490;a","descriptor":"apex://WP_CUPSDetail_CTRL/ACTION$getCUPSDetail","callingDescriptor":"markup://c:WP_cupsDetail","params":{"visSelected":"'+self.__identities['account_id']+'","cupsId":"'+cups+'"}}]}',
            }
        r = self.__command('other.WP_CUPSDetail_CTRL.getCUPSDetail=1', post=data)
        return r
    
    def get_cups_status(self, cups):
        data = {
            'message': '{"actions":[{"id":"629;a","descriptor":"apex://WP_CUPSDetail_CTRL/ACTION$getStatus","callingDescriptor":"markup://c:WP_cupsDetail","params":{"cupsId":"'+cups+'"}}]}',
            }
        r = self.__command('other.WP_CUPSDetail_CTRL.getStatus=1', post=data)
        return r
    
    def get_atr_detail(self, atr):
        data = {
            'message': '{"actions":[{"id":"62;a","descriptor":"apex://WP_ContractATRDetail_CTRL/ACTION$getATRDetail","callingDescriptor":"markup://c:WP_SuppliesATRDetailForm","params":{"atrId":"'+atr+'"}}]}',
            }
        r = self.__command('other.WP_ContractATRDetail_CTRL.getATRDetail=1', post=data)
        return r
    
    def get_solicitud_atr_detail(self, sol):
        data = {
            'message': '{"actions":[{"id":"56;a","descriptor":"apex://WP_SolicitudATRDetail_CTRL/ACTION$getSolicitudATRDetail","callingDescriptor":"markup://c:WP_ATR_Requests_Detail_Form","params":{"solId":"'+sol+'"}}]}',
            }
        r = self.__command('other.WP_SolicitudATRDetail_CTRL.getSolicitudATRDetail=1', post=data)
        return r
    
    def reconnect_ICP(self, cups):
        data = {
            'message': '{"actions":[{"id":"261;a","descriptor":"apex://WP_ContadorICP_F2_CTRL/ACTION$reconectarICP","callingDescriptor":"markup://c:WP_Reconnect_Detail_F2","params":{"cupsId":"'+cups+'"}}]}',
            }
        r = self.__command('other.WP_ContadorICP_F2_CTRL.reconectarICP=1', post=data)
        data = {
            'message': '{"actions":[{"id":"287;a","descriptor":"apex://WP_ContadorICP_CTRL/ACTION$goToReconectarICP","callingDescriptor":"markup://c:WP_Reconnect_Modal","params":{"cupsId":"'+cups+'"}}]}',
            }
        r = self.__command('other.WP_ContadorICP_CTRL.goToReconectarICP=1', post=data)
        return r
    
    def get_cups_list(self):
        data = {
            'message': '{"actions":[{"id":"1086;a","descriptor":"apex://WP_Measure_v3_CTRL/ACTION$getListCups","callingDescriptor":"markup://c:WP_Measure_List_v4","params":{"sIdentificador":"'+self.__identities['account_id']+'"}}]}',
            }
        r = self.__command('other.WP_Measure_v3_CTRL.getListCups=1', post=data)
        conts = []
        for cont in r['data']['lstCups']:
            if (cont['Id'] in r['data']['lstIds']):
                c = {}
                c['CUPS'] = cont.get('CUPs__r', None)['Name']
                c['CUPS_Id'] = cont.get('CUPs__r', None)['Id']
                c['Id'] = cont.get('Id', None)
                c['Active'] = False if 'Version_end_date__c' in cont else True
                c['Power'] = cont.get('Requested_power_1__c', None)
                c['Rate'] = cont.get('rate', None)
                conts.append(c)
        return conts

    def get_cycle_list(self, cont):
        data = {
            'message': '{"actions":[{"id":"1190;a","descriptor":"apex://WP_Measure_v3_CTRL/ACTION$getInfo","callingDescriptor":"markup://c:WP_Measure_Detail_v4","params":{"contId":"'+cont+'"},"longRunning":true}]}',
            }
        r = self.__command('other.WP_Measure_v3_CTRL.getInfo=1', post=data)
        return r['data']
        
      
    def get_cycle_curve(self, cont, range, value):
        data = {
            'message': '{"actions":[{"id":"1295;a","descriptor":"apex://WP_Measure_v3_CTRL/ACTION$getChartPoints","callingDescriptor":"markup://c:WP_Measure_Detail_v4","params":{"cupsId":"'+cont+'","dateRange":"'+range+'","cfactura":"'+value+'"},"longRunning":true}]}',
            }
        r = self.__command('other.WP_Measure_v3_CTRL.getChartPoints=1', post=data)
        return r['data']

    def get_cycle_csv(self, jsondata):
        data = {
            'message': '{"actions":[{"id":"351;a","descriptor":"apex://WP_Measure_v3_CTRL/ACTION$genericDownload","callingDescriptor":"markup://c:WP_Measure_Downloads_v4","params":{"options":{"typePM":"5","downloadType":"01","downloadFormat":"01"},"data":'+jsondata+'},"version":null}]}',
            }
        r = self.__command('other.WP_Measure_v3_CTRL.genericDownload=1', post=data)
        url = r['data']['url']
        r = self.__command(url, dashboard='https://zonaprivada.edistribucion.com')
        return r.content

    def get_day_curve (self, cont, date_start):
        data = {
            'message': '{"actions":[{"id":"751;a","descriptor":"apex://WP_Measure_v3_CTRL/ACTION$getChartPointsByRange","callingDescriptor":"markup://c:WP_Measure_Detail_Filter_By_Dates_v3","params":{"contId":"'+cont+'","type":"1","startDate":"'+date_start+'"},"version":null,"longRunning":true}]}',
            }
        r = self.__command('other.WP_Measure_v3_CTRL.getChartPointsByRange=1', post=data)
        return r
    
    def get_week_curve (self, cont, date_start):
        data = {
            'message': '{"actions":[{"id":"1497;a","descriptor":"apex://WP_Measure_v3_CTRL/ACTION$getChartPointsByRange","callingDescriptor":"markup://c:WP_Measure_Detail_Filter_By_Dates_v3","params":{"contId":"'+cont+'","type":"2","startDate":"'+date_start+'"},"version":null,"longRunning":true}]}',
            }
        r = self.__command('other.WP_Measure_v3_CTRL.getChartPointsByRange=1', post=data)
        return r

    def get_month_curve (self, cont, date_start):
        data = {
            'message': '{"actions":[{"id":"1461;a","descriptor":"apex://WP_Measure_v3_CTRL/ACTION$getChartPointsByRange","callingDescriptor":"markup://c:WP_Measure_Detail_Filter_By_Dates_v3","params":{"contId":"'+cont+'","type":"3","startDate":"'+date_start+'"},"version":null,"longRunning":true}]}',
            }
        r = self.__command('other.WP_Measure_v3_CTRL.getChartPointsByRange=1', post=data)
        return r

    def get_custom_curve (self, cont, date_start, date_end):
        data = {
            'message': '{"actions":[{"id":"981;a","descriptor":"apex://WP_Measure_v3_CTRL/ACTION$getChartPointsByRange","callingDescriptor":"markup://c:WP_Measure_Detail_Filter_Advanced_v3","params":{"contId":"'+cont+'","type":"4","startDate":"'+date_start+'","endDate":"'+date_end+'"},"version":null,"longRunning":true}]}'
            }
        r = self.__command('other.WP_Measure_v3_CTRL.getChartPointsByRange=1', post=data)
        return r['data']
        
    def get_maximeter (self, cups, date_start, date_end):
        data = {
            'message': '{"actions":[{"id":"688;a","descriptor":"apex://WP_MaximeterHistogram_CTRL/ACTION$getHistogramPoints","callingDescriptor":"markup://c:WP_MaximeterHistogramDetail","params":{"mapParams":{"startDate":"'+date_start+'","endDate":"'+date_end+'","id":"'+cups+'","sIdentificador":"'+self.__identities['account_id']+'"}}}]}',
            }
        r = self.__command('other.WP_MaximeterHistogram_CTRL.getHistogramPoints=1', post=data)
        return r['data']
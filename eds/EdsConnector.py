#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests, pickle, json, os, math
from bs4 import BeautifulSoup as bs
from urllib.parse import urlparse, unquote
import logging
from datetime import datetime, timedelta
from dateutil.tz import tzutc

UTC = tzutc()

_LOGGER = logging.getLogger(__name__)

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
    SESSION_FILE = '/tmp/edistribucion.session'
    ACCESS_FILE = '/tmp/edistribucion.access'
    _session = None
    _token = 'undefined'
    _credentials = {}
    _dashboard = 'https://zonaprivada.edistribucion.com/areaprivada/s/sfsites/aura?'
    _command_index = 0
    _identities = {}
    _appInfo = None
    _context = None
    _access_date = datetime.now()
    
    class EdsException (Exception):
        def _init_(self, message, where='EdsConnector'):
            self.message = message
            super()._init_(f'[{where}] {message}')
    
    def __init__(self, user, password, debug_level=_LOGGER.debug):
        self._session = requests.Session()
        self._credentials['user'] = user
        self._credentials['password'] = password
        try:
            with open(EdsConnector.SESSION_FILE, 'rb') as f:
                self._session.cookies.update(pickle.load(f))
        except FileNotFoundError:
            _LOGGER.debug ('Session file not found')
        try:
            with open(EdsConnector.ACCESS_FILE, 'rb') as f:
                d = json.load(f)
                self._token = d['token']
                self._identities = d['identities']
                self._context = d['context']
                self._access_date = datetime.fromisoformat(d['date'])
        except FileNotFoundError:
            _LOGGER.debug ('Access file not found')
        
    def _get_url(self, url,get=None,post=None,json=None,cookies=None,headers=None):
        _headers = {
            'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:77.0) Gecko/20100101 Firefox/77.0',
        }
        if (headers):
            _headers.update(headers)
        if (post is None and json is None):
            r = self._session.get(url, params=get, headers=_headers, cookies=cookies)
        else:
            r = self._session.post(url, data=post, json=json, params=get, headers=_headers, cookies=cookies)
        if r.status_code >= 400:
            raise self.EdsException ('Received status_code > 400')
        return r
    
    def _command(self, command, post=None, dashboard=None, accept='*/*', content_type=None):

        if dashboard is None: dashboard = self._dashboard 

        if (self._command_index):
            command = 'r='+self._command_index+'&'
            self._command_index += 1
        
        if (post):
            post['aura.context'] = self._context
            post['aura.pageURI'] = '/areaprivada/s/wp-online-access'
            post['aura.token'] = self._token

        headers = {}
        headers['Accept'] = accept
        if content_type is not None:
            headers['Content-Type'] = content_type

        r = self._get_url(dashboard+command, post=post, headers=headers)
        if ('window.location.href' in r.text or 'clientOutOfSync' in r.text):
                _LOGGER.info ('Redirection received. Aborting command.')
        elif ('json' in r.headers['Content-Type']):
            jr = r.json()
            if (jr['actions'][0]['state'] != 'SUCCESS'):
                _LOGGER.info ('Got an error. Aborting command.')
                raise self.EdsException (f'Error processing command: {command}')
            return jr['actions'][0]['returnValue']
        
        return r
    
    def _check_tokens(self):
        _LOGGER.debug('Checking tokens')
        return self._token != 'undefined' and self._access_date+timedelta(minutes=10) > datetime.now()
        
    def _save_state(self):
        try:
            with open(EdsConnector.SESSION_FILE, 'wb') as f:
                pickle.dump(self._session.cookies, f)
                _LOGGER.debug('Saving session')
        except FileNotFoundError:
            _LOGGER.debug ('Cannot save session file')
        try:
            t = {}
            t['token'] = self._token
            t['identities'] = self._identities
            t['context'] = self._context
            t['date'] = datetime.now()
            with open(EdsConnector.ACCESS_FILE, 'w') as f:
                json.dump(t, f, default=serialize_date)
            _LOGGER.debug('Saving access to file')
        except FileNotFoundError:
            _LOGGER.debug ('Cannot save access file')
        
    def login(self):
        if (not self._check_tokens()):
            _LOGGER.debug('Login')
            self._session = requests.Session()
            r = self._get_url('https://zonaprivada.edistribucion.com/areaprivada/s/login?ec=302&startURL=%2Fareaprivada%2Fs%2F')
            ix = r.text.find('auraConfig')
            if (ix == -1):
                raise self.EdsException ('auraConfig not found. Cannot continue')
            soup = bs(r.text, 'html.parser')
            scripts = soup.find_all('script')
            _LOGGER.debug('Loading scripts')
            for s in scripts:
                src = s.get('src')
                if (not src):
                    continue
                #print(s)
                upr = urlparse(r.url)
                r = self._get_url(upr.scheme+'://'+upr.netloc+src)
                if ('resources.js' in src):
                    unq = unquote(src)
                    self._context = unq[unq.find('{'):unq.rindex('}')+1]
                    self._appInfo = json.loads(self._context)
            _LOGGER.debug('Performing login routine')
            data = {
                    'message':'{"actions":[{"id":"91;a","descriptor":"apex://LightningLoginFormController/ACTION$login","callingDescriptor":"markup://c:WP_LoginForm","params":{"username":"'+self._credentials['user']+'","password":"'+self._credentials['password']+'","startUrl":"/areaprivada/s/"}}]}',
                    'aura.context':self._context,
                    'aura.pageURI':'/areaprivada/s/login/?language=es&startURL=%2Fareaprivada%2Fs%2F&ec=302',
                    'aura.token':'undefined',
                    }
            r = self._get_url(self._dashboard+'other.LightningLoginForm.login=1',post=data)
            #print(r.text)
            if ('/*ERROR*/' in r.text):
                if ('invalidSession' in r.text):
                    self._session = requests.Session()
                    self.login()
                raise self.EdsException ('Unexpected error in loginForm. Cannot continue')
            jr = r.json()
            if ('events' not in jr):
                raise self.EdsException ('Wrong login response. Cannot continue')
            
            _LOGGER.debug('Accessing to frontdoor')
            r = self._get_url(jr['events'][0]['attributes']['values']['url'])
            _LOGGER.debug('Accessing to landing page')
            r = self._get_url('https://zonaprivada.edistribucion.com/areaprivada/s/')
            ix = r.text.find('auraConfig')
            if (ix == -1):
                raise self.EdsException ('auraConfig not found. Cannot continue')
            ix = r.text.find('{',ix)
            ed = r.text.find(';',ix)
            try:
                jr = json.loads(r.text[ix:ed])
            except Exception:
                jr = {}
            if ('token' not in jr):
                raise self.EdsException ('token not found. Cannot continue')
            self._token = jr['token']
            _LOGGER.debug('Token received!')
            _LOGGER.debug(self._token)
            _LOGGER.debug('Retrieving account info')
            r = self.get_login_info()
            self._identities['account_id'] = r['visibility']['Id']
            self._identities['name'] = r['Name']
            _LOGGER.info('Received name: %s (%s)',r['Name'],r['visibility']['Visible_Account__r']['Identity_number__c'])
            _LOGGER.debug('Account_id: %s', self._identities['account_id'])
            self._save_state()

    def _safe_command (self, command, message):
        try:
            data = {}
            data['message'] = message
            r = self._command(command, post=data)
        except Exception as e:
            _LOGGER.info (e)
            r = {}
        return r

    def get_login_info(self):
        cmd = 'other.WP_Monitor_CTRL.getLoginInfo=1'
        msg = '{"actions":[{"id":"215;a","descriptor":"apex://WP_Monitor_CTRL/ACTION$getLoginInfo","callingDescriptor":"markup://c:WP_Monitor","params":{"serviceNumber":"S011"}}]}'
        return self._safe_command (cmd, msg)
        
    def get_cups(self):
        msg = '{"actions":[{"id":"270;a","descriptor":"apex://WP_ContadorICP_CTRL/ACTION$getCUPSReconectarICP","callingDescriptor":"markup://c:WP_Reconnect_ICP","params":{"visSelected":"'+self._identities['account_id']+'"}}]}',
        cmd = 'other.WP_ContadorICP_CTRL.getCUPSReconectarICP=1'
        return self._safe_command (cmd, msg)
    
    def get_cups_info(self, cups):
        msg = '{"actions":[{"id":"489;a","descriptor":"apex://WP_ContadorICP_CTRL/ACTION$getCupsInfo","callingDescriptor":"markup://c:WP_Reconnect_Detail","params":{"cupsId":"'+cups+'"}}]}',
        cmd = 'other.WP_ContadorICP_CTRL.getCupsInfo=1'
        return self._safe_command (cmd, msg)
    
    def get_cups_all(self):
        msg = '{"actions":[{"id":"294;a","descriptor":"apex://WP_ConsultaSuministros/ACTION$getAllCUPS","callingDescriptor":"markup://c:WP_MySuppliesForm","params":{"visSelected":"'+self._identities['account_id']+'"}}]}',
        cmd = 'other.WP_ConsultaSuministros.getAllCUPS=1'
        return self._safe_command (cmd, msg)

    def get_cups_list(self):
        msg = '{"actions":[{"id":"1086;a","descriptor":"apex://WP_Measure_v3_CTRL/ACTION$getListCups","callingDescriptor":"markup://c:WP_Measure_List_v4","params":{"sIdentificador":"'+self._identities['account_id']+'"}}]}',
        cmd = 'other.WP_Measure_v3_CTRL.getListCups=1'
        r = self._safe_command (cmd, msg)
        conts = []
        if 'data' in r and 'lstCups' in r['data']:
            for cont in r['data']['lstCups']:
                if (cont['Id'] in r['data']['lstIds']):
                    try:
                        c = {}
                        c['CUPS'] = cont.get('CUPs__r', None)['Name']
                        c['CUPS_Id'] = cont.get('CUPs__r', None)['Id']
                        c['Id'] = cont.get('Id', None)
                        c['Active'] = False if 'Version_end_date__c' in cont else True
                        c['Power'] = cont.get('Requested_power_1__c', None)
                        c['Rate'] = cont.get('rate', None)
                        conts.append(c)
                    except Exception:
                        pass
        return conts

    def get_meter(self, cups):
        msg = '{"actions":[{"id":"471;a","descriptor":"apex://WP_ContadorICP_F2_CTRL/ACTION$consultarContador","callingDescriptor":"markup://c:WP_Reconnect_Detail_F2","params":{"cupsId":"'+cups+'"}}]}'
        cmd = 'other.WP_ContadorICP_F2_CTRL.consultarContador=1'
        return self._safe_command (cmd, msg).get('data', None)
    
    def get_cups_detail(self, cups):
        msg = '{"actions":[{"id":"490;a","descriptor":"apex://WP_CUPSDetail_CTRL/ACTION$getCUPSDetail","callingDescriptor":"markup://c:WP_cupsDetail","params":{"visSelected":"'+self._identities['account_id']+'","cupsId":"'+cups+'"}}]}',
        cmd = 'other.WP_CUPSDetail_CTRL.getCUPSDetail=1'
        return self._safe_command (cmd, msg)
    
    def get_cups_status(self, cups):
        msg = '{"actions":[{"id":"629;a","descriptor":"apex://WP_CUPSDetail_CTRL/ACTION$getStatus","callingDescriptor":"markup://c:WP_cupsDetail","params":{"cupsId":"'+cups+'"}}]}',
        cmd = 'other.WP_CUPSDetail_CTRL.getStatus=1'
        return self._safe_command (cmd, msg)
    
    def get_atr_detail(self, atr):
        msg = '{"actions":[{"id":"62;a","descriptor":"apex://WP_ContractATRDetail_CTRL/ACTION$getATRDetail","callingDescriptor":"markup://c:WP_SuppliesATRDetailForm","params":{"atrId":"'+atr+'"}}]}',
        cmd = 'other.WP_ContractATRDetail_CTRL.getATRDetail=1'
        return self._safe_command (cmd, msg).get('data', None)
    
    def get_solicitud_atr_detail(self, sol):
        msg = '{"actions":[{"id":"56;a","descriptor":"apex://WP_SolicitudATRDetail_CTRL/ACTION$getSolicitudATRDetail","callingDescriptor":"markup://c:WP_ATR_Requests_Detail_Form","params":{"solId":"'+sol+'"}}]}',
        cmd = 'other.WP_SolicitudATRDetail_CTRL.getSolicitudATRDetail=1'
        return self._safe_command (cmd, msg)
    
    def get_cycle_list(self, cont):
        msg = '{"actions":[{"id":"1190;a","descriptor":"apex://WP_Measure_v3_CTRL/ACTION$getInfo","callingDescriptor":"markup://c:WP_Measure_Detail_v4","params":{"contId":"'+cont+'"},"longRunning":true}]}',
        cmd = 'other.WP_Measure_v3_CTRL.getInfo=1'
        return self._safe_command (cmd, msg).get('data', None)
        
    def get_cycle_curve(self, cont, range, value):
        msg = '{"actions":[{"id":"1295;a","descriptor":"apex://WP_Measure_v3_CTRL/ACTION$getChartPoints","callingDescriptor":"markup://c:WP_Measure_Detail_v4","params":{"cupsId":"'+cont+'","dateRange":"'+range+'","cfactura":"'+value+'"},"longRunning":true}]}',
        cmd = 'other.WP_Measure_v3_CTRL.getChartPoints=1'
        return self._safe_command (cmd, msg).get('data', None)

    def get_day_curve (self, cont, date_start):
        msg = '{"actions":[{"id":"751;a","descriptor":"apex://WP_Measure_v3_CTRL/ACTION$getChartPointsByRange","callingDescriptor":"markup://c:WP_Measure_Detail_Filter_By_Dates_v3","params":{"contId":"'+cont+'","type":"1","startDate":"'+date_start+'"},"version":null,"longRunning":true}]}',
        cmd = 'other.WP_Measure_v3_CTRL.getChartPointsByRange=1'
        return self._safe_command (cmd, msg).get('data', None)
    
    def get_week_curve (self, cont, date_start):
        msg = '{"actions":[{"id":"1497;a","descriptor":"apex://WP_Measure_v3_CTRL/ACTION$getChartPointsByRange","callingDescriptor":"markup://c:WP_Measure_Detail_Filter_By_Dates_v3","params":{"contId":"'+cont+'","type":"2","startDate":"'+date_start+'"},"version":null,"longRunning":true}]}',
        cmd = 'other.WP_Measure_v3_CTRL.getChartPointsByRange=1'
        return self._safe_command (cmd, msg).get('data', None)

    def get_month_curve (self, cont, date_start):
        msg = '{"actions":[{"id":"1461;a","descriptor":"apex://WP_Measure_v3_CTRL/ACTION$getChartPointsByRange","callingDescriptor":"markup://c:WP_Measure_Detail_Filter_By_Dates_v3","params":{"contId":"'+cont+'","type":"3","startDate":"'+date_start+'"},"version":null,"longRunning":true}]}',
        cmd = 'other.WP_Measure_v3_CTRL.getChartPointsByRange=1'
        return self._safe_command (cmd, msg).get('data', None)

    def get_custom_curve (self, cont, date_start, date_end):
        msg = '{"actions":[{"id":"981;a","descriptor":"apex://WP_Measure_v3_CTRL/ACTION$getChartPointsByRange","callingDescriptor":"markup://c:WP_Measure_Detail_Filter_Advanced_v3","params":{"contId":"'+cont+'","type":"4","startDate":"'+date_start+'","endDate":"'+date_end+'"},"version":null,"longRunning":true}]}'
        cmd = 'other.WP_Measure_v3_CTRL.getChartPointsByRange=1'
        return self._safe_command (cmd, msg).get('data', None)
        
    def get_maximeter (self, cups, date_start, date_end):
        msg = '{"actions":[{"id":"688;a","descriptor":"apex://WP_MaximeterHistogram_CTRL/ACTION$getHistogramPoints","callingDescriptor":"markup://c:WP_MaximeterHistogramDetail","params":{"mapParams":{"startDate":"'+date_start+'","endDate":"'+date_end+'","id":"'+cups+'","sIdentificador":"'+self._identities['account_id']+'"}}}]}',
        cmd = 'other.WP_MaximeterHistogram_CTRL.getHistogramPoints=1'
        return self._safe_command (cmd, msg).get('data', None)
    
    def reconnect_ICP(self, cups):
        msg = '{"actions":[{"id":"261;a","descriptor":"apex://WP_ContadorICP_F2_CTRL/ACTION$reconectarICP","callingDescriptor":"markup://c:WP_Reconnect_Detail_F2","params":{"cupsId":"'+cups+'"}}]}',
        cmd = 'other.WP_ContadorICP_F2_CTRL.reconectarICP=1'
        self._safe_command (cmd, msg)
        msg = '{"actions":[{"id":"287;a","descriptor":"apex://WP_ContadorICP_CTRL/ACTION$goToReconectarICP","callingDescriptor":"markup://c:WP_Reconnect_Modal","params":{"cupsId":"'+cups+'"}}]}',
        cmd = 'other.WP_ContadorICP_CTRL.goToReconectarICP=1'
        return self._safe_command (cmd, msg)
import logging

from .EdsConnector import EdsConnector
from datetime import datetime, timedelta
#import calendar
import pandas as pd
import asyncio
from aiopvpc import PVPCData, TARIFFS
import pytz as tz
import tzlocal

LIST_P1 = ['10 - 11 h', '11 - 12 h', '12 - 13 h', '13 - 14 h', '18 - 19 h', '19 - 20 h', '20 - 21 h', '21 - 22 h']
LIST_P2 = ['08 - 09 h', '09 - 10 h', '14 - 15 h', '15 - 16 h', '16 - 17 h', '17 - 18 h', '22 - 23 h', '23 - 24 h']
LIST_P3 = ['00 - 01 h', '01 - 02 h', '02 - 03 h', '03 - 04 h', '04 - 05 h', '05 - 06 h','06 - 07 h', '07 - 08 h']

DAYS_P3 = ['Saturday', 'Sunday']

DEFAULT_PRICE_P1 = 30.67266 # €/kW/year
DEFAULT_PRICE_P2 = 1.4243591 # €/kW/year
DEFAULT_DAILY_PRICE_P1 = DEFAULT_PRICE_P1 / 365
DEFAULT_DAILY_PRICE_P2 = DEFAULT_PRICE_P2 / 365
DEFAULT_PRICE_CONT = 0.81 # €/month
DEFAULT_PRICE_COMERC = 3.113 # €/kW/año
DEFAULT_DAILY_PRICE_COMERC = DEFAULT_PRICE_COMERC / 365
DEFAULT_TAX_ELECTR = 1.0511300560 # multiplicative
DEFAULT_TAX_IVA = 1.21 # multiplicative

DEFAULT_SHORT_INTERVAL = timedelta(minutes=10)
DEFAULT_LONG_INTERVAL = timedelta(minutes=60)

_LOGGER = logging.getLogger(__name__)
logging.getLogger("aiopvpc").setLevel(logging.ERROR)

class EdsHelper():
    _eds = None
    # raw data
    _username = None
    _password = None
    _last_short_update = None
    _last_long_update = None
    _short_interval = None
    _long_interval = None
    _cycles = None

    _meter_yesterday = None

    _last_meter_update = None
    _last_cycles_update = None
    _last_energy_update = None
    _last_maximeter_update = None
    _last_pvpc_update = None
    _last_try = None

    _busy = False
    _should_reset_day = None

    _pvpc_raw = None
    _cups_id = None
    _cont_id = None

    # dataframes
    _power_df = None
    _energy_df = None

    # attributes
    attributes = {}

    _pvpc_raw = None
    _pvpc_handler = None

    def __init__(self, user, password, cups=None, short_interval=None, long_interval=None):
        self._eds = EdsConnector(user, password)
        self._username = user
        self._password = password
        self._short_interval = short_interval if short_interval is not None else DEFAULT_SHORT_INTERVAL
        self._long_interval = long_interval if long_interval is not None else DEFAULT_LONG_INTERVAL
        self._last_short_update = None
        self._last_long_update = None
        self._loop = asyncio.get_event_loop()
        self._pvpc_handler = PVPCData(tariff=TARIFFS[0], local_timezone='Europe/Madrid')

    # To load CUPS into the helper
    def _set_cups (self, candidate=None):
        self._eds.login()
        all_cups = self._eds.get_cups_list()
        _LOGGER.debug ("CUPS:" + str(all_cups))
        found = False
        for c in all_cups:
            if candidate is None or c.get('CUPS', None) == candidate:
                self.attributes['cups'] = c.get('CUPS', None)
                self._cups_id = c.get('CUPS_Id', None)
                self._cont_id = c.get('Id', None)
                generic_power_limit = c.get('Power', None)
                self.attributes['power_limit_p1'] = generic_power_limit
                self.attributes['power_limit_p2'] = generic_power_limit
                found = True
                try:
                    for atr in self._eds.get_cups_detail (self._cups_id).get('lstATR', None):
                        if atr.get('Status', None) == 'EN VIGOR':
                            attr_id = atr.get ('Id', None)
                            attr = self._eds.get_atr_detail (attr_id)
                            for item in attr:
                                if 'title' in item:
                                    if item['title'] == 'Potencia contratada 1 (kW)':
                                        self.attributes['power_limit_p1'] = float(item['value'].replace(",", "."))
                                    elif item['title'] == 'Potencia contratada 2 (kW)':
                                        self.attributes['power_limit_p2'] = float(item['value'].replace(",", "."))
                except Exception as e:
                    _LOGGER.warning (e + f"; assuming {generic_power_limit} as P1 and P2 power limits")
                    self.attributes['power_limit_p1'] = generic_power_limit
                    self.attributes['power_limit_p2'] = generic_power_limit
                break
        else:
            found = False
        return found
    
    def update (self, cups=None):
        if not self._busy:
            self._busy = True
            try:
                # login in edistribucion
                if self._cups_id is None or (self._cups_id != cups and cups is not None):
                    self._set_cups(cups)
                else:
                    self._eds.login()
                # updating historical data and calculations
                if self._last_try is None or (datetime.now() - self._last_try) > self._short_interval:
                    if self._last_cycles_update is None or (datetime.now() - self._last_cycles_update) > self._long_interval:
                        self._update_cycles ()
                    if self._last_energy_update is None or (datetime.now() - self._last_energy_update) > self._long_interval:
                        self._update_energy ()
                        self.attributes['energy_last_update'] = self._last_energy_update.strftime("%d-%m-%Y %H:%M:%S") if self._last_energy_update is not None else None
                    if self._last_maximeter_update is None or (datetime.now() - self._last_maximeter_update) > self._long_interval:
                        self._update_maximeter ()
                        self.attributes['maximeter_last_update'] = self._last_maximeter_update.strftime("%d-%m-%Y %H:%M:%S") if self._last_maximeter_update is not None else None
                    if self._last_pvpc_update is None or (datetime.now() - self._last_pvpc_update) > self._long_interval:
                        self._update_pvpc_prices ()
                        self.attributes['pvpc_last_update'] = self._last_pvpc_update.strftime("%d-%m-%Y %H:%M:%S") if self._last_pvpc_update is not None else None
                    # Fetch meter data
                    if self._last_meter_update is None or (datetime.now() - self._last_meter_update) > self._short_interval:
                        self._update_meter ()
                        self.attributes['meter_last_update'] = self._last_meter_update.strftime("%d-%m-%Y %H:%M:%S") if self._last_meter_update is not None else None
                    self._last_try = datetime.now()
            except Exception as e:
                _LOGGER.info (e)
            self._busy = False

    async def async_update (self, cups=None):
        # update pvpc prices
        if self._last_pvpc_update is None or (datetime.now().day - self._last_pvpc_update.day) > 0:
            date = None
            try:
                date = datetime.strptime(self._cycles['lstCycles'][0]['label'].split(' - ')[0], '%d/%m/%Y').replace(hour=0,minute=0,second=0,microsecond=0)
            except Exception as e:
                pass
            self._pvpc_raw = await self._pvpc_handler.async_download_prices_for_range(date if date is not None else (datetime.today() - timedelta(days=365)), datetime.today().replace(hour=23,minute=59,second=59,microsecond=59))
        # update the sensor
        self._loop.run_in_executor(None, self.update, cups)

    def _update_cycles (self):
        try:
            self._cycles = self._eds.get_cycle_list(self._cont_id)
            self._last_cycles_update = datetime.now()
            _LOGGER.debug ('cycles got updated!')
        except Exception as e:
            _LOGGER.info (e)

    def _update_energy (self):
        try:
            d0 = datetime.strptime(self._cycles['lstCycles'][0]['label'].split(' - ')[0], '%d/%m/%Y') + timedelta(days=1)
            d1 = datetime.strptime(self._cycles['lstCycles'][0]['label'].split(' - ')[1], '%d/%m/%Y')
            d2 = d1 + timedelta(days=1)
            d3 = datetime.today()
            res0 = self._eds.get_custom_curve(self._cont_id, d0.strftime("%Y-%m-%d"), d1.strftime("%Y-%m-%d"))
            res1 = self._eds.get_custom_curve(self._cont_id, d2.strftime("%Y-%m-%d"), d3.strftime("%Y-%m-%d"))
            data = res0.get('mapHourlyPoints', {})
            data1 = res1.get('mapHourlyPoints', {})
            for day in data1:
                data[day] = data1[day]
            if data is not None and len(data) > 0:
                good_data = []
                for day in data:
                    for idx in data[day]:
                        item={}
                        item['datetime'] = datetime.strptime(day + "_" + idx['hour'].split(" - ")[0], "%d-%m-%Y_%H")
                        item['date'] = day
                        for key in idx:
                            item[key] = idx[key]
                        good_data.append(item)
            
                df = pd.DataFrame (good_data)
                df['datetime'] = pd.to_datetime(df['datetime'])
                df['weekday'] = df['datetime'].dt.day_name()
                self._energy_df = df

                y_df = df.loc[(pd.to_datetime((d3 - timedelta(days=1))).floor('D') <= df['datetime']) & (df['datetime'] < pd.to_datetime(d3).floor('D'))]
                self.attributes['energy_yesterday'] = round(y_df['value'].sum(), 2)
                self.attributes['energy_yesterday_p1'] = round(y_df['value'].loc[(y_df['hour'].isin(LIST_P1)) & (~y_df['weekday'].isin(DAYS_P3))].sum(), 2)
                self.attributes['energy_yesterday_p2'] = round(y_df['value'].loc[(y_df['hour'].isin(LIST_P2)) & (~y_df['weekday'].isin(DAYS_P3))].sum(), 2)
                self.attributes['energy_yesterday_p3'] = round(self.attributes['energy_yesterday'] - self.attributes['energy_yesterday_p1'] - self.attributes['energy_yesterday_p2'], 2)

                cc_df = df.loc[(pd.to_datetime(d2).floor('D') <= df['datetime'])]
                self.attributes['cycle_current'] = round(cc_df['value'].sum(), 2)
                self.attributes['cycle_current_days'] = int(cc_df['value'].count() / 24) - 1
                self.attributes['cycle_current_daily'] = round(self.attributes['cycle_current'] / self.attributes['cycle_current_days'], 2)
                self.attributes['cycle_current_p1'] = round(cc_df['value'].loc[(cc_df['hour'].isin(LIST_P1)) & (~cc_df['weekday'].isin(DAYS_P3))].sum(), 2)
                self.attributes['cycle_current_p2'] = round(cc_df['value'].loc[(cc_df['hour'].isin(LIST_P2)) & (~cc_df['weekday'].isin(DAYS_P3))].sum(), 2)
                self.attributes['cycle_current_p3'] = round(self.attributes['cycle_current'] - self.attributes['cycle_current_p1'] - self.attributes['cycle_current_p2'], 2)

                cl_df = df.loc[(df['datetime'] < pd.to_datetime(d2).floor('D'))]
                self.attributes['cycle_last'] = round(cl_df['value'].sum(), 2)
                self.attributes['cycle_last_days'] = round(cl_df['value'].count() / 24)
                self.attributes['cycle_last_daily'] = round(self.attributes['cycle_last'] / self.attributes['cycle_last_days'], 2)
                self.attributes['cycle_last_p1'] = round(cl_df['value'].loc[(cl_df['hour'].isin(LIST_P1)) & (~cl_df['weekday'].isin(DAYS_P3))].sum(), 2)
                self.attributes['cycle_last_p2'] = round(cl_df['value'].loc[(cl_df['hour'].isin(LIST_P2)) & (~cl_df['weekday'].isin(DAYS_P3))].sum(), 2)
                self.attributes['cycle_last_p3'] = round(self.attributes['cycle_last'] - self.attributes['cycle_last_p1'] - self.attributes['cycle_last_p2'], 2)
                
                self._last_energy_update = datetime.now()
                _LOGGER.debug ('energy got updated!')
        except Exception as e:
            _LOGGER.info (e)
    
    def _update_maximeter (self):
        try:
            d0 = datetime.today()-timedelta(days=395)
            d1 = datetime.today()
            maximeter = self._eds.get_maximeter (self._cups_id, d0.strftime("%m/%Y"), d1.strftime("%m/%Y"))
            if maximeter is not None:
                df =  pd.DataFrame([x for x in maximeter.get('lstData', None) if x['valid'] == True])
                self._power_df = df
                self.attributes['power_peak'] = round(df['value'].max(), 2)
                idx_max = df['value'].idxmax()
                self.attributes['power_peak_date'] = df.iloc[idx_max]['date'] + " " + df.iloc[idx_max]['hour']
                self.attributes['power_peak_mean'] = round(df['value'].mean(), 2)
                self.attributes['power_peak_tile99'] = round(df['value'].quantile(.99), 2)
                self.attributes['power_peak_tile95'] = round(df['value'].quantile(.95), 2)
                self.attributes['power_peak_tile90'] = round(df['value'].quantile(.90), 2)
                self._last_maximeter_update = datetime.now()
                _LOGGER.debug ('maximeter got updated!')
        except Exception as e:
            _LOGGER.info (e)

    def _update_meter (self):
        # fetching data
        try:
            meter = self._eds.get_meter(self._cups_id)
            if meter is not None:
                self.attributes['energy_total'] = int(str(meter.get('totalizador', None)).replace(".", ""))
                self.attributes['icp_status'] = meter.get('estadoICP', None)
                self.attributes['power_load'] = float(meter.get('percent', None).replace("%","").replace(",", "."))
                self.attributes['power'] = meter.get('potenciaActual', None)
                self._last_meter_update = datetime.now()
        except Exception as e:
            _LOGGER.info (e)
        
        # today's calculus
        try:
            if 'energy_total' in self.attributes and self.attributes['energy_total'] is not None and (self._meter_yesterday is None or (datetime.now().day - self._last_try.day) > 0):
                self._meter_yesterday = self.attributes['energy_total']                
            if 'energy_total' in self.attributes and self.attributes['energy_total'] is not None and self._meter_yesterday is not None:
                self.attributes['energy_today'] = self.attributes['energy_total'] - self._meter_yesterday
        except Exception as e:
            _LOGGER.info (e)

    def _update_pvpc_prices (self):
        try:
            if self._pvpc_raw is not None and self._energy_df is not None:
                timezone = str(tzlocal.get_localzone())
                d0 = datetime.strptime(self._cycles['lstCycles'][0]['label'].split(' - ')[0], '%d/%m/%Y') + timedelta(days=1)
                d1 = datetime.strptime(self._cycles['lstCycles'][0]['label'].split(' - ')[1], '%d/%m/%Y')
                d2 = d1 + timedelta(days=1)
                df = pd.DataFrame([{'date': x.astimezone(tz.timezone(timezone)).strftime("%d-%m-%Y"), 'hour': f"{x.astimezone(tz.timezone(timezone)).strftime('%H')} - {(x.astimezone(tz.timezone(timezone)).hour + 1):02d} h", 'price': self._pvpc_raw[x]} for x in self._pvpc_raw])
                if 'price' in df.columns:
                    if 'price' in self._energy_df.columns:
                        self._energy_df.drop('price', axis=1)
                    self._energy_df = self._energy_df.merge(df, how='left', left_on=['date', 'hour'], right_on=['date', 'hour'])
                    self._energy_df['energy_price'] = self._energy_df['value'].ffill() * self._energy_df['price'].ffill()
                    df = self._energy_df          
                    
                    # IVA fix
                    if (d2 >= datetime(2021, 6, 26) and d2 <= (2021, 12, 31)):
                        iva = 1.1
                    else:
                        iva = DEFAULT_TAX_IVA
                    cc_df = df.loc[(pd.to_datetime(d2).floor('D') <= df['datetime'])]
                    self.attributes['cycle_current_energy_term'] = round(cc_df['energy_price'].sum(), 2)
                    self.attributes['cycle_current_power_term'] = round((self.attributes['power_limit_p1'] * (DEFAULT_DAILY_PRICE_P1 + DEFAULT_DAILY_PRICE_COMERC) + self.attributes['power_limit_p2'] * DEFAULT_DAILY_PRICE_P2) * self.attributes['cycle_current_days'], 2)
                    self.attributes['cycle_current_pvpc'] = round(((self.attributes['cycle_current_energy_term'] + self.attributes['cycle_current_power_term']) * DEFAULT_TAX_ELECTR + (DEFAULT_PRICE_CONT * self.attributes['cycle_current_days'] / 30)) * DEFAULT_TAX_IVA, 2)
                    
                    # IVA fix
                    if (d0 >= datetime(2021, 6, 26) and d0 <= (2021, 12, 31)):
                        iva = 1.1
                    else:
                        iva = DEFAULT_TAX_IVA
                    cl_df = df.loc[(df['datetime'] < pd.to_datetime(d2).floor('D'))]
                    self.attributes['cycle_last_energy_term'] = round(cl_df['energy_price'].sum(), 2)
                    self.attributes['cycle_last_power_term'] = round((self.attributes['power_limit_p1'] * (DEFAULT_DAILY_PRICE_P1 + DEFAULT_DAILY_PRICE_COMERC) + self.attributes['power_limit_p2'] * DEFAULT_DAILY_PRICE_P2) * self.attributes['cycle_last_days'], 2)
                    self.attributes['cycle_last_pvpc'] = round(((self.attributes['cycle_last_energy_term'] + self.attributes['cycle_last_power_term']) * DEFAULT_TAX_ELECTR + (DEFAULT_PRICE_CONT * self.attributes['cycle_last_days'] / 30)) * iva, 2)
                    self._last_pvpc_update = datetime.now()
                    _LOGGER.debug ('prices got updated!')
        except Exception as e:
            _LOGGER.info (e)

    def __str__ (self):
        return str(self.attributes)
import logging
from .EdsConnector import EdsConnector
from datetime import datetime, timedelta
#import calendar
import pandas as pd
import asyncio
from aiopvpc import PVPCData, TARIFFS
import pytz as tz
from tabulate import tabulate

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

    _busy = False
    _should_reset_day = None

    Supply = {}
    Today = {}
    Yesterday = {}
    Cycles = []
    Meter = {}
    Maximeter = {}
    PVPC = {}

    def __init__(self, user, password, cups=None, short_interval=None, long_interval=None):
        self._eds = EdsConnector(user, password)
        self._username = user
        self._password = password
        self._short_interval = short_interval if short_interval is not None else DEFAULT_SHORT_INTERVAL
        self._long_interval = long_interval if long_interval is not None else DEFAULT_LONG_INTERVAL
        self._last_short_update = None
        self._last_long_update = None
        self._loop = asyncio.get_event_loop()

    # To load CUPS into the helper
    def _set_cups (self, candidate=None):
        self._eds.login()
        all_cups = self._eds.get_cups_list()
        _LOGGER.debug ("CUPS:" + str(all_cups))
        found = False
        for c in all_cups:
            if candidate is None or c.get('CUPS', None) == candidate:
                self.Supply['CUPS'] = c.get('CUPS', None)
                self.Supply['CUPS_Id'] = c.get('CUPS_Id', None)
                self.Supply['CONT_Id'] = c.get('Id', None)
                self.Supply['Active'] = c.get('Active', None)
                self.Supply['PowerLimit'] = c.get('Power', None)
                self.Supply['PowerLimit_P1'] = self.Supply['PowerLimit']
                self.Supply['PowerLimit_P2'] = self.Supply['PowerLimit']
                found = True
                try:
                    for atr in self._eds.get_cups_detail (self.Supply['CUPS_Id']).get('lstATR', None):
                        if atr.get('Status', None) == 'EN VIGOR':
                            self.Supply['ATTR_Id'] = atr.get ('Id', None)
                            attr = self._eds.get_atr_detail (self.Supply['ATTR_Id'])
                            for item in attr:
                                if 'title' in item:
                                    if item['title'] == 'Potencia contratada 1 (kW)':
                                        self.Supply['PowerLimit_P1'] = float(item['value'].replace(",", "."))
                                    elif item['title'] == 'Potencia contratada 2 (kW)':
                                        self.Supply['PowerLimit_P2'] = float(item['value'].replace(",", "."))
                except Exception as e:
                    _LOGGER.warning (e + f"; assuming {self.Supply['PowerLimit']} as P1 and P2 power limits")
                    self.Supply['PowerLimit_P1'] = self.Supply['PowerLimit']
                    self.Supply['PowerLimit_P2'] = self.Supply['PowerLimit']
                break
        else:
            found = False
        return found
    
    def update (self, cups=None):
        if not self._busy:
            self._busy = True
            try:
                # updating cups or login
                if self.Supply.get('CUPS', None) is None or self.Supply.get('CUPS', None) != cups:
                    self._set_cups(cups)
                else:
                    self._eds.login()
                # updating last and current bills
                self._fetch_all ()
            except Exception:
                pass
            self._busy = False

    async def async_update (self, cups=None):
        if self._should_reset_day is None or self._should_reset_day:
            await self._get_pvpc_prices()
        self._loop.run_in_executor(None, self.update, cups)
        if self._should_reset_day is None or self._should_reset_day:
            self._should_reset_day = False

    def _fetch_all (self):
        if self._last_long_update is None or (datetime.now() - self._last_long_update) > self._long_interval:
            # Fetch cycles data
            try:
                self._cycles = self._eds.get_cycle_list(self.Supply['CONT_Id'])
                d0 = datetime.strptime(self._cycles['lstCycles'][0]['label'].split(' - ')[0], '%d/%m/%Y')
                d1 = datetime.strptime(self._cycles['lstCycles'][0]['label'].split(' - ')[1], '%d/%m/%Y')
                d2 = d1 + timedelta(days=1)
                d3 = datetime.today()
                self._should_reset_day = self.Cycles[0]['DateStart'] != d2 if len(self.Cycles) > 0 else False
                if len(self.Cycles) < 2 or self._should_reset_day:
                    current = self._eds.get_custom_curve(self.Supply['CONT_Id'], d2.strftime("%Y-%m-%d"), d3.strftime("%Y-%m-%d"))
                    last = self._eds.get_cycle_curve(self.Supply['CONT_Id'], self._cycles['lstCycles'][0]['label'], self._cycles['lstCycles'][0]['value'])
                    self.Cycles = []
                    for period in [current, last]:
                        Period = self._rawcycle2data (period)
                        self.Cycles.append(Period)
                    # Fetch maximeter data
                    try:
                        d0 = datetime.today()-timedelta(days=395)
                        d1 = datetime.today()
                        maximeter = self._eds.get_maximeter (self.Supply['CUPS_Id'], d0.strftime("%m/%Y"), d1.strftime("%m/%Y"))
                        if maximeter is not None:
                            self.Maximeter = self._rawmaximeter2data (maximeter)
                    except Exception as e:
                        _LOGGER.warning(e)
                else:
                    current = self._eds.get_custom_curve(self.Supply['CONT_Id'], d2.strftime("%Y-%m-%d"), d3.strftime("%Y-%m-%d"))
                    self.Cycles[0] = self._rawcycle2data (current)
                self.Today = self._get_day(datetime.today())
                self.Yesterday = self._get_day(datetime.today()-timedelta(days=1))
            except Exception as e:
                _LOGGER.warning(e)
            self._last_long_update = datetime.now()

        if self._last_short_update is None or (datetime.now() - self._last_short_update) > self._short_interval:
            # Fetch meter data
            try:
                meter = self._eds.get_meter(self.Supply['CUPS_Id'])
                if meter is not None:
                    self.Meter = self._rawmeter2data (meter)
                    if self._should_reset_day or self._meter_yesterday is None:
                        self._meter_yesterday = self.Meter.get('EnergyMeter', None)
                    if self._meter_yesterday is not None:
                        self.Meter["EnergyToday"] = self.Meter['EnergyMeter'] - self._meter_yesterday
            except Exception as e:
                _LOGGER.warning(e)
            # Update prices if needed
            try:
                if self.PVPC is not None and self.PVPC.get('raw', None) is not None and self.PVPC['ready'] == False:
                    self.PVPC['df'] = pd.DataFrame([{'datetime': x.astimezone(tz.timezone('Europe/Madrid')),'date': x.astimezone(tz.timezone('Europe/Madrid')).strftime("%d-%m-%Y"), 'hour': f"{x.astimezone(tz.timezone('Europe/Madrid')).strftime('%H')} - {(x.astimezone(tz.timezone('Europe/Madrid')).hour + 1):02d} h", 'price': self.PVPC['raw'][x]} for x in self.PVPC['raw']])
                    self.PVPC['ready'] = True
                    for cycle in self.Cycles:
                        if cycle['DateStart'] >= datetime(2021, 6, 1):
                            cycle['df'] = cycle['df'].merge(self.PVPC['df'], how='left', left_on=['date', 'hour'], right_on=['date', 'hour'])
                            cycle['df']['energy_price'] = cycle['df']['value'] * cycle['df']['price']
                            cycle['Energy_Cost'] = round(cycle['df']['energy_price'].sum(), 2)
                            cycle['Energy_AvgCost'] = round(cycle['Energy_Cost'] / cycle['Energy'], 2)
                            cycle['Power_Cost'] = round((self.Supply['PowerLimit_P1'] * (DEFAULT_DAILY_PRICE_P1 + DEFAULT_DAILY_PRICE_COMERC) + self.Supply['PowerLimit_P2'] * DEFAULT_DAILY_PRICE_P2) * cycle['DateDelta'], 2)
                            cycle['Bill'] = round(((cycle['Energy_Cost'] + cycle['Power_Cost']) * DEFAULT_TAX_ELECTR + (DEFAULT_PRICE_CONT * cycle['DateDelta'] / 30)) * DEFAULT_TAX_IVA, 2)
            except Exception as e:
                _LOGGER.warning(e)
            self._last_short_update = datetime.now()

    async def _get_pvpc_prices (self):
        pvpc_handler = PVPCData(tariff=TARIFFS[0], local_timezone='Europe/Madrid')
        start = datetime.today() - timedelta(days=60)
        end = datetime.today()
        self.PVPC['raw'] = await pvpc_handler.async_download_prices_for_range(start, end)
        self.PVPC['ready'] = False

    def _rawmeter2data (self, meter):
        Meter = {}
        Meter['Power'] = meter.get('potenciaActual', None)
        Meter['ICP'] = meter.get('estadoICP', None)
        Meter['EnergyMeter'] = int(str(meter.get('totalizador', None)).replace(".", ""))
        Meter['Load'] = float(meter.get('percent', None).replace("%","").replace(",", "."))
        Meter['PowerLimit'] = meter.get('potenciaContratada', None)
        return Meter

    def _rawcycle2data (self, period):
        Period = {}
        Period['DateStart'] = datetime.fromisoformat(period.get('startDt','1990-01-01T22:00:00.000Z').split("T")[0]) + timedelta(days=1)
        Period['DateEnd'] = datetime.fromisoformat(period.get('endDt','1990-01-01T22:00:00.000Z').split("T")[0]) + timedelta(days=1)
        Period['DateDelta'] = (Period['DateEnd'] - Period['DateStart']).days
        Period['EnergyMax'] = float(period.get('maxPerMonth', None))
        Period['Energy'] = float(period.get('totalValue', None).replace(",","."))
        if Period['Energy'] is not None and Period['DateDelta'] > 0:
            Period['EnergyDaily'] = round(Period['Energy'] / Period['DateDelta'], 2)
        data = period.get('mapHourlyPoints', None)
        if data is not None:
            good_data = []
            for day in data:
                for idx in data[day]:
                    new_element={}
                    new_element['date'] = day
                    for key in idx:
                        new_element[key] = idx[key]
                    good_data.append(new_element)
            Period['df'] = pd.DataFrame(good_data)
            Period['df']['weekday'] = pd.to_datetime(Period['df']['date'], format='%d-%m-%Y').dt.day_name()
            Period['Energy_P1'] = round(Period['df']['value'].loc[(Period['df']['hour'].isin(LIST_P1)) & (~Period['df']['weekday'].isin(DAYS_P3))].sum(), 2)
            Period['Energy_P2'] = round(Period['df']['value'].loc[(Period['df']['hour'].isin(LIST_P2)) & (~Period['df']['weekday'].isin(DAYS_P3))].sum(), 2)
            Period['Energy_P3'] = round(Period['Energy'] - Period['Energy_P1'] - Period['Energy_P2'], 2)
        return Period

    def _rawmaximeter2data (self, maximeter):
        Maximeter = {}
        Maximeter['df'] =  pd.DataFrame([x for x in maximeter.get('lstData', None) if x['valid'] == True])
        Maximeter['Average'] = round(Maximeter['df']['value'].mean(), 2)
        Maximeter['Max'] = round(Maximeter['df']['value'].max(), 2)
        idx_max = Maximeter['df']['value'].idxmax()
        Maximeter['DateMax'] = datetime.strptime(Maximeter['df'].iloc[idx_max]['date'] + "_" + Maximeter['df'].iloc[idx_max]['hour'], '%d-%m-%Y_%H:%M')
        Maximeter['Percentile99'] = round(Maximeter['df']['value'].quantile(.99), 2)
        Maximeter['Percentile95'] = round(Maximeter['df']['value'].quantile(.95), 2)
        Maximeter['Percentile90'] = round(Maximeter['df']['value'].quantile(.90), 2)
        return Maximeter

    def _get_day (self, date):
        date_str = date.strftime('%d-%m-%Y')
        '''
        start_summer = calendar.monthcalendar(date_str.year, 3)
        end_summer = calendar.monthcalendar(date_str.year, 10)
        start_summer = datetime(date_str.year, 3, max(start_summer[-1][calendar.SUNDAY], start_summer[-2][calendar.SUNDAY])) 
        end_summer = datetime(date_str.year, 10, max(end_summer[-1][calendar.SUNDAY], end_summer[-2][calendar.SUNDAY])) 
        is_summer = True if start_summer < datetime.today() < end_summer else False
        '''
        Day = {}
        Day['Energy'] = None
        Day['Energy_P1'] = None
        Day['Energy_P2'] = None
        Day['Energy_P3'] = None
        for c in self.Cycles:
            if date_str in c['df']['date'].values:
                tempdf = c['df'].loc[c['df']['date'] == date_str]
                Day['Energy'] = round(tempdf['value'].sum(), 2)
                Day['Energy_P1'] = round(tempdf['value'].loc[(tempdf['hour'].isin(LIST_P1)) & (~tempdf['weekday'].isin(DAYS_P3))].sum(), 2)
                Day['Energy_P2'] = round(tempdf['value'].loc[(tempdf['hour'].isin(LIST_P2)) & (~tempdf['weekday'].isin(DAYS_P3))].sum(), 2)
                Day['Energy_P3'] = Day['Energy'] - Day['Energy_P1'] - Day['Energy_P2']
                break
        return Day

    def __str__ (self):
        value = \
            f"""
            \r* CUPS: {self.Supply.get('CUPS', '-')}
            \r* Contador (kWh): {self.Meter.get('EnergyMeter', '-')}
            \r* Energía hoy (kWh): {self.Meter.get('EnergyToday', '-')}
            \r* Estado ICP: {self.Meter.get('ICP', '-')}
            \r* Carga actual (%): {self.Meter.get('Load', '-')}
            \r* Potencia contratada (kW): {self.Supply.get('PowerLimit', '-')}
            \r* Potencia demandada (kW): {self.Meter.get('Power', '-')}
            \r* Hoy (kWh): {self.Today.get('Energy', '-')} 
            \r* Hoy detalle (kWh): (P1: {self.Today.get('Energy_P1', '-')} | P2: {self.Today.get('Energy_P2', '-')} | P3: {self.Today.get('Energy_P3', '-')})
            \r* Ayer (kWh): {self.Yesterday.get('Energy', '-')}
            \r* Ayer detalle (kWh): (P1: {self.Yesterday.get('Energy_P1', '-')} | P2: {self.Yesterday.get('Energy_P2', '-')} | P3: {self.Yesterday.get('Energy_P3', '-')})
            \r* Ciclo anterior (kWh): {self.Cycles[1].get('Energy', '-') if len(self.Cycles) > 1 else None} en {self.Cycles[1].get('DateDelta', '-') if len(self.Cycles) > 1 else None} días ({self.Cycles[1].get('EnergyDaily', '-') if len(self.Cycles) > 1 else None} kWh/día)
            \r* Ciclo anterior detalle (kWh): (P1: {self.Cycles[1].get('Energy_P1', '-')  if len(self.Cycles) > 1 else None} | P2: {self.Cycles[1].get('Energy_P2', '-')  if len(self.Cycles) > 1 else None} | P3: {self.Cycles[1].get('Energy_P3', '-')  if len(self.Cycles) > 1 else None})
            \r* Ciclo anterior - coste energía (sin IVA) (€): {self.Cycles[1].get('Energy_Cost', '-')  if len(self.Cycles) > 1 else None}
            \r* Ciclo actual - coste potencia (sin IVA) (€): {self.Cycles[1].get('Power_Cost', '-')  if len(self.Cycles) > 1 else None}
            \r* Ciclo actual - factura (con IVA) (€): {self.Cycles[1].get('Bill', '-')  if len(self.Cycles) > 1 else None}            
            \r* Ciclo actual (kWh): {self.Cycles[0].get('Energy', '-') if len(self.Cycles) > 1 else None} en {self.Cycles[0].get('DateDelta', '-') if len(self.Cycles) > 1 else None} días ({self.Cycles[0].get('EnergyDaily', '-') if len(self.Cycles) > 1 else None} kWh/día)
            \r* Ciclo actual detalle (kWh): (P1: {self.Cycles[0].get('Energy_P1', '-')  if len(self.Cycles) > 1 else None} | P2: {self.Cycles[0].get('Energy_P2', '-')  if len(self.Cycles) > 1 else None} | P3: {self.Cycles[0].get('Energy_P3', '-')  if len(self.Cycles) > 1 else None})
            \r* Ciclo actual - coste energía (sin IVA) (€): {self.Cycles[0].get('Energy_Cost', '-')  if len(self.Cycles) > 1 else None}
            \r* Ciclo actual - coste potencia (sin IVA) (€): {self.Cycles[0].get('Power_Cost', '-')  if len(self.Cycles) > 1 else None}
            \r* Ciclo actual - factura (con IVA) (€): {self.Cycles[0].get('Bill', '-')  if len(self.Cycles) > 1 else None}
            \r* Potencia máxima (kW): {self.Maximeter.get('Max', '-')} el {self.Maximeter.get('DateMax', datetime(1990, 1, 1)).strftime("%d/%m/%Y")}
            \r* Potencia media (kW): {self.Maximeter.get('Average', '-')}
            \r* Potencia percentil (99 | 95 | 90) (kW): {self.Maximeter.get('Percentile99', '-')} | {self.Maximeter.get('Percentile95', '-')} | {self.Maximeter.get('Percentile90', '-')} 
            """ 
        return value
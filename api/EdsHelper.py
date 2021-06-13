import logging
from api.EdsConnector import EdsConnector
from datetime import datetime, timedelta
#import calendar
import numpy as np

_LOGGER = logging.getLogger(__name__)

class EdsHelper():
    __eds = None
    # raw data
    __username = None
    __password = None
    __last_update = None
    __short_interval = None
    __long_interval = None

    Supply = {}
    Today = {}
    Yesterday = {}
    Cycles = []
    Meter = {}
    Maximeter = {}

    def __init__(self, user, password, cups=None, short_interval=10, long_interval=60):
        self.__eds = EdsConnector(user, password)
        self.__username = user
        self.__password = password
        self.__short_interval = short_interval
        self.__long_interval = long_interval

    # To load CUPS into the helper
    def set_cups (self, candidate=None):
        self.__eds.login()
        all_cups = self.__eds.get_cups_list()
        _LOGGER.debug ("CUPS:" + str(all_cups))
        found = False
        for c in all_cups:
            if candidate is None or c.get('CUPS', None) == candidate:
                self.Supply['CUPS'] = c.get('CUPS', None)
                self.Supply['CUPS_Id'] = c.get('CUPS_Id', None)
                self.Supply['CONT_Id'] = c.get('Id', None)
                self.Supply['Active'] = c.get('Active', None)
                self.Supply['PowerLimit'] = c.get('Power', None)
                found = True
                break
        else:
            found = False
        return found
    
    def update (self):
        # updating cups or login
        if self.Supply.get('CUPS', None) is None:
            self.set_cups()
        else:
            self.__eds.login()

        # updating last and current bills
        self.__fetch_all ()
        self.__last_update = datetime.now()

    def __fetch_all (self):
        if self.__last_update is None or (datetime.now() - self.__last_update).minutes > self.__long_interval:
            # Fetch cycles data
            try:
                cycles = self.__eds.get_cycle_list(self.Supply['CONT_Id'])
                d0 = datetime.strptime(cycles['lstCycles'][0]['label'].split(' - ')[0], '%d/%m/%Y')
                d1 = datetime.strptime(cycles['lstCycles'][0]['label'].split(' - ')[1], '%d/%m/%Y')
                d2 = d1 + timedelta(days=1)
                d3 = datetime.today()
                if len(self.Cycles) < 2 or self.Cycles[0]['DateStart'] != d2:
                    _LOGGER.info("Fetching complete history")
                    current = self.__eds.get_custom_curve(self.Supply['CONT_Id'], d2.strftime("%Y-%m-%d"), d3.strftime("%Y-%m-%d"))
                    last = self.__eds.get_cycle_curve(self.Supply['CONT_Id'], cycles['lstCycles'][0]['label'], cycles['lstCycles'][0]['value'])
                    self.Cycles = []
                    for period in [current, last]:
                        Period = self.__rawcycle2data (period)
                        self.Cycles.append(Period)
                    # Fetch maximeter data
                    try:
                        d0 = datetime.today()-timedelta(days=395)
                        d1 = datetime.today()
                        maximeter = self.__eds.get_maximeter (self.Supply['CUPS_Id'], d0.strftime("%m/%Y"), d1.strftime("%m/%Y"))
                        if maximeter is not None:
                            self.Maximeter = self.__rawmaximeter2data (maximeter)
                    except Exception as e:
                        _LOGGER.warning(e)
                else:
                    _LOGGER.info("Fetching only current period")
                    current = self.__eds.get_custom_curve(self.Supply['CONT_Id'], d2.strftime("%Y-%m-%d"), d3.strftime("%Y-%m-%d"))
                    self.Cycles[0] = self.__rawcycle2data (current)
                self.Today = self.__get_day(datetime.today())
                self.Yesterday = self.__get_day(datetime.today()-timedelta(days=1))
            except Exception as e:
                _LOGGER.warning(e)
            
        # Fetch meter data
        if self.__last_update is None or (datetime.now() - self.__last_update).minutes > self.__short_interval:
            try:
                meter = self.__eds.get_meter(self.Supply['CUPS_Id'])
                if meter is not None:
                    self.Meter = self.__rawmeter2data (meter)
            except Exception as e:
                _LOGGER.warning(e)

    def __rawmeter2data (self, meter):
        Meter = {}
        Meter['Power'] = meter.get('potenciaActual', None)
        Meter['ICP'] = meter.get('estadoICP', None)
        Meter['EnergyMeter'] = int(str(meter.get('totalizador', None)).replace(".", ""))
        Meter['Load'] = float(meter.get('percent', None).replace("%","").replace(",", "."))
        Meter['PowerLimit'] = meter.get('potenciaContratada', None)
        return Meter

    def __rawcycle2data (self, period):
        Period = {}
        Period['DateStart'] = datetime.fromisoformat(period.get('startDt','1990-01-01T22:00:00.000Z').split("T")[0]) + timedelta(days=1)
        Period['DateEnd'] = datetime.fromisoformat(period.get('endDt','1990-01-01T22:00:00.000Z').split("T")[0]) + timedelta(days=1)
        Period['DateDelta'] = (Period['DateEnd'] - Period['DateStart']).days
        Period['EnergyMax'] = float(period.get('maxPerMonth', None))
        Period['EnergySum'] = float(period.get('totalValue', None).replace(",","."))
        if Period['EnergySum'] is not None and Period['DateDelta'] > 0:
            Period['EnergyDaily'] = round(Period['EnergySum'] / Period['DateDelta'], 2)
        Period['Detail'] = period.get('mapHourlyPoints', None)
        return Period

    def __rawmaximeter2data (self, maximeter):
        Maximeter = {}
        Maximeter['Max'] = 0
        Maximeter['DateMax'] = None
        Maximeter['Average'] = 0
        Maximeter['Percentile99'] = 0
        Maximeter['Percentile95'] = 0
        Maximeter['Percentile90'] = 0
        Maximeter['Detail'] = maximeter.get('lstData', None)
        all_values = []
        count = 0
        for m in Maximeter['Detail']:
            if m['value'] > 0:
                all_values.append(m['value'])
                Maximeter['Average'] = Maximeter['Average'] + m['value']
                count = count + 1
                if m['value'] > Maximeter['Max']:
                    Maximeter['Max'] = m['value']
                    Maximeter['DateMax'] = datetime.strptime(m['date'] + "_" + m['hour'], '%d-%m-%Y_%H:%M')
        if count > 0:
            Maximeter['Average'] = round(Maximeter['Average'] / count, 2)
        Maximeter['Percentile99'] = round(np.percentile(np.array(all_values), 99), 2)
        Maximeter['Percentile95'] = round(np.percentile(np.array(all_values), 95), 2)
        Maximeter['Percentile90'] = round(np.percentile(np.array(all_values), 90), 2)
        return Maximeter

    def __get_day (self, date):
        date_str = date.strftime('%d-%m-%Y')
        '''
        start_summer = calendar.monthcalendar(date_str.year, 3)
        end_summer = calendar.monthcalendar(date_str.year, 10)
        start_summer = datetime(date_str.year, 3, max(start_summer[-1][calendar.SUNDAY], start_summer[-2][calendar.SUNDAY])) 
        end_summer = datetime(date_str.year, 10, max(end_summer[-1][calendar.SUNDAY], end_summer[-2][calendar.SUNDAY])) 
        is_summer = True if start_summer < datetime.today() < end_summer else False
        '''
        Day = {}
        Day['Energy'] = 0
        Day['P1'] = 0
        Day['P2'] = 0
        Day['P3'] = 0
        for c in self.Cycles:
            if date_str in c['Detail']:
                Day['Energy'] = round(np.sum( [ x['value'] for x in c['Detail'][date_str] ] ), 2)
                Day['P1'] = round(np.sum( [ x['value'] for ind, x in enumerate(c['Detail'][date_str]) if (10 <= ind < 14) or (18 <= ind < 22) ] ), 2)
                Day['P2'] = round(np.sum( [ x['value'] for ind, x in enumerate(c['Detail'][date_str]) if (8 <= ind < 10) or (14 <= ind < 18) or (22 <= ind <= 23) ] ), 2)
                Day['P3'] = round(np.sum( [ x['value'] for ind, x in enumerate(c['Detail'][date_str]) if (0 <= ind < 8) ] ), 2)
                break
        else:
            Day = None
        return Day

 
    def __str__ (self):
        value = \
            f"""
            \r* CUPS: {self.Supply.get('CUPS', '-')}
            \r* Contador (kWh): {self.Meter.get('EnergyMeter', '-')}
            \r* Estado ICP: {self.Meter.get('ICP', '-')}
            \r* Carga actual (%): {self.Meter.get('Load', '-')}
            \r* Potencia contratada (kW): {self.Supply.get('PowerLimit', '-')}
            \r* Potencia demandada (kW): {self.Meter.get('Power', '-')}
            \r* Hoy (kWh): {self.Today.get('Energy', '-')} (P1: {self.Today.get('P1', '-')} | P2: {self.Today.get('P2', '-')} | P3: {self.Today.get('P3', '-')})
            \r* Ayer (kWh): {self.Yesterday.get('Energy', '-')} (P1: {self.Yesterday.get('P1', '-')} | P2: {self.Yesterday.get('P2', '-')} | P3: {self.Yesterday.get('P3', '-')})
            \r* Ciclo anterior (kWh): {self.Cycles[1].get('EnergySum', '-') if len(self.Cycles) > 1 else None} en {self.Cycles[1].get('DateDelta', '-') if len(self.Cycles) > 1 else None} días ({self.Cycles[1].get('EnergyDaily', '-') if len(self.Cycles) > 1 else None} kWh/día)
            \r* Ciclo actual (kWh): {self.Cycles[0].get('EnergySum', '-') if len(self.Cycles) > 1 else None} en {self.Cycles[0].get('DateDelta', '-') if len(self.Cycles) > 1 else None} días ({self.Cycles[0].get('EnergyDaily', '-') if len(self.Cycles) > 1 else None} kWh/día)
            \r* Potencia máxima (kW): {self.Maximeter.get('Max', '-')} el {self.Maximeter.get('DateMax', datetime(1990, 1, 1)).strftime("%d/%m/%Y")}
            \r* Potencia media (kW): {self.Maximeter.get('Average', '-')}
            \r* Potencia percentil (99 | 95 | 90) (kW): {self.Maximeter.get('Percentile99', '-')} | {self.Maximeter.get('Percentile95', '-')} | {self.Maximeter.get('Percentile90', '-')} 
            """ 
        return value
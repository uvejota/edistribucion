import logging
from api.EdsConnector import EdsConnector
from datetime import datetime, timedelta

_LOGGER = logging.getLogger(__name__)

class EdsHelper():
    __eds = None
    # raw data
    __username = None
    __password = None
    __last_update = None

    Supply = {}
    Cycles = []
    Meter = {}
    Maximeter = {}

    def __init__(self, user, password, cups=None):
        self.__eds = EdsConnector(user, password)
        self.__username = user
        self.__password = password
        if cups is not None:
            self.set_cups (cups)

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
    
    def update (self, full_update=True):
        # updating cups or login
        if self.Supply.get('CUPS', None) is None:
            self.set_cups()
        else:
            self.__eds.login()

        # updating last and current bills
        self.__fetch_all (full_update)

        __last_update = datetime.now()

    def __fetch_all (self, full_update=True):

        if full_update:
            # Fetch cycles data
            try:
                cycles = self.__eds.get_list_cycles(self.Supply['CONT_Id'])
                d0 = datetime.strptime(cycles['lstCycles'][0]['label'].split(' - ')[0], '%d/%m/%Y')
                d1 = datetime.strptime(cycles['lstCycles'][0]['label'].split(' - ')[1], '%d/%m/%Y')
                d2 = d1 + timedelta(days=1)
                d3 = datetime.today()
                if len(self.Cycles) < 2 or self.Cycles[0]['DateStart'] != d2:
                    _LOGGER.warning("Fetching complete history")
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
                    _LOGGER.warning("Fetching only current period")
                    current = self.__eds.get_custom_curve(self.Supply['CONT_Id'], d2.strftime("%Y-%m-%d"), d3.strftime("%Y-%m-%d"))
                    self.Cycles[0] = self.__rawcycle2data (current)
            except Exception as e:
                _LOGGER.warning(e)
            
        # Fetch meter data
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
        Meter['EnergyMeter'] = float(str(meter.get('totalizador', None)).replace(".", ""))
        Meter['Load'] = float(meter.get('percent', None).replace("%","").replace(",", "."))
        Meter['PowerLimit'] = meter.get('potenciaContratada', None)
        return Meter

    def __rawcycle2data (self, period):
        Period = {}
        Period['DateStart'] = datetime.fromisoformat(period.get('startDt','1990-01-01T22:00:00.000Z').split("T")[0]) + timedelta(days=1)
        Period['DateEnd'] = datetime.fromisoformat(period.get('endDt','1990-01-01T22:00:00.000Z').split("T")[0]) + timedelta(days=1)
        Period['DateDelta'] = (Period['DateEnd'] - Period['DateStart']).days
        Period['PowerPeak'] = float(period.get('maxPerMonth', None))
        Period['EnergySum'] = float(period.get('totalValue', None).replace(",","."))
        if Period['EnergySum'] is not None and Period['DateDelta'] > 0:
            Period['EnergyDailyAvg'] = round(Period['EnergySum'] / Period['DateDelta'], 2)
        Period['Detail'] = period.get('mapHourlyPoints', None)
        return Period

    def __rawmaximeter2data (self, maximeter):
        Maximeter = {}
        Maximeter['Max'] = 0
        Maximeter['DateMax'] = None
        Maximeter['Average'] = 0
        Maximeter['Detail'] = maximeter.get('lstData', None)
        count = 0
        for m in Maximeter['Detail']:
            if m['value'] > 0:
                Maximeter['Average'] = Maximeter['Average'] + m['value']
                count = count + 1
                if m['value'] > Maximeter['Max']:
                    Maximeter['Max'] = m['value']
                    Maximeter['DateMax'] = datetime.strptime(m['date'] + "_" + m['hour'], '%d-%m-%Y_%H:%M')
        if count > 0:
            Maximeter['Average'] = Maximeter['Average'] / count
        return Maximeter
import logging
from homeassistant.const import POWER_KILO_WATT
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.event import async_track_point_in_time
from .api.EdistribucionAPI import Edistribucion
from datetime import datetime, timedelta

# HA variables
_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=10)
FRIENDLY_NAME = 'EDS Consumo eléctrico'

# Default values
DEFAULT_SAVE_SESSION = True

# Services
SERVICE_RECONNECT_ICP = "reconnect_icp"

# Attributes
ATTR_CUPS_NAME = "CUPS"
ATTR_CONSUMPTION_TODAY = "Consumo (hoy)"
ATTR_CONSUMPTION_YESTERDAY = "Consumo (ayer)"
ATTR_CONSUMPTION_CURRPERIOD = "Consumo (factura actual)"
ATTR_CONSUMPTION_LASTPERIOD = "Consumo (últ. factura)"
ATTR_CONSUMPTION_ALWAYS = "Consumo total"
ATTR_DAILYCONSUMPTION_CURRPERIOD = "Consumo diario medio (factura actual)"
ATTR_DAILYCONSUMPTION_LASTPERIOD = "Consumo diario medio (últ. factura)"
ATTR_MAXPOWER_1YEAR = "Máxima potencia registrada"
ATTR_ICPSTATUS = "Estado ICP"
ATTR_LOAD_NOW = "Carga actual"
ATTR_POWER_LIMIT = "Potencia contratada"

async def async_setup_platform(hass, config, add_entities, discovery_info=None):

    # Define entities
    entities = []

    #If save_session is not defined at configuration.yaml, default is DEFAULT_SAVE_SESSION
    save_session = config.get('save_session', DEFAULT_SAVE_SESSION)

    # Register services
    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
            SERVICE_RECONNECT_ICP,
            {},
            EDSSensor.reconnect_ICP.__name__,
        )

    # Register listeners
    def handle_next_day (event):
        _LOGGER.debug("handle_next_day called")
        for entity in entities:
            entity.handle_next_day ()
        schedule_next_day ()

    def handle_next_6am (event):
        _LOGGER.debug("handle_next_6am called")
        for entity in entities:
            entity.handle_next_6am ()
        schedule_next_6am ()

    # Set schedulers
    def schedule_next_day ():
        _LOGGER.debug("schedule_next_day called")
        now = datetime.now()
        tomorrow_begins = now.replace(hour=0, minute=0, second=0) + timedelta(days=1)
        async_track_point_in_time(
            hass, handle_next_day, tomorrow_begins
        )

    def schedule_next_6am ():
        _LOGGER.debug("schedule_next_6am called")
        now = datetime.now()
        tomorrow_begins = now.replace(hour=6, minute=0, second=0) + timedelta(days=1)
        async_track_point_in_time(
            hass, handle_next_6am, tomorrow_begins
        )

    # Create sensor entities and add them
    eds = EDSSensor(config['username'],config['password'],save_session)
    entities.append(eds)
    add_entities(entities)

    # Start schedulers
    schedule_next_day()
    schedule_next_6am()

class EDSSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self,usr,pw,session):
        """Initialize the sensor."""
        self._state = None
        self._attributes = {}
        self._usr=usr
        self._pw=pw
        self._session=session

        self._is_first_boot = True
        self._do_run_daily_tasks = False
        self._do_run_6am_tasks = False

        self._total_consumption = 0
        self._total_consumption_yesterday = 0

        # Initializing attributes to establish the order
        self._attributes[ATTR_CUPS_NAME] = ""
        self._attributes[ATTR_CONSUMPTION_TODAY] = ""
        self._attributes[ATTR_CONSUMPTION_YESTERDAY] = ""
        self._attributes[ATTR_CONSUMPTION_ALWAYS] = ""
        self._attributes[ATTR_CONSUMPTION_LASTPERIOD] = ""
        self._attributes[ATTR_CONSUMPTION_CURRPERIOD] = ""
        self._attributes[ATTR_MAXPOWER_1YEAR] = ""
        self._attributes[ATTR_ICPSTATUS] = ""
        self._attributes[ATTR_LOAD_NOW] = ""
        self._attributes[ATTR_POWER_LIMIT] = ""

        # Login into the cloud platform
        self._edis = None


    @property
    def name(self):
        """Return the name of the sensor."""
        return FRIENDLY_NAME

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return "mdi:flash" 

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return POWER_KILO_WATT

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    def handle_next_day (self):
        self._do_run_daily_tasks = True

    def handle_next_6am (self):
        self._do_run_6am_tasks = True

    def reconnect_ICP (self):
        ### Untested... impossible under the current setup
        _LOGGER.debug("ICP reconnect service called")
        if self._edis is None:
            self._edis = Edistribucion(self._usr,self._pw,self._session)
            self._edis.login()
        # Get CUPS list, at the moment we just explore the first element [0] in the table (valid if you only have a single contract)
        r = self._edis.get_list_cups()
        cups = r[0]['CUPS_Id']
        # Get response
        response = self._edis.reconnect_ICP(cups)
        _LOGGER.debug(response)

    def update(self):
        """Fetch new state data for the sensor."""
        if self._edis is None:
            self._edis = Edistribucion(self._usr,self._pw,self._session)
            self._edis.login()

        # Get CUPS list, at the moment we just explore the first element [0] in the table (valid if you only have a single contract)
        r = self._edis.get_list_cups()
        cups = r[0]['CUPS_Id']
        cont = r[0]['Id']

        self._attributes[ATTR_CUPS_NAME] = r[0]['CUPS'] # this is the name

        # First retrieve historical data if first boot or starting a new day (this is fast)
        if self._is_first_boot or self._do_run_6am_tasks:
            _LOGGER.debug("fetching historical data")
            # fetch last cycle from list
            cycles = self._edis.get_list_cycles(cont)
            lastcycle = cycles['lstCycles'][0]
            # prepare some datetimes...
            date_yesterday = (datetime.today()-timedelta(days=1)).strftime("%Y-%m-%d")
            date_currmonth = datetime.today().strftime("%m/%Y")
            date_ayearago = (datetime.today()-timedelta(days=365)).strftime("%m/%Y")
            date_currcycle = (datetime.strptime(lastcycle['label'].split(' - ')[1], '%d/%m/%Y') + timedelta(days=1)).strftime("%Y-%m-%d")
            # fetch historical data
            yesterday_curve=self._edis.get_day_curve(cont,date_yesterday)
            lastcycle_curve = self._edis.get_cycle_curve(cont, lastcycle['label'], lastcycle['value'])
            currcycle_curve=self._edis.get_custom_curve(cont,date_currcycle, date_yesterday)
            maximeter_histogram = self._edis.get_year_maximeter (cups, date_ayearago, date_currmonth)
            # store historical data as attributes
            self._attributes[ATTR_CONSUMPTION_YESTERDAY] = str(yesterday_curve['data']['totalValue']).replace(".","").replace(",",".") + ' kWh'
            self._attributes[ATTR_CONSUMPTION_CURRPERIOD] = str(currcycle_curve['data']['totalValue']).replace(".","").replace(",",".") + ' kWh'
            self._attributes[ATTR_CONSUMPTION_LASTPERIOD] = str(lastcycle_curve['totalValue']).replace(".","").replace(",",".") + ' kWh'
            self._attributes[ATTR_MAXPOWER_1YEAR] = str(maximeter_histogram['data']['maxValue']).replace(".","").replace(",",".")

        # Then retrieve real-time data (this is slow)
        _LOGGER.debug("fetching real-time data")
        meter = self._edis.get_meter(cups)
        self._attributes[ATTR_ICPSTATUS] = meter['data']['estadoICP']
        self._total_consumption = float(str(meter['data']['totalizador']).replace(".","").replace(",","."))
        self._attributes[ATTR_CONSUMPTION_ALWAYS] = str(meter['data']['totalizador']).replace(".","").replace(",",".") + ' kWh'
        self._attributes[ATTR_LOAD_NOW] = str(meter['data']['percent']).replace(".","").replace(",",".")
        self._attributes[ATTR_POWER_LIMIT] = str(meter['data']['potenciaContratada']) + ' kW'
        
        # if new day, store consumption TODO fix bad scaling...
        _LOGGER.debug("doing internal calculus")
        if self._do_run_daily_tasks or self._is_first_boot:
            # if a new day has started, store last total consumption as the base for the daily calculus
            self._total_consumption_yesterday = float(self._total_consumption)
        # do the maths and update it during the day
        self._attributes[ATTR_CONSUMPTION_TODAY] = str((self._total_consumption) - (self._total_consumption_yesterday)) + ' kWh'

        # at this point, we should have update all attributes
        _LOGGER.debug("Attributes updated for EDSSensor: " + str(self._attributes))

        # Update the state of the Sensor
        self._state = meter['data']['potenciaActual']
        _LOGGER.debug("State updated for EDSSensor: " + str(self._state))

        # set flags down
        self._do_run_daily_tasks = False
        self._is_first_boot = False
        self._do_run_6am_tasks = False
        
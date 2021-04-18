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
ATTR_CONSUMPTION_TODAY = "Consumo total (hoy)"
ATTR_CONSUMPTION_YESTERDAY = "Consumo total (ayer)"
ATTR_CONSUMPTION_7DAYS = "Consumo total (7 días)"
ATTR_CONSUMPTION_30DAYS = "Consumo total (30 días)"
ATTR_CONSUMPTION_ALWAYS = "Consumo total"
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
    def handle_next_day (self):
        _LOGGER.debug("handle_next_day called")
        for entity in entities:
            entity.handle_next_day ()

    def handle_next_6am (self):
        _LOGGER.debug("handle_next_6am called")
        for entity in entities:
            entity.handle_next_6am ()

    # Set schedulers
    def schedule_next_day (self):
        _LOGGER.debug("schedule_next_day called")
        today = datetime.today()
        tomorrow_begins = today.replace(hour=0, minute=0, second=0) + timedelta(days=1)
        async_track_point_in_time(
            hass, handle_next_day, datetime.as_utc(tomorrow_begins)
        )

    def schedule_next_6am (self):
        _LOGGER.debug("schedule_next_6am called")
        today = datetime.today()
        tomorrow_begins = today.replace(hour=6, minute=0, second=0) + timedelta(days=1)
        async_track_point_in_time(
            hass, handle_next_6am, datetime.as_utc(tomorrow_begins)
        )

    # Create sensor entities and add them
    eds = EDSSensor(config['username'],config['password'],save_session)
    entities.append(eds)
    add_entities(entities)

    # Start schedulers
    schedule_next_day
    schedule_next_6am

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
        self._attributes[ATTR_CONSUMPTION_TODAY] = ""
        self._attributes[ATTR_CONSUMPTION_YESTERDAY] = ""
        self._attributes[ATTR_CONSUMPTION_7DAYS] = ""
        self._attributes[ATTR_CONSUMPTION_30DAYS] = ""
        self._attributes[ATTR_CONSUMPTION_ALWAYS] = ""
        self._attributes[ATTR_MAXPOWER_1YEAR] = ""
        self._attributes[ATTR_ICPSTATUS] = ""
        self._attributes[ATTR_LOAD_NOW] = ""
        self._attributes[ATTR_POWER_LIMIT] = ""

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
        # Login into the edistribucion platform. 
        edis = Edistribucion(self._usr,self._pw,True)
        edis.login()
        # Get CUPS list, at the moment we just explore the first element [0] in the table (valid if you only have a single contract)
        r = edis.get_list_cups()
        cups = r[0]['CUPS_Id']
        # Get response
        response = edis.reconnect_ICP(cups)
        _LOGGER.debug(response)

    def update(self):
        """Fetch new state data for the sensor."""
        # Login into the edistribucion platform. 
        # TODO: try to save sessions by calling Edistribucion(self._usr,self._pw,True), for some reason this has been disabled until now
        edis = Edistribucion(self._usr,self._pw,self._session)
        edis.login()
        # Get CUPS list, at the moment we just explore the first element [0] in the table (valid if you only have a single contract)
        r = edis.get_list_cups()
        cups = r[0]['CUPS_Id']
        cont = r[0]['Id']

        self._attributes['CUPS'] = r[0]['CUPS'] # this is the name
        #self._attributes['Cont'] = cont # not really needed

        # First retrieve historical data if first boot or starting a new day (this is fast)
        if self._is_first_boot or self._do_run_6am_tasks:
            _LOGGER.debug("fetching historical data")
            yesterday = (datetime.today()-timedelta(days=1)).strftime("%Y-%m-%d")
            sevendaysago = (datetime.today()-timedelta(days=8)).strftime("%Y-%m-%d")
            onemonthago = (datetime.today()-timedelta(days=30)).strftime("%Y-%m-%d")

            yesterday_curve=edis.get_day_curve(cont,yesterday)
            self._attributes[ATTR_CONSUMPTION_YESTERDAY] = str(yesterday_curve['data']['totalValue']) + ' kWh'
            lastweek_curve=edis.get_week_curve(cont,sevendaysago)
            self._attributes[ATTR_CONSUMPTION_7DAYS] = str(lastweek_curve['data']['totalValue']) + ' kWh'
            lastmonth_curve=edis.get_month_curve(cont,onemonthago)
            self._attributes[ATTR_CONSUMPTION_30DAYS] = str(lastmonth_curve['data']['totalValue']) + ' kWh'

            thismonth = datetime.today().strftime("%m/%Y")
            ayearplusamonthago = (datetime.today()-timedelta(days=395)).strftime("%m/%Y")
            maximeter_histogram = edis.get_year_maximeter (cups, ayearplusamonthago, thismonth)
            self._attributes[ATTR_MAXPOWER_1YEAR] = maximeter_histogram['data']['maxValue']

        # Then retrieve real-time data (this is slow)
        _LOGGER.debug("fetching real-time data")
        meter = edis.get_meter(cups)
        self._attributes[ATTR_ICPSTATUS] = meter['data']['estadoICP']
        self._total_consumption = float(meter['data']['totalizador'])
        self._attributes[ATTR_CONSUMPTION_TODAY] = str(meter['data']['totalizador']) + ' kWh'
        self._attributes[ATTR_LOAD_NOW] = meter['data']['percent']
        self._attributes[ATTR_POWER_LIMIT] = str(meter['data']['potenciaContratada']) + ' kW'
        
        # if new day, store consumption
        _LOGGER.debug("doing internal calculus")
        if self._do_run_daily_tasks or self._is_first_boot:
            self._total_consumption_yesterday = float(self._total_consumption)

        self._attributes[ATTR_CONSUMPTION_TODAY] = str(self._total_consumption - self._total_consumption_yesterday) + ' kWh'

        self._state = meter['data']['potenciaActual']
        
        _LOGGER.debug("Attributes updated for EDSSensor: " + self._attributes)

        # set flags down
        self._do_run_daily_tasks = False
        self._is_first_boot = False
        self._do_run_6am_tasks = False
        
import logging
from homeassistant.const import POWER_KILO_WATT, ENERGY_KILO_WATT_HOUR 
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import config_validation as cv, entity_platform
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.event import async_track_point_in_time
from .api.EdistribucionAPI import Edistribucion
from datetime import datetime, timedelta

# HA variables
_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=10)
FRIENDLY_NAME = 'EDS Consumo eléctrico'
DOMAIN = 'edistribucion'

# Custom configuration entries
CONF_SAVE_SESSION = 'save_session'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SAVE_SESSION, default=True): vol.Boolean,
    }
)

# Services
SERVICE_RECONNECT_ICP = "reconnect_icp"

# Attributes
ATTR_CUPS_NAME = "CUPS"
ATTR_POWER_DEMAND = "Potencia demandada"
ATTR_ENERGY_TODAY = "Consumo (hoy)"
ATTR_ENERGY_YESTERDAY = "Consumo (ayer)"
ATTR_ENERGY_CURRPERIOD = "Consumo (factura actual)"
ATTR_ENERGY_LASTPERIOD = "Consumo (últ. factura)"
ATTR_ENERGY_ALWAYS = "Consumo total"
ATTR_DAYS_CURRPERIOD = "Días contabilizados (factura actual)"
ATTR_DAYS_LASTPERIOD = "Días contabilizados (últ. factura)"
ATTR_MAXPOWER_1YEAR = "Máxima potencia registrada"
ATTR_ICPSTATUS = "Estado ICP"
ATTR_LOAD_NOW = "Carga actual"
ATTR_POWER_LIMIT = "Potencia contratada"

# Other definitions
TYPE_SENSOR_ENERGY = 1
TYPE_SENSOR_POWER = 2

async def async_setup_platform(hass, config, add_entities, discovery_info=None):

    hass.data[DOMAIN] = {
        ATTR_CUPS_NAME: None,
        ATTR_POWER_DEMAND: None,
        ATTR_ENERGY_TODAY: None,
        ATTR_ENERGY_YESTERDAY: None,
        ATTR_ENERGY_CURRPERIOD: None,
        ATTR_ENERGY_LASTPERIOD: None,
        ATTR_ENERGY_ALWAYS: None,
        ATTR_DAYS_CURRPERIOD: None,
        ATTR_DAYS_LASTPERIOD: None,
        ATTR_MAXPOWER_1YEAR: None,
        ATTR_ICPSTATUS: None,
        ATTR_LOAD_NOW: None,
        ATTR_POWER_LIMIT: None
    }
    
    # Define entities
    entities = []

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

    def handle_in_5s (event):
        _LOGGER.debug("handle_in_5s called")
        for entity in entities:
            entity.handle_in_5s ()
        schedule_in_5s ()

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

    def schedule_in_5s ():
        _LOGGER.debug("schedule_in_5s called")
        now = datetime.now()
        wait_for_5s = now + timedelta(seconds=5)
        async_track_point_in_time(
            hass, handle_in_5s, wait_for_5s
        )

    # Declare Edistribucion API
    edis = Edistribucion(config[CONF_USERNAME],config[CONF_PASSWORD],config[CONF_SAVE_SESSION])

    # Create sensor entities and add them
    eds = EDSSensor(edis)
    entities.append(eds)

    # TEST
    entities.append(CustomSensor(edis, "Energía consumida", ATTR_ENERGY_ALWAYS, [ATTR_ENERGY_TODAY, ATTR_ENERGY_YESTERDAY], TYPE_SENSOR_ENERGY))
    entities.append(CustomSensor(edis, "Energía facturada", ATTR_ENERGY_CURRPERIOD, [ATTR_ENERGY_LASTPERIOD, ATTR_DAYS_CURRPERIOD, ATTR_DAYS_LASTPERIOD], TYPE_SENSOR_ENERGY))
    entities.append(CustomSensor(edis, "Potencia demandada", ATTR_POWER_DEMAND, [ATTR_POWER_LIMIT, ATTR_MAXPOWER_1YEAR, ATTR_LOAD_NOW], TYPE_SENSOR_POWER))
    add_entities(entities)

    # Start schedulers
    schedule_next_day()
    schedule_next_6am()
    schedule_in_5s()

class CustomSensor(Entity):
    ENERGY=1
    POWER=2
    def __init__(self, edis, name, state_key, attribute_keys, sensortype):
        self._attributes = {}
        self._key = state_key
        self._friendlyname = name
        self._edis = edis
        self._type = sensortype

        try:
            self._state = self.hass.data[DOMAIN][self._key]
        except: 
            self._state = None
        for attribute in attribute_keys:
            try:
                self._attributes[attribute] = self.hass.data[DOMAIN][attribute]
            except:
                self._attributes[attribute] = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._friendlyname

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        if self._type == TYPE_SENSOR_ENERGY:
            return "mdi:counter" 
        elif self._type == TYPE_SENSOR_POWER:
            return "mdi:flash"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self._type == TYPE_SENSOR_ENERGY:
            return ENERGY_KILO_WATT_HOUR
        elif self._type == TYPE_SENSOR_POWER:
            return POWER_KILO_WATT

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    def handle_next_day (self):
        pass

    def handle_next_6am (self):
        pass

    def handle_in_5s (self):
        self.update()

    def update(self):
        try:
            self._state = self.hass.data[DOMAIN][self._key]
        except: 
            self._state = None
        for attribute in self._attributes:
            try:
                self._attributes[attribute] = self.hass.data[DOMAIN][attribute]
            except:
                self._attributes[attribute] = None

def fetch_data (edis, attributes, cups_index=0):
    
    QUERY_ENERGY_YESTERDAY = [ATTR_ENERGY_YESTERDAY]
    QUERY_ENERGY_CURRPERIOD = [ATTR_ENERGY_CURRPERIOD, ATTR_DAYS_CURRPERIOD]
    QUERY_ENERGY_LASTPERIOD = [ATTR_ENERGY_LASTPERIOD, ATTR_DAYS_LASTPERIOD]
    QUERY_POWER_HISTOGRAM = [ATTR_MAXPOWER_1YEAR]
    QUERY_POWER_DEMAND = [ATTR_POWER_DEMAND, ATTR_ICPSTATUS, ATTR_LOAD_NOW, ATTR_POWER_LIMIT]

    queries = []
    cups = None
    cont = None
    cups_name = None

    fetched_attributes = {}

    # fetch always CUPS/CONT values
    r = edis.get_list_cups()
    cups = r[cups_index]['CUPS_Id']
    cont = r[cups_index]['Id']
    lastcycle = None
    
    fetched_attributes[ATTR_CUPS_NAME] = r[cups_index]['CUPS']
    for attr in attributes:
        fetched_attributes[attr] = None

    # group wanted attributes to minimize queries
    for attr in attributes:
        if fetched_attributes[attr] == None:
            try:
                if attr in QUERY_ENERGY_YESTERDAY:
                    # ask for yesterday curve
                    date_yesterday = (datetime.today()-timedelta(days=1)).strftime("%Y-%m-%d")
                    yesterday_curve = edis.get_day_curve(cont,date_yesterday)
                    fetched_attributes[ATTR_ENERGY_YESTERDAY] = str(yesterday_curve['data']['totalValue']).replace(".","").replace(",",".")
                elif attr in QUERY_ENERGY_CURRPERIOD:
                    # ask for current cycle curve
                    if lastcycle == None:
                        cycles =  edis.get_list_cycles(cont)
                        lastcycle = cycles['lstCycles'][0]
                    date_currcycle = (datetime.strptime(lastcycle['label'].split(' - ')[1], '%d/%m/%Y') + timedelta(days=1)).strftime("%Y-%m-%d")
                    date_yesterday = (datetime.today()-timedelta(days=1)).strftime("%Y-%m-%d")
                    currcycle_curve = edis.get_custom_curve(cont,date_currcycle, date_yesterday)
                    fetched_attributes[ATTR_ENERGY_CURRPERIOD] = str(currcycle_curve['data']['totalValue']).replace(".","").replace(",",".")
                    fetched_attributes[ATTR_DAYS_CURRPERIOD] = (datetime.today() - (datetime.strptime(lastcycle['label'].split(' - ')[1], '%d/%m/%Y') + timedelta(days=1))).days
                elif attr in QUERY_ENERGY_LASTPERIOD:
                    # ask for last cycle curve
                    if lastcycle == None:
                        cycles =  edis.get_list_cycles(cont)
                        lastcycle = cycles['lstCycles'][0]
                    lastcycle_curve = edis.get_cycle_curve(cont, lastcycle['label'], lastcycle['value'])
                    fetched_attributes[ATTR_ENERGY_LASTPERIOD] = str(lastcycle_curve['totalValue']).replace(".","").replace(",",".")
                    fetched_attributes[ATTR_DAYS_LASTPERIOD] = (datetime.strptime(lastcycle['label'].split(' - ')[1], '%d/%m/%Y') - datetime.strptime(lastcycle['label'].split(' - ')[0], '%d/%m/%Y')).days
                elif attr in QUERY_POWER_HISTOGRAM:
                    # ask for 1 year power demand histogram
                    date_currmonth = datetime.today().strftime("%m/%Y")
                    date_ayearago = (datetime.today()-timedelta(days=365)).strftime("%m/%Y")
                    maximeter_histogram = edis.get_year_maximeter (cups, date_ayearago, date_currmonth)
                    fetched_attributes[ATTR_MAXPOWER_1YEAR] = str(maximeter_histogram['data']['maxValue']).replace(".","").replace(",",".")
                elif attr in QUERY_POWER_DEMAND:
                    # same here
                    meter = edis.get_meter(cups)
                    fetched_attributes[ATTR_POWER_DEMAND] = meter['data']['potenciaActual']
                    fetched_attributes[ATTR_ICPSTATUS] = meter['data']['estadoICP']
                    fetched_attributes[ATTR_ENERGY_ALWAYS] = str(meter['data']['totalizador']).replace(".","").replace(",",".")
                    fetched_attributes[ATTR_LOAD_NOW] = str(meter['data']['percent']).replace(".","").replace(",",".")
                    fetched_attributes[ATTR_POWER_LIMIT] = str(meter['data']['potenciaContratada'])
            except:
                pass
    return fetched_attributes

class EDSSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, edis):
        """Initialize the sensor."""
        self._state = None
        self._attributes = {}

        self._is_first_boot = True
        self._do_run_daily_tasks = False
        self._do_run_6am_tasks = False

        self._total_energy = 0
        self._total_energy_yesterday = 0

        # Initializing attributes to establish the order
        self._attributes[ATTR_CUPS_NAME] = None
        self._attributes[ATTR_POWER_DEMAND] = None
        self._attributes[ATTR_ENERGY_TODAY] = None
        self._attributes[ATTR_ENERGY_YESTERDAY] = None
        self._attributes[ATTR_ENERGY_LASTPERIOD] = None
        self._attributes[ATTR_ENERGY_CURRPERIOD] = None
        self._attributes[ATTR_ENERGY_ALWAYS] = None
        self._attributes[ATTR_DAYS_LASTPERIOD] = None
        self._attributes[ATTR_DAYS_CURRPERIOD] = None
        self._attributes[ATTR_MAXPOWER_1YEAR] = None
        self._attributes[ATTR_ICPSTATUS] = None
        self._attributes[ATTR_LOAD_NOW] = None
        self._attributes[ATTR_POWER_LIMIT] = None
        
        self._edis = edis

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

    def handle_in_5s (self):
        pass

    def reconnect_ICP (self):
        ### Untested... impossible under the current setup
        _LOGGER.debug("ICP reconnect service called")
        # Get CUPS list, at the moment we just explore the first element [0] in the table (valid if you only have a single contract)
        r = self._edis.get_list_cups()
        cups = r[0]['CUPS_Id']
        # Get response
        response = self._edis.reconnect_ICP(cups)
        _LOGGER.debug(response)

    def update(self):
        """Fetch new state data for the sensor."""
        # Get CUPS list, at the moment we just explore the first element [0] in the table (valid if you only have a single contract)
        r = self._edis.get_list_cups()
        cups = r[0]['CUPS_Id']
        cont = r[0]['Id']

        self._attributes[ATTR_CUPS_NAME] = r[0]['CUPS'] # this is the name

        # First retrieve historical data if first boot or starting a new day (this is fast)
        if self._is_first_boot or self._do_run_6am_tasks:
            _LOGGER.debug("fetching historical data")
            # fetch last cycle from list
            #cycles = self._edis.get_list_cycles(cont)
            #lastcycle = cycles['lstCycles'][0]

            attributes = fetch_data (self._edis, 
            [ATTR_ENERGY_YESTERDAY, ATTR_ENERGY_CURRPERIOD, ATTR_DAYS_CURRPERIOD, 
            ATTR_ENERGY_LASTPERIOD, ATTR_DAYS_LASTPERIOD, ATTR_MAXPOWER_1YEAR])

            for attr in attributes:
                self._attributes[attr] = attributes[attr]

        # Then retrieve real-time data (this is slow)
        _LOGGER.debug("fetching real-time data")
        attributes = fetch_data (self._edis, 
            [ATTR_ICPSTATUS, ATTR_ENERGY_ALWAYS, ATTR_LOAD_NOW, 
            ATTR_POWER_LIMIT]
            )

        for attr in attributes:
            self._attributes[attr] = attributes[attr]

        self._total_energy = float(self._attributes[ATTR_ENERGY_ALWAYS])
        # if new day, store consumption
        _LOGGER.debug("doing internal calculus")
        if self._do_run_daily_tasks or self._is_first_boot:
            # if a new day has started, store last total consumption as the base for the daily calculus
            self._total_energy_yesterday = self._total_energy
        # do the maths and update it during the day
        self._attributes[ATTR_ENERGY_TODAY] = str((self._total_energy) - (self._total_energy_yesterday))

        # at this point, we should have update all attributes
        _LOGGER.debug("Attributes updated for EDSSensor: " + str(self._attributes))

        # Update the state of the Sensor
        self._state = self._attributes[ATTR_POWER_DEMAND]
        _LOGGER.debug("State updated for EDSSensor: " + str(self._state))

        self.hass.data[DOMAIN] = self._attributes

        # set flags down
        self._do_run_daily_tasks = False
        self._is_first_boot = False
        self._do_run_6am_tasks = False
        
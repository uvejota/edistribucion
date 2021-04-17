import logging
from homeassistant.const import POWER_KILO_WATT
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import config_validation as cv, entity_platform
from .api.EdistribucionAPI import Edistribucion
from datetime import datetime, timedelta

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=10)
FRIENDLY_NAME = 'EDS Consumo eléctrico'

SERVICE_RECONNECT_ICP = "reconnect_icp"

async def async_setup_platform(hass, config, add_entities, discovery_info=None):

    # Register services
    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
            SERVICE_RECONNECT_ICP,
            {},
            EDSSensor.reconnect_ICP.__name__,
        )

    """Set up the sensor platform."""
    add_entities([EDSSensor(config['username'],config['password'])])

class EDSSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self,usr,pw):
        """Initialize the sensor."""
        self._state = None
        self._attributes = {}
        self._usr=usr
        self._pw=pw

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

    def reconnect_ICP (self):
        ### to do
        _LOGGER.debug("ICP reconnect service called")

    def update(self):
        """Fetch new state data for the sensor."""
        attributes = {}

        # Login into the edistribucion platform. 
        # TODO: try to save sessions by calling Edistribucion(self._usr,self._pw,True), for some reason this has been disabled until now
        edis = Edistribucion(self._usr,self._pw,True)
        edis.login()
        # Get CUPS list, at the moment we just explore the first element [0] in the table (valid if you only have a single contract)
        r = edis.get_list_cups()
        cups = r[0]['CUPS_Id']
        cont = r[0]['Id']

        attributes['CUPS'] = r[0]['CUPS'] # this is the name
        #attributes['Cont'] = cont # not really needed

        # First retrieve historical data (this is fast)
        # TODO: this should be done just once a day
        yesterday = (datetime.today()-timedelta(days=1)).strftime("%Y-%m-%d")
        sevendaysago = (datetime.today()-timedelta(days=8)).strftime("%Y-%m-%d")
        onemonthago = (datetime.today()-timedelta(days=30)).strftime("%Y-%m-%d")

        yesterday_curve=edis.get_day_curve(cont,yesterday)
        attributes['Consumo total (ayer)'] = str(yesterday_curve['data']['totalValue']) + ' kWh'
        lastweek_curve=edis.get_week_curve(cont,sevendaysago)
        attributes['Consumo total (7 días)'] = str(lastweek_curve['data']['totalValue']) + ' kWh'
        lastmonth_curve=edis.get_month_curve(cont,onemonthago)
        attributes['Consumo total (30 días)'] = str(lastmonth_curve['data']['totalValue']) + ' kWh'

        # Then retrieve instant data (this is slow)
        meter = edis.get_meter(cups)
        _LOGGER.debug(meter)
        _LOGGER.debug(meter['data']['potenciaActual'])
        
        attributes['Estado ICP'] = meter['data']['estadoICP']
        attributes['Consumo total'] = str(meter['data']['totalizador']) + ' kWh'
        attributes['Carga actual'] = meter['data']['percent']
        attributes['Potencia contratada'] = str(meter['data']['potenciaContratada']) + ' kW'

        self._state = meter['data']['potenciaActual']
        self._attributes = attributes
        
import logging
from homeassistant.const import POWER_WATT
from homeassistant.helpers.entity import Entity
from backend.Edistribucion import Edistribucion

_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_entities, discovery_info=None):

    """Set up the sensor platform."""
    add_entities([EDSSensor(config['user'],config['password'])])

class EDSSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self,usr,pw):
        """Initialize the sensor."""
        self._state = None
        self._usr=usr
        self._pw=pw

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'EDS Power Temperature'

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return POWER_WATT

    def update(self):
        """Fetch new state data for the sensor."""
        
        edis = Edistribucion(self._usr,self._pw)
        edis.login()
        r = edis.get_cups()
        cups = r['data']['lstCups'][0]['Id']
        meter = edis.get_meter(cups)
        _LOGGER.debug(meter)
        _LOGGER.debug(meter['data']['potenciaActual'])
        self._state = meter['data']['potenciaActual']

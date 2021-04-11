import logging
from homeassistant.helpers import config_validation as cv, discovery
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.typing import HomeAssistantType
from .api.EdistribucionAPI import Edistribucion

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'edistribucion'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


async def async_setup(hass: HomeAssistantType, hass_config: dict):
    config = hass_config[DOMAIN]
    has_credentials = CONF_USERNAME in config and CONF_PASSWORD in config
    if(not has_credentials):
        _LOGGER.debug("No credentials provided")

    def reconnect_ICP(call):
        """Handle the service call."""
        edis = Edistribucion(self._usr,self._pw)
        edis.login()
        r = edis.get_cups()
        cups = r['data']['lstCups'][0]['Id']
        edis.reconnect_ICP(cups)

    def measure_now(call):
        """Handle the service call."""
        edis = Edistribucion(self._usr,self._pw)
        edis.login()
        r = edis.get_cups()
        cups = r['data']['lstCups'][0]['Id']
        meter = edis.get_meter(cups)
        _LOGGER.debug(meter)
        _LOGGER.debug(meter['data']['potenciaActual'])
        attributes = {}
        attributes['CUPS'] = r['data']['lstCups'][0]['Id']
        attributes['Estado ICP'] = meter['data']['estadoICP']
        attributes['Consumo Total'] = str(meter['data']['totalizador']) + ' kWh'
        attributes['Carga actual'] = meter['data']['percent']
        attributes['Potencia Contratada'] = str(meter['data']['potenciaContratada']) + ' kW'
        self._state = meter['data']['potenciaActual']
        self._attributes = attributes

    hass.services.register(DOMAIN, "Reconectar ICP", reconnect_ICP)
    hass.services.register(DOMAIN, "Medir ahora", measure_now)

    return True


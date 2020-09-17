import logging
from homeassistant.helpers import config_validation as cv, discovery
import voluptuous as vol
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'edistribucion'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string, 
    }, extra=vol.ALLOW_EXTRA),
}, extra=vol.ALLOW_EXTRA)

async def async_setup(hass: HomeAssistantType, hass_config: dict):
    config = hass_config[DOMAIN]
    has_credentials = CONF_USERNAME in config and CONF_PASSWORD in config
    if(not has_credentials):
        _LOGGER.debug("No credentials provided")

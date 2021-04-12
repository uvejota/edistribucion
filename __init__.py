import logging
from homeassistant.helpers import config_validation as cv, discovery
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.typing import HomeAssistantType

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
    return True


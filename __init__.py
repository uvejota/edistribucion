"""The example sensor integration."""
from homeassistant.helpers import config_validation as cv, discovery



CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string, 
    }, extra=vol.ALLOW_EXTRA),
}, extra=vol.ALLOW_EXTRA)
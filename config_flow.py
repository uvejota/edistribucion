from homeassistant import config_entries
from .const import DOMAIN
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from .api.EdistribucionAPI import *
import voluptuous as vol

class EDSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """EDS config flow."""

    def __init__(self):
        """Initialize flow."""
        self._password = None
        self._username = None
        self._is_import = False

    def login (self):
        edis = Edistribucion(self._username,self._password)
        try:
            edis.login()
            return True
        except EdisError:
            return False

    async def async_step_user(self, user_input=None):
        # Specify items in the order they are to be displayed in the UI

        if user_input is not None:
            self._password = user_input[CONF_PASSWORD]
            self._username = user_input[CONF_USERNAME]

            result_ok = await self.hass.async_add_executor_job(self.login)
            if result_ok:
                # next step
            else:
                # repeat

        data_schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        }

        if self.show_advanced_options:
            data_schema["allow_groups"]: bool

        return self.async_show_form(step_id="init", data_schema=vol.Schema(data_schema))

    
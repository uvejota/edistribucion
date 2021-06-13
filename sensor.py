import logging
from homeassistant.const import POWER_KILO_WATT, ENERGY_KILO_WATT_HOUR 
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import config_validation as cv, entity_platform
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.event import async_track_point_in_time
from .api.EdsHelper import EdsHelper
from datetime import datetime, timedelta

# HA variables
_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=10)
FRIENDLY_NAME = 'edistribucion'
DOMAIN = 'edistribucion'

# Custom configuration entries
CONF_CUPS = 'cups'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_CUPS): cv.string
    }
)

async def async_setup_platform(hass, config, add_entities, discovery_info=None):

    # Define entities
    entities = []

    # Declare eds helper
    helper = EdsHelper(config[CONF_USERNAME], config[CONF_PASSWORD], short_interval=SCAN_INTERVAL-timedelta(minutes=1), long_interval=6*SCAN_INTERVAL-timedelta(minutes=1))
    cups = None
    if config[CONF_CUPS]:
        cups = config[CONF_CUPS]
    entities.append(EdsSensor(helper, cups=cups))
    add_entities(entities)

class EdsSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, eds, cups=None):
        """Initialize the sensor."""
        self._state = None
        self._attributes = {}
        self.__cups = cups
        self.__helper = eds

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

    def update(self):
        """Fetch new state data for the sensor."""

        if self.__cups is not None:
            self.__helper.set_cups(self.__cups)

        self.__helper.update()
        self._attributes["CUPS"] = self.__helper.Supply.get('CUPS', None)
        self._attributes["Contador (kWh)"] = self.__helper.Meter.get('EnergyMeter', None)
        self._attributes["Estado ICP"] = self.__helper.Meter.get('ICP', None)
        self._attributes["Carga actual (%)"] = self.__helper.Meter.get('Load', None)
        self._attributes["Potencia contratada (kW)"] = self.__helper.Supply.get('PowerLimit', None)
        self._attributes["Potencia demandada (kW)"] = self.__helper.Meter.get('Power', None)
        self._attributes["Hoy (kWh)"] = f"{self.__helper.Today.get('Energy', None)} (P1: {self.__helper.Today.get('P1', None)}, P2: {self.__helper.Today.get('P2', None)}, P3: {self.__helper.Today.get('P3', None)})"
        self._attributes["Ayer (kWh)"] = f"{self.__helper.Yesterday.get('Energy', None)} (P1: {self.__helper.Yesterday.get('P1', None)}, P2: {self.__helper.Yesterday.get('P2', None)}, P3: {self.__helper.Yesterday.get('P3', None)})"
        self._attributes["Ciclo anterior (kWh)"] = f"{self.__helper.Cycles[1].get('EnergySum', None) if len(self.__helper.Cycles) > 1 else None} en {self.__helper.Cycles[1].get('DateDelta', None) if len(self.__helper.Cycles) > 1 else None} días ({self.__helper.Cycles[1].get('EnergyDaily', None) if len(self.__helper.Cycles) > 1 else None} kWh/día)"
        self._attributes["Ciclo actual (kWh)"] = f"{self.__helper.Cycles[0].get('EnergySum', None) if len(self.__helper.Cycles) > 1 else None} en {self.__helper.Cycles[0].get('DateDelta', None) if len(self.__helper.Cycles) > 1 else None} días ({self.__helper.Cycles[0].get('EnergyDaily', None) if len(self.__helper.Cycles) > 1 else None} kWh/día)"
        self._attributes["Potencia máxima (kW)"] = f"{self.__helper.Maximeter.get('Max', '-')} el {self.__helper.Maximeter.get('DateMax', datetime(1990, 1, 1)).strftime('%d/%m/%Y')}"
        self._attributes["Potencia media (kW)"] = self.__helper.Maximeter.get('Average', None)
        self._attributes["Potencia percentil (99 | 95 | 90) (kW)"] = f"{self.__helper.Maximeter.get('Percentile99', None)} | {self.__helper.Maximeter.get('Percentile95', None)} | {self.__helper.Maximeter.get('Percentile90', None)} "

        self._state = self.__helper.Meter.get('Power', None)

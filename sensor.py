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
SCAN_INTERVAL = timedelta(seconds=30)
FRIENDLY_NAME = 'edistribucion'
DOMAIN = 'edistribucion'

# Custom configuration entries
CONF_CUPS = 'cups'
CONF_SHORT_INTERVAL = 'short_interval'
CONF_LONG_INTERVAL = 'long_interval'
CONF_EXPLODE_SENSORS = 'explode_sensors'

SENSOR_TYPES = {
    "cups": ("CUPS", None),
    "cont": ("Contador", ENERGY_KILO_WATT_HOUR),
    "icp_status": ("ICP", None),
    "power_load": ("Carga actual", "%"),
    "power_limit": ("Límite", POWER_KILO_WATT),
    "power": ("Potencia", POWER_KILO_WATT),
    "energy_today": ("Energía hoy", ENERGY_KILO_WATT_HOUR),
    "energy_yesterday": ("Energía ayer", ENERGY_KILO_WATT_HOUR),
    "energy_yesterday_detail": ("Detalle ayer", None),
    "cycle_current": ("Ciclo actual", ENERGY_KILO_WATT_HOUR),
    "cycle_last": ("Ciclo anterior", ENERGY_KILO_WATT_HOUR),
    "power_peak": ("P. Pico", POWER_KILO_WATT),
    "power_peak_mean": ("P. Pico (media)", POWER_KILO_WATT),
    "power_peak_tile90": ("P. Pico (perc. 90)", POWER_KILO_WATT)
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_CUPS): cv.string,
        vol.Optional(CONF_SHORT_INTERVAL): cv.positive_int,
        vol.Optional(CONF_LONG_INTERVAL): cv.positive_int,
        vol.Optional(CONF_EXPLODE_SENSORS, default=[]): vol.All(
            cv.ensure_list, [vol.In([x for x in SENSOR_TYPES if SENSOR_TYPES[x][1] is not None])]
        ),
    }
)

async def async_setup_platform(hass, config, add_entities, discovery_info=None):

    # Define entities
    entities = []

    # Declare eds helper
    helper = EdsHelper(config[CONF_USERNAME], config[CONF_PASSWORD])
    cups = None
    if CONF_CUPS in config:
        cups = config[CONF_CUPS]
    entities.append(EdsSensor(helper, cups=cups))
    for sensor in config[CONF_EXPLODE_SENSORS]:
        entities.append(EdsSensor(helper, name=sensor, state=sensor, attrs=[], master=False))
    add_entities(entities)

class EdsSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, eds, name=FRIENDLY_NAME, state='power', attrs=[x for x in SENSOR_TYPES], cups=None, master=True):
        """Initialize the sensor."""
        self._state = None
        self._attributes = {}
        self.__cups = cups
        self.__helper = eds
        self.__statelabel = state
        self.__friendlyname = name
        self.__master = master
        self.__attrs = attrs
        self.__unit = SENSOR_TYPES[state][1]

        for attr in attrs:
            self._attributes[SENSOR_TYPES[attr][0]] = None
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.__friendlyname

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
        return self.__unit

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    def update(self):
        """Fetch new state data for the sensor."""
        if self.__master:
            if self.__cups is not None:
                self.__helper.set_cups(self.__cups)

            self.__helper.update()

        for attr in self.__attrs:
            if 'cups' == attr:
                self._attributes[SENSOR_TYPES[attr][0]] = self.__helper.Supply.get('CUPS', '-')
            elif 'cont' == attr:
                self._attributes[SENSOR_TYPES[attr][0]] = f"{self.__helper.Meter.get('EnergyMeter', '-')} kWh"
            elif 'icp_status' == attr:
                self._attributes[SENSOR_TYPES[attr][0]] = self.__helper.Meter.get('ICP', 'Desconocido')
            elif 'power_load' == attr:
                self._attributes[SENSOR_TYPES[attr][0]] = f"{self.__helper.Meter.get('Load', '-')} %"
            elif 'power_limit' == attr:
                self._attributes[SENSOR_TYPES[attr][0]] = f"{self.__helper.Supply.get('PowerLimit', '-')} kW"
            elif 'power' == attr:
                self._attributes[SENSOR_TYPES[attr][0]] = f"{self.__helper.Meter.get('Power', '-')} kW"
            elif 'energy_today' == attr:
                self._attributes[SENSOR_TYPES[attr][0]] = f"{self.__helper.Meter.get('EnergyToday', '-')} kWh"
            elif 'energy_yesterday' == attr:
                self._attributes[SENSOR_TYPES[attr][0]] = f"{self.__helper.Yesterday.get('Energy', '-')} kWh"
            elif 'energy_yesterday_detail' == attr:
                self._attributes[SENSOR_TYPES[attr][0]] = f"Pico: {self.__helper.Yesterday.get('P1', '-')}, Llano: {self.__helper.Yesterday.get('P2', '-')}, Valle: {self.__helper.Yesterday.get('P3', '-')}"
            elif 'cycle_current' == attr:
                self._attributes[SENSOR_TYPES[attr][0]] = f"{self.__helper.Cycles[0].get('EnergySum', '-') if len(self.__helper.Cycles) > 1 else '-'} kWh en {self.__helper.Cycles[0].get('DateDelta', '-') if len(self.__helper.Cycles) > 1 else '-'} días ({self.__helper.Cycles[0].get('EnergyDaily', '-') if len(self.__helper.Cycles) > 1 else '-'} kWh/día)"
            elif 'cycle_last' == attr:
                self._attributes[SENSOR_TYPES[attr][0]] = f"{self.__helper.Cycles[1].get('EnergySum', '-') if len(self.__helper.Cycles) > 1 else '-'} kWh en {self.__helper.Cycles[1].get('DateDelta', '-') if len(self.__helper.Cycles) > 1 else '-'} días ({self.__helper.Cycles[1].get('EnergyDaily', '-') if len(self.__helper.Cycles) > 1 else '-'} kWh/día)"
            elif 'power_peak' == attr:
                self._attributes[SENSOR_TYPES[attr][0]] = f"{self.__helper.Maximeter.get('Max', '-')} kW el {self.__helper.Maximeter.get('DateMax', datetime(1990, 1, 1)).strftime('%d/%m/%Y')}"
            elif 'power_peak_mean' == attr:
                self._attributes[SENSOR_TYPES[attr][0]] = f"{self.__helper.Maximeter.get('Average', '-')} kW"
            elif 'power_peak_tile90' == attr:
                self._attributes[SENSOR_TYPES[attr][0]] = f"{self.__helper.Maximeter.get('Percentile90', '-')} kW"
            else:
                _LOGGER.warning ("unrecognised attribute with label" + str(attr))

        if 'cups' == self.__statelabel:
            self._state = self.__helper.Supply.get('CUPS', None)
        elif 'cont' == self.__statelabel:
            self._state = self.__helper.Meter.get('EnergyMeter', None)
        elif 'icp_status' == self.__statelabel:
            self._state = self.__helper.Meter.get('ICP', 'Desconocido')
        elif 'power_load' == self.__statelabel:
            self._state = self.__helper.Meter.get('Load', None)
        elif 'power_limit' == self.__statelabel:
            self._state = self.__helper.Supply.get('PowerLimit', None)
        elif 'power' == self.__statelabel:
            self._state = self.__helper.Meter.get('Power', None)
        elif 'energy_today' == self.__statelabel:
            self._state = self.__helper.Meter.get('EnergyToday', None)
        elif 'energy_yesterday' == self.__statelabel:
            self._state = self.__helper.Yesterday.get('Energy', None)
        elif 'cycle_current' == self.__statelabel:
            self._state = self.__helper.Cycles[0].get('EnergySum', None) if len(self.__helper.Cycles) > 1 else None
        elif 'cycle_last' == self.__statelabel:
            self._state = self.__helper.Cycles[1].get('EnergySum', None) if len(self.__helper.Cycles) > 1 else None
        elif 'power_peak' == self.__statelabel:
            self._state = self.__helper.Maximeter.get('Max', '-')
        elif 'power_peak_mean' == self.__statelabel:
            self._state = self.__helper.Maximeter.get('Average', None)
        elif 'power_peak_tile90' == self.__statelabel:
            self._state = self.__helper.Maximeter.get('Percentile90', None)
        else:
            _LOGGER.warning ("unrecognised state with label" + str(attr))

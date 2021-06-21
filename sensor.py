import logging
from homeassistant.const import POWER_KILO_WATT, ENERGY_KILO_WATT_HOUR, TIME_DAYS, PERCENTAGE, CURRENCY_EURO
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
    "power_load": ("Carga actual", PERCENTAGE),
    "power_limit": ("Límite", POWER_KILO_WATT),
    "power": ("Potencia", POWER_KILO_WATT),
    "energy_today": ("Energía hoy", ENERGY_KILO_WATT_HOUR),
    "energy_yesterday": ("Energía ayer", ENERGY_KILO_WATT_HOUR),
    "energy_yesterday_p1": ("E. ayer (P1)", ENERGY_KILO_WATT_HOUR),
    "energy_yesterday_p2": ("E. ayer (P2)", ENERGY_KILO_WATT_HOUR),
    "energy_yesterday_p3": ("E. ayer (P3)", ENERGY_KILO_WATT_HOUR),
    "cycle_current": ("Ciclo actual", ENERGY_KILO_WATT_HOUR),
    "cycle_current_daily": ("C. actual (diario)", ENERGY_KILO_WATT_HOUR),
    "cycle_current_days": ("C. actual (días)", TIME_DAYS),
    "cycle_current_p1": ("C. actual (P1)", ENERGY_KILO_WATT_HOUR),
    "cycle_current_p2": ("C. actual (P2)", ENERGY_KILO_WATT_HOUR),
    "cycle_current_p3": ("C. actual (P3)", ENERGY_KILO_WATT_HOUR),
    "cycle_current_pvpc": ("C. actual (PVPC)", CURRENCY_EURO),
    "cycle_last": ("Ciclo anterior", ENERGY_KILO_WATT_HOUR),
    "cycle_last_daily": ("C. anterior (diario)", ENERGY_KILO_WATT_HOUR),
    "cycle_last_days": ("C. anterior (días)", TIME_DAYS),
    "cycle_last_p1": ("C. anterior (P1)", ENERGY_KILO_WATT_HOUR),
    "cycle_last_p2": ("C. anterior (P2)", ENERGY_KILO_WATT_HOUR),
    "cycle_last_p3": ("C. anterior (P3)", ENERGY_KILO_WATT_HOUR),
    "cycle_last_pvpc": ("C. anterior (PVPC)", CURRENCY_EURO),
    "power_peak": ("Potencia pico", POWER_KILO_WATT),
    "power_peak_date": ("P. pico (fecha)", None),
    "power_peak_mean": ("P. pico (media)", POWER_KILO_WATT),
    "power_peak_tile90": ("P. pico (perc. 90)", POWER_KILO_WATT)
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
    helper = EdsHelper(config[CONF_USERNAME], config[CONF_PASSWORD], short_interval=(timedelta(minutes=config[CONF_SHORT_INTERVAL]) if CONF_SHORT_INTERVAL in config else None), long_interval=(timedelta(minutes=config[CONF_LONG_INTERVAL]) if CONF_LONG_INTERVAL in config else None))
    cups = None
    if CONF_CUPS in config:
        cups = config[CONF_CUPS]
    entities.append(EdsSensor(helper, cups=cups))
    for sensor in config[CONF_EXPLODE_SENSORS]:
        if SENSOR_TYPES[sensor][1] is not None:
            entities.append(EdsSensor(helper, name=sensor, state=sensor, attrs=[], master=False))
    add_entities(entities)

class EdsSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, eds, name=FRIENDLY_NAME, state='power', attrs=[x for x in SENSOR_TYPES], cups=None, master=True):
        """Initialize the sensor."""
        self._state = None
        self._attributes = {}
        self._cups = cups
        self._helper = eds
        self._statelabel = state
        self._friendlyname = name
        self._master = master
        self._attrs = attrs
        self._unit = SENSOR_TYPES[state][1]

        for attr in attrs:
            self._attributes[SENSOR_TYPES[attr][0]] = None
        self._state = None

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
        return "mdi:flash" 

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    async def async_update(self):
        """Fetch new state data for the sensor."""
        if self._master:
            await self._helper.async_update(self._cups)

        # update attrs
        for attr in self._attrs:
            self._attributes[SENSOR_TYPES[attr][0]] = f"{self._get_attr_value(attr)} {SENSOR_TYPES[attr][1] if SENSOR_TYPES[attr][1] is not None else ''}"
            
        # update state
        self._state = self._get_attr_value(self._statelabel)

    def _get_attr_value (self, attr):
        if 'cups' == attr:
            return self._helper.Supply.get('CUPS', None)
        elif 'cont' == attr:
            return self._helper.Meter.get('EnergyMeter', None)
        elif 'icp_status' == attr:
            return self._helper.Meter.get('ICP', None)
        elif 'power_load' == attr:
            return self._helper.Meter.get('Load', None)
        elif 'power_limit' == attr:
            return self._helper.Supply.get('PowerLimit', None)
        elif 'power' == attr:
            return self._helper.Meter.get('Power', None)
        elif 'energy_today' == attr:
            return self._helper.Meter.get('EnergyToday', None)
        elif 'energy_yesterday' == attr:
            return self._helper.Yesterday.get('Energy', None)
        elif 'energy_yesterday_p1' == attr:
            return self._helper.Yesterday.get('Energy_P1', None)
        elif 'energy_yesterday_p2' == attr:
            return self._helper.Yesterday.get('Energy_P2', None)
        elif 'energy_yesterday_p3' == attr:
            return self._helper.Yesterday.get('Energy_P3', None)
        elif 'cycle_current' == attr:
            return self._helper.Cycles[0].get('Energy', None) if len(self._helper.Cycles) > 1 else None
        elif 'cycle_current_daily' == attr:
            return self._helper.Cycles[0].get('EnergyDaily', None) if len(self._helper.Cycles) > 1 else None
        elif 'cycle_current_days' == attr:
            return self._helper.Cycles[0].get('DateDelta', None) if len(self._helper.Cycles) > 1 else None
        elif 'cycle_current_p1' == attr:
            return self._helper.Cycles[0].get('Energy_P1', None) if len(self._helper.Cycles) > 1 else None
        elif 'cycle_current_p2' == attr:
            return self._helper.Cycles[0].get('Energy_P2', None) if len(self._helper.Cycles) > 1 else None
        elif 'cycle_current_p3' == attr:
            return self._helper.Cycles[0].get('Energy_P3', None) if len(self._helper.Cycles) > 1 else None
        elif 'cycle_current_pvpc' == attr:
            return self._helper.Cycles[0].get('Bill', None) if len(self._helper.Cycles) > 1 else None
        elif 'cycle_last' == attr:
            return self._helper.Cycles[1].get('Energy', None) if len(self._helper.Cycles) > 1 else None
        elif 'cycle_last_daily' == attr:
            return self._helper.Cycles[1].get('EnergyDaily', None) if len(self._helper.Cycles) > 1 else None
        elif 'cycle_last_days' == attr:
            return self._helper.Cycles[1].get('DateDelta', None) if len(self._helper.Cycles) > 1 else None
        elif 'cycle_last_p1' == attr:
            return self._helper.Cycles[1].get('Energy_P1', None) if len(self._helper.Cycles) > 1 else None
        elif 'cycle_last_p2' == attr:
            return self._helper.Cycles[1].get('Energy_P2', None) if len(self._helper.Cycles) > 1 else None
        elif 'cycle_last_p3' == attr:
            return self._helper.Cycles[1].get('Energy_P3', None) if len(self._helper.Cycles) > 1 else None
        elif 'cycle_last_pvpc' == attr:
            return self._helper.Cycles[1].get('Bill', None) if len(self._helper.Cycles) > 1 else None
        elif 'power_peak' == attr:
            return self._helper.Maximeter.get('Max', None)
        elif 'power_peak_date' == attr:
            return self._helper.Maximeter.get('DateMax', None).strftime('%d/%m/%Y') if self._helper.Maximeter.get('DateMax', None) is not None else None
        elif 'power_peak_mean' == attr:
            return self._helper.Maximeter.get('Average', None)
        elif 'power_peak_tile90' == attr:
            return self._helper.Maximeter.get('Percentile90', None)
        else:
            _LOGGER.warning ("unrecognised attribute with label " + str(attr))
"""binary_sensor for hahm."""
import logging
from hahomematic.platforms import binary_sensor
from .const import DOMAIN, ATTR_INSTANCENAME

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the hahm binary_sensor platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.debug("Sensor async_setup_entry")

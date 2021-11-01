"""binary_sensor for hahm."""
import logging

from hahomematic.const import HA_PLATFORM_SELECT

from homeassistant.components.select import SelectEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .controlunit import ControlUnit
from .generic_entity import HaHomematicGenericEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the hahm select platform."""
    cu: ControlUnit = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_add_select(args):
        """Add select from HAHM."""
        entities = []

        for hm_entity in args[0]:
            entities.append(HaHomematicSelect(cu, hm_entity))

        if entities:
            async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            cu.async_signal_new_hm_entity(HA_PLATFORM_SELECT),
            async_add_select,
        )
    )

    async_add_select([cu.server.get_hm_entities_by_platform(HA_PLATFORM_SELECT)])


class HaHomematicSelect(HaHomematicGenericEntity, SelectEntity):
    """Representation of the HomematicIP select entity."""

    @property
    def options(self) -> list[str]:
        """Return the options."""
        return self._hm_entity.value_list

    @property
    def current_option(self) -> str:
        """Return the currently selected option."""
        return self._hm_entity.STATE

    def select_option(self, option: str) -> None:
        """Select an option."""
        self._hm_entity.STATE = option

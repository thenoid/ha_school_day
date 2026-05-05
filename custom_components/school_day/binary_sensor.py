"""Binary sensors for the School Day integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SchoolDayCoordinator
from .calendar import SchoolDayState
from .const import (
    ATTR_BOUNDARY_EVENT,
    ATTR_CONFIGURED_SCHOOL_YEAR,
    ATTR_MATCHING_EVENTS,
    DOMAIN,
)


@dataclass(frozen=True)
class SchoolDayBinarySensorDescription:
    """Describe a School Day binary sensor."""

    key: str
    name: str
    value_fn: Callable[[SchoolDayState], bool]


SENSORS: tuple[SchoolDayBinarySensorDescription, ...] = (
    SchoolDayBinarySensorDescription(
        key="school_day",
        name="School Day",
        value_fn=lambda state: state.school_day,
    ),
    SchoolDayBinarySensorDescription(
        key="no_school",
        name="No School",
        value_fn=lambda state: state.no_school,
    ),
    SchoolDayBinarySensorDescription(
        key="summer_vacation",
        name="Summer Vacation",
        value_fn=lambda state: state.summer_vacation,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up School Day binary sensors."""
    coordinator: SchoolDayCoordinator = entry.runtime_data
    async_add_entities(
        SchoolDayBinarySensor(coordinator, entry, description) for description in SENSORS
    )


class SchoolDayBinarySensor(CoordinatorEntity[SchoolDayCoordinator], BinarySensorEntity):
    """Binary sensor backed by school calendar state."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SchoolDayCoordinator,
        entry: ConfigEntry,
        description: SchoolDayBinarySensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_translation_key = description.key
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
        }

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, str | list[str] | None]:
        """Return useful calendar-debugging attributes."""
        state = self.coordinator.data
        return {
            ATTR_MATCHING_EVENTS: list(state.matching_events),
            ATTR_BOUNDARY_EVENT: state.boundary_event,
            ATTR_CONFIGURED_SCHOOL_YEAR: state.configured_school_year,
        }


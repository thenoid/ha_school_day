"""School Day integration."""

from __future__ import annotations

from datetime import date
import logging

from aiohttp import ClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .calendar import (
    SchoolDayState,
    SchoolYear,
    compute_school_day_state,
    parse_ics_calendar,
)
from .const import CONF_SCHOOL_YEARS, CONF_URLS, DEFAULT_SCAN_INTERVAL, DOMAIN


PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]
_LOGGER = logging.getLogger(__name__)


class SchoolDayCoordinator(DataUpdateCoordinator[SchoolDayState]):
    """Fetch ICS calendars and calculate the current school state."""

    def __init__(
        self, hass: HomeAssistant, urls: list[str], school_years: list[SchoolYear]
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.urls = urls
        self.school_years = school_years

    async def _async_update_data(self) -> SchoolDayState:
        session = async_get_clientsession(self.hass)
        all_events = []

        try:
            for url in self.urls:
                response = await session.get(url, timeout=30)
                response.raise_for_status()
                all_events.extend(parse_ics_calendar(await response.text()))
        except (ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Unable to fetch school calendar: {err}") from err

        return compute_school_day_state(
            all_events, dt_util.now().date(), self.school_years
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up School Day from a config entry."""
    school_years = [
        SchoolYear(
            start=date.fromisoformat(item["start"]),
            end=date.fromisoformat(item["end"]),
        )
        for item in entry.data.get(CONF_SCHOOL_YEARS, [])
    ]
    coordinator = SchoolDayCoordinator(hass, entry.data[CONF_URLS], school_years)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

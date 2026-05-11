"""School Day integration."""

from __future__ import annotations

from datetime import date, datetime
import logging

from aiohttp import ClientError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .calendar import (
    SchoolCalendarEvent,
    SchoolDayPatterns,
    SchoolDayState,
    SchoolYear,
    compute_school_day_state,
    parse_ics_calendar,
)
from .const import (
    CONF_FIRST_DAY_PATTERNS,
    CONF_LAST_DAY_PATTERNS,
    CONF_NO_SCHOOL_PATTERNS,
    CONF_SCHOOL_YEARS,
    CONF_URLS,
    DEFAULT_FIRST_DAY_PATTERNS,
    DEFAULT_LAST_DAY_PATTERNS,
    DEFAULT_NO_SCHOOL_PATTERNS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ATTR_DATE,
    ATTR_ENTRY_ID,
    ATTR_NO_SCHOOL,
    ATTR_SCHOOL_DAY,
    ATTR_SUMMER_VACATION,
    SERVICE_CHECK_DATE,
)


PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]
_LOGGER = logging.getLogger(__name__)
SERVICE_SCHEMA_CHECK_DATE = vol.Schema(
    {
        vol.Required(ATTR_DATE): vol.All(cv.string, vol.Match(r"^\d{2}-\d{2}-\d{4}$")),
        vol.Optional(ATTR_ENTRY_ID): cv.string,
    }
)


def _parse_mmddyyyy(value: str) -> date:
    """Parse MM-DD-YYYY dates."""
    return datetime.strptime(value, "%m-%d-%Y").date()


async def _async_handle_check_date(call: ServiceCall) -> ServiceResponse:
    """Check school-day state for a specific date string."""
    target_date_raw = call.data[ATTR_DATE]
    try:
        target_date = _parse_mmddyyyy(target_date_raw)
    except ValueError as err:
        raise ServiceValidationError(
            f"Invalid date '{target_date_raw}'. Use MM-DD-YYYY."
        ) from err

    coordinators: dict[str, SchoolDayCoordinator] = call.hass.data.get(DOMAIN, {})
    if not coordinators:
        raise ServiceValidationError("School Day is not configured.")

    entry_id = call.data.get(ATTR_ENTRY_ID)
    if entry_id:
        coordinator = coordinators.get(entry_id)
        if coordinator is None:
            raise ServiceValidationError(
                f"No School Day config entry found for entry_id '{entry_id}'."
            )
    elif len(coordinators) > 1:
        raise ServiceValidationError(
            "Multiple School Day entries found. Pass entry_id to select one."
        )
    else:
        coordinator = next(iter(coordinators.values()))

    await coordinator.async_request_refresh()
    state = compute_school_day_state(
        coordinator.events,
        target_date,
        coordinator.school_years,
        coordinator.patterns,
    )

    return {
        ATTR_DATE: target_date.isoformat(),
        ATTR_SCHOOL_DAY: state.school_day,
        ATTR_NO_SCHOOL: state.no_school,
        ATTR_SUMMER_VACATION: state.summer_vacation,
    }


class SchoolDayCoordinator(DataUpdateCoordinator[SchoolDayState]):
    """Fetch ICS calendars and calculate the current school state."""

    def __init__(
        self,
        hass: HomeAssistant,
        urls: list[str],
        school_years: list[SchoolYear],
        patterns: SchoolDayPatterns,
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
        self.patterns = patterns
        self.events: list[SchoolCalendarEvent] = []

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

        self.events = all_events
        return compute_school_day_state(
            all_events, dt_util.now().date(), self.school_years, self.patterns
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
    patterns = SchoolDayPatterns(
        no_school=tuple(
            entry.data.get(CONF_NO_SCHOOL_PATTERNS, DEFAULT_NO_SCHOOL_PATTERNS)
        ),
        last_day=tuple(
            entry.data.get(CONF_LAST_DAY_PATTERNS, DEFAULT_LAST_DAY_PATTERNS)
        ),
        first_day=tuple(
            entry.data.get(CONF_FIRST_DAY_PATTERNS, DEFAULT_FIRST_DAY_PATTERNS)
        ),
    )
    coordinator = SchoolDayCoordinator(
        hass, entry.data[CONF_URLS], school_years, patterns
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    if not hass.services.has_service(DOMAIN, SERVICE_CHECK_DATE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CHECK_DATE,
            _async_handle_check_date,
            schema=SERVICE_SCHEMA_CHECK_DATE,
            supports_response=SupportsResponse.ONLY,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        loaded_coordinators: dict[str, SchoolDayCoordinator] = hass.data.get(DOMAIN, {})
        loaded_coordinators.pop(entry.entry_id, None)
        if not loaded_coordinators:
            hass.data.pop(DOMAIN, None)
            hass.services.async_remove(DOMAIN, SERVICE_CHECK_DATE)
    return unload_ok

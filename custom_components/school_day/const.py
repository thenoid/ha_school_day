"""Constants for the School Day integration."""

from datetime import timedelta

DOMAIN = "school_day"

CONF_URLS = "urls"
CONF_SCHOOL_YEARS = "school_years"

DEFAULT_NAME = "School Day"
DEFAULT_SCAN_INTERVAL = timedelta(hours=6)

EVENT_NO_SCHOOL = "no school"
EVENT_LAST_DAY = "last day of school"
EVENT_FIRST_DAY = "first day of school"

ATTR_MATCHING_EVENTS = "matching_events"
ATTR_BOUNDARY_EVENT = "boundary_event"
ATTR_CONFIGURED_SCHOOL_YEAR = "configured_school_year"

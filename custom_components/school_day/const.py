"""Constants for the School Day integration."""

from datetime import timedelta

DOMAIN = "school_day"

CONF_URLS = "urls"
CONF_SCHOOL_YEARS = "school_years"
CONF_NAME = "name"
CONF_NO_SCHOOL_PATTERNS = "no_school_patterns"
CONF_LAST_DAY_PATTERNS = "last_day_patterns"
CONF_FIRST_DAY_PATTERNS = "first_day_patterns"

DEFAULT_NAME = "School Day"
DEFAULT_SCAN_INTERVAL = timedelta(hours=6)

EVENT_NO_SCHOOL = "no school"
EVENT_LAST_DAY = "last day of school"
EVENT_FIRST_DAY = "first day of school"
DEFAULT_NO_SCHOOL_PATTERNS = (EVENT_NO_SCHOOL,)
DEFAULT_LAST_DAY_PATTERNS = (EVENT_LAST_DAY,)
DEFAULT_FIRST_DAY_PATTERNS = (EVENT_FIRST_DAY,)

ATTR_MATCHING_EVENTS = "matching_events"
ATTR_BOUNDARY_EVENT = "boundary_event"
ATTR_CONFIGURED_SCHOOL_YEAR = "configured_school_year"

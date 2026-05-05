"""Config flow for the School Day integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .calendar import parse_event_patterns, parse_school_years
from .const import (
    CONF_FIRST_DAY_PATTERNS,
    CONF_LAST_DAY_PATTERNS,
    CONF_NAME,
    CONF_NO_SCHOOL_PATTERNS,
    CONF_SCHOOL_YEARS,
    CONF_URLS,
    DEFAULT_FIRST_DAY_PATTERNS,
    DEFAULT_LAST_DAY_PATTERNS,
    DEFAULT_NAME,
    DEFAULT_NO_SCHOOL_PATTERNS,
    DOMAIN,
)


class SchoolDayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a School Day config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            urls = [
                line.strip()
                for line in user_input[CONF_URLS].splitlines()
                if line.strip()
            ]
            try:
                school_years = parse_school_years(user_input.get(CONF_SCHOOL_YEARS, ""))
            except ValueError:
                errors[CONF_SCHOOL_YEARS] = "invalid_school_years"
            else:
                if not urls:
                    errors[CONF_URLS] = "no_urls"
                elif not name:
                    errors[CONF_NAME] = "no_name"
                else:
                    no_school_patterns = parse_event_patterns(
                        user_input.get(CONF_NO_SCHOOL_PATTERNS, ""),
                        DEFAULT_NO_SCHOOL_PATTERNS,
                    )
                    last_day_patterns = parse_event_patterns(
                        user_input.get(CONF_LAST_DAY_PATTERNS, ""),
                        DEFAULT_LAST_DAY_PATTERNS,
                    )
                    first_day_patterns = parse_event_patterns(
                        user_input.get(CONF_FIRST_DAY_PATTERNS, ""),
                        DEFAULT_FIRST_DAY_PATTERNS,
                    )
                    return self.async_create_entry(
                        title=name,
                        data={
                            CONF_NAME: name,
                            CONF_URLS: urls,
                            CONF_SCHOOL_YEARS: [
                                {
                                    "start": school_year.start.isoformat(),
                                    "end": school_year.end.isoformat(),
                                }
                                for school_year in school_years
                            ],
                            CONF_NO_SCHOOL_PATTERNS: list(no_school_patterns),
                            CONF_LAST_DAY_PATTERNS: list(last_day_patterns),
                            CONF_FIRST_DAY_PATTERNS: list(first_day_patterns),
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_URLS): str,
                    vol.Optional(CONF_SCHOOL_YEARS, default=""): str,
                    vol.Optional(
                        CONF_NO_SCHOOL_PATTERNS,
                        default="\n".join(DEFAULT_NO_SCHOOL_PATTERNS),
                        description={"advanced": True},
                    ): str,
                    vol.Optional(
                        CONF_LAST_DAY_PATTERNS,
                        default="\n".join(DEFAULT_LAST_DAY_PATTERNS),
                        description={"advanced": True},
                    ): str,
                    vol.Optional(
                        CONF_FIRST_DAY_PATTERNS,
                        default="\n".join(DEFAULT_FIRST_DAY_PATTERNS),
                        description={"advanced": True},
                    ): str,
                }
            ),
            errors=errors,
        )

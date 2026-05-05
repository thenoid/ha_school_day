"""Config flow for the School Day integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .calendar import parse_school_years
from .const import CONF_SCHOOL_YEARS, CONF_URLS, DEFAULT_NAME, DOMAIN


class SchoolDayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a School Day config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
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
                else:
                    return self.async_create_entry(
                        title=DEFAULT_NAME,
                        data={
                            CONF_URLS: urls,
                            CONF_SCHOOL_YEARS: [
                                {
                                    "start": school_year.start.isoformat(),
                                    "end": school_year.end.isoformat(),
                                }
                                for school_year in school_years
                            ],
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URLS): str,
                    vol.Optional(CONF_SCHOOL_YEARS, default=""): str,
                }
            ),
            errors=errors,
        )


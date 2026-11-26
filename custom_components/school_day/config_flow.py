"""Config flow for the School Day integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

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

    VERSION = 3

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        return await self._async_step_settings("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit calendar sources and patterns without replacing the entry."""
        return await self._async_step_settings("reconfigure", user_input)

    async def _async_step_settings(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> FlowResult:
        """Share validation and form fields between setup and reconfiguration."""
        entry = self._get_reconfigure_entry() if step_id == "reconfigure" else None
        data = entry.data if entry else {}
        defaults = {
            CONF_NAME: data.get(CONF_NAME, entry.title if entry else DEFAULT_NAME),
            CONF_URLS: "\n".join(data.get(CONF_URLS, [])),
            CONF_SCHOOL_YEARS: "\n".join(
                f"{year['start']} to {year['end']}"
                for year in data.get(CONF_SCHOOL_YEARS, [])
            ),
            CONF_NO_SCHOOL_PATTERNS: "\n".join(
                data.get(CONF_NO_SCHOOL_PATTERNS, DEFAULT_NO_SCHOOL_PATTERNS)
            ),
            CONF_LAST_DAY_PATTERNS: "\n".join(
                data.get(CONF_LAST_DAY_PATTERNS, DEFAULT_LAST_DAY_PATTERNS)
            ),
            CONF_FIRST_DAY_PATTERNS: "\n".join(
                data.get(CONF_FIRST_DAY_PATTERNS, DEFAULT_FIRST_DAY_PATTERNS)
            ),
        }
        errors: dict[str, str] = {}

        if user_input is not None:
            defaults.update(user_input)
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
                    settings = {
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
                    }
                    if entry is not None:
                        return self.async_update_reload_and_abort(
                            entry, title=name, data_updates=settings
                        )
                    return self.async_create_entry(title=name, data=settings)

        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=defaults[CONF_NAME]): str,
                    vol.Required(
                        CONF_URLS, default=defaults[CONF_URLS]
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    ),
                    vol.Optional(
                        CONF_SCHOOL_YEARS, default=defaults[CONF_SCHOOL_YEARS]
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    ),
                    vol.Optional(
                        CONF_NO_SCHOOL_PATTERNS,
                        default=defaults[CONF_NO_SCHOOL_PATTERNS],
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    ),
                    vol.Optional(
                        CONF_LAST_DAY_PATTERNS,
                        default=defaults[CONF_LAST_DAY_PATTERNS],
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    ),
                    vol.Optional(
                        CONF_FIRST_DAY_PATTERNS,
                        default=defaults[CONF_FIRST_DAY_PATTERNS],
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    ),
                }
            ),
            errors=errors,
        )

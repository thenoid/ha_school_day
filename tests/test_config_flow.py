"""Settings and migration regressions using Home Assistant's flow classes.

Run separately from the dependency-free calendar runner:
    uv run --with homeassistant==2026.11.3 python tests/test_config_flow.py
"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.config_entries import ConfigEntry

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.school_day import async_migrate_entry, async_setup_entry
from custom_components.school_day.config_flow import SchoolDayConfigFlow
from custom_components.school_day.const import DEFAULT_NO_SCHOOL_PATTERNS


def make_entry(data, version=3):
    """Create a real entry so the framework's reconfigure helpers are tested."""
    return ConfigEntry(
        data=data,
        discovery_keys={},
        domain="school_day",
        minor_version=1,
        options={},
        source="user",
        subentries_data=[],
        title="Existing school",
        unique_id=None,
        version=version,
    )


def form_defaults(result):
    return {key.schema: key.default() for key in result["data_schema"].schema}


class SettingsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.data = {
            "name": "Existing school",
            "urls": ["https://example.com/old.ics", "https://example.com/district.ics"],
            "school_years": [{"start": "2026-08-12", "end": "2027-05-21"}],
            "no_school_patterns": ["district closure", "snow day"],
            "last_day_patterns": ["term complete"],
            "first_day_patterns": ["instruction resumes"],
            "unrelated_setting": "keep me",
        }
        self.entry = make_entry(self.data)
        self.hass = SimpleNamespace(config_entries=Mock())
        self.hass.config_entries.async_get_known_entry.return_value = self.entry
        self.flow = SchoolDayConfigFlow()
        self.flow.hass = self.hass
        self.flow.handler = "school_day"
        self.flow.context = {"source": "reconfigure", "entry_id": self.entry.entry_id}

    async def test_reconfigure_prefills_every_current_setting(self):
        result = await self.flow.async_step_reconfigure()
        self.assertEqual(result["step_id"], "reconfigure")
        self.assertEqual(
            form_defaults(result),
            {
                "name": "Existing school",
                "urls": "https://example.com/old.ics\nhttps://example.com/district.ics",
                "school_years": "2026-08-12 to 2027-05-21",
                "no_school_patterns": "district closure\nsnow day",
                "last_day_patterns": "term complete",
                "first_day_patterns": "instruction resumes",
            },
        )
        self.hass.config_entries.async_update_entry.assert_not_called()

    async def test_reconfigure_updates_calendar_and_patterns_then_reloads_same_entry(
        self,
    ):
        submitted = form_defaults(await self.flow.async_step_reconfigure())
        submitted.update(
            {
                "name": "New school",
                "urls": " https://webapp.vegaevents.com/community/new-school \n\nhttps://example.com/new.ics ",
                "school_years": "2026-08-17 to 2027-05-28",
                "no_school_patterns": " Recess \n No Activities \n Snow Day ",
                "last_day_patterns": " Term Ends ",
                "first_day_patterns": " Term Starts ",
            }
        )
        result = await self.flow.async_step_reconfigure(submitted)
        self.assertEqual(result["reason"], "reconfigure_successful")
        call = self.hass.config_entries.async_update_entry.call_args.kwargs
        self.assertIs(call["entry"], self.entry)
        self.assertEqual(call["title"], "New school")
        self.assertEqual(
            call["data"],
            {
                "name": "New school",
                "urls": [
                    "https://webapp.vegaevents.com/community/new-school",
                    "https://example.com/new.ics",
                ],
                "school_years": [{"start": "2026-08-17", "end": "2027-05-28"}],
                "no_school_patterns": ["recess", "no activities", "snow day"],
                "last_day_patterns": ["term ends"],
                "first_day_patterns": ["term starts"],
                "unrelated_setting": "keep me",
            },
        )
        self.hass.config_entries.async_schedule_reload.assert_called_once_with(
            self.entry.entry_id
        )

    async def test_invalid_input_preserves_form_and_does_not_update_or_reload(self):
        for key, value, error in (
            ("urls", " \n ", "no_urls"),
            ("name", "  ", "no_name"),
            ("school_years", "2027-05-21 to 2026-08-12", "invalid_school_years"),
        ):
            with self.subTest(key=key):
                submitted = form_defaults(await self.flow.async_step_reconfigure())
                submitted[key] = value
                submitted["no_school_patterns"] = "my custom closure"
                result = await self.flow.async_step_reconfigure(submitted)
                self.assertEqual(result["errors"], {key: error})
                self.assertEqual(form_defaults(result), submitted)
        self.hass.config_entries.async_update_entry.assert_not_called()
        self.hass.config_entries.async_schedule_reload.assert_not_called()
        self.assertEqual(self.entry.data, self.data)

    async def test_initial_setup_uses_new_defaults(self):
        self.flow.context = {"source": "user"}
        submitted = form_defaults(await self.flow.async_step_user())
        self.assertEqual(
            submitted["no_school_patterns"].splitlines(),
            list(DEFAULT_NO_SCHOOL_PATTERNS),
        )
        submitted.update(name="School", urls="https://example.com/calendar.ics")
        result = await self.flow.async_step_user(submitted)
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["version"], 3)
        self.assertEqual(
            result["data"]["no_school_patterns"], list(DEFAULT_NO_SCHOOL_PATTERNS)
        )

    async def test_blank_patterns_restore_defaults_and_empty_years_clear_ranges(self):
        submitted = form_defaults(await self.flow.async_step_reconfigure())
        submitted.update(no_school_patterns=" \n", school_years="")
        await self.flow.async_step_reconfigure(submitted)
        data = self.hass.config_entries.async_update_entry.call_args.kwargs["data"]
        self.assertEqual(data["no_school_patterns"], list(DEFAULT_NO_SCHOOL_PATTERNS))
        self.assertEqual(data["school_years"], [])

    async def test_setup_uses_saved_calendar_urls_and_patterns(self):
        self.hass.data = {}
        self.hass.services = Mock()
        self.hass.config_entries.async_forward_entry_setups = AsyncMock()
        with patch(
            "custom_components.school_day.SchoolDayCoordinator", autospec=True
        ) as coordinator:
            self.assertTrue(await async_setup_entry(self.hass, self.entry))
        args = coordinator.call_args.args
        self.assertEqual(args[1], self.data["urls"])
        self.assertEqual(args[3].no_school, tuple(self.data["no_school_patterns"]))
        self.assertEqual(args[3].last_day, ("term complete",))
        self.assertEqual(args[3].first_day, ("instruction resumes",))
        coordinator.return_value.async_config_entry_first_refresh.assert_awaited_once()


class MigrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_upgrades_both_previous_default_versions(self):
        for version, patterns in (
            (1, ["no school"]),
            (2, ["no school", "no students"]),
            (1, None),
            (2, None),
        ):
            with self.subTest(version=version, patterns=patterns):
                data = {"urls": ["https://example.com/calendar.ics"]}
                if patterns is not None:
                    data["no_school_patterns"] = patterns
                entry = make_entry(data, version=version)
                hass = SimpleNamespace(config_entries=Mock())
                self.assertTrue(await async_migrate_entry(hass, entry))
                hass.config_entries.async_update_entry.assert_called_once_with(
                    entry,
                    data={
                        **data,
                        "no_school_patterns": list(DEFAULT_NO_SCHOOL_PATTERNS),
                    },
                    version=3,
                )

    async def test_preserves_custom_patterns_including_deliberately_reduced_list(self):
        for version, patterns in (
            (1, ["district closure"]),
            (2, ["no school"]),
            (2, ["no school", "no students", "snow day"]),
        ):
            with self.subTest(version=version, patterns=patterns):
                data = {
                    "no_school_patterns": patterns,
                    "urls": ["https://example.com/custom.ics"],
                }
                entry = make_entry(data, version=version)
                hass = SimpleNamespace(config_entries=Mock())
                self.assertTrue(await async_migrate_entry(hass, entry))
                hass.config_entries.async_update_entry.assert_called_once_with(
                    entry, data=data, version=3
                )

    async def test_current_and_future_versions_are_not_modified(self):
        for version in (3, 4):
            hass = SimpleNamespace(config_entries=Mock())
            self.assertEqual(
                await async_migrate_entry(hass, make_entry({}, version)), version == 3
            )
            hass.config_entries.async_update_entry.assert_not_called()


if __name__ == "__main__":
    unittest.main()

"""Tests for school calendar calculations."""

from datetime import date
import importlib.util
from pathlib import Path
import sys
import types


def _load_calendar_module():
    root = Path(__file__).resolve().parents[1]
    package_name = "custom_components.school_day"

    custom_components = types.ModuleType("custom_components")
    package = types.ModuleType(package_name)
    package.__path__ = [str(root / "custom_components" / "school_day")]
    sys.modules.setdefault("custom_components", custom_components)
    sys.modules[package_name] = package

    for module_name in ("const", "calendar"):
        path = root / "custom_components" / "school_day" / f"{module_name}.py"
        spec = importlib.util.spec_from_file_location(f"{package_name}.{module_name}", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"{package_name}.{module_name}"] = module
        spec.loader.exec_module(module)

    return sys.modules[f"{package_name}.calendar"]


calendar = _load_calendar_module()
SchoolYear = calendar.SchoolYear
compute_school_day_state = calendar.compute_school_day_state
parse_ics_calendar = calendar.parse_ics_calendar
parse_school_years = calendar.parse_school_years


def test_no_school_event_makes_school_day_false() -> None:
    events = parse_ics_calendar(
        """BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:No School - Teacher Work Day
DTSTART;VALUE=DATE:20260116
DTEND;VALUE=DATE:20260117
END:VEVENT
END:VCALENDAR
"""
    )

    state = compute_school_day_state(events, date(2026, 1, 16))

    assert state.school_day is False
    assert state.no_school is True
    assert state.summer_vacation is False


def test_last_day_event_starts_summer_until_first_day_event() -> None:
    events = parse_ics_calendar(
        """BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:Last Day of School
DTSTART;VALUE=DATE:20260522
DTEND;VALUE=DATE:20260523
END:VEVENT
BEGIN:VEVENT
SUMMARY:First Day of School (Students)
DTSTART;VALUE=DATE:20260812
DTEND;VALUE=DATE:20260813
END:VEVENT
END:VCALENDAR
"""
    )

    summer = compute_school_day_state(events, date(2026, 7, 1))
    first_day = compute_school_day_state(events, date(2026, 8, 12))

    assert summer.school_day is False
    assert summer.no_school is True
    assert summer.summer_vacation is True
    assert first_day.school_day is True
    assert first_day.no_school is False
    assert first_day.summer_vacation is False


def test_configured_school_year_fills_missing_calendar_boundaries() -> None:
    school_years = [SchoolYear(date(2026, 8, 12), date(2027, 5, 21))]

    summer = compute_school_day_state([], date(2026, 7, 1), school_years)
    school = compute_school_day_state([], date(2026, 9, 1), school_years)

    assert summer.summer_vacation is True
    assert summer.no_school is True
    assert school.school_day is True
    assert school.configured_school_year == "2026-08-12..2027-05-21"


def test_calendar_boundary_overrides_configured_school_year() -> None:
    events = parse_ics_calendar(
        """BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:Last Day of School
DTSTART;VALUE=DATE:20260522
DTEND;VALUE=DATE:20260523
END:VEVENT
END:VCALENDAR
"""
    )
    school_years = [SchoolYear(date(2026, 8, 12), date(2027, 5, 21))]

    state = compute_school_day_state(events, date(2026, 7, 1), school_years)

    assert state.summer_vacation is True
    assert state.boundary_event == "Last Day of School"


def test_configured_fall_start_ends_summer_when_first_day_is_missing() -> None:
    events = parse_ics_calendar(
        """BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:Last Day of School
DTSTART;VALUE=DATE:20260522
DTEND;VALUE=DATE:20260523
END:VEVENT
END:VCALENDAR
"""
    )
    school_years = [SchoolYear(date(2026, 8, 12), date(2027, 5, 21))]

    state = compute_school_day_state(events, date(2026, 8, 12), school_years)

    assert state.school_day is True
    assert state.summer_vacation is False
    assert state.configured_school_year == "2026-08-12..2027-05-21"


def test_parse_school_years_accepts_multiple_range_separators() -> None:
    school_years = parse_school_years(
        """2025-08-12 to 2026-05-22
2026-08-13,2027-05-21
"""
    )

    assert school_years == [
        SchoolYear(date(2025, 8, 12), date(2026, 5, 22)),
        SchoolYear(date(2026, 8, 13), date(2027, 5, 21)),
    ]

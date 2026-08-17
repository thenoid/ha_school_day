"""Tests for school calendar calculations."""

import asyncio
from datetime import date, timedelta
import importlib.util
import json
from pathlib import Path
import sys
import types
from urllib.parse import parse_qs, urlparse


def _load_calendar_module():
    root = Path(__file__).resolve().parents[1]
    package_name = "custom_components.school_day"

    custom_components = types.ModuleType("custom_components")
    package = types.ModuleType(package_name)
    package.__path__ = [str(root / "custom_components" / "school_day")]
    sys.modules.setdefault("custom_components", custom_components)
    sys.modules[package_name] = package

    for module_name in ("const", "calendar", "vega"):
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
SchoolDayPatterns = calendar.SchoolDayPatterns
compute_school_day_state = calendar.compute_school_day_state
parse_event_patterns = calendar.parse_event_patterns
parse_ics_calendar = calendar.parse_ics_calendar
parse_school_years = calendar.parse_school_years
vega = sys.modules["custom_components.school_day.vega"]
VegaCalendarAdapter = vega.VegaCalendarAdapter
is_vega_community_url = vega.is_vega_community_url
parse_vega_events = vega.parse_vega_events


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


def test_weekend_inside_configured_school_year_is_not_school_day() -> None:
    school_years = [SchoolYear(date(2026, 8, 12), date(2027, 5, 21))]

    saturday = compute_school_day_state([], date(2026, 9, 5), school_years)
    sunday = compute_school_day_state([], date(2026, 9, 6), school_years)

    assert saturday.school_day is False
    assert saturday.no_school is True
    assert saturday.summer_vacation is False
    assert sunday.school_day is False
    assert sunday.no_school is True
    assert sunday.summer_vacation is False


def test_weekday_inside_configured_school_year_remains_school_day() -> None:
    school_years = [SchoolYear(date(2026, 8, 12), date(2027, 5, 21))]

    state = compute_school_day_state([], date(2026, 9, 7), school_years)

    assert state.school_day is True
    assert state.no_school is False


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


def test_custom_no_school_pattern_marks_no_school_day() -> None:
    events = parse_ics_calendar(
        """BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:District Closure
DTSTART;VALUE=DATE:20260116
DTEND;VALUE=DATE:20260117
END:VEVENT
END:VCALENDAR
"""
    )
    patterns = SchoolDayPatterns(no_school=("district closure",))

    state = compute_school_day_state(events, date(2026, 1, 16), patterns=patterns)

    assert state.school_day is False
    assert state.no_school is True


def test_custom_boundary_patterns_control_summer_vacation() -> None:
    events = parse_ics_calendar(
        """BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:Term Complete
DTSTART;VALUE=DATE:20260522
DTEND;VALUE=DATE:20260523
END:VEVENT
BEGIN:VEVENT
SUMMARY:Instruction Resumes Students
DTSTART;VALUE=DATE:20260812
DTEND;VALUE=DATE:20260813
END:VEVENT
END:VCALENDAR
"""
    )
    patterns = SchoolDayPatterns(
        last_day=("term complete",),
        first_day=("instruction resumes",),
    )

    summer = compute_school_day_state(events, date(2026, 7, 1), patterns=patterns)
    first_day = compute_school_day_state(events, date(2026, 8, 12), patterns=patterns)

    assert summer.summer_vacation is True
    assert first_day.summer_vacation is False


def test_parse_event_patterns_normalizes_lines_and_uses_default_when_empty() -> None:
    assert parse_event_patterns(" District Closure \n Snow Day \n", ("no school",)) == (
        "district closure",
        "snow day",
    )
    assert parse_event_patterns("", ("no school",)) == ("no school",)


def test_parse_vega_events_normalizes_local_dates_and_skips_cancelled_events() -> None:
    fixture = Path(__file__).with_name("fixtures") / "vega_events_redacted.json"

    events = parse_vega_events(json.loads(fixture.read_text()))

    assert events == [
        calendar.SchoolCalendarEvent(
            summary="First Day of School", start=date(2026, 8, 17), end=date(2026, 8, 18)
        ),
        calendar.SchoolCalendarEvent(
            summary="Evening practice", start=date(2026, 8, 19), end=date(2026, 8, 20)
        ),
    ]


def test_vega_adapter_resolves_community_url_and_fetches_public_events() -> None:
    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self.payload = payload
            self.status_checked = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        def raise_for_status(self) -> None:
            self.status_checked = True

        async def json(self) -> dict:
            return self.payload

    class FakeSession:
        def __init__(self, responses: list[dict]) -> None:
            self.requests: list[str] = []
            self.responses = responses

        def get(self, url: str, *, timeout: int) -> FakeResponse:
            assert timeout == 30
            self.requests.append(url)
            return FakeResponse(self.responses.pop(0))

    fixture = Path(__file__).with_name("fixtures") / "vega_events_redacted.json"
    adapter = VegaCalendarAdapter.from_url(
        "https://webapp.vegaevents.com/community/brighton-high-school?view=calendar"
    )
    assert adapter is not None
    session = FakeSession(
        [
            {"organization": {"id": "public-org-id"}},
            json.loads(fixture.read_text()),
        ]
    )

    events = asyncio.run(adapter.async_fetch_events(session, date(2026, 8, 17)))

    assert adapter.organization_id == "public-org-id"
    assert events[0].summary == "First Day of School"
    assert session.requests[0] == (
        "https://api.vegaevents.com/public/v1/organizations/"
        "brighton-high-school/community"
    )
    event_request = urlparse(session.requests[1])
    assert event_request.path == "/public/v2/events/organization/public-org-id/public"
    assert parse_qs(event_request.query) == {
        "q": ["*"],
        "limit": ["1000"],
        "offset": ["0"],
        "from": ["2025-08-12T00:00:00.000Z"],
        "to": [
            f"{(date(2026, 8, 17) + timedelta(days=550)).isoformat()}T23:59:59.999Z"
        ],
    }


def test_vega_adapter_recognizes_only_public_community_urls() -> None:
    assert is_vega_community_url(
        "https://webapp.vegaevents.com/community/brighton-high-school?view=calendar"
    )
    assert VegaCalendarAdapter.from_url(
        "https://webapp.vegaevents.com/community/brighton-high-school"
    ) == VegaCalendarAdapter(handle="brighton-high-school")
    assert not is_vega_community_url("https://api.vegaevents.com/public/v2/events")
    assert not is_vega_community_url("https://example.com/community/brighton-high-school")

"""ICS parsing and school day state calculation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re

from .const import (
    DEFAULT_FIRST_DAY_PATTERNS,
    DEFAULT_LAST_DAY_PATTERNS,
    DEFAULT_NO_SCHOOL_PATTERNS,
)


@dataclass(frozen=True)
class SchoolCalendarEvent:
    """A normalized calendar event."""

    summary: str
    start: date
    end: date

    def occurs_on(self, day: date) -> bool:
        """Return whether the event occurs on a date."""
        return self.start <= day < self.end


@dataclass(frozen=True)
class SchoolYear:
    """A statically configured student school-year range."""

    start: date
    end: date

    def contains(self, day: date) -> bool:
        """Return whether a date is inside the school year."""
        return self.start <= day <= self.end

    @property
    def label(self) -> str:
        """Return a stable label for attributes."""
        return f"{self.start.isoformat()}..{self.end.isoformat()}"


@dataclass(frozen=True)
class SchoolDayState:
    """Computed school calendar state for one date."""

    school_day: bool
    no_school: bool
    summer_vacation: bool
    matching_events: tuple[str, ...]
    boundary_event: str | None
    configured_school_year: str | None


@dataclass(frozen=True)
class SchoolDayPatterns:
    """Text patterns used to classify school calendar events."""

    no_school: tuple[str, ...] = DEFAULT_NO_SCHOOL_PATTERNS
    last_day: tuple[str, ...] = DEFAULT_LAST_DAY_PATTERNS
    first_day: tuple[str, ...] = DEFAULT_FIRST_DAY_PATTERNS


def parse_ics_calendar(ics_text: str) -> list[SchoolCalendarEvent]:
    """Parse VEVENT records from an ICS document.

    This intentionally supports the common subset used by public school
    calendars: SUMMARY, DTSTART, DTEND, folded lines, escaped text, and
    cancelled-event filtering.
    """
    events: list[SchoolCalendarEvent] = []
    current: dict[str, str] | None = None

    for line in _unfold_lines(ics_text):
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current is not None:
                event = _event_from_properties(current)
                if event is not None:
                    events.append(event)
            current = None
            continue
        if current is None or ":" not in line:
            continue

        name, value = line.split(":", 1)
        prop = name.split(";", 1)[0].upper()
        current[prop] = value

    return events


def compute_school_day_state(
    events: list[SchoolCalendarEvent],
    today: date,
    school_years: list[SchoolYear] | None = None,
    patterns: SchoolDayPatterns | None = None,
) -> SchoolDayState:
    """Compute school-day, no-school, and summer-vacation flags."""
    school_years = school_years or []
    patterns = patterns or SchoolDayPatterns()
    events_today = [event for event in events if event.occurs_on(today)]
    matching_events = tuple(event.summary for event in events_today)
    no_school_event = any(
        _matches_any(event.summary, patterns.no_school) for event in events_today
    )
    boundary = _current_school_year_boundary(events, today, patterns)
    configured_school_year = _configured_school_year_for_day(school_years, today)

    if boundary is not None and _is_first_day(boundary.summary, patterns):
        summer_vacation = False
    elif boundary is not None and today == boundary.start:
        summer_vacation = _is_last_day(boundary.summary, patterns)
    elif boundary is not None and _is_last_day(boundary.summary, patterns):
        summer_vacation = configured_school_year is None
    elif school_years:
        summer_vacation = configured_school_year is None
    else:
        summer_vacation = False

    no_school = no_school_event or summer_vacation or _is_weekend(today)
    return SchoolDayState(
        school_day=not no_school,
        no_school=no_school,
        summer_vacation=summer_vacation,
        matching_events=matching_events,
        boundary_event=boundary.summary if boundary else None,
        configured_school_year=configured_school_year.label
        if configured_school_year
        else None,
    )


def parse_school_years(value: str) -> list[SchoolYear]:
    """Parse configured school years from newline-delimited date ranges."""
    school_years: list[SchoolYear] = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parts = re.split(r"\s*(?:,|to|\.\.)\s*", line, maxsplit=1)
        if len(parts) != 2:
            raise ValueError(f"Invalid school year range: {line}")

        start = date.fromisoformat(parts[0])
        end = date.fromisoformat(parts[1])
        if end < start:
            raise ValueError(f"School year end is before start: {line}")

        school_years.append(SchoolYear(start=start, end=end))

    return school_years


def parse_event_patterns(value: str, default: tuple[str, ...]) -> tuple[str, ...]:
    """Parse newline-delimited event summary patterns."""
    patterns = tuple(
        _normalized_summary(line) for line in value.splitlines() if line.strip()
    )
    return patterns or default


def _unfold_lines(ics_text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in ics_text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw_line.startswith((" ", "\t")) and lines:
            lines[-1] += raw_line[1:]
        elif raw_line:
            lines.append(raw_line)
    return lines


def _event_from_properties(props: dict[str, str]) -> SchoolCalendarEvent | None:
    if props.get("STATUS", "").upper() == "CANCELLED":
        return None

    summary = _unescape_ics_text(props.get("SUMMARY", "")).strip()
    start_value = props.get("DTSTART")
    if not summary or not start_value:
        return None

    start = _parse_ics_date(start_value)
    end = _parse_ics_date(props["DTEND"]) if "DTEND" in props else start + timedelta(days=1)
    if end <= start:
        end = start + timedelta(days=1)

    return SchoolCalendarEvent(summary=summary, start=start, end=end)


def _parse_ics_date(value: str) -> date:
    if "T" not in value and re.fullmatch(r"\d{8}", value):
        return datetime.strptime(value, "%Y%m%d").date()

    date_part = value.split("T", 1)[0]
    if re.fullmatch(r"\d{8}", date_part):
        return datetime.strptime(date_part, "%Y%m%d").date()

    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def _unescape_ics_text(value: str) -> str:
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def _current_school_year_boundary(
    events: list[SchoolCalendarEvent], today: date, patterns: SchoolDayPatterns
) -> SchoolCalendarEvent | None:
    boundaries = [
        event
        for event in events
        if event.start <= today
        and (
            _is_first_day(event.summary, patterns)
            or _is_last_day(event.summary, patterns)
        )
    ]
    if not boundaries:
        return None

    return max(boundaries, key=lambda event: event.start)


def _configured_school_year_for_day(
    school_years: list[SchoolYear], today: date
) -> SchoolYear | None:
    for school_year in school_years:
        if school_year.contains(today):
            return school_year
    return None


def _is_weekend(day: date) -> bool:
    return day.weekday() >= 5


def _normalized_summary(summary: str) -> str:
    return " ".join(summary.casefold().split())


def _matches_any(summary: str, patterns: tuple[str, ...]) -> bool:
    normalized = _normalized_summary(summary)
    return any(pattern in normalized for pattern in patterns)


def _is_last_day(summary: str, patterns: SchoolDayPatterns) -> bool:
    return _matches_any(summary, patterns.last_day)


def _is_first_day(summary: str, patterns: SchoolDayPatterns) -> bool:
    normalized = _normalized_summary(summary)
    return any(
        pattern in normalized and ("student" in normalized or normalized == pattern)
        for pattern in patterns.first_day
    )

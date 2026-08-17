"""Public Vega community-calendar adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from urllib.parse import quote, urlencode, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .calendar import SchoolCalendarEvent


VEGA_API_URL = "https://api.vegaevents.com"
VEGA_PAGE_SIZE = 1000
VEGA_LOOKBACK_DAYS = 370
VEGA_LOOKAHEAD_DAYS = 550
_VEGA_COMMUNITY_HOSTS = frozenset(
    {"webapp.vegaevents.com", "vegaevents.com", "www.vegaevents.com"}
)


def is_vega_community_url(url: str) -> bool:
    """Return whether a URL is a public Vega community page."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False

    path = [part for part in parsed.path.split("/") if part]
    return (
        parsed.scheme in {"http", "https"}
        and parsed.hostname is not None
        and parsed.hostname.casefold() in _VEGA_COMMUNITY_HOSTS
        and len(path) >= 2
        and path[0].casefold() == "community"
        and bool(path[1])
    )


def parse_vega_events(payload: dict[str, Any]) -> list[SchoolCalendarEvent]:
    """Normalize Vega's public event-search response into calendar events."""
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("Vega events response does not contain an items list")

    events: list[SchoolCalendarEvent] = []
    for item in items:
        if not isinstance(item, dict) or _is_cancelled(item):
            continue

        summary = item.get("name") or item.get("title")
        start_value = item.get("startTime")
        if not isinstance(summary, str) or not summary.strip() or not isinstance(start_value, str):
            continue

        event_timezone = _event_timezone(item.get("timeZoneName"))
        try:
            start = _parse_datetime(start_value, event_timezone)
            end_value = item.get("endTime")
            end = (
                _parse_datetime(end_value, event_timezone)
                if isinstance(end_value, str)
                else None
            )
        except ValueError:
            continue

        start_date = start.date()
        end_date = _event_end_date(start_date, end, bool(item.get("isAllDay")))
        events.append(
            SchoolCalendarEvent(
                summary=summary.strip(),
                start=start_date,
                end=end_date,
            )
        )

    return events


@dataclass
class VegaCalendarAdapter:
    """Load public calendar events from a Vega community URL."""

    handle: str
    organization_id: str | None = None

    @classmethod
    def from_url(cls, url: str) -> VegaCalendarAdapter | None:
        """Create an adapter when *url* is a Vega public community page."""
        if not is_vega_community_url(url):
            return None

        handle = [part for part in urlparse(url).path.split("/") if part][1]
        return cls(handle=handle)

    async def async_fetch_events(
        self, session: Any, today: date
    ) -> list[SchoolCalendarEvent]:
        """Fetch the date window needed for school-day calculations."""
        if self.organization_id is None:
            self.organization_id = await self._async_fetch_organization_id(session)

        start = datetime.combine(
            today - timedelta(days=VEGA_LOOKBACK_DAYS), time.min, timezone.utc
        )
        end = datetime.combine(
            today + timedelta(days=VEGA_LOOKAHEAD_DAYS), time.max, timezone.utc
        )
        events: list[SchoolCalendarEvent] = []
        offset = 0

        while True:
            url = _events_url(self.organization_id, start, end, offset)
            async with session.get(url, timeout=30) as response:
                response.raise_for_status()
                payload = await response.json()

            if not isinstance(payload, dict):
                raise ValueError("Vega events response must be a JSON object")
            items = payload.get("items")
            if not isinstance(items, list):
                raise ValueError("Vega events response does not contain an items list")

            events.extend(parse_vega_events(payload))
            if len(items) < VEGA_PAGE_SIZE:
                return events

            offset += len(items)
            if offset > 100_000:
                raise ValueError("Vega events response exceeded 100,000 items")

    async def _async_fetch_organization_id(self, session: Any) -> str:
        """Resolve a public community handle to its Vega organization ID."""
        url = f"{VEGA_API_URL}/public/v1/organizations/{quote(self.handle, safe='')}/community"
        async with session.get(url, timeout=30) as response:
            response.raise_for_status()
            payload = await response.json()

        if not isinstance(payload, dict):
            raise ValueError("Vega community response must be a JSON object")
        organization = payload.get("organization")
        organization_id = organization.get("id") if isinstance(organization, dict) else None
        if not isinstance(organization_id, str) or not organization_id:
            raise ValueError("Vega community response does not contain an organization ID")
        return organization_id


def _events_url(organization_id: str, start: datetime, end: datetime, offset: int) -> str:
    """Build the public events-search URL used by Vega's calendar page."""
    query = urlencode(
        {
            "q": "*",
            "limit": VEGA_PAGE_SIZE,
            "offset": offset,
            "from": _isoformat_utc(start),
            "to": _isoformat_utc(end),
        }
    )
    return (
        f"{VEGA_API_URL}/public/v2/events/organization/"
        f"{quote(organization_id, safe='')}/public?{query}"
    )


def _isoformat_utc(value: datetime) -> str:
    """Format a UTC API timestamp with Vega's millisecond precision."""
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _is_cancelled(item: dict[str, Any]) -> bool:
    """Return whether a Vega event has been cancelled."""
    status = item.get("status")
    return isinstance(status, str) and status.casefold() in {"cancelled", "canceled"}


def _event_timezone(value: object) -> timezone | ZoneInfo:
    """Return the event timezone, defaulting to UTC for missing/invalid values."""
    if isinstance(value, str) and value:
        try:
            return ZoneInfo(value)
        except ZoneInfoNotFoundError:
            pass
    return timezone.utc


def _parse_datetime(value: str, event_timezone: timezone | ZoneInfo) -> datetime:
    """Parse Vega's ISO 8601 timestamps in the event's local timezone."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as err:
        raise ValueError(f"Invalid Vega event timestamp: {value}") from err

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=event_timezone)
    return parsed.astimezone(event_timezone)


def _event_end_date(
    start_date: date, end: datetime | None, is_all_day: bool
) -> date:
    """Return SchoolCalendarEvent's exclusive end date for a Vega event."""
    if end is None:
        return start_date + timedelta(days=1)

    if is_all_day or end.time() == time.min:
        end_date = end.date()
    else:
        end_date = end.date() + timedelta(days=1)
    return max(end_date, start_date + timedelta(days=1))

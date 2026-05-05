# School Day?

Home Assistant custom integration that creates binary sensors from one or more
ICS school-calendar URLs.

## Entities

- `binary_sensor.school_day`: on when school is considered in session.
- `binary_sensor.no_school`: on when a `No School` event is found, or when the
  date is in summer vacation.
- `binary_sensor.summer_vacation`: on after `Last Day of School` until
  `First Day of School (Students)`, or outside a configured school-year range.

All entities include attributes for matching calendar events, the latest
first/last-day boundary event, and the configured school-year range currently in
effect.

## Configuration

Install this repository's `custom_components/school_day` directory into your
Home Assistant `custom_components` directory, then add the integration from the
UI.

## HACS

This repository is structured for HACS as a custom integration repository. Add
the GitHub repository to HACS as a custom repository with category
`Integration`, restart Home Assistant after install, then add `School Day?`
from Settings > Devices & services.

Repository URL:

```text
https://github.com/thenoid/ha_school_day
```

For publishing, bump `version` in
`custom_components/school_day/manifest.json`. The release workflow tags that
version and creates a GitHub release automatically after the change lands on
`main` or `master`.

Use one or more ICS URLs, one per line. Example:

```text
https://www.calendarwiz.com/CalendarWiz_iCal.php?crd=brightoncanyons&cid%5B%5D=123299&lid%5B%5D=empty&
```

Optional static school-year ranges fill gaps when the calendar has not yet
published the next fall start date. Use one range per line:

```text
2025-08-12 to 2026-05-22
2026-08-12 to 2027-05-21
```

Calendar events still drive holiday and no-school detection. Configured ranges
only decide whether a date is summer vacation when calendar first/last-day
events are missing or incomplete.

The setup flow also asks for a school name, which is used as the Home Assistant
device name. Advanced setup options let you customize the event summary patterns
used to detect no-school days, last-day boundaries, and first-day boundaries.
Use one pattern per line. Defaults are:

```text
no school
last day of school
first day of school
```

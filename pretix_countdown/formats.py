"""Countdown and date formats.

The shop's countdown script (static/pretix_countdown/countdown.js)
renders countdown templates the same way as ``render_countdown``. Keep
the two in sync.
"""

import re
from django.utils import dateformat
from django.utils.formats import date_format
from django.utils.timezone import localtime
from django.utils.translation import gettext, gettext_lazy as _, pgettext_lazy

PLACEHOLDER = re.compile(r"\{(\w+)\}")
OPTIONAL_PART = re.compile(r"\[([^\[\]]*)\]")

NUMBER_PLACEHOLDERS = ("days", "hours", "minutes", "seconds", "hh", "mm", "ss")
LABEL_PLACEHOLDERS = ("days_label", "hours_label", "minutes_label", "seconds_label")
COUNTDOWN_PLACEHOLDERS = NUMBER_PLACEHOLDERS + LABEL_PLACEHOLDERS
PRODUCT_TEXT_PLACEHOLDERS = ("countdown", "date")
HEADING_PLACEHOLDERS = ("date",)

# Placeholders: {days}, {hours}, {minutes}, {seconds}; {hh}, {mm}, {ss} are padded to
# two digits; {days_label} etc. are "day" or "days" to match the number. Text in square
# brackets is left out when all numbers in it are zero.
COUNTDOWN_FORMATS = {
    "clock": pgettext_lazy("countdown format", "[{days} {days_label} ]{hh}:{mm}:{ss}"),
    "compact": pgettext_lazy("countdown format", "[{days}d ]{hours}h {mm}m {ss}s"),
    "long": pgettext_lazy(
        "countdown format",
        "[{days} {days_label}, ][{hours} {hours_label}, ]"
        "[{minutes} {minutes_label}, ]{seconds} {seconds_label}",
    ),
}
COUNTDOWN_FORMAT_CHOICES = (
    ("clock", _("Clock")),
    ("compact", _("Compact")),
    ("long", _("Written out")),
    ("custom", _("Custom")),
)

DATE_FORMATS = {
    "short": "SHORT_DATETIME_FORMAT",
    "long": "DATETIME_FORMAT",
}
DATE_FORMAT_CHOICES = (
    ("short", _("Short")),
    ("long", _("Long")),
    ("custom", _("Custom")),
)

# Seconds shown in the examples of the settings form: 2 days 4 hours 13 minutes 22 s
EXAMPLE_SECONDS = 2 * 86400 + 4 * 3600 + 13 * 60 + 22


def unit_labels() -> dict:
    """Return the singular and plural label of each unit for the current
    language."""
    return {
        "days_label": [gettext("day"), gettext("days")],
        "hours_label": [gettext("hour"), gettext("hours")],
        "minutes_label": [gettext("minute"), gettext("minutes")],
        "seconds_label": [gettext("second"), gettext("seconds")],
    }


def countdown_template(settings) -> str:
    """Return the countdown template the event is configured to use."""
    if settings.countdown__format == "custom":
        custom = str(settings.countdown__format_custom or "")
        if custom:
            return custom
    return str(
        COUNTDOWN_FORMATS.get(settings.countdown__format, COUNTDOWN_FORMATS["clock"])
    )


def countdown_parts(template: str, seconds: int, labels: dict) -> dict:
    """Split ``seconds`` into the values for a countdown template.

    Units that the template doesn't show are carried over into the next
    smaller one, so "{hours}:{mm}" shows 52:13 instead of 4:13 when two
    days are left.
    """
    used = set(PLACEHOLDER.findall(template))
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    if "days" not in used:
        hours += days * 24
        days = 0
    if not used & {"hours", "hh"}:
        minutes += hours * 60
        hours = 0
    if not used & {"minutes", "mm"}:
        secs += minutes * 60
        minutes = 0
    parts = {
        "days": days,
        "hours": hours,
        "minutes": minutes,
        "seconds": secs,
        "hh": f"{hours:02d}",
        "mm": f"{minutes:02d}",
        "ss": f"{secs:02d}",
    }
    for unit in ("days", "hours", "minutes", "seconds"):
        singular, plural = labels[f"{unit}_label"]
        parts[f"{unit}_label"] = singular if parts[unit] == 1 else plural
    return parts


def render_countdown(template: str, seconds: int, labels: dict) -> str:
    parts = countdown_parts(template, seconds, labels)

    def optional(match):
        names = [
            n for n in PLACEHOLDER.findall(match.group(1)) if n in NUMBER_PLACEHOLDERS
        ]
        if names and all(int(parts[n]) == 0 for n in names):
            return ""
        return match.group(1)

    text = OPTIONAL_PART.sub(optional, template)
    return PLACEHOLDER.sub(lambda m: str(parts.get(m.group(1), m.group(0))), text)


def format_date(dt, timezone, fmt="short", custom="") -> str:
    """Format ``dt`` with one of ``DATE_FORMATS``, or with a Django date format
    string if ``fmt`` is "custom"."""
    dt = localtime(dt, timezone)
    if fmt == "custom" and custom:
        return dateformat.format(dt, custom)
    return date_format(dt, DATE_FORMATS.get(fmt, DATE_FORMATS["short"]))


def replace_placeholders(text: str, values: dict) -> str:
    """Fill in ``{name}`` placeholders, leaving unknown ones and other braces
    alone."""
    return PLACEHOLDER.sub(lambda m: str(values.get(m.group(1), m.group(0))), text)


def unknown_placeholders(text: str, allowed) -> list:
    return sorted(set(PLACEHOLDER.findall(text)) - set(allowed))

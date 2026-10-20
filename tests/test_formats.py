import json
import pytest
import re
from datetime import datetime, timedelta, timezone
from django.utils.timezone import now
from i18nfield.strings import LazyI18nString

from pretix_countdown.formats import (
    COUNTDOWN_FORMATS,
    EXAMPLE_SECONDS,
    format_date,
    render_countdown,
    replace_placeholders,
)

LABELS = {
    "days_label": ["day", "days"],
    "hours_label": ["hour", "hours"],
    "minutes_label": ["minute", "minutes"],
    "seconds_label": ["second", "seconds"],
}
DAY = 86400


def render(template, seconds):
    return render_countdown(str(template), seconds, LABELS)


@pytest.mark.parametrize(
    "key,seconds,expected",
    [
        ("clock", EXAMPLE_SECONDS, "2 days 04:13:22"),
        ("clock", DAY + 5, "1 day 00:00:05"),
        ("clock", 3 * 60 + 7, "00:03:07"),
        ("compact", EXAMPLE_SECONDS, "2d 4h 13m 22s"),
        ("compact", 3 * 60 + 7, "0h 03m 07s"),
        ("long", EXAMPLE_SECONDS, "2 days, 4 hours, 13 minutes, 22 seconds"),
        ("long", DAY + 60 + 1, "1 day, 1 minute, 1 second"),
        ("long", 9, "9 seconds"),
    ],
)
def test_presets(key, seconds, expected):
    assert render(COUNTDOWN_FORMATS[key], seconds) == expected


def test_custom_carries_units_into_smaller_ones():
    assert render("{hours}:{mm}:{ss}", EXAMPLE_SECONDS) == "52:13:22"
    assert render("{minutes} min", 2 * 3600 + 30) == "120 min"
    assert render("{seconds}", 90) == "90"


def test_custom_optional_parts():
    template = "[{days} {days_label} ][{hours}h ]{mm}:{ss}"
    assert render(template, EXAMPLE_SECONDS) == "2 days 4h 13:22"
    assert render(template, 3600 * 4 + 1) == "4h 00:01"
    assert render(template, 61) == "01:01"
    # Without numbers, a part is always shown
    assert render("[soon] {ss}", 5) == "soon 05"


def test_custom_keeps_unknown_placeholders_and_braces():
    assert render("{foo} {ss} {", 5) == "{foo} 05 {"


def test_replace_placeholders():
    assert replace_placeholders("Opens {date}! {x}", {"date": "today"}) == (
        "Opens today! {x}"
    )


def test_format_date():
    dt = datetime(2026, 11, 1, 9, 30, tzinfo=timezone.utc)
    tz = timezone(timedelta(hours=1))
    assert format_date(dt, tz, "custom", "Y-m-d H:i") == "2026-11-01 10:30"
    # Without a custom format, the short format is used
    assert format_date(dt, tz, "custom", "") == format_date(dt, tz, "short")
    assert format_date(dt, tz, "long") != format_date(dt, tz, "short")


def head_config(html):
    match = re.search(
        r'<script id="pretix-countdown-config" type="application/json">(.*?)</script>',
        html,
        re.S,
    )
    return json.loads(match.group(1))


@pytest.mark.django_db
def test_config_in_shop(client, event, item):
    event.settings.countdown__format = "custom"
    event.settings.countdown__format_custom = LazyI18nString({"en": "{hours}h"})
    event.settings.countdown__product_text = LazyI18nString(
        {"en": "Opens {date}, in {countdown}"}
    )

    html = client.get("/dummy/dummy/").content.decode()
    config = head_config(html)
    assert config["format"] == "{hours}h"
    assert config["product"] == "Opens {date}, in {countdown}"
    assert config["labels"]["days_label"] == ["day", "days"]


@pytest.mark.django_db
def test_config_defaults(client, event, item):
    config = head_config(client.get("/dummy/dummy/").content.decode())
    assert config["format"] == str(COUNTDOWN_FORMATS["clock"])
    assert config["product"] == "Available in {countdown}"


@pytest.mark.django_db
def test_custom_format_falls_back_when_empty(client, event, item):
    event.settings.countdown__format = "custom"
    config = head_config(client.get("/dummy/dummy/").content.decode())
    assert config["format"] == str(COUNTDOWN_FORMATS["clock"])


@pytest.mark.django_db
def test_date_format_and_heading_placeholder(client, event, item):
    event.presale_start = now() + timedelta(days=1)
    event.save()
    event.settings.countdown__date_format = "custom"
    event.settings.countdown__date_format_custom = "Y-m-d"
    event.settings.countdown__event_heading = LazyI18nString(
        {"en": "Sales open on {date}"}
    )
    item.available_from = now() + timedelta(days=1)
    item.save()

    html = client.get("/dummy/dummy/").content.decode()
    date = event.presale_start.astimezone(event.timezone).strftime("%Y-%m-%d")
    assert f"Sales open on {date}" in html
    assert f'<span class="pretix-countdown-date">{date}</span>' in html


SETTINGS_URL = "/control/event/dummy/dummy/countdown/"


def post_settings(admin_client, **data):
    data.setdefault("countdown__format", "clock")
    data.setdefault("countdown__date_format", "short")
    return admin_client.post(SETTINGS_URL, data)


@pytest.mark.django_db
def test_settings_shows_examples(admin_client, event):
    html = admin_client.get(SETTINGS_URL).content.decode()
    assert "2 days 04:13:22" in html
    assert "2d 4h 13m 22s" in html
    assert 'data-display-dependency="#id_countdown__format_3"' in html
    assert 'data-display-dependency="#id_countdown__date_format_2"' in html


@pytest.mark.django_db
def test_settings_saves_custom_formats(admin_client, event):
    response = post_settings(
        admin_client,
        countdown__format="custom",
        countdown__format_custom_0="[{days}d ]{hh}:{mm}",
        countdown__date_format="custom",
        countdown__date_format_custom="j F Y",
        countdown__product_text_0="On sale in {countdown} ({date})",
    )
    assert response.status_code == 302
    event.settings.flush()
    assert event.settings.countdown__format == "custom"
    assert str(event.settings.countdown__format_custom) == "[{days}d ]{hh}:{mm}"
    assert event.settings.countdown__date_format_custom == "j F Y"
    assert str(event.settings.countdown__product_text) == (
        "On sale in {countdown} ({date})"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "data,field,message",
    [
        ({"countdown__format": "custom"}, "countdown__format_custom", "Enter a format"),
        (
            {"countdown__format": "custom", "countdown__format_custom_0": "soon"},
            "countdown__format_custom",
            "at least one placeholder",
        ),
        (
            {"countdown__format": "custom", "countdown__format_custom_0": "{weeks}"},
            "countdown__format_custom",
            "Unknown placeholder: {weeks}",
        ),
        (
            {"countdown__date_format": "custom"},
            "countdown__date_format_custom",
            "Enter a format",
        ),
        (
            {"countdown__product_text_0": "Soon at {date}"},
            "countdown__product_text",
            "needs to contain {countdown}",
        ),
        (
            {"countdown__event_heading_0": "In {countdown}"},
            "countdown__event_heading",
            "Unknown placeholder: {countdown}",
        ),
    ],
)
def test_settings_validation(admin_client, event, data, field, message):
    response = post_settings(admin_client, **data)
    assert response.status_code == 200
    errors = response.context["form"].errors
    assert message in " ".join(errors[field])

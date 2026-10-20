import pytest
from datetime import timedelta
from django.utils.timezone import now
from i18nfield.strings import LazyI18nString

from pretix_countdown.signals import presale_start, product_sales_start


def ts_class(dt):
    return f"pretix-countdown-ts-{int(dt.timestamp())}"


def front_page(client, event):
    response = client.get(f"/{event.organizer.slug}/{event.slug}/")
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.django_db
def test_defaults(event):
    assert event.settings.countdown__event is True
    assert event.settings.countdown__items is True
    assert str(event.settings.countdown__event_heading) == ""


@pytest.mark.django_db
def test_presale_start(event):
    assert presale_start(event) is None

    event.presale_start = now() + timedelta(days=1)
    assert presale_start(event) == event.presale_start

    event.presale_start = now() - timedelta(days=1)
    assert presale_start(event) is None


@pytest.mark.django_db
def test_presale_start_of_subevent(event):
    event.has_subevents = True
    event.save()
    subevent = event.subevents.create(name="Date", date_from=now(), active=True)
    assert presale_start(event, subevent) is None

    subevent.presale_start = now() + timedelta(days=2)
    assert presale_start(event, subevent) == subevent.presale_start


@pytest.mark.django_db
def test_product_sales_start(event, item):
    assert product_sales_start(event, item) is None

    item.available_from = now() - timedelta(hours=1)
    assert product_sales_start(event, item) is None

    item.available_from = now() + timedelta(hours=1)
    assert product_sales_start(event, item) == item.available_from


@pytest.mark.django_db
def test_product_sales_start_waits_for_presale(event, item):
    item.available_from = now() + timedelta(hours=1)
    event.presale_start = now() + timedelta(days=1)
    assert product_sales_start(event, item) == event.presale_start

    # Without a date of its own, the product has no countdown; the banner covers it
    item.available_from = None
    assert product_sales_start(event, item) is None


@pytest.mark.django_db
def test_product_sales_start_of_variation(event, item):
    item.has_variations = True
    item.save()
    variation = item.variations.create(value="Small")

    item.available_from = now() + timedelta(hours=1)
    # The product's countdown already shows its date, not every variation
    assert product_sales_start(event, item, variation) is None

    variation.available_from = now() + timedelta(minutes=30)
    assert product_sales_start(event, item, variation) == item.available_from

    variation.available_from = now() + timedelta(hours=2)
    assert product_sales_start(event, item, variation) == variation.available_from


@pytest.mark.django_db
def test_product_sales_start_subevent_override(event, item):
    event.has_subevents = True
    event.save()
    subevent = event.subevents.create(name="Date", date_from=now(), active=True)
    start = now() + timedelta(hours=3)
    subevent.subeventitem_set.create(item=item, available_from=start)
    subevent.refresh_from_db()

    assert product_sales_start(event, item) is None
    assert product_sales_start(event, item, subevent=subevent) == start


@pytest.mark.django_db
def test_front_page_banner(client, event, item):
    event.presale_start = now() + timedelta(days=1)
    event.save()

    html = front_page(client, event)
    assert "pretix-countdown-banner" in html
    assert ts_class(event.presale_start) in html
    assert "Ticket sales open in" in html
    assert "pretix_countdown/countdown.js" in html
    assert 'id="pretix-countdown-config"' in html


@pytest.mark.django_db
def test_front_page_banner_custom_heading(client, event, item):
    event.presale_start = now() + timedelta(days=1)
    event.save()
    event.settings.countdown__event_heading = LazyI18nString({"en": "Almost there!"})

    html = front_page(client, event)
    assert "Almost there!" in html
    assert "Ticket sales open in" not in html


@pytest.mark.django_db
def test_front_page_no_banner_when_presale_running(client, event, item):
    event.presale_start = now() - timedelta(days=1)
    event.save()

    assert "pretix-countdown-banner" not in front_page(client, event)


@pytest.mark.django_db
def test_front_page_no_banner_when_disabled(client, event, item):
    event.presale_start = now() + timedelta(days=1)
    event.save()
    event.settings.countdown__event = False

    assert "pretix-countdown-banner" not in front_page(client, event)


@pytest.mark.django_db
def test_product_countdown(client, event, item):
    item.available_from = now() + timedelta(hours=1)
    item.save()

    html = front_page(client, event)
    # The class has to survive pretix's markdown sanitizer
    assert f'class="pretix-countdown {ts_class(item.available_from)}"' in html
    assert "Available from" in html


@pytest.mark.django_db
def test_product_countdown_disabled(client, event, item):
    item.available_from = now() + timedelta(hours=1)
    item.save()
    event.settings.countdown__items = False

    assert ts_class(item.available_from) not in front_page(client, event)


@pytest.mark.django_db
def test_no_script_when_everything_disabled(client, event, item):
    event.settings.countdown__event = False
    event.settings.countdown__items = False

    assert "pretix_countdown/countdown.js" not in front_page(client, event)


@pytest.mark.django_db
def test_plugin_disabled(client, event, item):
    event.presale_start = now() + timedelta(days=1)
    event.disable_plugin("pretix_countdown")
    event.save()
    item.available_from = now() + timedelta(hours=1)
    item.save()

    html = front_page(client, event)
    assert "pretix-countdown" not in html


@pytest.mark.django_db
def test_settings_view_saves(admin_client, event):
    url = "/control/event/dummy/dummy/countdown/"
    response = admin_client.get(url)
    assert response.status_code == 200

    response = admin_client.post(
        url,
        {
            "countdown__event_heading_0": "Soon!",
            "countdown__items": "on",
            "countdown__format": "compact",
            "countdown__date_format": "long",
        },
        follow=True,
    )
    assert response.status_code == 200
    event.settings.flush()
    assert event.settings.countdown__event is False
    assert event.settings.countdown__items is True
    assert str(event.settings.countdown__event_heading) == "Soon!"
    assert event.settings.countdown__format == "compact"
    assert event.settings.countdown__date_format == "long"


@pytest.mark.django_db
def test_settings_view_requires_login(client, event):
    response = client.get("/control/event/dummy/dummy/countdown/")
    assert response.status_code == 302

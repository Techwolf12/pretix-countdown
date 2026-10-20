from django.dispatch import receiver
from django.template.loader import get_template
from django.urls import resolve, reverse
from django.utils.formats import date_format
from django.utils.html import escape
from django.utils.timezone import localtime
from django.utils.translation import gettext, gettext_lazy as _
from i18nfield.strings import LazyI18nString
from pretix.base.models import Event
from pretix.base.settings import settings_hierarkey
from pretix.base.timemachine import time_machine_now
from pretix.control.signals import nav_event_settings
from pretix.presale.signals import front_page_top, html_head, item_description

settings_hierarkey.add_default("countdown__event", "True", bool)
settings_hierarkey.add_default("countdown__event_heading", "", LazyI18nString)
settings_hierarkey.add_default("countdown__items", "True", bool)

# The countdown script finds its targets by class. The opening time is part of a class
# name because pretix's markdown sanitizer strips data attributes from product
# descriptions, but keeps classes.
CSS_CLASS = "pretix-countdown"


def countdown_classes(dt) -> str:
    return f"{CSS_CLASS} {CSS_CLASS}-ts-{int(dt.timestamp())}"


def format_start(event: Event, dt) -> str:
    return date_format(localtime(dt, event.timezone), "SHORT_DATETIME_FORMAT")


def presale_start(event: Event, subevent=None):
    """Return the presale start of the event or date, if it is in the
    future."""
    ev = subevent or event
    start = ev.effective_presale_start
    if start and start > time_machine_now() and not ev.presale_has_ended:
        return start
    return None


def product_sales_start(event: Event, item, variation=None, subevent=None):
    """Return when a product or variation that isn't available yet goes on
    sale.

    Returns ``None`` unless the product (or variation) has its own
    "Available from" date in the future. Other dates that also have to
    pass, like the presale start, can move the returned time further
    back.
    """
    item_override = subevent.item_overrides.get(item.pk) if subevent else None
    item_starts = [item.available_from, getattr(item_override, "available_from", None)]
    if variation is None:
        own_starts, other_starts = item_starts, []
    else:
        var_override = subevent.var_overrides.get(variation.pk) if subevent else None
        own_starts = [
            variation.available_from,
            getattr(var_override, "available_from", None),
        ]
        # The product's own countdown already shows the product's date
        other_starts = item_starts

    if not any(d and d > time_machine_now() for d in own_starts):
        return None
    other_starts = other_starts + [(subevent or event).effective_presale_start]
    return max(d for d in own_starts + other_starts if d)


@receiver(html_head, dispatch_uid="pretix_countdown_html_head")
def on_html_head(sender: Event, request, **kwargs):
    if not (sender.settings.countdown__event or sender.settings.countdown__items):
        return ""
    # Rendered without the request: its context processors would send html_head again
    template = get_template("pretix_countdown/presale_head.html")
    config = {
        # Lets the script correct for a visitor's clock being off
        "now": int(time_machine_now().timestamp() * 1000),
        "labels": {
            "day": gettext("day"),
            "days": gettext("days"),
            # {countdown} is replaced with the remaining time, e.g. "2 days 04:13:22"
            "product": gettext("Available in {countdown}"),
            "event_open": gettext("Ticket sales are open. Reloading…"),
            "product_open": gettext("Available now. Reloading…"),
        },
    }
    return template.render({"config": config})


@receiver(front_page_top, dispatch_uid="pretix_countdown_front_page_top")
def on_front_page_top(sender: Event, request, subevent=None, **kwargs):
    if not sender.settings.countdown__event:
        return ""
    if sender.has_subevents and not subevent:
        return ""
    start = presale_start(sender, subevent)
    if not start:
        return ""
    template = get_template("pretix_countdown/banner.html")
    heading = str(sender.settings.countdown__event_heading or "")
    return template.render(
        {
            "heading": heading or gettext("Ticket sales open in"),
            "classes": countdown_classes(start),
            "start": format_start(sender, start),
        }
    )


@receiver(item_description, dispatch_uid="pretix_countdown_item_description")
def on_item_description(sender: Event, item, variation=None, subevent=None, **kwargs):
    if not sender.settings.countdown__items:
        return ""
    start = product_sales_start(sender, item, variation, subevent)
    if not start:
        return ""
    # pretix appends this to the description and renders it as markdown. Without
    # JavaScript (e.g. in the widget) the date stays visible.
    text = gettext("Available from {date}").format(date=format_start(sender, start))
    return f'<span class="{countdown_classes(start)}">{escape(text)}</span>'


@receiver(nav_event_settings, dispatch_uid="pretix_countdown_nav_event_settings")
def navbar_settings(sender: Event, request, **kwargs):
    if not request.user.has_event_permission(
        request.organizer,
        request.event,
        "event.settings.general:write",
        request=request,
    ):
        return []
    url = resolve(request.path_info)
    return [
        {
            "label": _("Countdown"),
            "url": reverse(
                "plugins:pretix_countdown:control.countdown.settings",
                kwargs={
                    "event": request.event.slug,
                    "organizer": request.organizer.slug,
                },
            ),
            "active": url.namespace == "plugins:pretix_countdown"
            and url.url_name == "control.countdown.settings",
        }
    ]

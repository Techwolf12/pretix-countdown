from django import forms
from django.urls import reverse
from django.utils.html import format_html
from django.utils.timezone import now
from django.utils.translation import gettext, gettext_lazy as _
from i18nfield.forms import I18nFormField, I18nTextInput
from pretix.base.forms import SettingsForm
from pretix.base.models import Event
from pretix.control.views.event import EventSettingsFormView, EventSettingsViewMixin

from .formats import (
    COUNTDOWN_FORMAT_CHOICES,
    COUNTDOWN_FORMATS,
    COUNTDOWN_PLACEHOLDERS,
    DATE_FORMAT_CHOICES,
    EXAMPLE_SECONDS,
    HEADING_PLACEHOLDERS,
    PLACEHOLDER,
    PRODUCT_TEXT_PLACEHOLDERS,
    format_date,
    render_countdown,
    unit_labels,
    unknown_placeholders,
)


def i18n_values(value) -> list:
    """Return the non-empty texts of all languages of an i18n field value."""
    data = getattr(value, "data", value)
    if isinstance(data, dict):
        return [v for v in data.values() if v]
    return [data] if data else []


def placeholder_list(names) -> str:
    return ", ".join("{%s}" % n for n in names)


class CountdownSettingsForm(SettingsForm):
    countdown__event = forms.BooleanField(
        required=False,
        label=_("Show a countdown to the start of ticket sales"),
        help_text=_(
            "Shown on the shop's front page until the start of presale that is set in "
            "the event settings. In an event series, each date counts down to its own "
            "presale start."
        ),
    )
    countdown__event_heading = I18nFormField(
        required=False,
        widget=I18nTextInput,
        label=_("Countdown heading"),
        help_text=_(
            'Leave empty to use "Ticket sales open in". You can use {date} for the date '
            "and time ticket sales open."
        ),
    )
    countdown__items = forms.BooleanField(
        required=False,
        label=_("Show a countdown on products that are not available yet"),
        help_text=_(
            'Counts down to the "Available from" date of a product or variation. The '
            "product is only listed before that date if it is set to show info on why "
            "it is unavailable. Otherwise pretix hides it until then."
        ),
    )
    countdown__product_text = I18nFormField(
        required=False,
        widget=I18nTextInput,
        label=_("Product text"),
        help_text=_(
            'Leave empty to use "Available in {countdown}". {countdown} is replaced with '
            "the remaining time and {date} with the date and time the product goes on "
            "sale."
        ),
    )
    countdown__format = forms.ChoiceField(
        choices=COUNTDOWN_FORMAT_CHOICES,
        widget=forms.RadioSelect,
        label=_("Countdown format"),
    )
    countdown__format_custom = I18nFormField(
        required=False,
        widget=I18nTextInput,
        label=_("Custom countdown format"),
    )
    countdown__date_format = forms.ChoiceField(
        choices=DATE_FORMAT_CHOICES,
        widget=forms.RadioSelect,
        label=_("Date format"),
        help_text=_(
            "Used for {date} and shown instead of the countdown when JavaScript is not "
            "available, e.g. in the embedded widget."
        ),
    )
    countdown__date_format_custom = forms.CharField(
        required=False,
        label=_("Custom date format"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = unit_labels()
        self.fields["countdown__format"].choices = [
            (
                (
                    key,
                    self._with_example(
                        label,
                        render_countdown(
                            str(COUNTDOWN_FORMATS[key]), EXAMPLE_SECONDS, labels
                        ),
                    ),
                )
                if key in COUNTDOWN_FORMATS
                else (key, label)
            )
            for key, label in COUNTDOWN_FORMAT_CHOICES
        ]
        sample = self.obj.presale_start or now()
        self.fields["countdown__date_format"].choices = [
            (
                (
                    key,
                    self._with_example(
                        label, format_date(sample, self.obj.timezone, key)
                    ),
                )
                if key != "custom"
                else (key, label)
            )
            for key, label in DATE_FORMAT_CHOICES
        ]

        custom = len(COUNTDOWN_FORMAT_CHOICES) - 1
        self.fields["countdown__format_custom"].widget.attrs[
            "data-display-dependency"
        ] = f"#id_countdown__format_{custom}"
        self.fields["countdown__format_custom"].help_text = format_html(
            "{}<br>{}",
            gettext("Available placeholders: {placeholders}.").format(
                placeholders=placeholder_list(COUNTDOWN_PLACEHOLDERS)
            ),
            gettext(
                "{hh}, {mm} and {ss} are padded to two digits. {days_label} etc. "
                'become "day" or "days" to match the number. Text in square brackets '
                "is left out while all numbers in it are zero. Units you leave out are "
                "added to the next smaller unit. Example: {example}"
            ).replace("{example}", "[{days} {days_label} ]{hh}:{mm}:{ss}"),
        )

        custom = len(DATE_FORMAT_CHOICES) - 1
        self.fields["countdown__date_format_custom"].widget.attrs.update(
            {
                "data-display-dependency": f"#id_countdown__date_format_{custom}",
                "placeholder": "l j F Y, H:i",
            }
        )
        self.fields["countdown__date_format_custom"].help_text = format_html(
            '{} <a href="https://docs.djangoproject.com/en/stable/ref/templates/builtins/#date" '
            'target="_blank" rel="noopener">{}</a>',
            gettext("Uses Django's date format characters."),
            gettext("Show all format characters"),
        )

    @staticmethod
    def _with_example(label, example):
        return format_html("{} <span class='text-muted'>({})</span>", label, example)

    def _check_placeholders(self, name, allowed):
        for text in i18n_values(self.cleaned_data.get(name)):
            unknown = unknown_placeholders(text, allowed)
            if unknown:
                self.add_error(
                    name,
                    gettext(
                        "Unknown placeholder: {placeholders}. Available: {allowed}."
                    ).format(
                        placeholders=placeholder_list(unknown),
                        allowed=placeholder_list(allowed),
                    ),
                )
                return

    def clean(self):
        data = super().clean()
        self._check_placeholders("countdown__event_heading", HEADING_PLACEHOLDERS)
        self._check_placeholders("countdown__product_text", PRODUCT_TEXT_PLACEHOLDERS)
        self._check_placeholders("countdown__format_custom", COUNTDOWN_PLACEHOLDERS)

        for text in i18n_values(data.get("countdown__product_text")):
            if "{countdown}" not in text:
                self.add_error(
                    "countdown__product_text",
                    gettext("The product text needs to contain {countdown}."),
                )
                break

        if data.get("countdown__format") == "custom":
            texts = i18n_values(data.get("countdown__format_custom"))
            if not texts:
                self.add_error(
                    "countdown__format_custom",
                    gettext("Enter a format or choose one of the other formats."),
                )
            elif any(not PLACEHOLDER.search(t) for t in texts):
                self.add_error(
                    "countdown__format_custom",
                    gettext("The format needs to contain at least one placeholder."),
                )

        if data.get("countdown__date_format") == "custom" and not data.get(
            "countdown__date_format_custom"
        ):
            self.add_error(
                "countdown__date_format_custom",
                gettext("Enter a format or choose one of the other formats."),
            )
        return data


class SettingsView(EventSettingsViewMixin, EventSettingsFormView):
    model = Event
    form_class = CountdownSettingsForm
    template_name = "pretix_countdown/settings.html"
    permission = "event.settings.general:write"

    def get_success_url(self):
        return reverse(
            "plugins:pretix_countdown:control.countdown.settings",
            kwargs={
                "organizer": self.request.event.organizer.slug,
                "event": self.request.event.slug,
            },
        )

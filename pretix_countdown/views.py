from django import forms
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from i18nfield.forms import I18nFormField, I18nTextInput
from pretix.base.forms import SettingsForm
from pretix.base.models import Event
from pretix.control.views.event import EventSettingsFormView, EventSettingsViewMixin


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
        help_text=_('Leave empty to use "Ticket sales open in".'),
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

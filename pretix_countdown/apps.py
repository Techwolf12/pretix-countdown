from django.utils.translation import gettext_lazy

from . import __version__

try:
    from pretix.base.plugins import PluginConfig
except ImportError:
    raise RuntimeError("Please use pretix 2026.3 or above to run this plugin!")


class PluginApp(PluginConfig):
    name = "pretix_countdown"
    verbose_name = "Countdown"

    class PretixPluginMeta:
        name = gettext_lazy("Countdown")
        author = "Christiaan de Die le Clercq (techwolf12)"
        description = gettext_lazy(
            "Shows a live countdown to the start of ticket sales and of individual "
            "products"
        )
        visible = True
        version = __version__
        category = "FEATURE"
        compatibility = "pretix>=2026.3.0"
        settings_links = [
            (
                (gettext_lazy("Settings"), gettext_lazy("Countdown")),
                "plugins:pretix_countdown:control.countdown.settings",
                {},
            ),
        ]

    def ready(self):
        from . import signals  # NOQA

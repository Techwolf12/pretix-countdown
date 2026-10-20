Countdown
==========================

This is a plugin for `pretix`_.

Shows a live countdown in the ticket shop until ticket sales open:

* **Event countdown:** a banner on the shop's front page that counts down to the *Start of presale* set in the event
  settings. In an event series, each date counts down to its own presale start.
* **Product countdown:** products and variations that are not available yet show "Available in 2 days 04:13:22"
  until their *Available from* date. pretix only lists such a product before that date if its availability mode is
  set to show info on why it is unavailable. Otherwise the product stays hidden until then.

The plugin uses the dates you already set in pretix, so there is nothing extra to keep in sync. When a countdown
reaches zero, the page reloads so visitors can buy right away. pretix itself still decides whether something can be
bought, so the countdown can never open sales early. Without JavaScript, for example in the embedded widget, the
opening date and time is shown instead.

Configure it under *Settings → Countdown* in your event. You can turn both countdowns on or off and change the
heading of the event countdown.

To install:
``pip3 install pretix-countdown && python3 -m pretix migrate && python3 -m pretix rebuild && service pretix-web restart``

Then just activate it in your event config.

Development setup
-----------------

1. Make sure that you have a working `pretix development setup`_.

2. Clone this repository.

3. Activate the virtual environment you use for pretix development.

4. Execute ``pip3 install -e .`` within this directory to register this application with pretix's plugin registry.

5. Execute ``make`` within this directory to compile translations.

6. Restart your local pretix server. You can now use the plugin from this repository for your events by enabling it in
   the 'plugins' tab in the settings.

This plugin has CI set up to enforce a few code style rules. To check locally, you need these packages installed::

    pip install flake8 isort black docformatter

To check your plugin for rule violations, run::

    docformatter --check -r .
    black --check .
    isort -c .
    flake8 .

You can auto-fix some of these issues by running::

    docformatter -r .
    isort .
    black .

To automatically check for these issues before you commit, you can run ``.install-hooks``.


License
-------


Copyright 2026 Christiaan de Die le Clercq (techwolf12)

Released under the terms of the Apache License 2.0



.. _pretix: https://github.com/pretix/pretix
.. _pretix development setup: https://docs.pretix.eu/en/latest/development/setup.html

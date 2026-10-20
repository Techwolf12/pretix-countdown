import pytest
from decimal import Decimal
from django.utils.timezone import now
from django_scopes import scopes_disabled
from pretix.base.models import Event, Item, Organizer, Team, User


@pytest.fixture
def organizer():
    return Organizer.objects.create(name="Dummy", slug="dummy")


@pytest.fixture
def event(organizer):
    return Event.objects.create(
        organizer=organizer,
        name="Dummy",
        slug="dummy",
        date_from=now(),
        live=True,
        plugins="pretix_countdown",
    )


@pytest.fixture
def item(event):
    item = Item.objects.create(
        event=event,
        name="Ticket",
        default_price=Decimal("23.00"),
        available_from_mode=Item.UNAVAIL_MODE_INFO,
    )
    quota = event.quotas.create(name="Tickets", size=100)
    quota.items.add(item)
    return item


@pytest.fixture
def admin_client(client, organizer, event):
    user = User.objects.create_user("dummy@dummy.dummy", "dummy")
    team = Team.objects.create(
        organizer=organizer, all_events=True, all_event_permissions=True
    )
    team.members.add(user)
    client.login(email="dummy@dummy.dummy", password="dummy")
    return client


@pytest.fixture(autouse=True)
def no_scopes():
    # pretix activates the organizer scope before plugin signals fire. Outside
    # of a request we have no scope, so disable scoping for the tests.
    with scopes_disabled():
        yield

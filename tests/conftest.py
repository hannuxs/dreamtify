import pytest
from django.contrib.auth import get_user_model

from apps.core.actors import Actor

from . import factories


@pytest.fixture
def fanmeet(db):
    return factories.make_fanmeet()


@pytest.fixture
def admin_user(db):
    return get_user_model().objects.create_user("admin1", password="rahasia-panjang-1", is_staff=True)


@pytest.fixture
def admin(admin_user):
    """Actor admin untuk services."""
    return Actor.staff(admin_user, ip="127.0.0.1")

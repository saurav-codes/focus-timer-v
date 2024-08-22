import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def user():
    User = get_user_model()
    return User.objects.create_user(username="testuser", password="12345")


# Add more fixtures as needed

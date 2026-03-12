import sys
import os
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_admin_login_page_loads(client):
    response = client.get("/admin-login")
    assert response.status_code == 200

def test_admin_login_success(client):
    response = client.post("/admin-login", data={
        "username": "agent1",
        "password": "agent123"
    }, follow_redirects=True)

    assert response.status_code == 200
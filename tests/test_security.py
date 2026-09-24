"""The app only answers requests meant for this computer, and only accepts real JSON.

See PROJECT_SPEC.md section 10, "Security".
"""
import pytest


@pytest.mark.parametrize("host", ["127.0.0.1:8000", "localhost:8000", "localhost"])
def test_requests_addressed_to_this_computer_are_answered(client, host):
    assert client.get("/locations", headers={"Host": host}).status_code == 200


@pytest.mark.parametrize("host", ["evil.example", "192.168.1.20:8000"])
def test_requests_addressed_to_any_other_host_are_refused(client, host):
    # evil.example: a web page that pointed its own domain at 127.0.0.1 (DNS rebinding).
    # 192.168.1.20: someone on the same network, if the app were started with --host 0.0.0.0.
    assert client.get("/locations", headers={"Host": host}).status_code == 400


def test_forged_cross_site_favorite_is_rejected(client):
    # Another website can make a browser send a "plain text" POST without asking first.
    response = client.post("/favorites", content='{"keyword": "forged"}', headers={"Content-Type": "text/plain"})

    assert response.status_code == 422
    assert client.get("/favorites").json() == []

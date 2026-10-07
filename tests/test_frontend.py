"""Tests for the served browser interface and its static assets."""


def test_frontend_page_is_served(client):
    response = client.get("/app")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Create certificates" in response.text
    assert "/static/styles.css" in response.text
    assert "/static/app.js" in response.text


def test_frontend_assets_are_served(client):
    css_response = client.get("/static/styles.css")
    js_response = client.get("/static/app.js")

    assert css_response.status_code == 200
    assert "workspace-grid" in css_response.text
    assert js_response.status_code == 200
    assert "/api/jobs/upload" in js_response.text


def test_root_service_endpoint_remains_available(client):
    response = client.get("/", headers={"accept": "application/json"})

    assert response.status_code == 200
    assert response.json()["status"] == "online"


def test_root_serves_frontend_to_browsers(client):
    response = client.get("/", headers={"accept": "text/html"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Create certificates" in response.text

"""Automated Unit and Endpoint Tests for CloudPulse Microservice."""

import pytest
from fastapi.testclient import TestClient

from app.main import SERVICE_HEALTH_STATUS, SURGE_EVENTS_COUNT, app, state


@pytest.fixture(autouse=True)
def reset_state():
    """Reset microservice state before and after each test."""
    state["outage"] = False
    state["surge_active"] = False
    SERVICE_HEALTH_STATUS.set(1)
    yield
    state["outage"] = False
    state["surge_active"] = False
    SERVICE_HEALTH_STATUS.set(1)


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)


def test_get_dashboard(client):
    """Test GET / returns HTTP 200 and contains 'CloudPulse'."""
    response = client.get("/")
    assert response.status_code == 200
    assert "CloudPulse" in response.text
    assert (
        "CloudPulse — High-Availability Cloud Status & Incident Telemetry Platform"
        in response.text
    )
    assert "ONLINE — 200 OK" in response.text
    assert "Total Requests Served" in response.text
    assert "Active Flash-Sale Surge status" in response.text


def test_get_healthz_healthy(client):
    """Test GET /healthz returns HTTP 200 when healthy."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "pod" in data


def test_simulate_surge_increments_metrics(client):
    """Test POST /simulate-surge returns HTTP 200 and increments metrics."""
    initial_surge_count = SURGE_EVENTS_COUNT._value.get()

    response = client.post("/simulate-surge")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "surge_initiated"
    assert data["duration_seconds"] == 30
    assert data["surge_active"] is True

    # Verify metrics incremented
    new_surge_count = SURGE_EVENTS_COUNT._value.get()
    assert new_surge_count > initial_surge_count

    # Check metrics endpoint output
    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    metrics_text = metrics_response.text
    assert "cloudpulse_flash_surge_events_total" in metrics_text
    assert "cloudpulse_http_requests_total" in metrics_text


def test_simulate_outage_toggle(client):
    """Test POST /simulate-outage toggles /healthz to HTTP 503 and back to HTTP 200."""
    # Step 1: Baseline healthy check
    resp_healthy = client.get("/healthz")
    assert resp_healthy.status_code == 200
    assert resp_healthy.json()["status"] == "healthy"

    # Step 2: Toggle outage ON -> 503
    toggle_on_resp = client.post("/simulate-outage")
    assert toggle_on_resp.status_code == 200
    assert toggle_on_resp.json()["status"] == "unhealthy"
    assert toggle_on_resp.json()["outage_mode"] is True

    resp_outage = client.get("/healthz")
    assert resp_outage.status_code == 503
    assert resp_outage.json()["status"] == "unhealthy"

    # Step 3: Call second time -> restores healthy (200)
    toggle_off_resp = client.post("/simulate-outage")
    assert toggle_off_resp.status_code == 200
    assert toggle_off_resp.json()["status"] == "healthy"
    assert toggle_off_resp.json()["outage_mode"] is False

    resp_restored = client.get("/healthz")
    assert resp_restored.status_code == 200
    assert resp_restored.json()["status"] == "healthy"


def test_get_metrics_exposes_request_total(client):
    """Test GET /metrics returns HTTP 200 and exposes cloudpulse_http_requests_total."""
    client.get("/healthz")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "cloudpulse_http_requests_total" in response.text
    assert "cloudpulse_service_health_status" in response.text


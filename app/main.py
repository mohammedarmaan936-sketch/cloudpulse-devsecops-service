"""CloudPulse — High-Availability Cloud Status & Incident Telemetry Platform.

FastAPI microservice exposing high-availability telemetry, health endpoints,
Prometheus metrics, and interactive chaos/surge simulation capabilities.
"""

import asyncio
import os
import socket
import time
from typing import Any, Dict

from fastapi import FastAPI, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Initialize FastAPI application
app = FastAPI(
    title="CloudPulse Telemetry Platform",
    description="High-Availability Cloud Status & Incident Telemetry Platform",
    version=os.getenv("APP_VERSION", "v1.0.0"),
)


def _get_or_create_metric(collector_cls, name: str, documentation: str, *args, **kwargs):
    """Retrieve existing metric collector or register a new one to avoid conflicts."""
    if name in REGISTRY._names_to_collectors:
        return REGISTRY._names_to_collectors[name]
    return collector_cls(name, documentation, *args, **kwargs)


# Prometheus Metrics Definitions
REQUEST_COUNT: Counter = _get_or_create_metric(
    Counter,
    "cloudpulse_http_requests_total",
    "Total HTTP requests handled by CloudPulse",
    ["method", "endpoint", "status"],
)

SURGE_EVENTS_COUNT: Counter = _get_or_create_metric(
    Counter,
    "cloudpulse_flash_surge_events_total",
    "Total flash-sale surge events triggered",
)

SERVICE_HEALTH_STATUS: Gauge = _get_or_create_metric(
    Gauge,
    "cloudpulse_service_health_status",
    "Current service health status (1 = healthy, 0 = degraded/unhealthy)",
)

REQUEST_LATENCY: Histogram = _get_or_create_metric(
    Histogram,
    "cloudpulse_request_duration_seconds",
    "HTTP request latency in seconds",
    ["endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

# Set initial health gauge to 1 (healthy)
SERVICE_HEALTH_STATUS.set(1)

# Application state
state: Dict[str, Any] = {
    "outage": False,
    "surge_active": False,
    "total_requests": 0,
}


@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    """Middleware to track request duration and Prometheus request counters."""
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    endpoint = request.url.path
    method = request.method
    status_code = str(response.status_code)

    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status_code).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
    state["total_requests"] += 1

    return response


async def _simulate_surge_task() -> None:
    """Asynchronously simulate a 30-second flash-sale traffic spike without blocking the event loop."""
    state["surge_active"] = True
    try:
        for _ in range(30):
            # Simulate burst traffic across key shopping endpoints
            REQUEST_COUNT.labels(
                method="GET", endpoint="/api/v1/checkout", status="200"
            ).inc(25)
            REQUEST_LATENCY.labels(endpoint="/api/v1/checkout").observe(0.028)
            state["total_requests"] += 25
            await asyncio.sleep(1)
    finally:
        state["surge_active"] = False


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CloudPulse — High-Availability Cloud Status & Incident Telemetry Platform</title>
    <style>
        :root {
            --bg-primary: #0a0e1a;
            --bg-secondary: #111827;
            --bg-card: rgba(17, 24, 39, 0.75);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-primary: #f9fafb;
            --text-secondary: #9ca3af;
            --text-muted: #6b7280;
            --accent-cyan: #06b6d4;
            --accent-blue: #3b82f6;
            --accent-purple: #8b5cf6;
            --status-green: #10b981;
            --status-green-glow: rgba(16, 185, 129, 0.35);
            --status-red: #ef4444;
            --status-red-glow: rgba(239, 68, 68, 0.35);
            --status-amber: #f59e0b;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        body {
            background-color: var(--bg-primary);
            background-image:
                radial-gradient(circle at 15% 15%, rgba(6, 182, 212, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 85% 85%, rgba(139, 92, 246, 0.08) 0%, transparent 40%);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            padding: 24px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            width: 100%;
        }

        /* Header */
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 28px;
            flex-wrap: wrap;
            gap: 16px;
        }

        .brand-section {
            display: flex;
            align-items: center;
            gap: 14px;
        }

        .brand-logo {
            width: 44px;
            height: 44px;
            border-radius: 12px;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 20px rgba(6, 182, 212, 0.35);
        }

        .brand-logo svg {
            width: 26px;
            height: 26px;
            fill: none;
            stroke: #ffffff;
            stroke-width: 2.2;
            stroke-linecap: round;
            stroke-linejoin: round;
        }

        .brand-titles h1 {
            font-size: 1.45rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            background: linear-gradient(to right, #ffffff, #d1d5db);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .brand-titles p {
            font-size: 0.85rem;
            color: var(--text-secondary);
        }

        .header-meta {
            display: flex;
            gap: 12px;
            align-items: center;
            flex-wrap: wrap;
        }

        .meta-tag {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 0.8rem;
            color: var(--text-secondary);
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

        .meta-tag strong {
            color: var(--text-primary);
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }

        /* Hero Status Banner */
        .status-hero {
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 28px;
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: relative;
            overflow: hidden;
            flex-wrap: wrap;
            gap: 20px;
        }

        .status-info {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .status-headline {
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--text-muted);
            font-weight: 600;
        }

        .badge-live {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            padding: 10px 20px;
            border-radius: 9999px;
            font-size: 1.15rem;
            font-weight: 700;
            letter-spacing: -0.01em;
            transition: all 0.3s ease;
        }

        .badge-online {
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.4);
            box-shadow: 0 0 25px var(--status-green-glow);
        }

        .badge-degraded {
            background: rgba(239, 68, 68, 0.15);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.4);
            box-shadow: 0 0 25px var(--status-red-glow);
        }

        .pulsing-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
        }

        .badge-online .pulsing-dot {
            background-color: var(--status-green);
            box-shadow: 0 0 8px var(--status-green);
            animation: pulse-green 1.8s infinite;
        }

        .badge-degraded .pulsing-dot {
            background-color: var(--status-red);
            box-shadow: 0 0 8px var(--status-red);
            animation: pulse-red 1.2s infinite;
        }

        @keyframes pulse-green {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { transform: scale(1.1); box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }

        @keyframes pulse-red {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
            70% { transform: scale(1.15); box-shadow: 0 0 0 12px rgba(239, 68, 68, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }

        .status-description {
            font-size: 0.95rem;
            color: var(--text-secondary);
        }

        /* Telemetry Cards Grid */
        .grid-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }

        .card {
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 22px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            transition: transform 0.2s ease, border-color 0.2s ease;
        }

        .card:hover {
            transform: translateY(-2px);
            border-color: rgba(255, 255, 255, 0.15);
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .card-label {
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            font-weight: 600;
        }

        .card-icon {
            color: var(--accent-cyan);
            font-size: 1.1rem;
        }

        .card-value {
            font-size: 1.7rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            color: var(--text-primary);
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }

        .card-subtext {
            font-size: 0.8rem;
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            gap: 6px;
        }

        /* Control Panel */
        .controls-card {
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 24px;
        }

        .controls-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .controls-desc {
            font-size: 0.88rem;
            color: var(--text-secondary);
            margin-bottom: 20px;
        }

        .btn-group {
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
        }

        .btn {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            padding: 12px 24px;
            border-radius: 10px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            border: none;
            outline: none;
        }

        .btn-surge {
            background: linear-gradient(135deg, #2563eb, #06b6d4);
            color: #ffffff;
            box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
        }

        .btn-surge:hover {
            box-shadow: 0 6px 20px rgba(6, 182, 212, 0.5);
            transform: translateY(-2px);
        }

        .btn-surge:active {
            transform: translateY(0);
        }

        .btn-outage {
            background: linear-gradient(135deg, #d97706, #dc2626);
            color: #ffffff;
            box-shadow: 0 4px 14px rgba(220, 38, 38, 0.35);
        }

        .btn-outage:hover {
            box-shadow: 0 6px 20px rgba(220, 38, 38, 0.5);
            transform: translateY(-2px);
        }

        .btn-outage:active {
            transform: translateY(0);
        }

        /* Endpoints & Activity Log */
        .footer-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }

        @media (max-width: 800px) {
            .footer-grid {
                grid-template-columns: 1fr;
            }
        }

        .panel {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 20px;
        }

        .panel-title {
            font-size: 0.9rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .endpoint-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .endpoint-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(0, 0, 0, 0.25);
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }

        .endpoint-item a {
            color: var(--accent-cyan);
            text-decoration: none;
        }

        .endpoint-item a:hover {
            text-decoration: underline;
        }

        .endpoint-method {
            background: rgba(6, 182, 212, 0.2);
            color: #22d3ee;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }

        .log-terminal {
            background: #05070d;
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 8px;
            padding: 12px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 0.8rem;
            color: #10b981;
            height: 140px;
            overflow-y: auto;
            line-height: 1.5;
        }

        .log-entry {
            margin-bottom: 4px;
        }

        .log-time {
            color: var(--text-muted);
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            <div class="brand-section">
                <div class="brand-logo">
                    <svg viewBox="0 0 24 24">
                        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
                    </svg>
                </div>
                <div class="brand-titles">
                    <h1>CloudPulse</h1>
                    <p>High-Availability Cloud Status & Incident Telemetry Platform</p>
                </div>
            </div>
            <div class="header-meta">
                <div class="meta-tag">Pod: <strong id="header-pod">{{HOSTNAME}}</strong></div>
                <div class="meta-tag">Version: <strong id="header-version">{{VERSION}}</strong></div>
                <div class="meta-tag">UTC: <strong id="clock">00:00:00</strong></div>
            </div>
        </header>

        <!-- Status Hero Banner -->
        <div class="status-hero">
            <div class="status-info">
                <div class="status-headline">Live Microservice Status</div>
                <div class="status-description" id="status-desc">{{STATUS_DESC}}</div>
            </div>
            <div>
                <span id="status-badge" class="badge-live {{STATUS_CLASS}}">
                    <span class="pulsing-dot"></span>
                    <span id="badge-text">{{STATUS_BADGE_TEXT}}</span>
                </span>
            </div>
        </div>

        <!-- Telemetry Cards Grid -->
        <div class="grid-cards">
            <!-- Card 1: System Health -->
            <div class="card">
                <div class="card-header">
                    <span class="card-label">Health Check status</span>
                    <span class="card-icon">⚡</span>
                </div>
                <div class="card-value" id="card-health">{{HEALTH_TEXT}}</div>
                <div class="card-subtext" id="card-health-sub">Kubernetes /healthz Probe</div>
            </div>

            <!-- Card 2: Total Requests Served -->
            <div class="card">
                <div class="card-header">
                    <span class="card-label">Total Requests Served</span>
                    <span class="card-icon">📈</span>
                </div>
                <div class="card-value" id="card-requests">{{TOTAL_REQUESTS}}</div>
                <div class="card-subtext">Prometheus Counter Aggregate</div>
            </div>

            <!-- Card 3: Active Flash-Sale Surge Status -->
            <div class="card">
                <div class="card-header">
                    <span class="card-label">Active Flash-Sale Surge status</span>
                    <span class="card-icon">🔥</span>
                </div>
                <div class="card-value" id="card-surge">{{SURGE_STATUS_TEXT}}</div>
                <div class="card-subtext" id="card-surge-sub">{{SURGE_SUBTEXT}}</div>
            </div>

            <!-- Card 4: Hostname & Scaling -->
            <div class="card">
                <div class="card-header">
                    <span class="card-label">Container / Pod Hostname</span>
                    <span class="card-icon">☸️</span>
                </div>
                <div class="card-value" style="font-size: 1.15rem; word-break: break-all;" id="card-pod">{{HOSTNAME}}</div>
                <div class="card-subtext">Version: <strong style="color: var(--accent-cyan);">{{VERSION}}</strong></div>
            </div>
        </div>

        <!-- Interactive Control Console -->
        <div class="controls-card">
            <div class="controls-title">⚙️ Interactive Chaos & Load Testing Suite</div>
            <div class="controls-desc">Trigger real-time telemetry events and Kubernetes probe failover simulations via asynchronous background tasks:</div>
            <div class="btn-group">
                <button id="btn-surge" class="btn btn-surge" onclick="triggerSurge()">
                    ⚡ Simulate Flash-Sale Traffic Surge
                </button>
                <button id="btn-outage" class="btn btn-outage" onclick="toggleOutage()">
                    🛡️ Toggle Server Outage / Auto-Heal Test
                </button>
            </div>
        </div>

        <!-- Endpoints & Terminal Log Preview -->
        <div class="footer-grid">
            <div class="panel">
                <div class="panel-title">Active Observability Endpoints</div>
                <div class="endpoint-list">
                    <div class="endpoint-item">
                        <a href="/healthz" target="_blank">GET /healthz</a>
                        <span class="endpoint-method">PROBE</span>
                    </div>
                    <div class="endpoint-item">
                        <a href="/metrics" target="_blank">GET /metrics</a>
                        <span class="endpoint-method">PROMETHEUS</span>
                    </div>
                    <div class="endpoint-item">
                        <a href="/api/status" target="_blank">GET /api/status</a>
                        <span class="endpoint-method">JSON</span>
                    </div>
                </div>
            </div>

            <div class="panel">
                <div class="panel-title">Live Telemetry & Incident Event Log</div>
                <div class="log-terminal" id="terminal-log">
                    <div class="log-entry"><span class="log-time">[INIT]</span> CloudPulse Telemetry Engine online.</div>
                    <div class="log-entry"><span class="log-time">[INFO]</span> Connected to Prometheus metrics registry.</div>
                    <div class="log-entry"><span class="log-time">[OK]</span> Kubernetes liveness & readiness probes healthy.</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function updateClock() {
            const now = new Date();
            document.getElementById("clock").innerText = now.toTimeString().split(' ')[0] + " UTC";
        }
        setInterval(updateClock, 1000);
        updateClock();

        function addLog(tag, message) {
            const log = document.getElementById("terminal-log");
            const entry = document.createElement("div");
            entry.className = "log-entry";
            const timeStr = new Date().toTimeString().split(' ')[0];
            entry.innerHTML = `<span class="log-time">[${timeStr} ${tag}]</span> ${message}`;
            log.appendChild(entry);
            log.scrollTop = log.scrollHeight;
        }

        async function fetchStatus() {
            try {
                const res = await fetch("/api/status");
                if (!res.ok) throw new Error("HTTP error " + res.status);
                const data = await res.json();

                // Update Hostname & Version
                document.getElementById("header-pod").innerText = data.pod;
                document.getElementById("card-pod").innerText = data.pod;
                document.getElementById("header-version").innerText = data.app_version;

                // Update Total Requests
                document.getElementById("card-requests").innerText = Number(data.total_requests).toLocaleString();

                // Update Status Badge & Health Card
                const badge = document.getElementById("status-badge");
                const badgeText = document.getElementById("badge-text");
                const statusDesc = document.getElementById("status-desc");
                const cardHealth = document.getElementById("card-health");
                const cardHealthSub = document.getElementById("card-health-sub");

                if (data.outage_mode) {
                    badge.className = "badge-live badge-degraded";
                    badgeText.innerText = "DEGRADED — 503 OUTAGE";
                    statusDesc.innerText = "Incident simulation active: Service returning HTTP 503 to test auto-healing / failover";
                    cardHealth.innerText = "503 OUTAGE";
                    cardHealth.style.color = "var(--status-red)";
                    cardHealthSub.innerText = "Health Check status: DEGRADED";
                } else {
                    badge.className = "badge-live badge-online";
                    badgeText.innerText = "ONLINE — 200 OK";
                    statusDesc.innerText = "All cluster microservice instances reporting nominal operation within SLO";
                    cardHealth.innerText = "200 OK";
                    cardHealth.style.color = "var(--status-green)";
                    cardHealthSub.innerText = "Health Check status: HEALTHY";
                }

                // Update Surge Card
                const cardSurge = document.getElementById("card-surge");
                const cardSurgeSub = document.getElementById("card-surge-sub");
                if (data.surge_active) {
                    cardSurge.innerText = "ACTIVE (Spike)";
                    cardSurge.style.color = "var(--accent-cyan)";
                    cardSurgeSub.innerText = "Flash-Sale Surge Status: ACTIVE";
                } else {
                    cardSurge.innerText = "IDLE";
                    cardSurge.style.color = "var(--text-primary)";
                    cardSurgeSub.innerText = "Flash-Sale Surge Status: NORMAL";
                }
            } catch (err) {
                console.error("Telemetry sync error:", err);
            }
        }

        async function triggerSurge() {
            const btn = document.getElementById("btn-surge");
            btn.disabled = true;
            btn.innerText = "⚡ Spiking Traffic (30s)...";
            addLog("BURST", "Flash-sale traffic surge simulation initiated across cluster.");
            try {
                const res = await fetch("/simulate-surge", { method: "POST" });
                const data = await res.json();
                addLog("BURST", `Traffic spike event registered. Response: ${data.status}`);
                await fetchStatus();
            } catch (err) {
                addLog("ERROR", `Failed to initiate surge: ${err}`);
            } finally {
                setTimeout(() => {
                    btn.disabled = false;
                    btn.innerText = "⚡ Simulate Flash-Sale Traffic Surge";
                }, 30000);
            }
        }

        async function toggleOutage() {
            const btn = document.getElementById("btn-outage");
            addLog("CHAOS", "Toggling server outage simulation...");
            try {
                const res = await fetch("/simulate-outage", { method: "POST" });
                const data = await res.json();
                addLog("CHAOS", `Outage state toggled. New Status: ${data.status} (HTTP ${data.health_status_code})`);
                await fetchStatus();
            } catch (err) {
                addLog("ERROR", `Failed to toggle outage state: ${err}`);
            }
        }

        // Live telemetry polling loop every 1.5 seconds
        setInterval(fetchStatus, 1500);
    </script>
</body>
</html>
"""


def render_dashboard_html(is_outage: bool, is_surge: bool, requests_count: int) -> str:
    """Render the dashboard HTML with current server-side telemetry values injected."""
    hostname = socket.gethostname()
    version = os.getenv("APP_VERSION", "v1.0.0")

    if is_outage:
        status_class = "badge-degraded"
        status_badge_text = "DEGRADED — 503 OUTAGE"
        status_desc = "Incident simulation active: Service returning HTTP 503 to test auto-healing / failover"
        health_text = "503 OUTAGE"
    else:
        status_class = "badge-online"
        status_badge_text = "ONLINE — 200 OK"
        status_desc = "All cluster microservice instances reporting nominal operation within SLO"
        health_text = "200 OK"

    if is_surge:
        surge_status_text = "ACTIVE (Spike)"
        surge_subtext = "Flash-Sale Surge Status: ACTIVE"
    else:
        surge_status_text = "IDLE"
        surge_subtext = "Flash-Sale Surge Status: NORMAL"

    rendered = (
        HTML_TEMPLATE.replace("{{HOSTNAME}}", hostname)
        .replace("{{VERSION}}", version)
        .replace("{{STATUS_CLASS}}", status_class)
        .replace("{{STATUS_BADGE_TEXT}}", status_badge_text)
        .replace("{{STATUS_DESC}}", status_desc)
        .replace("{{HEALTH_TEXT}}", health_text)
        .replace("{{TOTAL_REQUESTS}}", f"{requests_count:,}")
        .replace("{{SURGE_STATUS_TEXT}}", surge_status_text)
        .replace("{{SURGE_SUBTEXT}}", surge_subtext)
    )
    return rendered


@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    """Serve the modern dark-mode telemetry dashboard."""
    return HTMLResponse(
        content=render_dashboard_html(
            is_outage=state["outage"],
            is_surge=state["surge_active"],
            requests_count=state["total_requests"],
        )
    )


@app.get("/healthz")
def healthz():
    """Kubernetes liveness and readiness probe endpoint."""
    hostname = socket.gethostname()
    if state["outage"]:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "pod": hostname},
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "healthy", "pod": hostname},
    )


@app.post("/simulate-surge")
async def simulate_surge():
    """Trigger simulated flash-sale traffic surge metrics without blocking the event loop."""
    SURGE_EVENTS_COUNT.inc()
    REQUEST_COUNT.labels(
        method="POST", endpoint="/simulate-surge", status="200"
    ).inc()
    state["total_requests"] += 1

    # Launch 30-second asynchronous non-blocking traffic burst
    asyncio.create_task(_simulate_surge_task())

    return {
        "status": "surge_initiated",
        "duration_seconds": 30,
        "surge_active": True,
        "message": "Flash-sale traffic surge simulation initiated across cluster",
    }


@app.post("/simulate-outage")
def simulate_outage():
    """Toggle internal health state between healthy (200) and unhealthy (503)."""
    state["outage"] = not state["outage"]
    if state["outage"]:
        SERVICE_HEALTH_STATUS.set(0)
        current_status = "unhealthy"
        code = 503
    else:
        SERVICE_HEALTH_STATUS.set(1)
        current_status = "healthy"
        code = 200

    return {
        "status": current_status,
        "outage_mode": state["outage"],
        "health_status_code": code,
        "pod": socket.gethostname(),
        "message": f"Service health toggled to {current_status}",
    }


@app.get("/metrics")
def metrics():
    """Expose Prometheus metrics for scraping."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/status")
def api_status():
    """Return JSON telemetry summary for UI polling."""
    return {
        "status": "unhealthy" if state["outage"] else "healthy",
        "outage_mode": state["outage"],
        "surge_active": state["surge_active"],
        "total_requests": state["total_requests"],
        "pod": socket.gethostname(),
        "app_version": os.getenv("APP_VERSION", "v1.0.0"),
    }

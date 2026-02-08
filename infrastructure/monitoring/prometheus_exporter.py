"""
Prometheus metrics exporter.

Exposes /metrics endpoint for Prometheus scraping.
Uses start_http_server() which runs in a background thread
(does not conflict with aiogram polling).
"""

import asyncio
import logging

from prometheus_client import Counter, Gauge, Info, start_http_server

logger = logging.getLogger(__name__)

# ============== System Gauges ==============

cpu_usage = Gauge(
    'bot_cpu_usage_percent',
    'Host CPU usage percentage'
)
memory_usage = Gauge(
    'bot_memory_usage_percent',
    'Host memory usage percentage'
)
memory_used_gb = Gauge(
    'bot_memory_used_gb',
    'Host memory used in GB'
)
disk_usage = Gauge(
    'bot_disk_usage_percent',
    'Host disk usage percentage'
)
load_avg_1m = Gauge(
    'bot_load_average_1m',
    '1-minute load average'
)

# ============== Application Counters ==============

messages_total = Counter(
    'bot_messages_total',
    'Total messages processed',
    ['type']  # text, voice, file, callback
)
claude_requests_total = Counter(
    'bot_claude_requests_total',
    'Total Claude API requests'
)
claude_errors_total = Counter(
    'bot_claude_errors_total',
    'Claude API errors',
    ['error_type']
)
claude_cost_usd_total = Counter(
    'bot_claude_cost_usd_total',
    'Total Claude API cost in USD'
)

# ============== Active Sessions ==============

active_tasks = Gauge(
    'bot_active_tasks',
    'Currently running Claude tasks'
)

# ============== Bot Info ==============

bot_info = Info('bot', 'Bot information')


async def update_system_metrics(monitor) -> None:
    """Background task to periodically update system metrics from SystemMonitor."""
    while True:
        try:
            metrics = await monitor.get_metrics()
            cpu_usage.set(metrics.cpu_percent)
            memory_usage.set(metrics.memory_percent)
            memory_used_gb.set(metrics.memory_used_gb)
            disk_usage.set(metrics.disk_percent)
            if metrics.load_average:
                load_avg_1m.set(metrics.load_average[0])
        except Exception as e:
            logger.debug(f"Error updating system metrics: {e}")
        await asyncio.sleep(15)


def start_metrics_server(port: int = 9090) -> None:
    """
    Start Prometheus HTTP metrics server in a background thread.

    This is non-blocking and runs alongside the Telegram bot polling.
    Metrics are available at http://localhost:{port}/metrics
    """
    try:
        start_http_server(port)
        logger.info(f"Prometheus metrics server started on port {port}")
    except Exception as e:
        logger.error(f"Failed to start Prometheus metrics server: {e}")

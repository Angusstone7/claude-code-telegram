"""
Docker Logs API - простой HTTP сервер для чтения логов контейнеров.

Доступен всем контейнерам на сервере по адресу:
  http://host.docker.internal:9999

Примеры:
  GET /containers              - список контейнеров
  GET /logs/container_name     - логи контейнера
  GET /logs/container_name?tail=100  - последние 100 строк
  GET /logs/container_name?since=1h  - логи за последний час
"""

import asyncio
import re
from aiohttp import web
import docker
from docker.errors import NotFound, APIError

# Инициализация Docker клиента
client = docker.from_env()


async def list_containers(request):
    """Список всех контейнеров."""
    try:
        containers = client.containers.list(all=True)
        result = []
        for c in containers:
            result.append({
                "id": c.short_id,
                "name": c.name,
                "status": c.status,
                "image": c.image.tags[0] if c.image.tags else c.image.short_id,
            })
        return web.json_response({"containers": result})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def get_logs(request):
    """Получить логи контейнера."""
    container_name = request.match_info.get("name")

    # Параметры
    tail = request.query.get("tail", "500")  # По умолчанию 500 строк
    since = request.query.get("since")  # Например: 1h, 30m, 2d
    follow = request.query.get("follow", "false").lower() == "true"

    try:
        container = client.containers.get(container_name)
    except NotFound:
        return web.json_response(
            {"error": f"Container '{container_name}' not found"},
            status=404
        )
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

    # Парсим since (1h -> 3600, 30m -> 1800, etc.)
    since_seconds = None
    if since:
        match = re.match(r"(\d+)([smhd])", since)
        if match:
            value, unit = int(match.group(1)), match.group(2)
            multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
            since_seconds = value * multipliers.get(unit, 1)

    try:
        # Получаем логи
        logs_kwargs = {
            "stdout": True,
            "stderr": True,
            "timestamps": True,
        }

        if tail != "all":
            logs_kwargs["tail"] = int(tail)

        if since_seconds:
            import time
            logs_kwargs["since"] = int(time.time() - since_seconds)

        if follow:
            # Streaming режим
            response = web.StreamResponse(
                status=200,
                reason="OK",
                headers={"Content-Type": "text/plain; charset=utf-8"}
            )
            await response.prepare(request)

            logs_kwargs["follow"] = True
            logs_kwargs["stream"] = True

            for line in container.logs(**logs_kwargs):
                await response.write(line)
                await asyncio.sleep(0)  # Yield control

            await response.write_eof()
            return response
        else:
            # Обычный режим
            logs = container.logs(**logs_kwargs)
            return web.Response(
                text=logs.decode("utf-8", errors="replace"),
                content_type="text/plain"
            )

    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def health(request):
    """Health check."""
    return web.json_response({"status": "ok"})


async def index(request):
    """Документация API."""
    docs = """
Docker Logs API
===============

Endpoints:
  GET /                        - эта документация
  GET /health                  - health check
  GET /containers              - список контейнеров
  GET /logs/{name}             - логи контейнера

Query параметры для /logs/{name}:
  tail=100                     - количество строк (по умолчанию 500, "all" для всех)
  since=1h                     - логи за период (1h, 30m, 2d, 60s)
  follow=true                  - streaming режим (как docker logs -f)

Примеры:
  curl http://host.docker.internal:9999/containers
  curl http://host.docker.internal:9999/logs/claude_agent
  curl http://host.docker.internal:9999/logs/claude_agent?tail=100
  curl http://host.docker.internal:9999/logs/claude_agent?since=1h
  curl http://host.docker.internal:9999/logs/claude_agent?follow=true
"""
    return web.Response(text=docs, content_type="text/plain")


def create_app():
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/health", health)
    app.router.add_get("/containers", list_containers)
    app.router.add_get("/logs/{name}", get_logs)
    return app


if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=9999)

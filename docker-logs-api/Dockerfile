FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir aiohttp docker

COPY main.py .

EXPOSE 9999

CMD ["python", "main.py"]

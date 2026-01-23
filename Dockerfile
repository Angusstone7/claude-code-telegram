FROM python:3.11-slim

# Устанавливаем системные зависимости (ssh client нужен обязательно)
RUN apt-get update && apt-get install -y openssh-client && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]

FROM python:3.11-slim

WORKDIR /app

COPY build_artifact /app
COPY config_repo/configs /app/configs  # Подключаем внешний конфиг

RUN pip install --no-cache-dir -r requirements.txt

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

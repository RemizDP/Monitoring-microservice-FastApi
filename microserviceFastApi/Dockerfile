# Dockerfile — финальный образ с конфигами
FROM python:3.11-slim

WORKDIR /app

# Копируем бинарник из артефакта
COPY ./build_artifact/main /app/main

# Копируем конфиги
COPY ./configs/ /app/configs/

# Делаем бинарник исполняемым
RUN chmod +x /app/main

CMD ["./main"]

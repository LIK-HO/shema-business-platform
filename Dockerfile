FROM python:3.13-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production \
    PYTHONPATH=/app/src

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && curl --fail --silent --show-error --location \
        https://storage.yandexcloud.net/cloud-certs/CA.pem \
        --output /etc/ssl/certs/yandex-cloud-ca.pem \
    && chmod 0644 /etc/ssl/certs/yandex-cloud-ca.pem \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system shema && adduser --system --ingroup shema --home /app shema
WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY db ./db
RUN python -m pip install --upgrade pip && python -m pip install .

USER shema
EXPOSE 8080

CMD ["uvicorn", "shema_platform.experience.production:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]

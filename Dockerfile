FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY retail_risk_aug /app/retail_risk_aug

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

CMD ["python", "-m", "retail_risk_aug.cli", "serve", "--target", "api", "--host", "0.0.0.0", "--port", "8000"]

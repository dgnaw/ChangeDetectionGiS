FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CONTRACTS_DIR=/contracts \
    PROCESSED_DIR=/data/processed \
    AUTO_SEED=false \
    SEED_SOURCE=/contracts/mock \
    UVICORN_RELOAD=false

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2)" || exit 1

# AUTO_SEED=true: nap SEED_SOURCE vao PostGIS neu DB con trong (--if-empty), roi khoi dong uvicorn.
CMD ["sh", "-c", "if [ \"$AUTO_SEED\" = \"true\" ]; then python scripts/seed.py --source \"$SEED_SOURCE\" --if-empty || echo '[start] seed failed - API still starting'; fi; if [ \"$UVICORN_RELOAD\" = \"true\" ]; then set -- --reload; fi; exec uvicorn app.main:app --host 0.0.0.0 --port 8000 \"$@\""]

# syntax=docker/dockerfile:1

# ============================================================
# Stage 1 — builder : installe les dépendances dans un venv
# ============================================================
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Le venv isolé sera copié tel quel dans l'image finale.
RUN python -m venv "$VIRTUAL_ENV"

# On installe d'abord les seules métadonnées de dépendances pour profiter du cache.
COPY pyproject.toml ./
RUN pip install --upgrade pip \
    && pip install .

# ============================================================
# Stage 2 — runtime : image légère avec le venv + le code
# ============================================================
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copie de l'environnement virtuel prêt à l'emploi.
COPY --from=builder /opt/venv /opt/venv

# Copie du code applicatif et des artefacts Alembic.
COPY . .

RUN chmod +x /app/entrypoint.sh \
    && useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# L'entrypoint joue `alembic upgrade head` puis lance uvicorn.
# Invoqué via `bash` explicitement : robuste même quand un bind-mount dev
# (docker-compose) masque le bit exécutable posé sur l'image.
ENTRYPOINT ["bash", "/app/entrypoint.sh"]
# --reload adapté au dev ; à retirer/surcharger en production via docker-compose.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

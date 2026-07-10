"""Environnement Alembic — lit l'URL DB depuis la config app et Base.metadata."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Importer le package des modèles enregistre chaque modèle sur Base.metadata
# afin que l'autogenerate les détecte. Ajouter les imports concrets dans
# app/models/__init__.py au fur et à mesure.
import app.models  # noqa: F401
from app.core.config import settings
from app.core.database import Base

# Objet de config Alembic (accès aux valeurs du .ini).
config = context.config

# Injecte l'URL depuis la config applicative (jamais en dur dans le .ini).
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Logging Alembic.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Métadonnées cibles pour l'autogenerate.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Migrations en mode 'offline' (génère du SQL sans connexion active)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Migrations en mode 'online' (connexion réelle à la base)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

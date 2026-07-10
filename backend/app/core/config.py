"""Configuration applicative chargée depuis l'environnement (Pydantic Settings)."""

from __future__ import annotations

from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres de l'application, lus depuis les variables d'environnement / .env.

    Les noms des variables suivent le contrat partagé (docs/CONVENTIONS.md).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Base de données ----
    # URL SQLAlchemy, driver psycopg v3 : postgresql+psycopg://user:pass@host:port/db
    DATABASE_URL: str = "postgresql+psycopg://jirou:jirou_dev_password@db:5432/jirou"

    # ---- Auth / JWT ----
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ---- CORS ----
    # Peut être fourni sous forme d'une chaîne séparée par des virgules
    # (ex. "http://localhost:5173,http://localhost:3000") ou d'une liste.
    # NoDecode : empêche la source env de tenter un décodage JSON de la valeur,
    # laissant le validateur ci-dessous découper la chaîne CSV.
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # ---- Pièces jointes (EPIC-09, JIR-65) ----
    # Dossier racine de stockage des fichiers téléversés (créé au runtime).
    UPLOAD_DIR: str = "uploads"
    # Taille maximale d'un fichier téléversé, en octets (défaut : 10 Mo).
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024

    # ---- Divers ----
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Jirou API"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Accepte une chaîne CSV pour CORS_ORIGINS et la convertit en liste."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


settings = Settings()

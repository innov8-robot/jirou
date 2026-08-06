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

    # ---- Veille R&D (domaine VEILLE) ----
    # Taille maximale d'un média de veille (image/vidéo), en octets (défaut : 200 Mo).
    WATCH_MAX_UPLOAD_SIZE: int = 200 * 1024 * 1024
    # Taille maximale d'un CSV d'import de sous-nœuds (défaut : 2 Mo).
    # Un CSV de veille est du texte : 2 Mo, c'est déjà des milliers de lignes.
    WATCH_MAX_CSV_SIZE: int = 2 * 1024 * 1024

    # ---- Chatbot RAG (Qdrant + Mistral) ----
    # URL interne du service Qdrant (vecteurs). Cf. docker-compose.
    QDRANT_URL: str = "http://qdrant:6333"
    # Clé API Mistral ; vide => chatbot désactivé (endpoints en 503).
    MISTRAL_API_KEY: str = ""
    MISTRAL_API_BASE: str = "https://api.mistral.ai"
    MISTRAL_CHAT_MODEL: str = "mistral-small-latest"
    MISTRAL_EMBED_MODEL: str = "mistral-embed"
    # Nom de la collection Qdrant et dimension des embeddings mistral-embed.
    RAG_COLLECTION: str = "jirou_rag"
    RAG_EMBED_DIM: int = 1024

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

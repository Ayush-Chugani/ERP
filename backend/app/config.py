"""Application settings, read from the environment (and an optional .env file)."""
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

INSECURE_SECRETS = {"", "change-me", "changeme", "secret", "replace-with-random-secret"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SIMS_", extra="ignore", case_sensitive=False)

    env: Literal["development", "test", "production"] = "development"
    # PostgreSQL (Supabase in production). Use the Supabase *direct* or *session pooler* string for the API
    # and `SIMS_DB_POOLER=transaction` if you point at the transaction pooler (port 6543).
    database_url: str = "postgresql+psycopg://sims:sims_dev_password@127.0.0.1:54329/sims"
    db_pool_size: int = 10
    db_max_overflow: int = 10
    db_pooler: Literal["none", "transaction"] = "none"
    db_ssl_mode: str = ""  # e.g. "require" for Supabase

    secret_key: str = "change-me"
    jwt_issuer: str = "sims-api"
    access_token_minutes: int = 10
    refresh_token_days: int = 7
    refresh_idle_days: int = 2
    cookie_secure: bool = True
    cookie_samesite: Literal["lax", "strict", "none"] = "strict"
    cookie_domain: str | None = None

    allowed_hosts: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["localhost", "127.0.0.1", "testserver"])
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    docs_enabled: bool = True
    max_body_bytes: int = 12 * 1024 * 1024
    trusted_proxy_hops: int = 1

    login_max_failures: int = 5
    login_lock_minutes: int = 15
    rate_login: str = "10/60"          # attempts / seconds, per IP
    rate_default: str = "300/60"       # per authenticated user or IP
    password_min_length: int = 12
    password_history: int = 5

    storage_backend: Literal["local", "s3"] = "local"
    storage_local_root: str = "./var/private_files"
    storage_s3_endpoint: str = ""       # Supabase Storage S3 endpoint
    storage_s3_region: str = "us-east-1"
    storage_s3_bucket: str = ""
    storage_s3_access_key: str = ""
    storage_s3_secret_key: str = ""
    upload_max_bytes: int = 10 * 1024 * 1024

    # AES-256-GCM keys for personal identifiers (Aadhaar, PAN, bank account): JSON {"1": "<base64 32 bytes>"}.
    field_encryption_keys: str = ""
    field_encryption_active: str = "1"
    fingerprint_key: str = ""           # HMAC key for duplicate detection of encrypted identifiers

    # AI assistance (Featherless AI, OpenAI-compatible). Off unless enabled AND a key is set; the key never leaves the server.
    ai_enabled: bool = False
    ai_base_url: str = "https://api.featherless.ai/v1"
    ai_api_key: str = ""
    ai_model: str = "Qwen/Qwen2.5-7B-Instruct"
    ai_timeout_seconds: float = 45.0
    ai_max_tokens: int = 700
    ai_rate: str = "20/60"             # requests / seconds, per user

    bootstrap_admin_username: str = ""
    bootstrap_admin_password: str = ""
    bootstrap_admin_email: str = ""

    worker_poll_seconds: float = 2.0
    worker_max_attempts: int = 5

    @field_validator("allowed_hosts", "cors_origins", mode="before")
    @classmethod
    def _split(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json

                return json.loads(v)
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @model_validator(mode="after")
    def _production_guards(self):
        if self.env == "production":
            if self.secret_key in INSECURE_SECRETS or len(self.secret_key) < 32:
                raise ValueError("SIMS_SECRET_KEY must be a random string of at least 32 characters in production")
            if "*" in self.allowed_hosts:
                raise ValueError("Wildcard SIMS_ALLOWED_HOSTS is not allowed in production")
            if not self.cookie_secure:
                raise ValueError("SIMS_COOKIE_SECURE must be true in production")
            if "*" in self.cors_origins:
                raise ValueError("Wildcard CORS origins are not allowed")
            if not self.field_encryption_keys or len(self.fingerprint_key) < 32:
                raise ValueError("SIMS_FIELD_ENCRYPTION_KEYS and a 32+ character SIMS_FINGERPRINT_KEY are required in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

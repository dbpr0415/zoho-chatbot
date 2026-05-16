"""
Application configuration module.
Loads environment variables and provides a centralized Settings class.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ZohoConfig:
    """Zoho OAuth and API configuration."""
    client_id: str = field(default_factory=lambda: os.getenv("ZOHO_CLIENT_ID", ""))
    client_secret: str = field(default_factory=lambda: os.getenv("ZOHO_CLIENT_SECRET", ""))
    redirect_uri: str = field(default_factory=lambda: os.getenv("ZOHO_REDIRECT_URI", "http://localhost:8000/auth/callback"))
    auth_url: str = "https://accounts.zoho.in/oauth/v2/auth"
    token_url: str = "https://accounts.zoho.in/oauth/v2/token"
    api_base_url: str = field(default_factory=lambda: os.getenv("ZOHO_API_BASE_URL", "https://projectsapi.zoho.in/restapi"))
    portal_name: str = field(default_factory=lambda: os.getenv("ZOHO_PORTAL_NAME", ""))
    scopes: str = "ZohoProjects.portals.READ,ZohoProjects.projects.READ,ZohoProjects.tasks.READ,ZohoProjects.tasks.CREATE,ZohoProjects.tasks.UPDATE,ZohoProjects.tasks.DELETE,ZohoProjects.users.READ"


@dataclass
class LLMConfig:
    """LLM (Groq) configuration."""
    api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    model_name: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "llama-3.1-8b-instant"))
    temperature: float = 0.0


@dataclass
class AppConfig:
    """Main application configuration."""
    secret_key: str = field(default_factory=lambda: os.getenv("APP_SECRET_KEY", "zoho-assistant-secret-key-change-me"))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./zoho_assistant.db"))
    frontend_url: str = field(default_factory=lambda: os.getenv("FRONTEND_URL", "http://localhost:5173"))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")


@dataclass
class Settings:
    """Centralized application settings."""
    app: AppConfig = field(default_factory=AppConfig)
    zoho: ZohoConfig = field(default_factory=ZohoConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)

    def validate(self) -> list[str]:
        """Validate that all required settings are present."""
        errors = []
        if not self.zoho.client_id:
            errors.append("ZOHO_CLIENT_ID is required")
        if not self.zoho.client_secret:
            errors.append("ZOHO_CLIENT_SECRET is required")
        if not self.llm.api_key:
            errors.append("GROQ_API_KEY is required")
        if not self.zoho.portal_name:
            errors.append("ZOHO_PORTAL_NAME is required")
        return errors


settings = Settings()

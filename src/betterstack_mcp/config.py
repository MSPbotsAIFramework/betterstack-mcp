"""Non-credential configuration for the service.

Per the vendor-mcp-development SOP section 1.2, the server must tolerate
unknown environment variables (the runtime injects variables this project
never declared), so ``extra="ignore"`` is required here. No credential or
secret field belongs in this module -- credentials only ever arrive on a
per-request HTTP header (see server.py), never through the environment.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_BASE_URL = "https://uptime.betterstack.com/api/v2"


class Settings(BaseSettings):
    """Process-wide, non-tenant configuration."""

    model_config = SettingsConfigDict(extra="ignore")

    mcp_http_host: str = "0.0.0.0"
    mcp_http_port: int = 8080
    base_url: str = DEFAULT_BASE_URL


settings = Settings()

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables or .env, never from code.

    The LLM is reached through any OpenAI-compatible endpoint, so switching
    between free-tier providers only means changing these three variables.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    data_dir: Path = Path("data/releases")
    policy_path: Path = Path("config/policy.yaml")
    github_token: str = ""
    notion_token: str = ""


def get_settings() -> Settings:
    return Settings()

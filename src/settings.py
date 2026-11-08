from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from src.envfile import load_env


class Settings(BaseSettings):
    """All configuration comes from environment variables or .env, never from code.

    The LLM is reached through any OpenAI-compatible endpoint, so switching
    between free-tier providers only means changing these three variables.
    """

    model_config = SettingsConfigDict(extra="ignore")

    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    data_dir: Path = Path("data/releases")
    policy_path: Path = Path("config/policy.yaml")
    # What the scanners look at. Set here, never by the agent, so it cannot point a scan somewhere else.
    scan_target: Path = Path("demo_app")
    semgrep_rules_dir: Path = Path("config/semgrep-rules")
    github_token: str = ""
    notion_token: str = ""


def get_settings() -> Settings:
    load_env()  # the shared .env reader; real environment variables still win
    return Settings()

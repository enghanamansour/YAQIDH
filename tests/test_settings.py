from pathlib import Path

from src.settings import Settings


def test_defaults(monkeypatch):
    for var in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert s.llm_model == ""
    assert s.data_dir == Path("data/releases")


def test_env_overrides_llm(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_MODEL", "some-model")
    s = Settings(_env_file=None)
    assert s.llm_base_url == "https://example.test/v1"
    assert s.llm_model == "some-model"

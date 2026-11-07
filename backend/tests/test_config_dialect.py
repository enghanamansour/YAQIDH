import json

import httpx

from app import config
from app.explainer import ChainExplainer, DialectRewriter, preserves_meaning
from app.models import Explanation, Finding


# ---- .env loader ----
def test_parse_handles_comments_quotes_and_export():
    text = """
# a comment
LLM_API_KEY="abc 123"
LLM_MODEL=llama-x   # trailing comment
export DIALECT_MODEL='allam'
EMPTY=
not a valid line
1BAD=x
"""
    assert config.parse(text) == {"LLM_API_KEY": "abc 123", "LLM_MODEL": "llama-x",
                                  "DIALECT_MODEL": "allam", "EMPTY": ""}


def test_load_reads_the_file_but_real_environment_wins(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("YQ_ONE=from_file\nYQ_TWO=from_file\nYQ_BLANK=\n", encoding="utf-8")
    monkeypatch.setenv("ENV_FILE", str(f))
    monkeypatch.delenv("YAQIDH_NO_DOTENV")
    monkeypatch.setenv("YQ_TWO", "from_real_env")
    monkeypatch.delenv("YQ_ONE", raising=False)
    monkeypatch.delenv("YQ_BLANK", raising=False)
    used = config.load_env()
    import os
    assert used == f
    assert os.environ["YQ_ONE"] == "from_file"
    assert os.environ["YQ_TWO"] == "from_real_env"
    assert "YQ_BLANK" not in os.environ  # a blank value sets nothing
    monkeypatch.delenv("YQ_ONE")


def test_load_does_nothing_when_switched_off_or_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("ENV_FILE", str(tmp_path / "missing.env"))
    monkeypatch.delenv("YAQIDH_NO_DOTENV")
    assert config.load_env() is None
    f = tmp_path / ".env"
    f.write_text("YQ_OFF=1\n", encoding="utf-8")
    monkeypatch.setenv("ENV_FILE", str(f))
    monkeypatch.setenv("YAQIDH_NO_DOTENV", "1")
    assert config.load_env() is None
    import os
    assert "YQ_OFF" not in os.environ


def test_load_never_returns_the_values(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("YQ_SECRET=topsecret\n", encoding="utf-8")
    monkeypatch.setenv("ENV_FILE", str(f))
    monkeypatch.delenv("YAQIDH_NO_DOTENV")
    monkeypatch.delenv("YQ_SECRET", raising=False)
    result = config.load_env()
    assert "topsecret" not in repr(result)
    monkeypatch.delenv("YQ_SECRET")


# ---- dialect rewrite and the two-model chain ----
ORIGINAL = Explanation(
    problem="حقنة SQL في السطر 12 (CWE-89): النص يُركَّب مباشرة في الاستعلام.",
    why_dangerous="المهاجم يقدر يقرأ أو يعدّل بيانات قاعدة البيانات، وتصنيفها OWASP A03.",
    direction="استخدم استعلامات مُهيَّأة بدل تركيب النص، وتأكد من كل مدخل.",
)


def _rewrite_with(content):
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
    return DialectRewriter("http://x", "k", "allam", client=httpx.Client(transport=httpx.MockTransport(handler)))


GOOD = json.dumps({
    "problem": "فيه حقنة SQL في السطر 12 (CWE-89): النص ينركّب على طول في الاستعلام.",
    "why_dangerous": "المهاجم يقدر يقرأ أو يعدّل بيانات قاعدة البيانات، وتصنيفها OWASP A03.",
    "direction": "استخدم استعلامات مُهيَّأة بدل تركيب النص، وتأكد من كل مدخل.",
}, ensure_ascii=False)


def test_a_faithful_rewrite_is_accepted():
    assert _rewrite_with(GOOD).rewrite(ORIGINAL).problem.startswith("فيه حقنة")


def test_a_rewrite_that_loses_a_technical_term_is_rejected():
    bad = json.loads(GOOD); bad["problem"] = "فيه حقنة في السطر 12: النص ينركّب على طول في الاستعلام."
    assert _rewrite_with(json.dumps(bad, ensure_ascii=False)).rewrite(ORIGINAL) is None  # CWE-89 and SQL gone


def test_a_rewrite_with_code_is_rejected():
    bad = json.loads(GOOD); bad["direction"] = "غيّرها إلى `execute(q, params)` وتأكد من كل مدخل (SQL)."
    assert _rewrite_with(json.dumps(bad, ensure_ascii=False)).rewrite(ORIGINAL) is None


def test_a_rewrite_that_changes_size_wildly_is_rejected():
    bad = json.loads(GOOD); bad["why_dangerous"] = "OWASP A03 03"
    assert not preserves_meaning(ORIGINAL, Explanation(**bad))


def test_garbage_from_the_dialect_model_is_rejected():
    assert _rewrite_with("not json at all").rewrite(ORIGINAL) is None


class _Reasoner:
    def explain(self, finding, lang="ar"):
        return ORIGINAL


FINDING = Finding(rule_id="R", title="t", severity="high", file="a.py", line=1)


def test_the_chain_uses_the_dialect_when_it_is_good():
    out = ChainExplainer(_Reasoner(), _rewrite_with(GOOD)).explain(FINDING, "ar")
    assert out.problem.startswith("فيه حقنة")


def test_the_chain_keeps_the_strong_models_answer_when_the_dialect_drifts():
    out = ChainExplainer(_Reasoner(), _rewrite_with("not json")).explain(FINDING, "ar")
    assert out == ORIGINAL


def test_the_chain_does_not_touch_english():
    out = ChainExplainer(_Reasoner(), _rewrite_with(GOOD)).explain(FINDING, "en")
    assert out == ORIGINAL

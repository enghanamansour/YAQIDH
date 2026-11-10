"""Two things added to the agent: the Saudi-dialect step on each explanation, and one explanation per library."""

import json
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

from src.agent.dialect import DialectStep, parse
from src.agent.loop import AgentLoop
from src.agent.skills import Skills
from src.mcp_server import create_server
from src.schema import Finding, Severity, StageName
from src.service import ReleaseService, ServiceError
from src.storage import EvidenceStore
from tests.test_loop import ScriptedChat, call, say
from tests.test_service import POLICY, FakeScanner, seed_approved_qa

pytestmark = pytest.mark.anyio

ORIGINAL = ("المشكلة: الاستعلام في app.py يبنى من مدخلات المستخدم (SQL injection).\n"
            "ليش خطرة: المهاجم يقدر يقرأ بيانات ما يحق له.\n"
            "اتجاه الإصلاح: لا تدمج المدخلات في النص، استخدم استعلامات بمعاملات.")


@pytest.fixture
def anyio_backend():
    return "asyncio"


class DialectChat:
    """Stands in for the dialect model: returns the scripted content, records the model it was asked for."""

    def __init__(self, content=None, error=None):
        self.content, self.error, self.models = content, error, []

    def complete(self, messages, tools=None, model=None):
        self.models.append(model)
        if self.error:
            raise self.error
        return {"role": "assistant", "content": self.content}


def faithful():
    return json.dumps({
        "problem": "الاستعلام في app.py ينبني من مدخلات المستخدم (SQL injection).",
        "why_dangerous": "المهاجم يقدر يقرأ بيانات ما يحق له.",
        "direction": "لا تدمج المدخلات في النص، استخدم استعلامات بمعاملات.",
    }, ensure_ascii=False)


def test_parse_reads_the_three_labelled_parts_and_refuses_anything_else():
    parts = parse(ORIGINAL)
    assert set(parts) == {"problem", "why_dangerous", "direction"} and "app.py" in parts["problem"]
    assert parse("شرح بدون عناوين") is None


def test_a_faithful_rewrite_is_applied_with_the_dialect_model():
    chat = DialectChat(faithful())
    step = DialectStep(chat, "dialect-model")
    out = step.rewrite(ORIGINAL)
    assert out != ORIGINAL and "ينبني" in out and step.last == "applied"
    assert chat.models == ["dialect-model"]
    assert out.count("المشكلة:") == 1 and "ليش خطرة:" in out and "اتجاه الإصلاح:" in out


def test_a_rewrite_that_drops_a_technical_term_keeps_the_original():
    bad = json.loads(faithful())
    bad["problem"] = "الاستعلام ينبني من مدخلات المستخدم."  # app.py and SQL injection are gone
    step = DialectStep(DialectChat(json.dumps(bad, ensure_ascii=False)), "m")
    assert step.rewrite(ORIGINAL) == ORIGINAL
    assert step.last == "kept" and "lost technical terms" in step.last_reason


@pytest.mark.parametrize("chat", [
    DialectChat("not json at all"),
    DialectChat(error=RuntimeError("429")),
    DialectChat(json.dumps({"problem": "x"})),
])
def test_a_failing_model_or_bad_answer_keeps_the_original(chat):
    step = DialectStep(chat, "m")
    assert step.rewrite(ORIGINAL) == ORIGINAL and step.last == "kept"


def test_text_without_labels_is_not_sent_to_the_model_at_all():
    chat = DialectChat(faithful())
    assert DialectStep(chat, "m").rewrite("شرح بدون عناوين") == "شرح بدون عناوين"
    assert chat.models == []


# --- library grouping ---

def lib(fp, rule, severity=Severity.HIGH, fixed="", component="flask==0.12.2"):
    return Finding(fingerprint=fp, tool="trivy", severity=severity, location="requirements.txt", rule=rule,
                   component=component, fixed_version=fixed)


@pytest.fixture
def service(tmp_path):
    found = [lib("F-1", "CVE-1", fixed="0.12.3"), lib("F-2", "CVE-2", fixed="2.3.2, 2.2.5"),
             lib("F-3", "CVE-3", Severity.LOW, fixed="1.0"), lib("F-4", "CVE-4", component="requests==2.19.0", fixed="2.20.0"),
             Finding(fingerprint="F-5", tool="semgrep", severity=Severity.HIGH, location="a.py:1", rule="sqli")]
    svc = ReleaseService(EvidenceStore(tmp_path / "d"), POLICY, {StageName.SECURITY: FakeScanner(found)}, Path(tmp_path))
    seed_approved_qa(svc.store)
    svc.run_scan("r1", "security")
    return svc


def explained(service):
    stage = next(s for s in service.get_evidence("r1")["stages"] if s["name"] == "security")
    return {f["fingerprint"]: f for f in stage["findings"]}


def test_service_shares_one_explanation_across_the_same_library_and_keeps_every_fingerprint(service):
    out = service.append_evidence("r1", "security", "F-1", "شرح", ["F-2", "F-3"])
    assert out["also_for"] == ["F-2", "F-3"] and out["skipped"] == []
    f = explained(service)
    assert all(f[k]["explanation"]["text"] == "شرح" for k in ("F-1", "F-2", "F-3"))
    assert f["F-4"]["explanation"] is None and set(f) == {"F-1", "F-2", "F-3", "F-4", "F-5"}
    assert all(f[k]["status"] == "open" for k in f)  # identity and status untouched


def test_service_refuses_other_components_and_never_overwrites(service):
    service.append_evidence("r1", "security", "F-2", "قديم")
    out = service.append_evidence("r1", "security", "F-1", "جديد", ["F-2", "F-4", "F-5", "F-404"])
    assert out["also_for"] == [] and set(out["skipped"]) == {"F-2", "F-4", "F-5", "F-404"}
    f = explained(service)
    assert f["F-2"]["explanation"]["text"] == "قديم" and f["F-4"]["explanation"] is None and f["F-5"]["explanation"] is None


def test_a_finding_without_component_cannot_share(service):
    service.append_evidence("r1", "security", "F-5", "شرح", ["F-1"])
    assert explained(service)["F-1"]["explanation"] is None


def test_the_view_shows_one_item_per_library_with_the_version_that_fixes_all(service):
    class R:
        structuredContent = {"result": service.get_findings("r1", "security")}

    view = json.loads(AgentLoop._findings_view(R))
    assert view["need_explanation"] == 5 and len(view["shown"]) == 3  # flask, requests, semgrep
    flask = next(s for s in view["shown"] if s.get("component") == "flask==0.12.2")
    assert flask["fingerprint"] == "F-1" and flask["also_for"] == ["F-2", "F-3"]
    assert flask["fix_all_by_upgrading_to"] == "2.3.2" and len(flask["group"]) == 3
    others = [s for s in view["shown"] if s.get("component") != "flask==0.12.2"]
    assert all("also_for" not in s for s in others)


async def test_loop_stores_the_dialect_text_and_the_group(service, tmp_path):
    chat = ScriptedChat(
        call("append_evidence", release_id="r1", stage="security", fingerprint="F-1", text=ORIGINAL, also_for=["F-2"]),
        say("done"),
    )
    step = DialectStep(DialectChat(faithful()), "m")
    async with connect(create_server(service)) as session:
        run = await AgentLoop(session, chat, Skills(tmp_path / "none"), dialect=step).run("r1")
    assert run.stopped == "done" and not run.calls[0]["error"]
    f = explained(service)
    assert "ينبني" in f["F-1"]["explanation"]["text"] and f["F-2"]["explanation"]["text"] == f["F-1"]["explanation"]["text"]


async def test_an_explanation_with_an_egyptian_word_is_sent_back_to_the_model(service, tmp_path):
    egyptian = ORIGINAL.replace("المهاجم يقدر", "المهاجم يقدر تاني")
    chat = ScriptedChat(
        call("append_evidence", release_id="r1", stage="security", fingerprint="F-5", text=egyptian),
        say("done"),
    )
    async with connect(create_server(service)) as session:
        run = await AgentLoop(session, chat, Skills(tmp_path / "none")).run("r1")
    assert run.calls[0]["error"]
    assert "Saudi" in chat.sent[1][0][-1]["content"]
    assert explained(service)["F-5"]["explanation"] is None  # nothing was stored


def test_a_plural_verb_that_drops_its_noon_is_not_accepted_as_saudi():
    from src.agent.dialect import non_saudi_word

    assert non_saudi_word("ممكن يكتشفوا الثغرة") == "يكتشفوا"
    assert non_saudi_word("ممكن يكتشفون الثغرة") is None
    assert non_saudi_word("المهاجم يقدر يقرأ البيانات") is None

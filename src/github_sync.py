"""Posts a release's state back to its pull request on GitHub.

Two things, as in the backend's GitHub client (backend/app/github.py, reused here):
  * one comment on the pull request, edited in place on every change, that the developer reads;
  * two commit statuses, yaqidh/staging and yaqidh/main. They come from the same gate the API serves, so
    when branch protection requires them, GitHub itself refuses a merge the gate would refuse.
A failed post is written to the history and never changes any decision.
"""

import re
import sys
from pathlib import Path
from typing import Protocol

from src.gate import check_gate
from src.history import HistoryLog
from src.phases.status import ReleaseStatus, release_status
from src.schema import Evidence, FindingStatus, StageName, StageRecord
from src.storage import EvidenceStore

MAX_COMMENT = 60000  # GitHub allows 65536 characters in a comment

_STATUS_TEXT = {
    ReleaseStatus.NOT_STARTED: "لسا ما بدأ الفحص",
    ReleaseStatus.QA_BLOCKED: "فحص الـ QA فيه ملاحظات عالية الخطورة، الدمج ممنوع لين المطوّر يصلحها",
    ReleaseStatus.AWAITING_QA_APPROVAL: "الـ QA نجح، بانتظار موافقة مراجع الـ QA",
    ReleaseStatus.QA_REJECTED: "مراجع الـ QA رفض، يرجع للمطوّر",
    ReleaseStatus.AWAITING_SECURITY_SCAN: "الـ QA انوافق عليه، الفحص الأمني لسا ما اشتغل",
    ReleaseStatus.SECURITY_BLOCKED: "الفحص الأمني فيه ملاحظات عالية الخطورة، الدمج على main ممنوع لين المطوّر يصلحها",
    ReleaseStatus.AWAITING_SECURITY_APPROVAL: "الفحص الأمني نجح، بانتظار موافقة مراجع الأمن",
    ReleaseStatus.SECURITY_REJECTED: "مراجع الأمن رفض، يرجع للمطوّر",
    ReleaseStatus.READY_TO_MERGE: "كل شي نجح وانوافق عليه، الدمج مسموح",
}
_STAGE_NAME = {StageName.QA: "فحص الـ QA الأمني", StageName.SECURITY: "الفحص الأمني"}


class Poster(Protocol):
    def upsert_comment(self, repo: str, pr: int, phase: str, body: str) -> dict: ...
    def set_status(self, repo: str, commit: str, phase: str, *, allowed: bool, description: str) -> dict: ...


def release_id_for(repo: str, pr: int) -> str:
    """owner/name + PR number -> a safe release id, e.g. 'owner-name-pr12'. The tail is kept if it is too long."""
    safe = re.sub(r"[^A-Za-z0-9_-]", "-", f"{repo}-pr{pr}")
    return safe[-64:].lstrip("-") or f"pr{pr}"


def _stage_section(record: StageRecord) -> list[str]:
    name = _STAGE_NAME[record.name]
    if record.scanned_at is None:
        return [f"### {name}", "لسا ما انفحصت.", ""]
    decision = record.decision.result if record.decision else None
    verdict = {"pass": "✅ نجحت", "fail": "❌ فشلت", None: "⏳ بانتظار قرار السياسة"}[decision]
    open_ = [f for f in record.findings if f.status == FindingStatus.OPEN]
    closed = [f for f in record.findings if f.status == FindingStatus.FIXED and f.closure and f.closure.result == "closed"]
    lines = [f"### {name}: {verdict}", f"_القرار من محرك السياسة، مو من الـ AI._ مفتوح: {len(open_)} | انقفل: {len(closed)}", ""]
    for f in sorted(open_, key=lambda f: (f.severity.value != "high", f.location)):
        lines.append(f"#### [{f.severity.value.upper()}] `{f.rule}` — {f.location}")
        meta = [f"البصمة: {f.fingerprint}"]
        if f.component:
            meta.append(f"المكتبة: {f.component}")
        if f.fixed_version:
            meta.append(f"النسخة المصلحة: {f.fixed_version}")
        if f.cwe:
            meta.append(f"التصنيف: {f.cwe}")
        lines.append(" | ".join(meta))
        if f.confidence == "low":
            lines.append("⚠️ الأداة نفسها غير متأكدة من هذي الملاحظة (ثقة منخفضة)، تأكد منها قبل ما تعدّل.")
        if f.explanation:
            lines += ["", f"> **شرح يقظ (كتبه الـ AI، مو حقيقة مثبتة):**", *[f"> {line}" for line in f.explanation.text.splitlines()]]
        elif f.detail:
            lines.append(f"ملاحظة الأداة: {f.detail}")
        lines.append("")
    if closed:
        lines += ["**انقفلت (تأكد منها الفحص المعاد):** " + ", ".join(f.fingerprint for f in closed), ""]
    if record.flaky_tests:
        lines += ["**فحوصات متذبذبة (نجحت بعد إعادة المحاولة، مسجلة ومو ملاحظات):** " + ", ".join(record.flaky_tests), ""]
    return lines


def render_comment(evidence: Evidence) -> str:
    report = release_status(evidence)
    lines = ["## يقظ — حالة الإصدار", "", f"**{_STATUS_TEXT[report.status]}**", ""]
    if evidence.head_commit:
        lines += [f"الكوميت: `{evidence.head_commit[:8]}`", ""]
    for name in (StageName.QA, StageName.SECURITY):
        lines += _stage_section(evidence.stage(name))
    lines += ["---", "يقظ يشرح فقط: ما يقرر ولا يصلح ولا يدمج. القرار من السياسة، والموافقة من الناس."]
    text = "\n".join(lines)
    return text if len(text) <= MAX_COMMENT else text[:MAX_COMMENT] + "\n\n_(تم قص التعليق لأنه طويل، التفاصيل الكاملة في الداشبورد)_"


class GitHubPublisher:
    def __init__(self, store: EvidenceStore, history: HistoryLog, client: Poster):
        self.store, self.history, self.client = store, history, client

    def publish(self, release_id: str) -> dict:
        evidence = self.store.get(release_id)
        if not evidence.repo or not evidence.pr_number:
            return {"skipped": "this release is not linked to a pull request"}
        result: dict = {}
        try:
            result["comment"] = self.client.upsert_comment(evidence.repo, evidence.pr_number, "release", render_comment(evidence))
            if re.fullmatch(r"[0-9a-fA-F]{40}", evidence.head_commit or ""):
                for target in ("staging", "main"):
                    gate = check_gate(evidence, evidence.head_commit, target)
                    reason = "; ".join(gate.detail)[:100] or gate.reason
                    result[target] = self.client.set_status(
                        evidence.repo, evidence.head_commit, target, allowed=gate.allowed,
                        description=("مسموح" if gate.allowed else f"ممنوع: {reason}"),
                    )
            self.history.append(release_id, "github_published", "system", {"commit": evidence.head_commit, **{k: v for k, v in result.items()}})
        except Exception as e:  # a failed post is reported, never hidden, and changes no decision
            self.history.append(release_id, "github_post_failed", "system", {"error": str(e)[:300]})
            result["error"] = str(e)[:300]
        return result


def github_client(token: str):
    """The backend's GitHub client (comment upsert + commit status)."""
    backend = str(Path(__file__).resolve().parents[1] / "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from app.github import GitHubClient

    return GitHubClient(token)

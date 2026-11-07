"""Builds the pull request comment the agent posts."""
from __future__ import annotations

from .models import SEVERITY_ORDER, Explanation, Finding, Phase

_T = {
    "ar": {
        "phase": {"qa": "فحص الجودة", "security": "الفحص الأمني"},
        "blocked": "الدمج ممنوع لين تنتهي كل الملاحظات التالية. الوكيل يشرح فقط ولا يعدّل الكود، والمطوّر هو اللي يصلح.",
        "clean": "ما بقي أي ملاحظة مفتوحة في هذا الفحص. يمر الآن لمراجعة الفريق البشري.",
        "closed": "ملاحظات انقفلت منذ الفحص السابق",
        "problem": "المشكلة",
        "why": "ليش خطيرة",
        "direction": "اتجاه الإصلاح",
        "id": "البصمة",
        "where": "الموضع",
    },
    "en": {
        "phase": {"qa": "Quality check", "security": "Security check"},
        "blocked": "Merging is blocked until every finding below is closed. The agent only explains and never edits code; the developer does the fixing.",
        "clean": "No open findings remain in this check. It now goes to the human team for review.",
        "closed": "Findings closed since the previous scan",
        "problem": "Problem",
        "why": "Why it is dangerous",
        "direction": "Direction of the fix",
        "id": "Fingerprint",
        "where": "Location",
    },
}


def render(phase: Phase, items: list[tuple[Finding, Explanation]], closed: list[str], lang: str = "ar") -> str:
    t = _T[lang if lang in _T else "ar"]
    lines = [f"### {t['phase'][phase]}", ""]
    if not items:
        lines.append(t["clean"])
    else:
        lines += [t["blocked"], ""]
        for finding, exp in sorted(items, key=lambda x: SEVERITY_ORDER[x[0].severity]):
            where = f"{finding.file}:{finding.line}" if finding.line else finding.file
            lines += [
                f"#### [{finding.severity.upper()}] {finding.title}",
                f"- **{t['where']}:** {where}",
                f"- **{t['id']}:** {finding.fingerprint}",
                f"- **{t['problem']}:** {exp.problem}",
                f"- **{t['why']}:** {exp.why_dangerous}",
                f"- **{t['direction']}:** {exp.direction}",
                "",
            ]
    if closed:
        lines += ["", f"**{t['closed']}:** " + ", ".join(closed)]
    return "\n".join(lines).strip() + "\n"

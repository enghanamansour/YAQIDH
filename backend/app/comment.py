"""Builds the pull request comment the agent posts."""
from __future__ import annotations

from .models import BLOCKING, SEVERITY_ORDER, Explanation, Finding, Phase

_T = {
    "ar": {
        "phase": {"qa": "فحص الجودة", "security": "الفحص الأمني"},
        "blocked": "الدمج ممنوع لين تنتهي كل الملاحظات عالية الخطورة التالية. الوكيل يشرح فقط ولا يعدّل الكود، والمطوّر هو اللي يصلح.",
        "clean": "ما بقي أي ملاحظة عالية الخطورة في هذا الفحص. يمر الآن لمراجعة الفريق البشري.",
        "low": "ملاحظات منخفضة الخطورة: ما تمنع الدمج، لكنها مسجّلة وليست بلا ضرر. الأفضل إصلاحها.",
        "closed": "ملاحظات انقفلت منذ الفحص السابق",
        "problem": "المشكلة",
        "why": "ليش خطيرة",
        "direction": "اتجاه الإصلاح",
        "id": "البصمة",
        "where": "الموضع",
    },
    "en": {
        "phase": {"qa": "Quality check", "security": "Security check"},
        "blocked": "Merging is blocked until every high-severity finding below is closed. The agent only explains and never edits code; the developer does the fixing.",
        "clean": "No high-severity findings remain in this check. It now goes to the human team for review.",
        "low": "Low-severity findings: they do not block the merge, but they are recorded and not harmless. Better fixed.",
        "closed": "Findings closed since the previous scan",
        "problem": "Problem",
        "why": "Why it is dangerous",
        "direction": "Direction of the fix",
        "id": "Fingerprint",
        "where": "Location",
    },
}


def _block(finding: Finding, exp: Explanation, t: dict) -> list[str]:
    where = f"{finding.file}:{finding.line}" if finding.line else finding.file
    return [
        f"#### [{finding.severity.upper()}] {finding.title}",
        f"- **{t['where']}:** {where}",
        f"- **{t['id']}:** {finding.fingerprint}",
        f"- **{t['problem']}:** {exp.problem}",
        f"- **{t['why']}:** {exp.why_dangerous}",
        f"- **{t['direction']}:** {exp.direction}",
        "",
    ]


def render(phase: Phase, items: list[tuple[Finding, Explanation]], closed: list[str], lang: str = "ar") -> str:
    t = _T[lang if lang in _T else "ar"]
    ordered = sorted(items, key=lambda x: SEVERITY_ORDER[x[0].severity])
    blocking = [i for i in ordered if i[0].severity in BLOCKING]
    low = [i for i in ordered if i[0].severity not in BLOCKING]

    lines = [f"### {t['phase'][phase]}", ""]
    if blocking:
        lines += [t["blocked"], ""]
        for finding, exp in blocking:
            lines += _block(finding, exp, t)
    else:
        lines += [t["clean"], ""]
    if low:
        lines += [f"**{t['low']}**", ""]
        for finding, exp in low:
            lines += _block(finding, exp, t)
    if closed:
        lines += ["", f"**{t['closed']}:** " + ", ".join(closed)]
    return "\n".join(lines).strip() + "\n"

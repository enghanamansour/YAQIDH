"""Builds the pull request comment the agent posts."""
from __future__ import annotations

from .grouping import Group
from .models import BLOCKING, Explanation, Phase

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
        "rules": "ملاحظة واحدة، نبّهت عليها {n} قواعد",
        "cwe": "التصنيف",
        "unsure": "تنبيه: الأداة نفسها غير متأكدة من هذي الملاحظة (ثقة منخفضة)، فهي احتمال. تأكد منها قبل ما تعدّل.",
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
        "rules": "One problem, flagged by {n} rules",
        "cwe": "Category",
        "unsure": "Note: the tool itself is not sure about this finding (low confidence), so it is only a possibility. Check it before you change anything.",
    },
}


def _block(group: Group, exp: Explanation, t: dict) -> list[str]:
    main = group.representative
    where = f"{main.file}:{main.line}" if main.line else main.file
    ids = ", ".join(group.fingerprints)
    lines = [
        f"#### [{group.severity.upper()}] {main.title}",
        f"- **{t['where']}:** {where}",
        f"- **{t['id']}:** {ids}",
    ]
    if len(group.findings) > 1:
        lines.append(f"- **{t['rules'].format(n=len(group.findings))}:** {', '.join(group.rules)}")
    if main.cwe:
        lines.append(f"- **{t['cwe']}:** {main.cwe}")
    lines += [
        f"- **{t['problem']}:** {exp.problem}",
        f"- **{t['why']}:** {exp.why_dangerous}",
        f"- **{t['direction']}:** {exp.direction}",
    ]
    if group.low_confidence:
        lines.append(f"- {t['unsure']}")
    lines.append("")
    return lines


def render(phase: Phase, items: list[tuple[Group, Explanation]], closed: list[str], lang: str = "ar") -> str:
    t = _T[lang if lang in _T else "ar"]
    blocking = [i for i in items if i[0].severity in BLOCKING]
    low = [i for i in items if i[0].severity not in BLOCKING]

    lines = [f"### {t['phase'][phase]}", ""]
    if blocking:
        lines += [t["blocked"], ""]
        for group, exp in blocking:
            lines += _block(group, exp, t)
    else:
        lines += [t["clean"], ""]
    if low:
        lines += [f"**{t['low']}**", ""]
        for group, exp in low:
            lines += _block(group, exp, t)
    if closed:
        lines += ["", f"**{t['closed']}:** " + ", ".join(closed)]
    return "\n".join(lines).strip() + "\n"

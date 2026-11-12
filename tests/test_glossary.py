"""One word for one thing: the old synonyms must not come back into the dashboard or the pull request comment (docs/glossary.md)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# banned word -> the one to use
BANNED = {
    "تحتاج معالجة": "قيد التنفيذ",
    "إغلاق مثبت": "أُغلقت",
    "إغلاقات مثبتة": "أُغلقت",
    "مُصلحة": "أُغلقت",
    "مرتفعة الخطورة": "عالية الخطورة",
    "انقفل": "أُغلقت",
    "اعتماد البناء": "موافقة",
    "تسجيل الموافقة": "موافقة",
    "مسؤول الأمن": "مراجع الأمن السيبراني",
    "السايبر": "مراجع الأمن السيبراني",
    "الـ QA": "الجودة",
    "حالة الإصدار": "حالة الطلب",
    "ليش خطيرة": "ليش خطرة",
    "مطور": "مطوّر (بالشدة)",
}


def texts():
    files = list((ROOT / "frontend-preview/web").rglob("*.js"))
    files += [ROOT / "src/github_sync.py", ROOT / "backend/app/comment.py", ROOT / "src/agent/prompt.py"]
    for path in files:
        yield path, path.read_text(encoding="utf-8")


def test_no_old_synonym_is_left():
    found = [f"{path.relative_to(ROOT).as_posix()}: «{word}» -> «{use}»"
             for path, text in texts() for word, use in BANNED.items() if word in text]
    assert not found, "use the glossary words:\n" + "\n".join(found)


def test_the_glossary_file_lists_every_banned_word():
    doc = (ROOT / "docs/glossary.md").read_text(encoding="utf-8")
    missing = [word for word in BANNED if word not in doc and word != "مطور"]
    assert not missing, f"docs/glossary.md does not mention: {missing}"


# the same, in English (the second text of every copy('عربي','English'))
BANNED_EN = {
    "Needs remediation": "In progress",
    "Verified closed": "Closed",
    "Verified closure": "Closed",
    "Closed, verified": "Closed",
    "Closed, proven": "Closed",
    "Record approval": "Approve",
    "Assigned changes": "Assigned requests",
    "Returned change": "Returned request",
    "Return change": "Return request",
    "Blocking vulnerability": "Blocking finding",
}


def test_no_old_english_synonym_is_left():
    found = [f"{path.relative_to(ROOT).as_posix()}: «{word}» -> «{use}»"
             for path, text in texts() for word, use in BANNED_EN.items() if word in text]
    assert not found, "use the glossary words:\n" + "\n".join(found)

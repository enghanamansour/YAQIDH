"""The agent that explains findings.

Rules it must follow, and that the code enforces (not only the prompt):
  * it explains in words, it never writes code or a ready fix;
  * it only talks about the finding it was given;
  * if the model misbehaves, we fall back to a fixed template instead.
"""
from __future__ import annotations

import json
import os
import re
from typing import Protocol

import httpx
from pydantic import ValidationError

from .models import Explanation, Finding

SYSTEM_PROMPT = (
    "You are a security reviewer inside a pull request. You receive ONE finding "
    "reported by the team's checking tools. Explain it to the developer in plain "
    "language. Rules: describe what the problem is, why it is dangerous, and "
    "which direction a fix should take, in words only. Never write code, never "
    "write commands, never include code fences or backticks. Base your explanation "
    "on the finding's description and CWE when they are given, and mention if the "
    "tool says its confidence is low. If other rules flagged the same place, "
    "explain it as one problem. Talk only about the given finding and do not "
    "invent facts that are not in it. Answer with one "
    'JSON object with exactly these string keys: "problem", "why_dangerous", '
    '"direction". Write in {language}.'
)

_WHY = {
    "ar": {
        "high": "خطورتها عالية: استغلالها ممكن ويؤثر على بيانات أو خدمات مهمة، ولذلك تمنع الدمج.",
        "low": "خطورتها منخفضة: أثرها أقل ولا تمنع الدمج، لكنها ليست بلا ضرر. الأفضل إصلاحها قبل ما تتراكم.",
    },
    "en": {
        "high": "High: exploitation is realistic and affects important data or services, so it blocks the merge.",
        "low": "Low: lower impact and it does not block the merge, but it is not harmless. Better fixed before they pile up.",
    },
}
_DIRECTION = {
    "ar": "راجع الموضع المذكور، وافهم ليش اللي كتبته يطلع هذي الملاحظة، وعدّله بنفسك بحيث تزول. بعدها تُعاد الفحوصات للتأكد.",
    "en": "Review the location mentioned, understand why what is written there triggers this finding, and change it yourself so it goes away. The checks then run again to confirm.",
}


class Explainer(Protocol):
    def explain(self, finding: Finding, lang: str) -> Explanation: ...


def explain_group(agent: Explainer, group, lang: str) -> Explanation:
    """Explains a group of findings once, through its main finding.

    The other rules that flagged the same place are added to the description,
    so the explanation covers the whole problem and not only one rule.
    """
    main = group.representative
    others = [r for r in group.rules if r != main.rule_id]
    if others:
        extra = "Also flagged at the same place by: " + ", ".join(others) + "."
        main = main.model_copy(update={"description": (main.description + " " + extra).strip()[:4000]})
    return agent.explain(main, lang)


def violates_rules(exp: Explanation) -> bool:
    """True when an explanation breaks the 'words only' rule."""
    text = " ".join([exp.problem, exp.why_dangerous, exp.direction])
    return "`" in text or "```" in text


class TemplateExplainer:
    """Fixed, predictable text built only from the finding's own fields."""

    def explain(self, finding: Finding, lang: str = "ar") -> Explanation:
        lang = lang if lang in _WHY else "ar"
        where = f"{finding.file}:{finding.line}" if finding.line else finding.file
        problem = (
            f"{finding.title} (في {where})." if lang == "ar" else f"{finding.title} (at {where})."
        )
        if finding.description:
            problem += " " + finding.description.strip()
        return Explanation(problem=problem[:800], why_dangerous=_WHY[lang][finding.severity], direction=_DIRECTION[lang])


def _chat_json(client: httpx.Client, base_url: str, api_key: str, model: str, messages: list[dict]) -> dict | None:
    """One call to an OpenAI-compatible chat endpoint that must answer with a JSON object.

    Returns None on any failure (network, bad status, not JSON), never raises.
    """
    try:
        resp = client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "temperature": 0, "messages": messages},
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):  # some models wrap JSON in a fence
            content = content.strip("`").removeprefix("json").strip()
        data = json.loads(content)
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        return None
    return data if isinstance(data, dict) else None


class LLMExplainer:
    """Asks an OpenAI-compatible chat endpoint. Falls back to the template."""

    def __init__(self, base_url: str, api_key: str, model: str, *, send_snippets: bool = False,
                 client: httpx.Client | None = None, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.send_snippets = send_snippets
        self.client = client or httpx.Client(timeout=timeout)
        self.fallback = TemplateExplainer()

    def _payload(self, finding: Finding, lang: str) -> dict:
        data = finding.model_dump(exclude={"snippet"} if not self.send_snippets else set())
        language = "Arabic" if lang == "ar" else "English"
        return {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.format(language=language)},
                {"role": "user", "content": json.dumps(data, ensure_ascii=False)},
            ],
        }

    def _ask(self, finding: Finding, lang: str) -> Explanation | None:
        payload = self._payload(finding, lang)
        data = _chat_json(self.client, self.base_url, self.api_key, payload["model"], payload["messages"])
        if data is None:
            return None
        try:
            exp = Explanation(**data)
        except ValidationError:
            return None
        return None if violates_rules(exp) else exp

    def explain(self, finding: Finding, lang: str = "ar") -> Explanation:
        for _ in range(2):  # one retry, then the fixed template
            exp = self._ask(finding, lang)
            if exp is not None:
                return exp
        return self.fallback.explain(finding, lang)


DIALECT_PROMPT = (
    "You rewrite a short security explanation in natural, easy Saudi Arabic dialect, "
    "the way a Saudi colleague would say it. Keep the meaning exactly: do not add, "
    "remove or change any fact. Keep every technical term, acronym, rule name, CWE id, "
    "file name and number exactly as written, in its original form. Keep location words "
    'such as "السطر" (line) and "الملف" (file) as they are, and never turn a prohibition '
    "into a permission or the reverse. Keep addressing the developer directly: an "
    "instruction stays an instruction to 'you', never 'I need'. Use Saudi forms (for "
    "example: كذا، وش، ليش، هالـ، لازم، ما) and avoid Egyptian, Levantine and Maghrebi "
    "forms (for example: ده، دي، كده، بتـ، ـش، عايز، هادي). Never write code, commands or backticks. Answer "
    "with one JSON object with exactly the same three string keys: "
    '"problem", "why_dangerous", "direction". Follow the style of the examples.'
)

# Few-shot examples: (formal explanation, the same explanation in Saudi dialect).
# They are about findings that are NOT in the comparison sample, so testing on that
# sample does not just measure how well the model copies the examples.
# Written by the assistant: Hana should review and adjust the dialect wording.
DIALECT_EXAMPLES: list[tuple[dict, dict]] = [
    (
        {
            "problem": "يتم عرض مدخلات المستخدم في الصفحة دون ترميز، في الملف views.py عند السطر 40، مما يجعل التطبيق عرضة لهجوم XSS (CWE-79).",
            "why_dangerous": "يستطيع المهاجم حقن شيفرة JavaScript تعمل في متصفح الضحية، فيسرق الجلسة أو ينفذ إجراءات باسمه.",
            "direction": "يجب ترميز أي قيمة قادمة من المستخدم قبل عرضها، ولا تعتمد على التحقق في الواجهة الأمامية وحده.",
        },
        {
            "problem": "مدخلات المستخدم تنعرض في الصفحة بدون ترميز، في الملف views.py عند السطر 40، وهذا يخلي التطبيق عرضة لهجوم XSS (CWE-79).",
            "why_dangerous": "المهاجم يقدر يحقن شيفرة JavaScript تشتغل في متصفح الضحية، وبعدها يسرق الجلسة أو يسوي إجراءات باسمه.",
            "direction": "لازم ترمّز أي قيمة جاية من المستخدم قبل ما تعرضها، ولا تعتمد على التحقق في الواجهة الأمامية لحاله.",
        },
    ),
    (
        {
            "problem": "تُخزَّن كلمات المرور باستخدام خوارزمية MD5 في الملف auth.py عند السطر 18 (CWE-327)، وهي خوارزمية ضعيفة وسريعة الكسر.",
            "why_dangerous": "إذا تسربت قاعدة البيانات، يستطيع المهاجم استرجاع كلمات المرور الأصلية بسهولة، ولا يحتاج إلى وقت طويل.",
            "direction": "لا تستخدم MD5 لحماية كلمات المرور، واستبدلها بخوارزمية مخصصة لذلك وبطيئة عمدًا، مثل bcrypt.",
        },
        {
            "problem": "كلمات المرور تنخزّن بخوارزمية MD5 في الملف auth.py عند السطر 18 (CWE-327)، وهي خوارزمية ضعيفة وتنكسر بسرعة.",
            "why_dangerous": "لو تسربت قاعدة البيانات، المهاجم يقدر يرجّع كلمات المرور الأصلية بسهولة، وما يحتاج وقت طويل.",
            "direction": "لا تستخدم MD5 لحماية كلمات المرور، وبدّلها بخوارزمية مخصصة لهذا الغرض وبطيئة عمدًا، مثل bcrypt.",
        },
    ),
]


def _example_messages() -> list[dict]:
    messages: list[dict] = []
    for formal, dialect in DIALECT_EXAMPLES:
        messages.append({"role": "user", "content": json.dumps(formal, ensure_ascii=False)})
        messages.append({"role": "assistant", "content": json.dumps(dialect, ensure_ascii=False)})
    return messages

_FIELDS = ("problem", "why_dangerous", "direction")
# Everything written in Latin letters (CWE-89, SQL, debug, app.py, parameterized) and every number.
_LATIN = re.compile(r"[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)*")
_TECHNICAL = re.compile(_LATIN.pattern + r"|\d+")
# Models sometimes write CWE-22 with a non-breaking hyphen; treat all dashes as a normal one.
_DASHES = dict.fromkeys(map(ord, "‐‑‒–−"), "-")
_SENTENCE_END = re.compile(r"[.!?؟]+")


def _normalize(text: str) -> str:
    return text.translate(_DASHES)
# Location words that a rewrite must not swap for something else ("السطر 12" became "بالصفحة 12" once).
_POSITION_STEMS = ("سطر", "ملف")
# "ما" is left out of the formal list on purpose: in formal Arabic it is mostly "what" or
# "ما إذا" (whether), not a negation. In the dialect it is the normal negation, so it counts there.
_FORMAL_NEGATIONS = frozenset({"لا", "لم", "لن", "ليس", "غير", "بدون", "دون", "عدم"})
_DIALECT_NEGATIONS = _FORMAL_NEGATIONS | {"ما", "مو", "مب"}
_ARABIC_WORD = re.compile(r"[؀-ۿ]+")


def _has_word(text: str, stem: str) -> bool:
    """True if `stem` is a word of its own, also with a one-letter prefix or the article
    (سطر، السطر، بالسطر، للملف). A longer word that merely contains it does not count:
    "ملفات تعريف الارتباط" means cookies, it is not "the file"."""
    for word in _ARABIC_WORD.findall(text):
        w = word
        for _ in range(2):
            if len(w) > len(stem) and w[0] in "وفبلك":
                w = w[1:]
        if w.startswith("ال") and len(w) > len(stem):
            w = w[2:]
        if w == stem:
            return True
    return False


# Clear markers of Egyptian / Levantine / Maghrebi speech. The model drifted into these
# even when told to write Saudi, so an answer that uses one is not accepted as Saudi.
_NOT_SAUDI = frozenset({"ده", "دي", "دا", "كده", "كدا", "هادي", "هاد", "مش", "عايز", "عايزة",
                        "دلوقتي", "دلوقت", "إنو", "انو", "أوي", "اوي", "تاني", "تانية", "تانيه", "بتاع", "بتاعة",
                        "بتاعت", "إزاي", "ازاي", "برضو", "برضه", "بقى", "بقا"})


def _not_saudi_word(text: str) -> str | None:
    for word in _ARABIC_WORD.findall(text):
        for candidate in (word, word[1:] if len(word) > 2 and word[0] in "وفب" else ""):
            if candidate in _NOT_SAUDI:
                return candidate
    return None


def _has_negation(text: str, words: frozenset[str]) -> bool:
    """True if the text has one of the negation words, also with a one-letter prefix (ولا، وما، فلا)."""
    for word in _ARABIC_WORD.findall(text):
        if word in words or (len(word) > 2 and word[0] in "وف" and word[1:] in words):
            return True
    return False


def _text(exp: Explanation) -> str:
    return " ".join(getattr(exp, f) for f in _FIELDS)


def meaning_problem(original: Explanation, rewritten: Explanation) -> str | None:
    """Cheap checks that a dialect rewrite did not change the substance.

    These are cheap rules, not a proof: they catch lost technical terms, changed
    numbers, swapped location words, a dropped negation, code, and big size changes.
    They cannot catch a subtle change of meaning, so a human should still read samples.
    """
    if violates_rules(rewritten):
        return "contains code or backticks"
    before_all, after_all = _normalize(_text(original)), _normalize(_text(rewritten))
    # every Latin-letter token (CWE ids, SQL, file names, English terms) and every number
    missing = sorted(t for t in set(_TECHNICAL.findall(before_all)) if t not in after_all)
    if missing:
        return "lost technical terms or numbers: " + ", ".join(missing)
    # ...and nothing new in Latin letters: a made-up "CWE-476" must not slip in
    added = sorted(set(_LATIN.findall(after_all)) - set(_LATIN.findall(before_all)))
    if added:
        return "added terms that were not in the original: " + ", ".join(added)
    foreign = _not_saudi_word(after_all)
    if foreign:
        return f"not Saudi dialect: the word '{foreign}' is Egyptian or Levantine"
    first_person = {"احتاج", "أحتاج"}
    if first_person & set(_ARABIC_WORD.findall(after_all)) and not first_person & set(_ARABIC_WORD.findall(before_all)):
        return "an instruction to the developer became a sentence about the speaker ('I need')"
    sentences = [s.strip() for s in _SENTENCE_END.split(after_all) if len(s.strip()) >= 25]
    if len(sentences) != len(set(sentences)):
        return "a sentence is repeated"
    for stem in _POSITION_STEMS:
        if _has_word(before_all, stem) and not _has_word(after_all, stem):
            return f"the location word '{stem}' is gone"
    for f in _FIELDS:
        before, after = getattr(original, f), getattr(rewritten, f)
        if not 0.5 * len(before) <= len(after) <= 1.8 * len(before):
            return f"'{f}' changed size too much ({len(before)} -> {len(after)} chars)"
        if _has_negation(before, _FORMAL_NEGATIONS) and not _has_negation(after, _DIALECT_NEGATIONS):
            # "لا تستخدم" must not become "استخدم"
            return f"a negation was dropped in '{f}'"
    return None


def preserves_meaning(original: Explanation, rewritten: Explanation) -> bool:
    """True when `meaning_problem` finds nothing wrong."""
    return meaning_problem(original, rewritten) is None


class DialectRewriter:
    """Rewrites an explanation in Saudi dialect. Returns None if it drifts."""

    def __init__(self, base_url: str, api_key: str, model: str, *, client: httpx.Client | None = None,
                 timeout: float = 30.0):
        self.base_url, self.api_key, self.model = base_url, api_key, model
        self.client = client or httpx.Client(timeout=timeout)

    def build_messages(self, exp: Explanation) -> list[dict]:
        return [
            {"role": "system", "content": DIALECT_PROMPT},
            *_example_messages(),
            {"role": "user", "content": json.dumps(exp.model_dump(), ensure_ascii=False)},
        ]

    def rewrite(self, exp: Explanation) -> Explanation | None:
        data = _chat_json(self.client, self.base_url, self.api_key, self.model, self.build_messages(exp))
        if data is None:
            return None
        try:
            out = Explanation(**data)
        except ValidationError:
            return None
        return out if preserves_meaning(exp, out) else None


class ChainExplainer:
    """A strong model understands and explains; a second one only changes the dialect.

    If the dialect step fails or drifts, the first explanation is kept as it is.
    """

    def __init__(self, reasoner: Explainer, rewriter: DialectRewriter):
        self.reasoner, self.rewriter = reasoner, rewriter

    def explain(self, finding: Finding, lang: str = "ar") -> Explanation:
        exp = self.reasoner.explain(finding, lang)
        if lang != "ar":
            return exp
        return self.rewriter.rewrite(exp) or exp


def get_explainer() -> Explainer:
    key = os.environ.get("LLM_API_KEY")
    if not key:
        return TemplateExplainer()
    base_url = os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    reasoner = LLMExplainer(
        base_url=base_url,
        api_key=key,
        model=os.environ.get("LLM_MODEL", "openai/gpt-oss-120b"),
        send_snippets=os.environ.get("SEND_SNIPPETS", "0") == "1",
    )
    dialect_model = os.environ.get("DIALECT_MODEL", "").strip()
    if dialect_model:
        return ChainExplainer(reasoner, DialectRewriter(base_url, key, dialect_model))
    return reasoner

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
    "You rewrite a short security explanation in natural, easy Saudi Arabic dialect. "
    "Keep the meaning exactly: do not add, remove or change any fact. Keep every "
    "technical term, acronym, rule name, CWE id and number exactly as written, in "
    "its original English form. Never write code, commands or backticks. Answer with "
    'one JSON object with exactly the same three string keys: "problem", '
    '"why_dangerous", "direction".'
)

_FIELDS = ("problem", "why_dangerous", "direction")
_TECHNICAL = re.compile(r"CWE-\d+|\b[A-Z][A-Z0-9]{2,}\b|\d+")


def _text(exp: Explanation) -> str:
    return " ".join(getattr(exp, f) for f in _FIELDS)


def preserves_meaning(original: Explanation, rewritten: Explanation) -> bool:
    """Cheap checks that a dialect rewrite did not change the substance.

    Every technical token (CWE ids, acronyms like SQL, numbers) of the original
    must still be there, no code appeared, and no field changed size wildly.
    """
    if violates_rules(rewritten):
        return False
    after = _text(rewritten)
    if any(token not in after for token in set(_TECHNICAL.findall(_text(original)))):
        return False
    for f in _FIELDS:
        a, b = len(getattr(original, f)), len(getattr(rewritten, f))
        if b < 0.3 * a or b > 3 * a:
            return False
    return True


class DialectRewriter:
    """Rewrites an explanation in Saudi dialect. Returns None if it drifts."""

    def __init__(self, base_url: str, api_key: str, model: str, *, client: httpx.Client | None = None,
                 timeout: float = 30.0):
        self.base_url, self.api_key, self.model = base_url, api_key, model
        self.client = client or httpx.Client(timeout=timeout)

    def rewrite(self, exp: Explanation) -> Explanation | None:
        data = _chat_json(self.client, self.base_url, self.api_key, self.model, [
            {"role": "system", "content": DIALECT_PROMPT},
            {"role": "user", "content": json.dumps(exp.model_dump(), ensure_ascii=False)},
        ])
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
        model=os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile"),
        send_snippets=os.environ.get("SEND_SNIPPETS", "0") == "1",
    )
    dialect_model = os.environ.get("DIALECT_MODEL", "").strip()
    if dialect_model:
        return ChainExplainer(reasoner, DialectRewriter(base_url, key, dialect_model))
    return reasoner

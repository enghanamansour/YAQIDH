"""The agent that explains findings.

Rules it must follow, and that the code enforces (not only the prompt):
  * it explains in words, it never writes code or a ready fix;
  * it only talks about the finding it was given;
  * if the model misbehaves, we fall back to a fixed template instead.
"""
from __future__ import annotations

import json
import os
from typing import Protocol

import httpx
from pydantic import ValidationError

from .models import Explanation, Finding

SYSTEM_PROMPT = (
    "You are a security reviewer inside a pull request. You receive ONE finding "
    "reported by the team's checking tools. Explain it to the developer in plain "
    "language. Rules: describe what the problem is, why it is dangerous, and "
    "which direction a fix should take, in words only. Never write code, never "
    "write commands, never include code fences or backticks. Talk only about the "
    "given finding and do not invent facts that are not in it. Answer with one "
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
        try:
            resp = self.client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=self._payload(finding, lang),
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):  # some models wrap JSON in a fence
                content = content.strip("`").removeprefix("json").strip()
            exp = Explanation(**json.loads(content))
        except (httpx.HTTPError, KeyError, IndexError, ValueError, ValidationError):
            return None
        return None if violates_rules(exp) else exp

    def explain(self, finding: Finding, lang: str = "ar") -> Explanation:
        for _ in range(2):  # one retry, then the fixed template
            exp = self._ask(finding, lang)
            if exp is not None:
                return exp
        return self.fallback.explain(finding, lang)


def get_explainer() -> Explainer:
    key = os.environ.get("LLM_API_KEY")
    if not key:
        return TemplateExplainer()
    return LLMExplainer(
        base_url=os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
        api_key=key,
        model=os.environ.get("LLM_MODEL", "meta-llama/llama-3.3-70b-instruct"),
        send_snippets=os.environ.get("SEND_SNIPPETS", "0") == "1",
    )

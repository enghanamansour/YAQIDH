"""Saudi-dialect step for the agent's explanations, reusing Hana's rewriter and meaning checks (backend/app/explainer.py).

After the agent writes an explanation, this step asks a second model to rewrite it in Saudi dialect, then runs the
same cheap checks the backend uses (lost terms or numbers, dropped negation, code, size). If anything goes wrong
(no labels, the model fails, the answer is not JSON, a check rejects it) the ORIGINAL text is kept. It never raises.
"""

import json
import re

from src.agent.explain import LABELS, _backend_modules

_LABEL_RE = re.compile(
    r"المشكلة\s*:\s*(?P<problem>.*?)\s*ليش خطرة\s*:\s*(?P<why_dangerous>.*?)\s*اتجاه الإصلاح\s*:\s*(?P<direction>.*)",
    re.DOTALL,
)


def parse(text: str) -> dict | None:
    m = _LABEL_RE.search(text)
    if not m:
        return None
    parts = {k: v.strip() for k, v in m.groupdict().items()}
    return parts if all(parts.values()) else None


def assemble(parts: dict) -> str:
    return "\n".join(f"{LABELS[k]}: {parts[k]}" for k in LABELS)


def _json_object(content: str) -> dict | None:
    content = (content or "").strip()
    if content.startswith("```"):
        content = content.strip("`").removeprefix("json").strip()
    try:
        data = json.loads(content)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


class DialectStep:
    """chat: any object with complete(messages, tools=None, model=None) (ChatClient). model: the dialect model."""

    def __init__(self, chat, model: str):
        self.chat, self.model = chat, model
        self.last = "kept"  # applied | kept (+ reason), for the run log
        self.last_reason = ""

    def _keep(self, text: str, reason: str) -> str:
        self.last, self.last_reason = "kept", reason
        return text

    def rewrite(self, text: str) -> str:
        parts = parse(text)
        if parts is None:
            return self._keep(text, "no labelled parts")
        try:
            _, module = _backend_modules()
            from app.models import Explanation

            original = Explanation(**parts)
            messages = module.DialectRewriter("", "", self.model).build_messages(original)
            message = self.chat.complete(messages, None, model=self.model)
            data = _json_object(message.get("content") or "")
            if data is None:
                return self._keep(text, "the answer was not JSON")
            rewritten = Explanation(**data)
            problem = module.meaning_problem(original, rewritten)
            if problem:
                return self._keep(text, problem)
            result = assemble(rewritten.model_dump())
        except Exception as e:  # a failed dialect step must never lose the explanation
            return self._keep(text, f"{type(e).__name__}")
        self.last, self.last_reason = "applied", ""
        return result

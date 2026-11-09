"""Turns a finding into an explanation text using the team's explainer (backend/app/explainer.py).

That explainer already refuses answers that contain code, falls back to a fixed template when the model
misbehaves, and can rewrite the text in Saudi dialect. This module only adapts our finding to its shape.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"

LABELS = {"problem": "المشكلة", "why_dangerous": "ليش خطرة", "direction": "اتجاه الإصلاح"}


def _backend_modules():
    """The backend package is called `app`; it is imported only when needed."""
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    from app import adapters, explainer

    return adapters, explainer


class BackendExplainer:
    def __init__(self, explainer=None, lang: str = "ar"):
        self._explainer = explainer
        self.lang = lang

    def explain(self, finding: dict) -> str:
        adapters, module = _backend_modules()
        if self._explainer is None:
            self._explainer = module.get_explainer()  # reads LLM_* from the environment; template if no key
        item = {**finding, "message": finding.get("detail", "")}
        exp = self._explainer.explain(adapters.from_team_finding(item), self.lang)
        return "\n".join(f"{LABELS[k]}: {getattr(exp, k)}" for k in LABELS)

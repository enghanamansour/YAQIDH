import hashlib


def normalize_snippet(snippet: str) -> str:
    """Collapse whitespace so reformatting the code does not change the finding fingerprint."""
    return " ".join(snippet.split())


def fingerprint(tool: str, rule: str, file: str, snippet: str) -> str:
    """Stable fingerprint from what the finding IS, not where it sits.

    The line number is left out on purpose: after a fix elsewhere in the file the line
    shifts, and the verifier would lose track of the same finding.
    """
    key = "\x1f".join([tool, rule, file, normalize_snippet(snippet)])
    return "F-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:10]

"""Turns findings from the team's checking tools into our own `Finding`.

This only reads their output. It never changes how the tools work.

Two shapes are accepted: the current one (`fingerprint`) and the first one
(`id`), so an older sample still works.

The raw JSON of Semgrep and Trivy is accepted too (`from_tool_output`), because
it carries what the team's own format drops: the tool's message, the CWE and,
for Semgrep, the confidence.
"""
from __future__ import annotations

import re

from .models import Finding


def _title_from_rule(rule: str) -> str:
    """'python.flask.security.audit.debug-enabled' -> 'debug enabled (flask)'."""
    parts = rule.split(".")
    name = parts[-1].replace("-", " ").replace("_", " ")
    family = parts[1] if len(parts) > 2 else ""
    return f"{name} ({family})" if family else name


def _split_location(location: str) -> tuple[str, int | None]:
    """'app.py:12' -> ('app.py', 12). A path with no line number is kept as is."""
    m = re.match(r"^(.*):(\d+)$", location.strip())
    if m:
        return m.group(1), int(m.group(2))
    return location.strip(), None


def _fingerprint(item: dict) -> str:
    value = item.get("fingerprint") or item.get("id")
    if not value:
        raise ValueError("a finding needs a 'fingerprint' (or the older 'id')")
    return str(value)


def _title(item: dict, rule: str) -> str:
    if item.get("title"):
        return item["title"]
    if item.get("component"):  # a vulnerable library: say which one
        return f"{rule} in {item['component']}"
    return _title_from_rule(rule)


def _description(item: dict) -> str:
    parts = [item.get("message", "")]
    if item.get("component"):
        parts.append(f"Affected component: {item['component']}.")
    if item.get("reported_as"):
        parts.append(f"The tool itself reported it as: {item['reported_as']}.")
    return " ".join(p.strip() for p in parts if p and p.strip())


def _verified_closed(item: dict) -> bool:
    """Only a finding the team's verifier proved closed leaves the list."""
    closure = item.get("closure") or {}
    return item.get("status") == "fixed" and closure.get("result") == "closed"


def from_team_finding(item: dict) -> Finding:
    """Accepts one finding in the shape the team's tools produce.

    Required: fingerprint (or id), rule, location, severity.
    Optional: title, message, snippet, cwe, confidence, component, reported_as.
    The fingerprint they give is kept as ours, so there is one id everywhere.
    """
    file, line = _split_location(item["location"])
    rule = item["rule"]
    return Finding(
        rule_id=rule,
        title=_title(item, rule),
        severity=item["severity"],
        file=file,
        line=line,
        description=_description(item),
        snippet=item.get("snippet", ""),
        external_id=_fingerprint(item),
        cwe=item.get("cwe"),
        confidence=item.get("confidence"),
    )


def from_team_findings(items: list[dict]) -> list[Finding]:
    """Everything still counts except what the verifier proved closed.

    A finding marked 'fixed' without a verified closure, or 'excepted', stays in
    the list. Whether an exception is valid is the team's policy engine's call,
    so this adapter never lets one through by itself (it fails closed).
    """
    return [from_team_finding(i) for i in items if not _verified_closed(i)]


# ---- the raw output of the tools themselves ----

# Without an account Semgrep prints this instead of the code lines and the fingerprint.
_LOGIN_PLACEHOLDER = "requires login"
_SEMGREP_RULE_PREFIX = re.compile(r"^.*?semgrep-rules\.")


def _clean(value) -> str:
    """One line of text; Semgrep's 'requires login' placeholder counts as nothing."""
    text = " ".join(str(value or "").split())
    return "" if text.lower() == _LOGIN_PLACEHOLDER else text


def _cwe_text(value) -> str | None:
    """Semgrep gives the CWE as a list in one rule and as a plain string in another."""
    items = value if isinstance(value, list) else [value]
    text = "; ".join(_clean(i) for i in items if i)
    return text[:300] or None


def from_semgrep_result(item: dict) -> Finding:
    """One entry of Semgrep's `results`.

    ERROR and WARNING count as high and only INFO as low (the policy agreed with the
    team). Semgrep's own `fingerprint` is never used: it is empty without a login and
    we cannot verify that it ignores line numbers, so our own fingerprint stays.
    """
    extra = item.get("extra") or {}
    meta = extra.get("metadata") or {}
    rule = _SEMGREP_RULE_PREFIX.sub("", item["check_id"])
    info_only = str(extra.get("severity", "")).strip().upper() == "INFO"
    return Finding(
        rule_id=rule,
        title=_title_from_rule(rule),
        severity="low" if info_only else "high",
        file=item["path"],
        line=(item.get("start") or {}).get("line"),
        description=_clean(extra.get("message"))[:4000],
        snippet=_clean(extra.get("lines"))[:4000],
        cwe=_cwe_text(meta.get("cwe")),
        confidence=meta.get("confidence"),
    )


def from_semgrep_output(doc: dict) -> list[Finding]:
    fatal = [e for e in doc.get("errors") or [] if str(e.get("level", "error")).lower() == "error"]
    if fatal:  # a scan that stopped half way must not look like a clean one
        raise ValueError(f"Semgrep reported {len(fatal)} error(s): the scan may be incomplete")
    return [from_semgrep_result(r) for r in doc.get("results") or []]


def from_trivy_vulnerability(target: str, vuln: dict) -> Finding:
    """One vulnerable library. Trivy's own `Status: fixed` only means a fixed version
    exists, it is NOT a proof that this project was fixed, so it is never read."""
    component = f"{vuln['PkgName']}=={vuln['InstalledVersion']}"
    vuln_id = vuln["VulnerabilityID"]
    parts = [vuln.get("Title"), vuln.get("Description")]
    if vuln.get("FixedVersion"):
        parts.append(f"Fixed in: {vuln['FixedVersion']}.")
    parts.append(f"Affected component: {component}.")
    return Finding(
        rule_id=vuln_id,
        title=f"{vuln_id} in {component}",
        severity=vuln.get("Severity", ""),  # only LOW is low; MEDIUM, HIGH, CRITICAL, UNKNOWN are high
        file=target,
        line=None,  # a library has no line, so different vulnerabilities are never merged
        description=_clean(" ".join(p for p in parts if p))[:4000],
        external_id=vuln.get("Fingerprint") or None,
        cwe=_cwe_text(vuln.get("CweIDs")),
    )


def from_trivy_secret(target: str, secret: dict) -> Finding:
    """One secret found in a file. Only the line that triggered the rule is used, never the
    lines around it, and only when Trivy has masked the value."""
    title = secret.get("Title") or secret["RuleID"]
    match = secret.get("Match", "")
    return Finding(
        rule_id=secret["RuleID"],
        title=title,
        severity=secret.get("Severity", ""),
        file=target,
        line=secret.get("StartLine"),
        description=f"{title} ({secret.get('Category', 'secret')}) found in the file. The value itself is masked in the report.",
        snippet=match[:4000] if "*" in match else "",
    )


def from_trivy_output(doc: dict) -> list[Finding]:
    findings: list[Finding] = []
    for result in doc.get("Results") or []:
        if result.get("Misconfigurations"):
            raise ValueError("Trivy misconfigurations are not supported yet; they would be silently ignored")
        target = result["Target"]
        findings += [from_trivy_vulnerability(target, v) for v in result.get("Vulnerabilities") or []]
        findings += [from_trivy_secret(target, s) for s in result.get("Secrets") or []]
    return findings


def from_tool_output(doc: dict) -> list[Finding]:
    """Raw JSON of Semgrep or Trivy, told apart by its keys."""
    if "SchemaVersion" in doc and "Results" in doc:
        return from_trivy_output(doc)
    if isinstance(doc.get("results"), list):
        return from_semgrep_output(doc)
    raise ValueError("unknown tool output: expected the JSON of Semgrep or Trivy")

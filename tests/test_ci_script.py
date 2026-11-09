import importlib.util
from pathlib import Path

from src.scanning import ScanResult
from src.schema import Finding, Severity

spec = importlib.util.spec_from_file_location("ci_scan", Path(__file__).resolve().parents[1] / "scripts" / "ci_scan.py")
ci_scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci_scan)


def test_the_submission_has_exactly_what_the_server_route_expects():
    result = ScanResult([Finding(fingerprint="F-1", tool="semgrep", severity=Severity.HIGH, location="a.py:1")],
                        {"semgrep-rules": "r", "trivy": "1", "trivy-db": "d"}, {"trivy", "semgrep"}, {"flask==0.12.2"})
    body = ci_scan.build_submission(result, "abc1234")
    assert body["commit"] == "abc1234" and body["tools_run"] == ["semgrep", "trivy"]
    assert body["findings"][0]["fingerprint"] == "F-1" and body["components"] == ["flask==0.12.2"]
    # the server's model accepts it as is
    from src.api.app import ScanSubmission
    assert ScanSubmission(**body).findings[0].location == "a.py:1"

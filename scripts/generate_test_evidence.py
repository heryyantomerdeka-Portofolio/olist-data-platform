"""Generate test evidence from an actual pytest execution."""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "test_evidence.json"


def main():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests",
            "-q",
            "--tb=short",
            "--junitxml=outputs/pytest_results.xml",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": "python -m pytest tests -q --tb=short",
        "exit_code": result.returncode,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "status": "PASSED" if result.returncode == 0 else "FAILED",
        "stdout": result.stdout,
        "stderr": result.stderr,
    }

    report_path = ROOT / "outputs" / "pytest_results.xml"

    if report_path.exists():
        import xml.etree.ElementTree as ET

        root = ET.parse(report_path).getroot()
        suites = [root] if root.tag == "testsuite" else root.findall("testsuite")

        for suite in suites:
            summary["failed"] += int(suite.attrib.get("failures", 0))
            summary["errors"] += int(suite.attrib.get("errors", 0))
            summary["skipped"] += int(suite.attrib.get("skipped", 0))

        summary["passed"] = (
            sum(int(suite.attrib.get("tests", 0)) for suite in suites)
            - summary["failed"]
            - summary["errors"]
            - summary["skipped"]
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Status   : {summary['status']}")
    print(f"Passed   : {summary['passed']}")
    print(f"Failed   : {summary['failed']}")
    print(f"Errors   : {summary['errors']}")
    print(f"Skipped  : {summary['skipped']}")
    print(f"Evidence : {OUTPUT.relative_to(ROOT)}")

    if result.stdout:
        print(result.stdout)

    if result.stderr:
        print(result.stderr, file=sys.stderr)

    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()

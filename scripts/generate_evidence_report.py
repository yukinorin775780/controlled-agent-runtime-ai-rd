"""Generate an engineering evidence report for project review.

The report is intentionally command-backed: it runs the local quality gates,
parses their results, and writes a compact Markdown artifact that can be linked
from README without turning the project into a screenshot-first demo.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "evidence-report.md"


@dataclass(frozen=True)
class GateResult:
    name: str
    command: str
    status: str
    summary: str
    returncode: int
    details: str = ""


def _run(cmd: Sequence[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(cmd),
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )


def _command_text(cmd: Sequence[str]) -> str:
    return " ".join(cmd)


def _find_last_json_object(output: str, marker: str) -> dict:
    start = output.rfind(marker)
    if start < 0:
        raise ValueError(f"Could not find JSON marker: {marker}")
    return json.loads(output[start:])


def _gate_pytest(timeout: int) -> GateResult:
    cmd = [sys.executable, "-m", "pytest", "-q"]
    display_cmd = "python -m pytest -q"
    proc = _run(cmd, timeout=timeout)
    match = re.search(r"(?P<count>\d+) passed(?:, (?P<warnings>\d+) warnings?)? in (?P<seconds>[\d.]+)s", proc.stdout)
    if proc.returncode == 0 and match:
        warnings = match.group("warnings") or "0"
        return GateResult(
            name="Python unit and integration tests",
            command=display_cmd,
            status="passed",
            summary=f"{match.group('count')} tests passed in {match.group('seconds')}s; warnings: {warnings}.",
            returncode=proc.returncode,
        )
    return GateResult(
        name="Python unit and integration tests",
        command=display_cmd,
        status="failed",
        summary="pytest did not complete successfully.",
        returncode=proc.returncode,
        details=proc.stdout[-3000:],
    )


def _gate_golden(timeout: int) -> GateResult:
    cmd = [sys.executable, "-m", "core.eval.runner", "--suite", "golden"]
    display_cmd = "python -m core.eval.runner --suite golden"
    proc = _run(cmd, timeout=timeout)
    try:
        payload = _find_last_json_object(proc.stdout, '{\n  "case_count"')
    except Exception as exc:
        return GateResult(
            name="Golden replay evals",
            command=display_cmd,
            status="failed",
            summary=f"Could not parse golden eval JSON: {exc}",
            returncode=proc.returncode,
            details=proc.stdout[-3000:],
        )

    case_count = int(payload.get("case_count") or 0)
    passed_count = int(payload.get("passed_count") or 0)
    failed_count = int(payload.get("failed_count") or 0)
    ok = bool(payload.get("ok"))
    status = "passed" if proc.returncode == 0 and ok and failed_count == 0 else "failed"
    return GateResult(
        name="Golden replay evals",
        command=display_cmd,
        status=status,
        summary=f"{passed_count}/{case_count} replay cases passed; failed: {failed_count}.",
        returncode=proc.returncode,
    )


def _gate_benchmark_dry_run(timeout: int) -> GateResult:
    cmd = [sys.executable, "scripts/generate_benchmark.py", "--dry-run", "--max-cases", "4"]
    display_cmd = "python scripts/generate_benchmark.py --dry-run --max-cases 4"
    proc = _run(cmd, timeout=timeout)
    cases = [
        line.strip()[2:]
        for line in proc.stdout.splitlines()
        if line.strip().startswith("- ")
    ]
    status = "passed" if proc.returncode == 0 and cases else "failed"
    return GateResult(
        name="Benchmark dry-run selection",
        command=display_cmd,
        status=status,
        summary=f"{len(cases)} benchmark cases selected: {', '.join(cases) if cases else 'none'}.",
        returncode=proc.returncode,
        details="" if status == "passed" else proc.stdout[-3000:],
    )


def _gate_ui(timeout: int) -> GateResult:
    if shutil.which("npm") is None:
        return GateResult(
            name="Web UI tests",
            command="npm test",
            status="skipped",
            summary="npm is not available in PATH.",
            returncode=127,
        )

    cmd = ["npm", "test"]
    proc = _run(cmd, timeout=timeout)
    match = re.search(r"Tests:\s+(?P<passed>\d+) passed,\s+(?P<total>\d+) total", proc.stdout)
    if proc.returncode == 0 and match:
        return GateResult(
            name="Web UI tests",
            command=_command_text(cmd),
            status="passed",
            summary=f"{match.group('passed')}/{match.group('total')} Jest tests passed.",
            returncode=proc.returncode,
        )
    return GateResult(
        name="Web UI tests",
        command=_command_text(cmd),
        status="failed",
        summary="npm test did not complete successfully.",
        returncode=proc.returncode,
        details=proc.stdout[-3000:],
    )


def _status_icon(status: str) -> str:
    return {
        "passed": "PASS",
        "failed": "FAIL",
        "skipped": "SKIP",
    }.get(status, status.upper())


def _gate_table(results: Iterable[GateResult]) -> str:
    rows = [
        "| Gate | Result | Evidence |",
        "| --- | --- | --- |",
    ]
    for result in results:
        rows.append(
            f"| {result.name} | {_status_icon(result.status)} | `{result.command}` -> {result.summary} |"
        )
    return "\n".join(rows)


def _claim_table() -> str:
    return "\n".join(
        [
            "| Claim | What proves it | Relevant code/tests |",
            "| --- | --- | --- |",
            "| Scoped AgentView | Agents receive role-specific prompt/data/tool views rather than raw global state. | `core/actors/builders.py`, `core/actors/visibility.py`, `tests/test_actor_view_builder.py`, `tests/test_visibility_rules.py` |",
            "| Deterministic state mutation | LLM-facing nodes can propose intent, while typed events and event drain own authoritative state writes. | `core/events/models.py`, `core/events/apply.py`, `core/graph/nodes/event_drain.py`, `tests/test_event_drain.py`, `tests/test_actor_invocation_node.py` |",
            "| Replayable behavior | Golden YAML cases validate routing, visibility, memory, state transfer, hidden-state handling, and scenario outcomes without live model calls. | `evals/golden/`, `core/eval/runner.py`, `tests/test_golden_suite_smoke.py` |",
            "| Operator observability | Runtime decisions and state changes are inspectable through route trace, payload summaries, and state diff. | `web_ui/director-trace.js`, `web_ui/state-diff-renderer.js`, `web_ui/tests/app.test.js` |",
            "| Full-stack delivery | The same service path powers API, browser UI, eval runner, and benchmark tooling. | `server.py`, `core/application/game_service.py`, `web_ui/`, `scripts/generate_benchmark.py` |",
        ]
    )


def _write_report(output: Path, results: Sequence[GateResult]) -> None:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    all_required_passed = all(r.status == "passed" for r in results if r.name != "Web UI tests") and any(
        r.name == "Web UI tests" and r.status == "passed" for r in results
    )
    overall = "PASS" if all_required_passed else "CHECK REQUIRED"

    content = f"""# Engineering Evidence Report

Generated at: {generated_at}

Overall status: **{overall}**

This report is a command-backed project evidence artifact. It focuses on reproducible engineering signals instead of screenshots or subjective demo claims.

## Quality Gate

{_gate_table(results)}

## Runtime Claims

{_claim_table()}

## Why This Matters

This project does not claim to be a content-complete product or a model-training system. It demonstrates that LLM agents can be placed inside an engineering runtime with scoped context, tool gates, deterministic state commits, replayable evals, and observable execution traces.

The key engineering claim is:

> The scenario preview is the stress test. The reusable asset is the controlled Agent runtime and its quality gate.

## Reproduce

Run the full evidence report:

```bash
python scripts/generate_evidence_report.py
```

Run the core gate directly:

```bash
make check
```

Run UI tests after installing Node dependencies:

```bash
npm install
npm test
```
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate docs/evidence-report.md from local quality gates.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Markdown report output path.")
    parser.add_argument("--skip-ui", action="store_true", help="Skip npm/Jest UI tests.")
    parser.add_argument("--timeout", type=int, default=180, help="Timeout per gate in seconds.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output

    gates = [
        _gate_pytest,
        _gate_golden,
        _gate_benchmark_dry_run,
    ]
    if not args.skip_ui:
        gates.append(_gate_ui)

    results: list[GateResult] = []
    for gate in gates:
        print(f"Running {gate.__name__.removeprefix('_gate_')}...")
        try:
            result = gate(timeout=int(args.timeout))
        except subprocess.TimeoutExpired as exc:
            result = GateResult(
                name=gate.__name__.removeprefix("_gate_"),
                command="",
                status="failed",
                summary=f"Timed out after {args.timeout}s.",
                returncode=124,
                details=str(exc),
            )
        results.append(result)
        print(f"  {result.status}: {result.summary}")

    _write_report(output, results)
    print(f"Wrote {output}")

    return 0 if all(r.status == "passed" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

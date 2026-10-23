"""Generate backend-owned golden replay evidence for the local workbench."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.eval.runner import run_eval_suite_sync
from core.gate.workbench import ROOT, source_digest


def main() -> int:
    before = source_digest()
    result = run_eval_suite_sync(suite="golden", eval_dir=ROOT / "evals/golden", case_selector=None)
    evidence = {k: result[k] for k in ("suite", "ok", "case_count", "passed_count")}
    evidence["source_digest"] = before
    if before != source_digest():
        raise RuntimeError("Source changed during evaluation; rerun before using evidence.")
    target = ROOT / "artifacts/gate-evidence.json"
    target.parent.mkdir(exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(evidence, indent=2))
    temporary.replace(target)
    print(json.dumps(evidence, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

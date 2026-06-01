.PHONY: test eval benchmark-dry-run evidence check eval-case

test:
	pytest -q

eval:
	python -m core.eval.runner --suite golden

benchmark-dry-run:
	python scripts/generate_benchmark.py --dry-run --max-cases 4

evidence:
	python scripts/generate_evidence_report.py

check:
	pytest -q
	python -m core.eval.runner --suite golden
	python scripts/generate_benchmark.py --dry-run --max-cases 4

eval-case:
ifndef CASE
	$(error CASE is required. Example: make eval-case CASE=analyst_artifact_probe)
endif
	python -m core.eval.runner --case $(CASE)

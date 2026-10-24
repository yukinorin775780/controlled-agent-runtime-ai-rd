# Docker verification — 2026-10-24

Both repositories were built and exercised as actual Linux/arm64 containers on Docker Engine 29.1.3. The images use Python 3.11.17 and run the server as the non-root runtime user (UID 1000).

Per repository: **473 pytest tests passed, 50/50 golden replay passed, Ruff passed, mypy passed for eight boundary modules, and thirteen live HTTP acceptance checks passed.** Static pages loaded over HTTP; role gates allowed Research, denied Reviewer and unknown actors, and denied Ops until source-bound golden evidence passed. Both local-origin CORS acceptance and remote-origin rejection passed. Eight concurrent writes to one session survived without loss. Checkpoints survived forced container recreation, and reset worked afterward.

## Build and run

The host's default Docker Hub route returned an authorization error. These temporary parameters successfully used a public distribution of the official Python image and an accessible package mirror; global Docker settings were untouched.

```bash
CONTROLLED_AGENT_PYTHON_IMAGE=public.ecr.aws/docker/library/python:3.11-slim \
CONTROLLED_AGENT_PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple \
docker compose up --build -d
```

Open http://127.0.0.1:8000/web_ui/. The two repositories both default to port 8000; run them separately or override one host port. No live LLM request was used in this verification; open-ended model chat still needs credentials. No GitHub push or remote CI run was performed.

During acceptance, project names `controlled-agent-rd-test` and `controlled-agent-sim-test` isolated containers and data from existing services. The test containers, test networks and synthetic-data volumes were removed afterward. Built images remain cached.

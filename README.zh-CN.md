# Controlled Agent Runtime Workbench

[![checks](https://github.com/yukinorin775780/controlled-agent-runtime-ai-rd/actions/workflows/checks.yml/badge.svg)](https://github.com/yukinorin775780/controlled-agent-runtime-ai-rd/actions/workflows/checks.yml)

## 出身与真实边界

本项目从 [BG3-LLM-Agent](https://github.com/yukinorin775780/BG3-LLM-Agent) 抽离，早期迭代历史保留在原仓库。[业务工作台](https://github.com/yukinorin775780/controlled-agent-runtime-ai-rd) 与 [仿真版](https://github.com/yukinorin775780/controlled-agent-sim-runtime) 共享可控 Agent Runtime；Hazard Lab 是压力测试场景。

Ops / Research / Reviewer 属于**展示层 reframing**。工作台现在调用真实后端 PolicyGate，但没有外部业务连接器：门控判断不会实际发布、写审计日志或提交 DomainEvent；脱敏字段名也是展示约定。下方历史截图早于此次修复，不作为当前门控结果的证据。

## Evidence / Eval 分层

上方 CI 链接可核查 pytest、golden eval、npm test、Ruff 和核心新模块 mypy 的实际运行。结果以对应提交的公开 CI 运行记录为准。

- **50/50 golden eval** 是无 live model 的确定性逻辑重放，固定模型回复、骰子与时钟，证明逻辑无回归，不证明真实模型质量。
- **真实 LLM benchmark** 只有 4 个 case，需要模型密钥；结论范围限于这些案例。`--dry-run` 只是选择案例。
- 同一状态下路由确定；实时模型文本和普通游戏骰子仍可能变化，重放会显式控制它们。

## 可复现启动

Linux/macOS，Python 3.11+：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
npm ci
pytest -q
python -m core.eval.runner --suite golden
npm test
python server.py
```

或运行 `docker compose up --build`，访问 http://127.0.0.1:8000/web_ui/。开放式聊天需配置模型密钥；工作台门控不需要模型。可选 Chroma / Streamlit 依赖见 `requirements-optional.txt`。

工作台候选请求由 `/api/gate/evaluate` 返回 `allow / deny + reason + matched_rule`。Ops 发布候选默认拒绝；运行 `python scripts/generate_gate_evidence.py`，后端记录当前源码摘要与完整 50/50 结果后才可允许。源码变更使证据失效；这不是生产发布审批。

意图解析、重试和并发边界见 [工程说明](docs/engineering-boundaries.md)。

## 实现关系

仿真主链路由 GameService、LangGraph、ActorView、mechanics、typed events / legacy physics 和 checkpoint 构成。部分旧 mechanics 仍直接修改领域快照，不能声称所有变更都已事件化。业务工作台单独展示候选请求的权限评估：

```text
样例候选 → POST /api/gate/evaluate → 后端 ScopedAgentView → PolicyGate → decision / reason / matched_rule
```

历史截图与旧 evidence report 仅留档。当前验证见 [优化验收记录](docs/optimization-verification.md)，实际结果以 API 与 CI 运行记录为准。

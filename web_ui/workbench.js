/**
 * workbench.js
 * Sample candidate requests; authorization results always come from the backend.
 */
(() => {
  "use strict";

  const PRESETS = Object.freeze({
    policy_publish: {
      intent: "评估 Ops Agent 的分阶段发布候选，核查当前源码的 golden 回放证据。",
      agent: "ops_agent",
      toolCall: {
        name: "publish_policy_patch",
        args: {
          patch_id: "kb-policy-2026-06-01-a",
          eval_suite: "golden",
          rollout: "staged",
        },
      },
    },
    ticket_triage: {
      intent: "评估 Research Agent 近 24 小时公开知识库候选的检索权限。",
      agent: "research_agent",
      toolCall: {
        name: "ticket_search",
        args: {
          window: "24h",
          severity: "high",
          output_scope: "public_kb_candidate",
        },
      },
    },
    release_audit: {
      intent: "验证 Reviewer Agent 的直接发布候选会被权限规则拒绝。",
      agent: "reviewer_agent",
      toolCall: {
        name: "publish_policy_patch",
        args: {patch_id: "agent-runtime-rc-12", eval_suite: "golden", rollout: "staged"},
      },
    },
  });

  const TRACE_NODES = Object.freeze([
    "player_input",
    "dm_router",
    "actor_view_filter",
    "actor_runtime",
    "domain_event",
    "event_drain",
    "ui_events",
  ]);

  function $(id) {
    return document.getElementById(id);
  }

  function safeArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function queryParams() {
    try {
      return new URLSearchParams(window.location.search || "");
    } catch (_err) {
      return new URLSearchParams();
    }
  }

  function hasPreset(key) {
    return Object.prototype.hasOwnProperty.call(PRESETS, key);
  }

  function initialPresetKey() {
    const requested = String(queryParams().get("workbench_preset") || "").trim();
    return hasPreset(requested) ? requested : "policy_publish";
  }

  function queryFlag(name) {
    const value = String(queryParams().get(name) || "").trim().toLowerCase();
    return value === "1" || value === "true" || value === "yes";
  }

  function isBlockedDecision(decision) {
    return decision === "deny";
  }

  async function payloadForPreset(preset) {
    const response = await fetch("/api/gate/evaluate", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({actor_id: preset.agent, tool_name: preset.toolCall.name, args: preset.toolCall.args}),
    });
    if (!response.ok) throw new Error("Gate service returned HTTP " + response.status);
    const payload = await response.json();
    if (!payload.policy_gate || !["allow", "deny"].includes(payload.policy_gate.decision)) {
      throw new Error("Invalid gate response");
    }
    return payload;
  }

  function traceDetails(preset, payload) {
    const base = {
      ms: 0,
      estimated: true,
    };
    const status = payload.policy_gate.decision;
    const blocked = isBlockedDecision(status);
    return {
      player_input: {
        ...base,
        explanation: "Business intent enters the runtime boundary.",
        input: preset.intent,
        output: "TOOL_ORCHESTRATION",
      },
      dm_router: {
        ...base,
        explanation: "Director selects target agent and tool route before model generation.",
        input: "intent + policy registry",
        output: payload.route,
      },
      actor_view_filter: {
        ...base,
        explanation: "Scoped AgentView builds role prompt slice, allowed tools, and masked fields.",
        input: preset.agent + " role policy",
        output: payload.scoped_agent_view.allowed_tools.join(", "),
        signal: "agent_signal",
      },
      actor_runtime: {
        ...base,
        explanation: "Agent runtime prepares a typed tool candidate under the scoped view.",
        input: "scoped AgentView",
        output: preset.toolCall.name,
        signal: "agent_signal",
      },
      domain_event: {
        ...base,
        explanation: "Policy/tool gate validates schema, permission, and preconditions.",
        input: JSON.stringify(preset.toolCall.args),
        output: payload.policy_gate.reason,
        signal: "agent_signal",
      },
      event_drain: {
        ...base,
        explanation: "Evaluation only; no tool execution or durable commit occurred.",
        input: "DomainEvent queue",
        output: "No events committed",
        signal: "agent_signal",
      },
      ui_events: {
        ...base,
        explanation: "Workbench projects response, trace evidence, and state diff.",
        input: "committed events",
        output: "operator trace",
        signal: "agent_signal",
      },
    };
  }

  function setText(id, value) {
    const el = $(id);
    if (el) el.textContent = String(value || "-");
  }

  function renderPayload(payload) {
    const summary = $("payload-summary");
    if (summary) {
      summary.innerHTML = [
        ["Intent", payload.intent],
        ["Agent", payload.selected_agent],
        ["Route", payload.route],
        ["Tools", safeArray(payload.scoped_agent_view.allowed_tools).join(", ")],
        ["Masked", safeArray(payload.scoped_agent_view.masked_fields).join(", ")],
        ["Decision", payload.policy_gate.decision],
      ].map(([label, value]) => (
        '<div class="payload-summary-row"><span>' + label + '</span><strong>' + String(value || "-") + '</strong></div>'
      )).join("");
    }
    const inspector = $("json-inspector");
    if (inspector) {
      inspector.textContent = JSON.stringify(payload, null, 2);
    }
  }

  function renderSignals(payload) {
    const section = document.querySelector(".xray-section--state-watcher");
    if (section) section.classList.remove("is-hidden");
    const confidence = $("patience-label");
    const confidenceValue = $("patience-value");
    const confidenceBar = $("patience-bar");
    const risk = $("fear-label");
    const riskValue = $("fear-value");
    const riskBar = $("fear-bar");
    const approved = !isBlockedDecision(payload.policy_gate.decision);
    if (confidence) confidence.textContent = "Gate Decision";
    if (confidenceValue) confidenceValue.textContent = payload.policy_gate.decision;
    if (confidenceBar) confidenceBar.style.width = approved ? "100%" : "0%";
    if (risk) risk.textContent = "Matched Rule";
    if (riskValue) riskValue.textContent = payload.policy_gate.matched_rule;
    if (riskBar) riskBar.style.width = "0%";
  }

  function setActiveButton(key) {
    document.querySelectorAll("[data-workbench-preset]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.workbenchPreset === key);
    });
  }

  function renderWorkbenchEvidence(preset, payload) {
    const tone = isBlockedDecision(payload.policy_gate.decision) ? "blocked" : "approved";
    const root = $("runtime-workbench");
    if (root) root.dataset.outcome = tone;

    const status = document.querySelector(".workbench-status strong");
    if (status) status.textContent = payload.policy_gate.decision.toUpperCase();

    const outcome = $("workbench-outcome");
    if (outcome) outcome.dataset.outcome = tone;
    setText("workbench-outcome-label", payload.policy_gate.decision.toUpperCase());
    setText("workbench-outcome-title", payload.policy_gate.matched_rule);
    setText("workbench-outcome-detail", payload.policy_gate.reason);

    setText("workbench-proof-agent", payload.selected_agent);
    setText("workbench-proof-tools", safeArray(payload.scoped_agent_view.allowed_tools).join(", "));
    setText("workbench-proof-masked", safeArray(payload.scoped_agent_view.masked_fields).join(", "));
    setText("workbench-proof-events", safeArray(payload.domain_events).join(" -> ") || "No events committed");

    document.querySelectorAll(".scope-table [data-agent]").forEach((row) => {
      const selected = row.dataset.agent === payload.selected_agent;
      row.classList.toggle("is-selected", selected);
      row.classList.toggle("is-muted", !selected);
    });

    document.querySelectorAll(".workbench-flow [data-step]").forEach((step) => {
      step.classList.toggle("is-route-active", ["intent", "router", "scope"].includes(step.dataset.step || ""));
      step.classList.toggle("is-gate-active", ["tool_gate", "event_drain"].includes(step.dataset.step || ""));
    });
  }

  let requestSequence = 0;

  async function activatePreset(key, options = {}) {
    const preset = PRESETS[key] || PRESETS.policy_publish;
    const sequence = ++requestSequence;
    setText("workbench-outcome-label", "EVALUATING");
    const root = $("runtime-workbench");
    if (root) root.dataset.outcome = "pending";
    let payload;
    try {
      payload = await payloadForPreset(preset);
    } catch (error) {
      if (sequence !== requestSequence) return;
      if (root) root.dataset.outcome = "unavailable";
      const status = document.querySelector(".workbench-status strong");
      if (status) status.textContent = "UNAVAILABLE";
      setText("patience-value", "Unavailable");
      setText("fear-value", "Unavailable");
      setText("workbench-outcome-label", "GATE UNAVAILABLE");
      setText("workbench-outcome-title", "No decision received");
      setText("workbench-outcome-detail", error.message);
      const inspector = $("json-inspector");
      if (inspector) inspector.textContent = "No backend decision available.";
      for (const id of ["payload-summary", "workbench-proof-events", "workbench-proof-agent", "workbench-proof-tools", "workbench-proof-masked"]) setText(id, "Unavailable");
      return;
    }
    if (sequence !== requestSequence) return;
    setActiveButton(key);
    const dock = $("dock-input");
    if (dock) dock.value = preset.intent;
    renderWorkbenchEvidence(preset, payload);
    renderPayload(payload);
    renderSignals(payload);
    if (window.ControlledAgentDirectorTrace && typeof window.ControlledAgentDirectorTrace.activateTrace === "function") {
      const staticTrace = options.staticTrace === true;
      window.ControlledAgentDirectorTrace.activateTrace(TRACE_NODES, {
        animate: options.animate !== false,
        stepMs: 280,
        autoIdleMs: staticTrace ? 3600000 : 9000,
        data: payload,
        userLine: preset.intent,
        intent: "TOOL_ORCHESTRATION",
        details: traceDetails(preset, payload),
      });
    }
  }

  function bind() {
    const staticTrace = queryFlag("workbench_static");
    document.querySelectorAll("[data-workbench-preset]").forEach((button) => {
      button.addEventListener("click", () => activatePreset(button.dataset.workbenchPreset || "policy_publish", {
        staticTrace,
      }));
    });
    window.setTimeout(() => activatePreset(initialPresetKey(), {
      animate: !staticTrace,
      staticTrace,
    }), 60);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind, { once: true });
  } else {
    bind();
  }

  window.ControlledAgentWorkbench = Object.freeze({
    PRESETS,
    activatePreset,
    initialPresetKey,
    payloadForPreset,
  });
})();

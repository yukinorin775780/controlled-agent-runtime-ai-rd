/**
 * workbench.js
 * Business-shaped runtime trace presets for the browser workbench.
 */
(() => {
  "use strict";

  const PRESETS = Object.freeze({
    policy_publish: {
      intent: "让 Ops Agent 校验客服知识库变更，eval 通过后调用 publish_policy_patch。",
      agent: "ops_agent",
      route: "tool_orchestration.policy_publish",
      tools: ["eval_summary", "policy_diff_read", "publish_policy_patch"],
      maskedFields: ["raw_user_pii", "billing_token", "private_escalation_notes"],
      toolCall: {
        name: "publish_policy_patch",
        args: {
          patch_id: "kb-policy-2026-06-01-a",
          eval_suite: "golden_support_qa",
          rollout: "staged",
        },
      },
      domainEvents: ["POLICY_CHECK_PASSED", "TOOL_CALL_APPROVED", "AUDIT_LOG_WRITTEN"],
      result: "approved",
    },
    ticket_triage: {
      intent: "让 Research Agent 查询近 24 小时玩家反馈异常，并只返回可公开的知识库候选。",
      agent: "research_agent",
      route: "tool_orchestration.ticket_triage",
      tools: ["ticket_search", "kb_lookup", "semantic_cluster"],
      maskedFields: ["account_id", "payment_context", "internal_owner_notes"],
      toolCall: {
        name: "ticket_search",
        args: {
          window: "24h",
          severity: "high",
          output_scope: "public_kb_candidate",
        },
      },
      domainEvents: ["SCOPE_FILTER_APPLIED", "TOOL_CALL_APPROVED", "TRIAGE_CANDIDATES_EMITTED"],
      result: "approved",
    },
    release_audit: {
      intent: "让 Reviewer Agent 检查灰度发布状态，禁止直接发布，只写入 release audit。",
      agent: "reviewer_agent",
      route: "tool_orchestration.release_audit",
      tools: ["ci_status", "eval_summary", "audit_log_write"],
      maskedFields: ["deploy_token", "direct_publish_action"],
      toolCall: {
        name: "audit_log_write",
        args: {
          release_id: "agent-runtime-rc-12",
          gate: "ci_and_eval",
          decision: "hold_for_manual_release",
        },
      },
      domainEvents: ["DIRECT_PUBLISH_BLOCKED", "CI_STATUS_READ", "AUDIT_LOG_WRITTEN"],
      result: "blocked_publish",
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

  function payloadForPreset(preset) {
    const status = preset.result === "blocked_publish" ? "blocked" : "approved";
    return {
      intent: "TOOL_ORCHESTRATION",
      route: preset.route,
      selected_agent: preset.agent,
      scoped_agent_view: {
        prompt_slice: [
          "task_intent",
          "policy_boundary",
          "allowed_tool_schema",
          "visible_business_context",
        ],
        allowed_tools: preset.tools,
        masked_fields: preset.maskedFields,
      },
      policy_gate: {
        schema_valid: true,
        role_allowed: true,
        preconditions_met: status === "approved",
        decision: status,
      },
      proposed_tool_call: preset.toolCall,
      domain_events: preset.domainEvents,
      ui_events: [
        { type: "policy_check", result: status },
        { type: status === "approved" ? "tool_call_approved" : "tool_call_blocked", tool: preset.toolCall.name },
        { type: "audit_event", result: preset.domainEvents[preset.domainEvents.length - 1] },
      ],
    };
  }

  function traceDetails(preset, payload) {
    const base = {
      ms: 0,
      estimated: true,
    };
    const status = payload.policy_gate.decision;
    return {
      player_input: {
        ...base,
        ms: 42,
        explanation: "Business intent enters the runtime boundary.",
        input: preset.intent,
        output: "TOOL_ORCHESTRATION",
      },
      dm_router: {
        ...base,
        ms: 87,
        explanation: "Director selects target agent and tool route before model generation.",
        input: "intent + policy registry",
        output: preset.route,
      },
      actor_view_filter: {
        ...base,
        ms: 63,
        explanation: "Scoped AgentView builds role prompt slice, allowed tools, and masked fields.",
        input: preset.agent + " role policy",
        output: preset.tools.join(", "),
        signal: "agent_signal",
      },
      actor_runtime: {
        ...base,
        ms: 118,
        explanation: "Agent runtime prepares a typed tool candidate under the scoped view.",
        input: "scoped AgentView",
        output: preset.toolCall.name,
        signal: "agent_signal",
      },
      domain_event: {
        ...base,
        ms: 96,
        explanation: "Policy/tool gate validates schema, permission, and preconditions.",
        input: JSON.stringify(preset.toolCall.args),
        output: status === "approved" ? "tool call approved" : "direct publish blocked",
        signal: "agent_signal",
      },
      event_drain: {
        ...base,
        ms: 52,
        explanation: "EventDrain commits typed audit events and durable state.",
        input: "DomainEvent queue",
        output: preset.domainEvents.join(" -> "),
        signal: "agent_signal",
      },
      ui_events: {
        ...base,
        ms: 39,
        explanation: "Workbench projects response, trace evidence, and state diff.",
        input: "committed events",
        output: "operator trace",
        signal: "agent_signal",
      },
    };
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
    const approved = payload.policy_gate.decision === "approved";
    if (confidence) confidence.textContent = "Policy Confidence";
    if (confidenceValue) confidenceValue.textContent = approved ? "92" : "68";
    if (confidenceBar) confidenceBar.style.width = approved ? "92%" : "68%";
    if (risk) risk.textContent = "Tool Risk";
    if (riskValue) riskValue.textContent = approved ? "18" : "61";
    if (riskBar) riskBar.style.width = approved ? "18%" : "61%";
  }

  function setActiveButton(key) {
    document.querySelectorAll("[data-workbench-preset]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.workbenchPreset === key);
    });
  }

  function activatePreset(key, options = {}) {
    const preset = PRESETS[key] || PRESETS.policy_publish;
    const payload = payloadForPreset(preset);
    setActiveButton(key);
    const dock = $("dock-input");
    if (dock) dock.value = preset.intent;
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

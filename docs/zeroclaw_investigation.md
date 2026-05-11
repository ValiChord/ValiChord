# ZeroClaw Investigation — Findings

> Investigated: 2026-05-11  
> Repo: https://github.com/zeroclaw-labs/zeroclaw  
> Latest release at time of investigation: v0.7.5 (2026-05-08)

---

## Q1. Does the [identity] block (AIEOS persona) actually affect the LLM call?

### a. Where is identity loaded/parsed?

`crates/zeroclaw-runtime/src/identity.rs:160` — `pub fn load_aieos_identity(config: &IdentityConfig, workspace_dir: &Path)`.

The function checks `config.format == "aieos"`, then loads either `config.aieos_path` (file relative to workspace) or `config.aieos_inline` (raw JSON string). The `IdentityConfig` struct is defined in `crates/zeroclaw-config/src/schema.rs:2035`.

### b. Where is it used?

Injected directly into the system prompt at `crates/zeroclaw-runtime/src/agent/system_prompt.rs` (build_system_prompt_with_mode_and_autonomy, step 5, "## Project Context" section). Key code:

```rust
// crates/zeroclaw-runtime/src/agent/system_prompt.rs ~line 280
if let Some(config) = identity_config {
    if identity::is_aieos_configured(config) {
        match identity::load_aieos_identity(config, workspace_dir) {
            Ok(Some(aieos_identity)) => {
                let aieos_prompt = identity::aieos_to_system_prompt(&aieos_identity);
                if !aieos_prompt.is_empty() {
                    prompt.push_str(&aieos_prompt);
                    prompt.push_str("\n\n");
                }
            }
            ...
        }
    }
}
```

`aieos_to_system_prompt` is called at `crates/zeroclaw-runtime/src/identity.rs:718`. This is **not** logs/metadata only — it is placed verbatim in the system prompt string that is subsequently sent to the LLM provider. The system prompt is consumed at `crates/zeroclaw-runtime/src/agent/loop_.rs:2521` where `build_system_prompt_with_mode_and_autonomy` is called, and the resulting string is passed to the provider `chat()` / `stream_chat()` calls.

### c. Sample resulting system prompt

Given an AIEOS block with `identity.names.first = "Nova"`, `identity.psychology.mbti = "INTJ"`, the rendered fragment (placed after the "## Project Context" heading) would be:

```
## Project Context

## Identity

**Name:** Nova

## Personality

**MBTI:** INTJ
```

The full system prompt wraps this in sections for Tools, Safety, Skills, Workspace, Project Context (→ AIEOS fragment here), Current Date & Time, and Runtime. Identity replaces the `AGENTS.md / SOUL.md / IDENTITY.md` workspace-file injection — it does not stack on top.

### d. Do 9 instances with 3 distinct identity blocks produce 3 distinct system prompts?

Yes. Each ZeroClaw process reads its own `config.identity` block at startup (`crates/zeroclaw-runtime/src/agent/loop_.rs:2526` passes `Some(&config.identity)` to the builder). The builder deterministically converts the AIEOS JSON to a prompt string (keys are sorted for determinism: `crates/zeroclaw-runtime/src/identity.rs:1457`). Three distinct AIEOS files produce three distinct `## Identity` / `## Personality` blocks in the system prompt. Instances sharing the same AIEOS file produce identical system prompts for that section. There is no global static that caches the system prompt across instances.

---

## Q2. Process supervision

### a. Health-check endpoint

Present. `GET /health` — `crates/zeroclaw-gateway/src/lib.rs:1049` routes it to `handle_health`. Response shape:

```json
{
  "status": "ok",
  "paired": true,
  "require_pairing": true,
  "runtime": { "pid": ..., "uptime_seconds": ..., "components": { ... } }
}
```

No authentication required (not behind `PairingGuard`). The `runtime` field comes from `crates/zeroclaw-runtime/src/health::snapshot_json()`.

### b. Automatic restart mechanism

**Not present in-process.** ZeroClaw has a `DaemonExit::Reload` path (`crates/zeroclaw-runtime/src/daemon/mod.rs:18-20`) that tears down and re-initialises in-process subsystems without changing the PID — triggered by `POST /admin/reload`. This is a config reload, not a crash recovery. There is no supervisor loop inside the binary that re-spawns on panic. Crash recovery depends entirely on the external process manager:

- `zeroclaw service install` registers the process as systemd (Linux) / launchctl (macOS) / Windows Service (`src/service/`). The OS service manager provides restart-on-crash by its own policy (e.g. `Restart=on-failure` in the generated systemd unit).
- Docker / Kubernetes deployments use the container runtime's restart policy.
- Running `zeroclaw gateway start` without a service manager gives no automatic restart.

### c. Failure mode from caller's perspective if instance crashes mid-request

The TCP connection is dropped without a response. The caller receives a connection-reset or EOF on the open HTTP/WebSocket socket. The gateway does not use a queue that persists across crashes; the in-flight request is lost. On reconnect the caller must re-submit the request.

### d. Log surfacing for crashes

Component health is tracked in-memory by `crates/zeroclaw-runtime/src/health/mod.rs`. `mark_component_error(component, error)` stores the last error string per component. These appear in `GET /health` under `components.<name>.last_error`. A process crash does not call `mark_component_error` — there is no crash-to-health-endpoint feedback path. Crashes are surfaced only via the OS service manager journal (systemd: `journalctl -u zeroclaw`) or stdout/stderr tracing output.

---

## Q3. Five open questions from DemoZero plan

### a. Env var names for config path and workspace

- Config dir: `ZEROCLAW_CONFIG_DIR` — `crates/zeroclaw-config/src/schema.rs:9714`. Overrides the `~/.zeroclaw/` parent directory.
- Workspace: `ZEROCLAW_WORKSPACE` — `crates/zeroclaw-config/src/schema.rs:69` (doc comment) and parsed in the same `apply_env_overrides` block. Overrides the resolved workspace directory directly.

Resolution order for workspace: `ZEROCLAW_WORKSPACE` env → `active_workspace.toml` marker file → default `~/.zeroclaw/workspace`.

### b. Gateway /webhook response shape

Success response: `crates/zeroclaw-gateway/src/lib.rs:~1516`:

```rust
let body = serde_json::json!({"response": response, "model": state.model});
(StatusCode::OK, Json(body))
```

The LLM response text is in the `"response"` key. There is no `WebhookResponse` struct; the JSON is constructed inline. The request body requires `{"message": "..."}` (`WebhookBody` struct at `lib.rs:1622`).

### c. `require_pairing = false` — valid config key?

Yes. It is defined at `crates/zeroclaw-config/src/schema.rs:2325-2326` inside `GatewayConfig`:

```rust
/// Require pairing before accepting requests (default: true)
#[serde(default = "default_true")]
pub require_pairing: bool,
```

In `config.toml` it lives under `[gateway]`:

```toml
[gateway]
require_pairing = false
```

It can also be overridden at runtime via `ZEROCLAW_REQUIRE_PAIRING=false` (`schema.rs:11501`). Default is `true`.

### d. OpenRouter model IDs: are `mistralai/mistral-large` and `meta-llama/llama-3.3-70b-instruct` current valid slugs?

Neither slug was confirmed as a current valid slug on the OpenRouter `/api/v1/models` endpoint as of 2026-05-11. The WebFetch query against `https://openrouter.ai/api/v1/models` returned no match for `mistral-large` or `llama-3.3-70b`. Available Mistral models at time of investigation: `mistralai/mistral-medium-3.5`, `mistralai/mistral-small-2603`. ZeroClaw's `openrouter.rs` does **no client-side model validation** (`crates/zeroclaw-providers/src/openrouter.rs:485` — `list_models()` is a utility function, not a guard). An invalid slug will return a 4xx error from OpenRouter at call time, not at startup.

**Action required before DemoZero:** verify current slugs at https://openrouter.ai/models or via `zeroclaw models list --provider openrouter`.

### e. `num_validators_required` in ValiChord

Defined in the **integrity zome** as a field of the `ValidationRequest` entry type:

- `valichord/dnas/attestation/zomes/attestation_integrity/src/lib.rs:70` — `pub num_validators_required: u8` (inside `ValidationRequest` struct)
- Integrity validation enforces `>= 1` and `>= props.minimum_validators` at `attestation_integrity/src/lib.rs:582-594`

Referenced in the coordinator zomes:

- `valichord/dnas/attestation/zomes/attestation_coordinator/src/lib.rs:591` — `pub fn get_num_validators_required(data_hash: ExternalHash) -> ExternResult<u8>`
- `valichord/dnas/governance/zomes/governance_coordinator/src/lib.rs:163` — cross-DNA call to `get_num_validators_required`

---

## Q4. Cross-process independence

### a. Shared static state between instances?

Three process-level statics exist in `crates/zeroclaw-runtime/src/agent/loop_.rs`:

- `CLI_CHANNEL_FN: OnceLock<...>` (line 4) — CLI channel factory, set once at startup
- `PERIPHERAL_TOOLS_FN: OnceLock<...>` (line 26) — hardware tools factory
- `MODEL_SWITCH_REQUEST: LazyLock<Arc<Mutex<Option<(String, String)>>>>` (line 93) — live model switch state

`crates/zeroclaw-runtime/src/health/mod.rs` has `static REGISTRY: OnceLock<HealthRegistry>`.

All are process-local statics (standard Rust `static`). They are **not shared across OS processes**. Separate ZeroClaw processes each have independent copies. Within a single process, `MODEL_SWITCH_REQUEST` is shared across async tasks (it is wrapped in `Arc<Mutex>`) — this is intra-process coordination, not cross-instance.

### b. Shared filesystem state?

Yes, if two instances point at the same workspace directory:
- `brain.db` (SQLite memory store) — concurrent writes will contend on the SQLite lock
- `config.toml` — both processes read it at startup; `/admin/reload` on one instance writes paired tokens back
- `costs.jsonl` — both instances append cost records

Mitigation: use distinct workspace directories per instance (`ZEROCLAW_WORKSPACE` or `workspace.active_workspace` in config). The multi-workspace feature (`WorkspaceConfig`, `schema.rs:494`) exists precisely for this isolation.

### c. LLM response caching across instances?

No response caching across instances. OpenRouter's prompt caching (recently added in `feat(provider): add prompt caching to OpenRouter` commit `d8ba18c4`, 2026-05-11) is server-side at OpenRouter — it reduces billing on repeated prefixes but is transparent to the caller and per-session, not shared across ZeroClaw processes.

---

## Q5. Skill-loading mechanism

### a. Does SKILL.md get injected into every LLM call, only on triggers, or only when invoked?

Skills are loaded at startup from `~/.zeroclaw/workspace/skills/<name>/SKILL.md` (or `SKILL.toml`) by `load_skills()` at `crates/zeroclaw-runtime/src/skills/mod.rs:164`. The loaded skills are passed to `build_system_prompt_with_mode_and_autonomy` at `loop_.rs:2525`. In the default `SkillsPromptInjectionMode::Full` mode, **all skill instructions are injected into every LLM call** as part of the system prompt (section `## Available Skills`, `skills/mod.rs:882`). There is no trigger-based or lazy loading for `Full` mode.

In `SkillsPromptInjectionMode::Compact` mode (`skills/mod.rs:888`), only skill names and tool metadata are injected; the full instructions are loaded on-demand by the model calling `read_skill(name)`.

### b. Does it stack with [identity] system prompt or replace it?

Skills **stack with** the AIEOS identity. The build order in `build_system_prompt_with_mode_and_autonomy` is:

1. Anti-narration + Tool Honesty (always)
2. Tools list
3. Safety
4. **Skills** (section 3 of the prompt)
5. Workspace
6. **Identity** (section 5, "## Project Context")
7. Date & Time
8. Runtime
9. Channel Capabilities

AIEOS identity replaces the OpenClaw workspace-file injection (AGENTS.md, SOUL.md, etc.) but does not replace the Skills section. Skills and identity coexist in the same prompt string.

### c. Response format risk — would SKILL.md instructions override the JSON format requirement?

Yes, a SKILL.md that includes output-format instructions (e.g. "always respond with plain text") would override a caller-imposed JSON format requirement because both land in the same flat system prompt string. There is no priority mechanism between them — the LLM sees them as sequential markdown sections. If ValiChord's Oracle validation workflow requires structured JSON output from the agent, either: (a) the JSON format requirement must appear after the skill instructions in the prompt, or (b) the format instruction must be placed in the `user` message rather than the system prompt. This is a real integration risk for any ZeroClaw instance with community skills installed.

---

## Q6. Project health

- **Last commit date:** 2026-05-11 (active on day of investigation)
- **Last release date and version:** v0.7.5, 2026-05-08
- **Open issues count:** 481 open issues; none stale (all updated within 90 days as of 2026-05-11)
- **Contributor count (last 6 months):** The GitHub contributors API shows 100+ contributors listed; 24 contributors are credited in the v0.7.5 CHANGELOG entry. The `/stats/contributors` API returned an empty array (GitHub stats lag on active repos), but commit history shows daily activity from multiple authors.
- **Maintenance/backing signals:** 31,247 stars, 4,602 forks, 145 releases since Feb 2026, 3,204 commits. Active Discord, dual MIT/Apache license, Harvard/MIT incubation credit. Project lead `@JordanTheJet` and original creator `@theonlyhennygod` are actively committing. Org is `zeroclaw-labs`.
- **Breaking change frequency:** One breaking change in the last 10 releases (v0.7.3 / v0.7.0-beta, April 2026): config schema V1→V2 migration (`zeroclaw config migrate`). The v0.7.3 changelog entry describes it as auto-migrated with backward compatibility. No breaking changes in v0.7.4 or v0.7.5.

---

## Q7. Cost predictability

### a. Per-call cost tracking

Present. `crates/zeroclaw-config/src/schema.rs:2067` defines `CostConfig` with `enabled: bool` (default `true`), `daily_limit_usd` (default 10.00), `monthly_limit_usd` (default 100.00). Cost is recorded on every webhook call: `crates/zeroclaw-gateway/src/lib.rs:1774` calls `state.observer.record_event(ObserverEvent::LlmResponse { ... })`. Per-provider pricing is configured under `ModelProviderConfig` (added in v0.7.5: `feat: per-provider pricing makes cost tracking real`). Results are accessible via `GET /api/cost` and appended to `costs.jsonl`.

### b. Rate limiting / budget caps

Present. `CostEnforcementConfig` (`schema.rs:2102`) with three modes:
- `"warn"` (default) — log warning when budget is approached/exceeded
- `"block"` — refuse requests that would exceed budget
- `"route_down"` — route to a cheaper model (`route_down_model` field)

Warn threshold: `warn_at_percent` (default 80% of limit). `allow_override: bool` (default `false`) controls whether the `--override` flag can bypass the block.

Webhook rate limiting: `webhook_rate_limit_per_minute` in `GatewayConfig` (default set by `default_webhook_rate_limit()`), enforced in `handle_webhook` at `lib.rs:1636`.

### c. Kill-switch for runaway instances

No dedicated kill-switch. The available options:
- `POST /admin/shutdown` — graceful shutdown (`lib.rs:1044`)
- SIGTERM to the process — triggers `DaemonExit::Shutdown`
- OS service manager: `systemctl stop zeroclaw` / `zeroclaw service stop`
- Budget enforcement in `"block"` mode effectively prevents additional LLM calls without stopping the process

There is no circuit-breaker that auto-halts a specific runaway instance based on cost or call rate.

---

## Decision Recommendation

**(b) Use direct API calls because:**

The primary use case for ValiChord's DemoZero is: a single-study Oracle validator calls an LLM once per validation cycle with a structured prompt and receives a structured JSON verdict. ZeroClaw adds: AIEOS identity injection (confirmed useful for Q1), skills injection into every call (introduces format-override risk per Q5c), mandatory filesystem state for workspace/config (adds deployment surface per Q4b), a pairing handshake (adds a setup step), and a process that must be supervised externally (Q2b). The benefit — AIEOS persona differentiation per validator instance (Q1d: confirmed distinct prompts from distinct identity files) — is real but achievable more cheaply by including the persona text directly in the system prompt of a direct API call.

The specific risks that outweigh ZeroClaw's benefits for DemoZero:

1. **Q3b / response shape:** the `/webhook` endpoint returns `{"response": "...", "model": "..."}` — straightforward, but adds a network hop through the ZeroClaw gateway running on the same or adjacent machine, buying nothing over a direct Anthropic/OpenRouter call.
2. **Q5c / format risk:** any installed `SKILL.md` can silently override the JSON verdict format ValiChord requires. Safe only on a clean instance with zero skills installed — a fragile operational constraint.
3. **Q3d / model slug uncertainty:** `mistralai/mistral-large` and `meta-llama/llama-3.3-70b-instruct` are not confirmed valid slugs as of 2026-05-11. Direct API calls expose the same risk but make it immediately visible at the call site.

If ValiChord later needs multi-channel routing, SOP automation, or a persistent agent loop, ZeroClaw becomes the better choice and Q1/Q6 findings confirm it is well-maintained.

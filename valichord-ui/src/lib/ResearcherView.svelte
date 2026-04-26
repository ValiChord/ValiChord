<script lang="ts">
  import { onMount } from "svelte";
  import { callZome, externalHashFromHex, shortHash } from "./holochain.js";
  import { notify } from "./store.js";
  import type {
    ValidationRequest,
    Discipline,
    ValidationTier,
    DepositAccessType,
    LockedResult,
    LockResultInput,
    ResearcherRevealInput,
    MetricResult,
    HolochainRecord,
  } from "./types.js";
  import { disciplineLabel, entryFromRecord, hashFromRecord } from "./types.js";
  import type { ActionHash } from "@holochain/client";

  // ── State ────────────────────────────────────────────────────────────────────

  type Screen = "list" | "new-request" | "request-detail";

  let screen: Screen = "list";
  let loading = false;

  // ── Form state ───────────────────────────────────────────────────────────────

  let form = {
    data_access_url: "",
    data_hash_hex: "",
    protocol_access_url: "",
    discipline_type: "ComputationalBiology",
    discipline_other: "",
    validation_tier: "Basic" as ValidationTier,
    num_validators_required: 3,
    researcher_institution: "",
    deposit_access_type: "PublicUrl" as DepositAccessType,
    deposit_token: "",
  };

  // ── Load ─────────────────────────────────────────────────────────────────────

  async function loadRequests() {
    // No "get my requests" endpoint exists — requests are looked up by data_hash.
    // This is a no-op placeholder; look-up is via the hash input below.
  }

  onMount(loadRequests);

  // ── Submit ────────────────────────────────────────────────────────────────────

  async function submitRequest() {
    if (!form.data_hash_hex || form.data_hash_hex.length !== 64) {
      notify("error", "Data hash must be a 64-character hex SHA-256");
      return;
    }
    loading = true;
    try {
      const dataHash = externalHashFromHex(form.data_hash_hex);
      const discipline: Discipline =
        form.discipline_type === "Other"
          ? { type: "Other", content: form.discipline_other }
          : ({ type: form.discipline_type } as Discipline);

      const input: ValidationRequest = {
        data_hash: dataHash,
        data_access_url: form.data_access_url,
        deposit_access_type: form.deposit_access_type,
        deposit_token: form.deposit_access_type === "TokenGated" ? form.deposit_token || null : null,
        protocol_ref: null,
        protocol_access_url: form.protocol_access_url || null,
        num_validators_required: form.num_validators_required,
        validation_tier: form.validation_tier,
        discipline,
        researcher_institution: form.researcher_institution,
      };

      const hash = await callZome<ActionHash>("attestation", "submit_validation_request", input);
      notify("success", `Validation request submitted — ${shortHash(hash)}`);
      screen = "list";
      await loadRequests();
    } catch (err) {
      notify("error", `Failed: ${err}`);
    } finally {
      loading = false;
    }
  }

  // ── Look up a request by data hash ───────────────────────────────────────────

  let lookupHex = "";
  let lookedUpRequest: HolochainRecord<ValidationRequest> | null = null;

  async function lookupByHash() {
    if (lookupHex.length !== 64) {
      notify("error", "Enter a 64-character hex SHA-256");
      return;
    }
    loading = true;
    try {
      const dataHash = externalHashFromHex(lookupHex);
      const record = await callZome<HolochainRecord<ValidationRequest> | null>(
        "attestation",
        "get_validation_request_for_data_hash",
        dataHash,
      );
      lookedUpRequest = record;
      if (!record) notify("info", "No request found for that hash");
    } catch (err) {
      notify("error", `Lookup failed: ${err}`);
    } finally {
      loading = false;
    }
  }

  const DISCIPLINES = [
    "ComputationalBiology",
    "ClimateScience",
    "SocialScience",
    "Economics",
    "Psychology",
    "Neuroscience",
    "MachineLearning",
    "Other",
  ];

  const TIERS: ValidationTier[] = ["Basic", "Enhanced", "Comprehensive"];
  const metricsPlaceholder = '[{"metric_name":"...","produced_value":"...","expected_value":"...","within_tolerance":true}]';

  // ── Researcher commit-reveal ──────────────────────────────────────────────────
  // Step 1: lock result — call researcher_repository to store metrics+nonce privately
  //         and publish commitment hash to attestation DNA.
  // Step 2: reveal — retrieve the locked nonce, then call reveal_researcher_result
  //         on attestation DNA to publish metrics.

  let lockHex = "";
  let metricsJson = '[{"metric_name":"","produced_value":"","expected_value":"","within_tolerance":true}]';
  let lockLoading = false;
  let lockedResult: LockedResult | null = null;
  let revealLoading = false;
  let revealHex = "";

  async function lockResult() {
    if (lockHex.length !== 64) {
      notify("error", "Enter the 64-character hex SHA-256 of the study's request_ref");
      return;
    }
    lockLoading = true;
    try {
      let metrics: MetricResult[];
      try {
        metrics = JSON.parse(metricsJson) as MetricResult[];
      } catch {
        notify("error", "Metrics JSON is invalid");
        return;
      }
      const requestRef = externalHashFromHex(lockHex);
      const input: LockResultInput = { request_ref: requestRef, metrics };
      await callZome<ActionHash>("researcher_repository", "lock_researcher_result", input);
      notify("success", "Result locked — commitment published to attestation DHT");
      lockHex = "";
    } catch (err) {
      notify("error", `Lock failed: ${err}`);
    } finally {
      lockLoading = false;
    }
  }

  async function fetchLockedResult() {
    if (revealHex.length !== 64) {
      notify("error", "Enter the 64-character hex SHA-256");
      return;
    }
    revealLoading = true;
    try {
      const requestRef = externalHashFromHex(revealHex);
      const record = await callZome<HolochainRecord<LockedResult> | null>(
        "researcher_repository",
        "get_locked_result",
        requestRef,
      );
      if (!record) {
        notify("info", "No locked result found — lock your result first");
        return;
      }
      lockedResult = entryFromRecord(record);
    } catch (err) {
      notify("error", `Fetch failed: ${err}`);
    } finally {
      revealLoading = false;
    }
  }

  async function revealResult() {
    if (!lockedResult) return;
    revealLoading = true;
    try {
      const input: ResearcherRevealInput = {
        request_ref: lockedResult.request_ref,
        metrics: lockedResult.metrics,
        nonce: lockedResult.nonce,
      };
      await callZome("attestation", "reveal_researcher_result", input);
      notify("success", "Researcher result revealed — validators can now compare their findings");
      lockedResult = null;
      revealHex = "";
    } catch (err) {
      notify("error", `Reveal failed: ${err}`);
    } finally {
      revealLoading = false;
    }
  }
</script>

<div class="researcher">
  <!-- ── Top bar ──────────────────────────────────────────────────────────── -->
  <div class="topbar">
    <h1>
      {#if screen === "list"}Researcher Dashboard
      {:else if screen === "new-request"}Submit Validation Request
      {:else}Request Detail{/if}
    </h1>
    {#if screen === "list"}
      <button class="btn-primary" on:click={() => (screen = "new-request")}>+ New Request</button>
    {:else}
      <button class="btn-ghost" on:click={() => (screen = "list")}>← Back</button>
    {/if}
  </div>

  <!-- ── List screen ──────────────────────────────────────────────────────── -->
  {#if screen === "list"}
    <!-- Look up any request by data hash -->
    <section class="card">
      <h2>Look up a request by data hash</h2>
      <p class="sub">Enter the SHA-256 hex of your deposit to view its validation status.</p>
      <div class="row">
        <input
          type="text"
          placeholder="64-char hex SHA-256 (e.g. a3f2…)"
          maxlength="64"
          bind:value={lookupHex}
          class="mono"
        />
        <button class="btn-primary" on:click={lookupByHash} disabled={loading}>Look up</button>
      </div>

      {#if lookedUpRequest}
        {@const entry = entryFromRecord(lookedUpRequest)}
        {@const hash = hashFromRecord(lookedUpRequest)}
        {#if entry}
          <div class="request-card">
            <div class="rcard-header">
              <span class="discipline-tag">{disciplineLabel(entry.discipline)}</span>
              <span class="tier-tag tier-{entry.validation_tier.toLowerCase()}"
                >{entry.validation_tier}</span
              >
            </div>
            <div class="rcard-url">
              <a href={entry.data_access_url} target="_blank" rel="noreferrer">
                {entry.data_access_url}
              </a>
            </div>
            <div class="rcard-meta">
              <span>{entry.num_validators_required} validators required</span>
              <span class="hash-label">{shortHash(hash)}</span>
            </div>
            {#if entry.protocol_access_url}
              <div class="rcard-meta">
                Protocol: <a href={entry.protocol_access_url} target="_blank" rel="noreferrer">
                  {entry.protocol_access_url}
                </a>
              </div>
            {/if}
          </div>
        {/if}
      {/if}
    </section>

    <!-- Step 2: Lock result (commit your metrics before validators reveal) -->
    <section class="card">
      <h2>Step 2 — Lock your result</h2>
      <p class="sub">
        Before validators reveal their assessments, commit your original metrics. This prevents you
        from changing your claimed result after seeing validator findings.
      </p>
      <label>
        Request data hash (hex)
        <input type="text" bind:value={lockHex} placeholder="64-char hex SHA-256" maxlength="64" class="mono" />
      </label>
      <label>
        Metrics (JSON array)
        <textarea bind:value={metricsJson} rows="4" placeholder={metricsPlaceholder}></textarea>
        <span class="hint">Each entry: metric_name, produced_value, expected_value, within_tolerance (bool)</span>
      </label>
      <div class="form-actions">
        <button class="btn-primary" on:click={lockResult} disabled={lockLoading}>
          {lockLoading ? "Locking…" : "Lock result"}
        </button>
      </div>
    </section>

    <!-- Step 3: Reveal result (after all validators have committed) -->
    <section class="card">
      <h2>Step 3 — Reveal your result</h2>
      <p class="sub">
        Once all validators have sealed their private attestations, publish your metrics to the
        shared DHT. This opens the reveal phase.
      </p>
      <div class="row">
        <input type="text" bind:value={revealHex} placeholder="64-char hex SHA-256" maxlength="64" class="mono" />
        <button class="btn-ghost" on:click={fetchLockedResult} disabled={revealLoading}>
          {revealLoading ? "Loading…" : "Load locked result"}
        </button>
      </div>
      {#if lockedResult}
        <div class="locked-summary">
          <span class="locked-label">Locked metrics: {lockedResult.metrics.length} metric{lockedResult.metrics.length !== 1 ? "s" : ""}</span>
          {#each lockedResult.metrics as m}
            <div class="metric-row">
              <span class="metric-name">{m.metric_name}</span>
              <span class="metric-val">produced: <code>{m.produced_value}</code></span>
              <span class="metric-val">expected: <code>{m.expected_value}</code></span>
              <span class:match={m.within_tolerance} class:mismatch={!m.within_tolerance}>
                {m.within_tolerance ? "✓ within tolerance" : "✗ outside tolerance"}
              </span>
            </div>
          {/each}
        </div>
        <div class="form-actions">
          <button class="btn-primary" on:click={revealResult} disabled={revealLoading}>
            {revealLoading ? "Revealing…" : "Publish reveal"}
          </button>
        </div>
      {/if}
    </section>

  <!-- ── New request form ─────────────────────────────────────────────────── -->
  {:else if screen === "new-request"}
    <form class="request-form card" on:submit|preventDefault={submitRequest}>
      <fieldset>
        <legend>Deposit</legend>

        <label>
          Deposit URL <span class="req">*</span>
          <input
            type="url"
            bind:value={form.data_access_url}
            placeholder="https://zenodo.org/record/..."
            required
          />
          <span class="hint">Public URL where validators can download the deposit</span>
        </label>

        <label>
          Data hash (SHA-256 hex) <span class="req">*</span>
          <input
            type="text"
            bind:value={form.data_hash_hex}
            placeholder="64-character lowercase hex"
            maxlength="64"
            pattern="[0-9a-f]{64}"
            required
            class="mono"
          />
          <span class="hint">Run <code>sha256sum &lt;deposit.zip&gt;</code> to compute</span>
        </label>

        <label>
          Access type
          <select bind:value={form.deposit_access_type}>
            <option value="PublicUrl">Public URL (no credential required)</option>
            <option value="TokenGated">Token-gated (validators receive a one-time token)</option>
          </select>
        </label>

        {#if form.deposit_access_type === "TokenGated"}
          <label>
            Access token <span class="req">*</span>
            <input
              type="text"
              bind:value={form.deposit_token}
              placeholder="Secret download token"
              required
            />
            <span class="hint"
              >Stored on the credentialed validator-only Attestation DHT — not public</span
            >
          </label>
        {/if}
      </fieldset>

      <fieldset>
        <legend>Protocol</legend>
        <label>
          Pre-registration URL
          <input
            type="url"
            bind:value={form.protocol_access_url}
            placeholder="https://osf.io/... (optional)"
          />
          <span class="hint">OSF, AsPredicted, ClinicalTrials.gov pre-registration</span>
        </label>
      </fieldset>

      <fieldset>
        <legend>Validation parameters</legend>

        <label>
          Discipline <span class="req">*</span>
          <select bind:value={form.discipline_type} required>
            {#each DISCIPLINES as d}
              <option value={d}>{disciplineLabel({ type: d } as Discipline)}</option>
            {/each}
          </select>
        </label>

        {#if form.discipline_type === "Other"}
          <label>
            Discipline name <span class="req">*</span>
            <input
              type="text"
              bind:value={form.discipline_other}
              placeholder="e.g. Epidemiology"
              required
            />
          </label>
        {/if}

        <label>
          Validation tier
          <select bind:value={form.validation_tier}>
            {#each TIERS as t}
              <option value={t}>{t}</option>
            {/each}
          </select>
          <span class="hint"
            >Basic = code runs + key results reproduced · Enhanced = + methodology audit ·
            Comprehensive = + data quality</span
          >
        </label>

        <label>
          Number of validators required
          <input
            type="number"
            bind:value={form.num_validators_required}
            min="1"
            max="20"
            required
          />
        </label>

        <label>
          Your institution
          <input
            type="text"
            bind:value={form.researcher_institution}
            placeholder="e.g. University of Edinburgh"
          />
          <span class="hint">Used for conflict-of-interest checks — validators from the same institution will not be assigned</span>
        </label>
      </fieldset>

      <div class="form-actions">
        <button type="button" class="btn-ghost" on:click={() => (screen = "list")}>Cancel</button>
        <button type="submit" class="btn-primary" disabled={loading}>
          {loading ? "Submitting…" : "Submit request"}
        </button>
      </div>
    </form>
  {/if}
</div>

<style>
  .researcher {
    max-width: 760px;
  }

  .topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1.5rem;
  }
  h1 {
    margin: 0;
    font-size: 1.5rem;
  }

  .card {
    background: #1a1d27;
    border: 1px solid #2d3148;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
  }
  .card h2 {
    margin: 0 0 0.4rem;
    font-size: 1rem;
    color: #e2e8f0;
  }
  .card .sub {
    color: #9ca3af;
    font-size: 0.875rem;
    margin: 0 0 1rem;
  }

  .empty-hint {
    color: #6b7280;
    font-size: 0.9rem;
  }
  .empty-hint p {
    margin: 0;
  }

  .row {
    display: flex;
    gap: 0.75rem;
  }
  .row input {
    flex: 1;
  }

  .request-card {
    margin-top: 1.25rem;
    background: #111827;
    border: 1px solid #2d3148;
    border-radius: 8px;
    padding: 1rem;
  }
  .rcard-header {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
  }
  .discipline-tag {
    background: #1e3a5f;
    color: #93c5fd;
    font-size: 0.78rem;
    padding: 0.2em 0.6em;
    border-radius: 4px;
  }
  .tier-tag {
    font-size: 0.78rem;
    padding: 0.2em 0.6em;
    border-radius: 4px;
  }
  .tier-basic {
    background: #1c2014;
    color: #a3e635;
  }
  .tier-enhanced {
    background: #1c1f2e;
    color: #818cf8;
  }
  .tier-comprehensive {
    background: #1c1a20;
    color: #e879f9;
  }
  .rcard-url {
    font-size: 0.875rem;
    margin-bottom: 0.5rem;
  }
  .rcard-url a {
    color: #7c8fdb;
    text-decoration: none;
    word-break: break-all;
  }
  .rcard-meta {
    display: flex;
    justify-content: space-between;
    font-size: 0.8rem;
    color: #6b7280;
  }
  .hash-label {
    font-family: monospace;
  }

  /* ── Form ──────────────────────────────────────────────────────────────── */

  .request-form {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  fieldset {
    border: 1px solid #2d3148;
    border-radius: 8px;
    padding: 1.25rem;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  legend {
    padding: 0 0.5rem;
    font-size: 0.85rem;
    color: #9ca3af;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    font-size: 0.9rem;
    color: #d1d5db;
  }
  label input,
  label select {
    background: #111827;
    border: 1px solid #374151;
    color: #e2e8f0;
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
    font-size: 0.9rem;
    outline: none;
    transition: border-color 0.15s;
  }
  label input:focus,
  label select:focus {
    border-color: #7c8fdb;
  }
  .hint {
    font-size: 0.78rem;
    color: #6b7280;
  }
  .req {
    color: #f87171;
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.75rem;
    padding-top: 0.5rem;
  }

  /* ── Buttons ────────────────────────────────────────────────────────────── */

  .btn-primary {
    background: #4f46e5;
    color: #fff;
    border: none;
    padding: 0.5rem 1.2rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 500;
    transition: background 0.15s;
  }
  .btn-primary:hover:not(:disabled) {
    background: #4338ca;
  }
  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .btn-ghost {
    background: none;
    border: 1px solid #374151;
    color: #9ca3af;
    padding: 0.5rem 1.2rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.9rem;
    transition: border-color 0.15s, color 0.15s;
  }
  .btn-ghost:hover {
    border-color: #7c8fdb;
    color: #e2e8f0;
  }

  .mono {
    font-family: "JetBrains Mono", "Fira Code", monospace;
    font-size: 0.85rem !important;
  }

  input[type="text"],
  input[type="url"],
  input[type="number"] {
    background: #111827;
    border: 1px solid #374151;
    color: #e2e8f0;
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
    font-size: 0.9rem;
    outline: none;
  }
  input:focus {
    border-color: #7c8fdb;
  }

  /* ── Commit-reveal extras ──────────────────────────────────────────────── */
  label textarea {
    background: #111827;
    border: 1px solid #374151;
    color: #e2e8f0;
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
    font-size: 0.85rem;
    font-family: "JetBrains Mono", "Fira Code", monospace;
    outline: none;
    resize: vertical;
  }
  label textarea:focus { border-color: #7c8fdb; }

  .locked-summary {
    background: #111827;
    border: 1px solid #2d3148;
    border-radius: 8px;
    padding: 1rem;
    margin-top: 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .locked-label { font-size: 0.85rem; color: #9ca3af; margin-bottom: 0.25rem; }
  .metric-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.75rem;
    font-size: 0.82rem;
    padding: 0.4rem 0;
    border-top: 1px solid #1f2937;
  }
  .metric-name { font-weight: 600; color: #e2e8f0; min-width: 120px; }
  .metric-val { color: #9ca3af; }
  .match { color: #86efac; }
  .mismatch { color: #fca5a5; }
</style>

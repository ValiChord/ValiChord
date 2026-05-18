<script lang="ts">
  import { onMount } from "svelte";
  import { callZome, shortHash, hashesEqual } from "./holochain.js";
  import { myPubKey, myValidatorProfile, notify, myClaims, pendingReveals } from "./store.js";
  import type {
    ValidatorProfile,
    ValidationRequest,
    ValidationAttestation,
    ValidatorPrivateAttestation,
    ValidationTask,
    SealAttestationInput,
    AttestationRevealInput,
    Discipline,
    AttestationOutcome,
    AttestationConfidence,
    CertificationTier,
    ValidatorAgentType,
    OutcomeSummary,
    AgreementLevel,
    TimeBreakdown,
    ComputationalResources,
    HolochainRecord,
  } from "./types.js";
  import { disciplineLabel, entryFromRecord, hashFromRecord } from "./types.js";
  import type { ActionHash } from "@holochain/client";

  // ── Screens ──────────────────────────────────────────────────────────────────

  type Screen =
    | "dashboard"
    | "setup-profile"
    | "browse-requests"
    | "attest"        // commit (seal private attestation)
    | "reveal";       // reveal (publish public attestation)

  let screen: Screen = "dashboard";
  let loading = false;

  // ── Profile state ─────────────────────────────────────────────────────────────

  let profileEntry: ValidatorProfile | null = null;
  $: profileEntry = $myValidatorProfile ? entryFromRecord($myValidatorProfile) : null;

  let profileForm = {
    institution: "",
    disciplines: [] as string[],
    discipline_other: "",
    available: true,
    max_concurrent_tasks: 2,
    orcid: "",
    agent_type: "Individual" as ValidatorAgentType,
  };

  // ── Pending requests ──────────────────────────────────────────────────────────

  let pendingRequests: HolochainRecord<ValidationRequest>[] = [];
  let selectedRequestRecord: HolochainRecord<ValidationRequest> | null = null;

  // ── Task tracking (for commit-reveal) ────────────────────────────────────────
  // task_hash is stored here after receive_task so seal_private_attestation can use it.

  let currentTaskHash: ActionHash | null = null;

  // ── Reveal state ──────────────────────────────────────────────────────────────
  // When a RevealOpen signal arrives, request_ref lands in $pendingReveals.
  // The reveal screen shows when the user has a task matching a pending reveal.

  let revealRequestRecord: HolochainRecord<ValidationRequest> | null = null;
  let revealTaskHash: ActionHash | null = null;
  let revealPrivateAttestation: ValidatorPrivateAttestation | null = null;

  // Watch pendingReveals — auto-surface reveal prompt when matching task exists.
  $: if ($pendingReveals.length > 0 && screen === "dashboard") {
    checkPendingReveals();
  }

  let checkingReveals = false;

  async function checkPendingReveals() {
    if (checkingReveals) return;
    checkingReveals = true;
    try {
      const tasks = await callZome<HolochainRecord<ValidationTask>[]>(
        "validator_workspace",
        "get_all_tasks",
        null,
      );
      for (const taskRecord of tasks) {
        const task = entryFromRecord(taskRecord);
        if (!task) continue;
        const match = $pendingReveals.find((ref) => hashesEqual(ref, task.request_ref));
        if (!match) continue;
        // Check we haven't already revealed (get_private_attestation_for_task returns null after reveal)
        const taskHash = hashFromRecord(taskRecord);
        const privateRec = await callZome<HolochainRecord<ValidatorPrivateAttestation> | null>(
          "validator_workspace",
          "get_private_attestation_for_task",
          taskHash,
        );
        if (!privateRec) continue; // already revealed
        const pa = entryFromRecord(privateRec);
        if (!pa) continue;
        // Look up the request
        const reqRecord = await callZome<HolochainRecord<ValidationRequest> | null>(
          "attestation",
          "get_validation_request_for_data_hash",
          task.request_ref,
        );
        revealTaskHash = taskHash;
        revealPrivateAttestation = pa;
        revealRequestRecord = reqRecord;
        screen = "reveal";
        return;
      }
    } catch (err) {
      console.warn("checkPendingReveals:", err);
    } finally {
      checkingReveals = false;
    }
  }

  // ── Load ──────────────────────────────────────────────────────────────────────

  onMount(async () => {
    if ($myValidatorProfile) {
      await loadMyClaims();
    }
  });

  async function loadMyClaims() {
    try {
      const claims = await callZome<HolochainRecord<unknown>[]>(
        "attestation",
        "get_my_claimed_studies",
        null,
      );
      myClaims.set(claims);
    } catch (err) {
      console.warn("get_my_claimed_studies:", err);
    }
  }

  async function loadPendingRequests() {
    if (!profileEntry) return;
    loading = true;
    try {
      const disc = profileEntry.disciplines[0];
      if (!disc) { pendingRequests = []; return; }
      const records = await callZome<HolochainRecord<ValidationRequest>[]>(
        "attestation",
        "get_pending_requests_for_discipline",
        disc,
      );
      pendingRequests = records;
    } catch (err) {
      notify("error", `Failed to load requests: ${err}`);
    } finally {
      loading = false;
    }
  }

  // ── Profile submit ────────────────────────────────────────────────────────────

  async function submitProfile() {
    if (profileForm.disciplines.length === 0) {
      notify("error", "Select at least one discipline");
      return;
    }
    loading = true;
    try {
      const disciplines: Discipline[] = profileForm.disciplines.map((d) =>
        d === "Other"
          ? { type: "Other", content: profileForm.discipline_other }
          : ({ type: d } as Discipline),
      );
      const profile: ValidatorProfile = {
        institution: profileForm.institution,
        disciplines,
        certification_tier: "Provisional" as CertificationTier,
        available: profileForm.available,
        max_concurrent_tasks: profileForm.max_concurrent_tasks,
        orcid: profileForm.orcid || null,
        agent_type: profileForm.agent_type || null,
        person_key: null,
      };
      const fn_name = $myValidatorProfile ? "update_validator_profile" : "publish_validator_profile";
      await callZome("attestation", fn_name, profile);
      notify("success", "Validator profile saved");
      const record = await callZome<HolochainRecord<ValidatorProfile> | null>(
        "attestation",
        "get_validator_profile",
        $myPubKey,
      );
      myValidatorProfile.set(record ?? undefined);
      screen = "dashboard";
    } catch (err) {
      notify("error", `Failed: ${err}`);
    } finally {
      loading = false;
    }
  }

  // ── Claim ─────────────────────────────────────────────────────────────────────

  async function claimStudy(record: HolochainRecord<ValidationRequest>) {
    const entry = entryFromRecord(record);
    if (!entry) return;
    loading = true;
    try {
      const claimHash = await callZome<ActionHash | null>(
        "attestation",
        "claim_study",
        entry.data_hash,
      );
      if (!claimHash) {
        notify("info", "Study may be full or already claimed by you");
        return;
      }

      // Register the task in the validator workspace so seal_private_attestation
      // has a task_hash to link the private attestation to.
      const task: ValidationTask = {
        request_ref: entry.data_hash,
        discipline: entry.discipline,
        deadline_secs: Math.floor(Date.now() / 1000) + 7 * 24 * 3600,
        validation_focus: "ComputationalReproducibility",
        time_cap_secs: 14400,
        compensation_tier: { Tier1: { amount_pence: 5000 } },
      };
      const taskHash = await callZome<ActionHash>(
        "validator_workspace",
        "receive_task",
        task,
      );
      currentTaskHash = taskHash;
      selectedRequestRecord = record;
      notify("success", "Study claimed — fill in your private attestation");
      screen = "attest";
    } catch (err) {
      notify("error", `Claim failed: ${err}`);
    } finally {
      loading = false;
    }
  }

  // ── Attest form state ─────────────────────────────────────────────────────────

  let attestForm = {
    outcome_type: "Reproduced" as string,
    outcome_details: "",
    outcome_reason: "",
    effect_direction_matches: null as boolean | null,
    confidence_interval_overlap: "" as string,
    overall_agreement: "ExactMatch" as AgreementLevel,
    time_invested_secs: 3600,
    env_setup_secs: 0,
    data_acq_secs: 0,
    code_exec_secs: 0,
    troubleshoot_secs: 0,
    personal_hw: true,
    hpc: false,
    gpu: false,
    cloud: false,
    compute_cost: "" as string,
    confidence: "Medium" as AttestationConfidence,
  };

  // ── Seal (commit phase) ───────────────────────────────────────────────────────

  async function sealAttestation() {
    const reqEntry = selectedRequestRecord ? entryFromRecord(selectedRequestRecord) : null;
    if (!reqEntry || !currentTaskHash) return;
    loading = true;
    try {
      let outcome: AttestationOutcome;
      if (attestForm.outcome_type === "Reproduced") {
        outcome = { type: "Reproduced" };
      } else if (attestForm.outcome_type === "PartiallyReproduced") {
        outcome = { type: "PartiallyReproduced", content: { details: attestForm.outcome_details } };
      } else if (attestForm.outcome_type === "FailedToReproduce") {
        outcome = { type: "FailedToReproduce", content: { details: attestForm.outcome_details } };
      } else {
        outcome = { type: "UnableToAssess", content: { reason: attestForm.outcome_reason } };
      }

      const outcomeSummary: OutcomeSummary = {
        key_metrics: [],
        effect_direction_matches: attestForm.effect_direction_matches,
        confidence_interval_overlap:
          attestForm.confidence_interval_overlap !== ""
            ? parseFloat(attestForm.confidence_interval_overlap)
            : null,
        overall_agreement: attestForm.overall_agreement,
      };

      const timeBreakdown: TimeBreakdown = {
        environment_setup_secs: attestForm.env_setup_secs,
        data_acquisition_secs: attestForm.data_acq_secs,
        code_execution_secs: attestForm.code_exec_secs,
        troubleshooting_secs: attestForm.troubleshoot_secs,
      };

      const resources: ComputationalResources = {
        personal_hardware_sufficient: attestForm.personal_hw,
        hpc_required: attestForm.hpc,
        gpu_required: attestForm.gpu,
        cloud_compute_required: attestForm.cloud,
        estimated_compute_cost_pence:
          attestForm.compute_cost !== ""
            ? Math.round(parseFloat(attestForm.compute_cost) * 100)
            : null,
      };

      const attestation: ValidationAttestation = {
        request_ref: reqEntry.data_hash,
        outcome,
        outcome_summary: outcomeSummary,
        time_invested_secs: attestForm.time_invested_secs,
        time_breakdown: timeBreakdown,
        confidence: attestForm.confidence,
        deviation_flags: [],
        computational_resources: resources,
        discipline: reqEntry.discipline,
        commitment_anchor_hash: null,
      };

      // Commit phase: seal in validator_workspace DNA.
      // post_commit automatically calls notify_commitment_sealed on attestation DNA —
      // do NOT call it here.
      const input: SealAttestationInput = {
        task_hash: currentTaskHash,
        attestation,
      };
      await callZome("validator_workspace", "seal_private_attestation", input);

      notify(
        "success",
        "Attestation sealed privately. Waiting for all validators to commit — you'll be notified when it's time to reveal.",
      );
      screen = "dashboard";
      await loadMyClaims();
    } catch (err) {
      notify("error", `Seal failed: ${err}`);
    } finally {
      loading = false;
    }
  }

  // ── Reveal (public phase) ─────────────────────────────────────────────────────

  async function revealAttestation() {
    if (!revealTaskHash || !revealPrivateAttestation) return;
    loading = true;
    try {
      const pa = revealPrivateAttestation;

      // Reconstruct the full ValidationAttestation from the private record.
      const attestation: ValidationAttestation = {
        request_ref: pa.request_ref,
        outcome: pa.outcome,
        outcome_summary: pa.outcome_summary,
        time_invested_secs: pa.time_invested_secs,
        time_breakdown: pa.time_breakdown,
        confidence: pa.confidence,
        deviation_flags: pa.deviation_flags,
        computational_resources: pa.computational_resources,
        discipline: pa.discipline,
        commitment_anchor_hash: null,
      };

      const input: AttestationRevealInput = {
        attestation,
        nonce: pa.nonce,
      };
      await callZome("attestation", "submit_attestation", input);
      notify("success", "Attestation published to the shared DHT — round may now finalise");

      // Clear reveal state and remove from pending
      pendingReveals.update((rs) =>
        rs.filter((r) => !hashesEqual(r, pa.request_ref)),
      );
      revealTaskHash = null;
      revealPrivateAttestation = null;
      revealRequestRecord = null;
      screen = "dashboard";
    } catch (err) {
      notify("error", `Reveal failed: ${err}`);
    } finally {
      loading = false;
    }
  }

  // ── Edit profile helper ───────────────────────────────────────────────────────

  function startEditProfile() {
    if (profileEntry) {
      profileForm.institution = profileEntry.institution;
      profileForm.disciplines = profileEntry.disciplines.map((d) =>
        d.type === "Other" ? "Other" : d.type,
      );
      profileForm.available = profileEntry.available;
      profileForm.max_concurrent_tasks = profileEntry.max_concurrent_tasks;
      profileForm.orcid = profileEntry.orcid ?? "";
      profileForm.agent_type = profileEntry.agent_type ?? "Individual";
    }
    screen = "setup-profile";
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

  const DISCIPLINE_LABELS: Record<string, string> = {
    ComputationalBiology: "Computational Biology",
    ClimateScience: "Climate Science",
    SocialScience: "Social Science",
    Economics: "Economics",
    Psychology: "Psychology",
    Neuroscience: "Neuroscience",
    MachineLearning: "Machine Learning",
    Other: "Other",
  };

  function toggleDiscipline(d: string) {
    profileForm.disciplines = profileForm.disciplines.includes(d)
      ? profileForm.disciplines.filter((x) => x !== d)
      : [...profileForm.disciplines, d];
  }
</script>

<div class="validator">
  <!-- ── Top bar ──────────────────────────────────────────────────────────── -->
  <div class="topbar">
    <h1>
      {#if screen === "dashboard"}Validator Dashboard
      {:else if screen === "setup-profile"}
        {profileEntry ? "Edit Profile" : "Set Up Validator Profile"}
      {:else if screen === "browse-requests"}Browse Validation Requests
      {:else if screen === "attest"}Seal Private Attestation
      {:else}Reveal Attestation{/if}
    </h1>
    {#if screen !== "dashboard"}
      <button class="btn-ghost" on:click={() => (screen = "dashboard")}>← Back</button>
    {/if}
  </div>

  <!-- ── Pending reveals banner ────────────────────────────────────────────── -->
  {#if $pendingReveals.length > 0 && screen === "dashboard"}
    <div class="reveal-banner">
      <span class="reveal-icon">🔓</span>
      <span>
        {$pendingReveals.length} study{$pendingReveals.length > 1 ? " studies have" : " has"} entered
        the reveal phase — all validators have committed.
      </span>
      <button class="btn-reveal" on:click={checkPendingReveals}>Reveal now</button>
    </div>
  {/if}

  <!-- ── No profile yet ───────────────────────────────────────────────────── -->
  {#if !profileEntry && screen !== "setup-profile"}
    <div class="card onboard">
      <h2>Set up your validator profile</h2>
      <p>
        Before you can claim studies or submit attestations, you need a validator profile on the
        Attestation DHT.
      </p>
      <button class="btn-primary" on:click={() => (screen = "setup-profile")}>
        Create profile
      </button>
    </div>

  <!-- ── Dashboard ────────────────────────────────────────────────────────── -->
  {:else if screen === "dashboard" && profileEntry}
    <div class="profile-banner">
      <div class="profile-info">
        <span class="profile-inst">{profileEntry.institution || "No institution set"}</span>
        <span class="tier-badge">{profileEntry.certification_tier}</span>
        {#if profileEntry.agent_type}<span class="agent-type">{profileEntry.agent_type}</span>{/if}
      </div>
      <div class="profile-disciplines">
        {#each profileEntry.disciplines as d}
          <span class="disc-chip">{disciplineLabel(d)}</span>
        {/each}
      </div>
      <div class="profile-actions">
        <button class="btn-ghost" on:click={startEditProfile}>Edit profile</button>
      </div>
    </div>

    <div class="actions-row">
      <button
        class="btn-primary"
        on:click={async () => { screen = "browse-requests"; await loadPendingRequests(); }}
      >
        Browse pending requests
      </button>
    </div>

    <section class="card">
      <h2>My claimed studies</h2>
      {#if $myClaims.length === 0}
        <p class="empty">No active claims.</p>
      {:else}
        <ul class="claim-list">
          {#each $myClaims as claim}
            <li class="claim-item mono">{shortHash(hashFromRecord(claim as HolochainRecord<unknown>))}</li>
          {/each}
        </ul>
      {/if}
    </section>

  <!-- ── Profile setup form ───────────────────────────────────────────────── -->
  {:else if screen === "setup-profile"}
    <form class="profile-form card" on:submit|preventDefault={submitProfile}>
      <label>
        Institution
        <input type="text" bind:value={profileForm.institution} placeholder="e.g. University of Edinburgh" />
        <span class="hint">Used for conflict-of-interest checks</span>
      </label>

      <div class="discipline-group">
        <span class="label">Disciplines <span class="req">*</span></span>
        <div class="discipline-chips">
          {#each DISCIPLINES as d}
            <button
              type="button"
              class="disc-toggle"
              class:selected={profileForm.disciplines.includes(d)}
              on:click={() => toggleDiscipline(d)}
            >
              {DISCIPLINE_LABELS[d]}
            </button>
          {/each}
        </div>
        {#if profileForm.disciplines.includes("Other")}
          <input type="text" bind:value={profileForm.discipline_other} placeholder="Discipline name" />
        {/if}
      </div>

      <label>
        Agent type
        <select bind:value={profileForm.agent_type}>
          <option value="Individual">Individual (human)</option>
          <option value="Institution">Institution / group</option>
          <option value="AutomatedTool">Automated tool / AI pipeline</option>
        </select>
      </label>

      <label>
        Max concurrent tasks
        <input type="number" bind:value={profileForm.max_concurrent_tasks} min="1" max="20" />
      </label>

      <label>
        ORCID iD
        <input type="text" bind:value={profileForm.orcid} placeholder="0000-0000-0000-0000 (optional)" />
      </label>

      <label class="checkbox-label">
        <input type="checkbox" bind:checked={profileForm.available} />
        Available for new studies
      </label>

      <div class="form-actions">
        <button type="button" class="btn-ghost" on:click={() => (screen = "dashboard")}>Cancel</button>
        <button type="submit" class="btn-primary" disabled={loading}>
          {loading ? "Saving…" : "Save profile"}
        </button>
      </div>
    </form>

  <!-- ── Browse requests ──────────────────────────────────────────────────── -->
  {:else if screen === "browse-requests"}
    {#if loading}
      <div class="loading-row"><div class="spinner"></div> Loading…</div>
    {:else if pendingRequests.length === 0}
      <div class="card empty-hint"><p>No pending requests found for your disciplines.</p></div>
    {:else}
      <div class="request-list">
        {#each pendingRequests as record}
          {@const entry = entryFromRecord(record)}
          {@const hash = hashFromRecord(record)}
          {#if entry}
            <div class="request-card">
              <div class="rcard-header">
                <span class="discipline-tag">{disciplineLabel(entry.discipline)}</span>
                <span class="tier-tag tier-{entry.validation_tier.toLowerCase()}">{entry.validation_tier}</span>
              </div>
              <div class="rcard-url">
                <a href={entry.data_access_url} target="_blank" rel="noreferrer">{entry.data_access_url}</a>
              </div>
              <div class="rcard-meta">
                <span>{entry.num_validators_required} validators required</span>
                <span class="mono">{shortHash(hash)}</span>
              </div>
              {#if entry.protocol_access_url}
                <div class="rcard-meta">
                  Protocol: <a href={entry.protocol_access_url} target="_blank" rel="noreferrer">{entry.protocol_access_url}</a>
                </div>
              {/if}
              <div class="rcard-actions">
                <button class="btn-primary" on:click={() => claimStudy(record)} disabled={loading}>
                  Claim this study
                </button>
              </div>
            </div>
          {/if}
        {/each}
      </div>
    {/if}

  <!-- ── Seal attestation form (commit phase) ─────────────────────────────── -->
  {:else if screen === "attest" && selectedRequestRecord}
    {@const reqEntry = entryFromRecord(selectedRequestRecord)}
    {#if reqEntry}
      <div class="phase-strip">
        <div class="phase-step active">
          <span class="phase-dot">1</span>
          <span class="phase-name">Commit</span>
        </div>
        <div class="phase-connector"></div>
        <div class="phase-step">
          <span class="phase-dot">2</span>
          <span class="phase-name">Reveal</span>
        </div>
        <div class="phase-connector"></div>
        <div class="phase-step">
          <span class="phase-dot">3</span>
          <span class="phase-name">Harmony</span>
        </div>
      </div>
      <div class="phase-label">
        <span class="phase-badge commit">Phase 1 — Commit</span>
        Your attestation will be sealed privately. You cannot change it after this step.
      </div>
      <form class="attest-form card" on:submit|preventDefault={sealAttestation}>
        <div class="attest-context">
          <span class="dim">Study:</span>
          <a href={reqEntry.data_access_url} target="_blank" rel="noreferrer">{reqEntry.data_access_url}</a>
          <span class="discipline-tag">{disciplineLabel(reqEntry.discipline)}</span>
        </div>

        <fieldset>
          <legend>Outcome</legend>
          <label>
            Result
            <select bind:value={attestForm.outcome_type}>
              <option value="Reproduced">Reproduced — key results match</option>
              <option value="PartiallyReproduced">Partially reproduced</option>
              <option value="FailedToReproduce">Failed to reproduce</option>
              <option value="UnableToAssess">Unable to assess</option>
            </select>
          </label>
          {#if attestForm.outcome_type === "PartiallyReproduced" || attestForm.outcome_type === "FailedToReproduce"}
            <label>
              Details <span class="req">*</span>
              <textarea bind:value={attestForm.outcome_details} rows="3" placeholder="Describe the discrepancy…" required></textarea>
            </label>
          {/if}
          {#if attestForm.outcome_type === "UnableToAssess"}
            <label>
              Reason <span class="req">*</span>
              <textarea bind:value={attestForm.outcome_reason} rows="3" placeholder="Why were you unable to assess?" required></textarea>
            </label>
          {/if}
          <label>
            Overall agreement
            <select bind:value={attestForm.overall_agreement}>
              <option value="ExactMatch">Exact match</option>
              <option value="WithinTolerance">Within tolerance</option>
              <option value="DirectionalMatch">Directional match only</option>
              <option value="Divergent">Divergent</option>
              <option value="UnableToAssess">Unable to assess</option>
            </select>
          </label>
          <label>
            Confidence
            <select bind:value={attestForm.confidence}>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
          </label>
        </fieldset>

        <fieldset>
          <legend>Time invested</legend>
          <label>
            Total time (seconds)
            <input type="number" bind:value={attestForm.time_invested_secs} min="0" />
            <span class="hint">{Math.floor(attestForm.time_invested_secs / 3600)}h {Math.floor((attestForm.time_invested_secs % 3600) / 60)}m</span>
          </label>
          <div class="time-breakdown">
            <label>Environment setup (s)<input type="number" bind:value={attestForm.env_setup_secs} min="0" /></label>
            <label>Data acquisition (s)<input type="number" bind:value={attestForm.data_acq_secs} min="0" /></label>
            <label>Code execution (s)<input type="number" bind:value={attestForm.code_exec_secs} min="0" /></label>
            <label>Troubleshooting (s)<input type="number" bind:value={attestForm.troubleshoot_secs} min="0" /></label>
          </div>
        </fieldset>

        <fieldset>
          <legend>Computational resources</legend>
          <div class="checkbox-row">
            <label class="checkbox-label"><input type="checkbox" bind:checked={attestForm.personal_hw} /> Personal hardware sufficient</label>
            <label class="checkbox-label"><input type="checkbox" bind:checked={attestForm.hpc} /> HPC required</label>
            <label class="checkbox-label"><input type="checkbox" bind:checked={attestForm.gpu} /> GPU required</label>
            <label class="checkbox-label"><input type="checkbox" bind:checked={attestForm.cloud} /> Cloud compute</label>
          </div>
          <label>
            Estimated cost (£)
            <input type="number" bind:value={attestForm.compute_cost} min="0" step="0.01" placeholder="optional" />
          </label>
        </fieldset>

        <div class="form-actions">
          <button type="button" class="btn-ghost" on:click={() => (screen = "dashboard")}>Cancel</button>
          <button type="submit" class="btn-primary" disabled={loading}>
            {loading ? "Sealing…" : "Seal private attestation"}
          </button>
        </div>
      </form>
    {/if}

  <!-- ── Reveal form (public phase) ───────────────────────────────────────── -->
  {:else if screen === "reveal" && revealPrivateAttestation}
    {@const pa = revealPrivateAttestation}
    <div class="phase-strip">
      <div class="phase-step done">
        <span class="phase-dot">✓</span>
        <span class="phase-name">Commit</span>
      </div>
      <div class="phase-connector done"></div>
      <div class="phase-step active">
        <span class="phase-dot">2</span>
        <span class="phase-name">Reveal</span>
      </div>
      <div class="phase-connector"></div>
      <div class="phase-step">
        <span class="phase-dot">3</span>
        <span class="phase-name">Harmony</span>
      </div>
    </div>
    <div class="phase-label">
      <span class="phase-badge reveal">Phase 2 — Reveal</span>
      All validators have committed. Publish your attestation to the shared DHT.
    </div>
    <div class="card reveal-card">
      {#if revealRequestRecord}
        {@const reqEntry = entryFromRecord(revealRequestRecord)}
        {#if reqEntry}
          <div class="attest-context">
            <span class="dim">Study:</span>
            <a href={reqEntry.data_access_url} target="_blank" rel="noreferrer">{reqEntry.data_access_url}</a>
          </div>
        {/if}
      {/if}

      <div class="sealed-summary">
        <div class="summary-row">
          <span class="summary-label">Your sealed outcome:</span>
          <span class="outcome-label outcome-{pa.outcome.type.toLowerCase()}">
            {pa.outcome.type === "Reproduced" ? "Reproduced"
              : pa.outcome.type === "PartiallyReproduced" ? "Partially reproduced"
              : pa.outcome.type === "FailedToReproduce" ? "Failed to reproduce"
              : "Unable to assess"}
          </span>
        </div>
        <div class="summary-row">
          <span class="summary-label">Agreement:</span>
          <span>{pa.outcome_summary.overall_agreement}</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">Time invested:</span>
          <span>{Math.floor(pa.time_invested_secs / 3600)}h {Math.floor((pa.time_invested_secs % 3600) / 60)}m</span>
        </div>
      </div>

      <p class="reveal-note">
        Once published, your attestation is permanently on the shared DHT and cannot be changed.
        This is the exact content you sealed — no modifications.
      </p>

      <div class="form-actions">
        <button class="btn-ghost" on:click={() => (screen = "dashboard")}>Back</button>
        <button class="btn-reveal-submit" on:click={revealAttestation} disabled={loading}>
          {loading ? "Publishing…" : "Publish attestation"}
        </button>
      </div>
    </div>
  {/if}
</div>

<style>
  .validator { max-width: 760px; }

  .topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1.5rem;
  }
  h1 { margin: 0; font-size: 1.5rem; }

  /* ── Reveal banner ─────────────────────────────────────────────────────── */
  .reveal-banner {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    background: var(--bg-reveal-banner);
    border: 1px solid var(--border-success);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 1.25rem;
    font-size: 0.9rem;
    color: var(--color-success);
    flex-wrap: wrap;
  }
  .reveal-icon { font-size: 1.1rem; }
  .btn-reveal {
    background: var(--reveal-bg);
    color: var(--color-success);
    border: 1px solid var(--reveal-border);
    padding: 0.35rem 0.9rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 600;
    font-family: var(--font-body);
    margin-left: auto;
    transition: background 0.15s;
  }
  .btn-reveal:hover { background: var(--reveal-bg-hover); }

  /* ── Phase progress strip ──────────────────────────────────────────────── */
  .phase-strip {
    display: flex;
    align-items: center;
    margin-bottom: 1.25rem;
  }
  .phase-step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.3rem;
  }
  .phase-dot {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    border: 2px solid var(--border);
    background: var(--bg-inset);
    color: var(--text-dim);
    font-size: 0.75rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
  }
  .phase-name {
    font-size: 0.7rem;
    color: var(--text-dim);
    letter-spacing: 0.04em;
  }
  .phase-step.active .phase-dot {
    border-color: var(--accent);
    background: var(--accent-solid);
    color: #fff;
  }
  .phase-step.active .phase-name { color: var(--accent-bright); }
  .phase-step.done .phase-dot {
    border-color: var(--border-success);
    background: var(--bg-success-notif);
    color: var(--color-success);
  }
  .phase-step.done .phase-name { color: var(--color-success); }
  .phase-connector {
    flex: 1;
    height: 2px;
    background: var(--border);
    margin: 0 0.5rem;
    margin-bottom: 1rem;
  }
  .phase-connector.done { background: var(--border-success); }

  /* ── Phase labels ──────────────────────────────────────────────────────── */
  .phase-label {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-size: 0.875rem;
    color: var(--text-muted);
    margin-bottom: 1.25rem;
  }
  .phase-badge {
    padding: 0.25em 0.75em;
    border-radius: 4px;
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.04em;
  }
  .phase-badge.commit { background: var(--tier-enhanced-bg); color: var(--indigo-text); }
  .phase-badge.reveal { background: var(--bg-success-notif); color: var(--color-success); }

  /* ── Reveal card ───────────────────────────────────────────────────────── */
  .reveal-card { display: flex; flex-direction: column; gap: 1rem; }
  .sealed-summary {
    background: var(--bg-inset);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .summary-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-size: 0.875rem;
  }
  .summary-label { color: var(--text-dim); min-width: 140px; }
  .reveal-note {
    font-size: 0.8rem;
    color: var(--text-dim);
    margin: 0;
    line-height: 1.5;
  }
  .btn-reveal-submit {
    background: var(--reveal-bg-hover);
    color: #fff;
    border: none;
    padding: 0.5rem 1.2rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 600;
    font-family: var(--font-body);
    transition: background 0.15s;
  }
  .btn-reveal-submit:hover:not(:disabled) { background: var(--reveal-bg); }
  .btn-reveal-submit:disabled { opacity: 0.5; cursor: not-allowed; }

  /* ── Card ──────────────────────────────────────────────────────────────── */
  .card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
  }
  .card h2 { margin: 0 0 0.75rem; font-size: 1rem; }
  .empty { color: var(--text-dim); font-size: 0.875rem; }
  .empty-hint p { margin: 0; color: var(--text-dim); font-size: 0.9rem; }

  .onboard h2 { margin: 0 0 0.5rem; }
  .onboard p { color: var(--text-muted); font-size: 0.9rem; margin: 0 0 1.25rem; }

  /* ── Profile ───────────────────────────────────────────────────────────── */
  .profile-banner {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.5rem;
  }
  .profile-info { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem; }
  .profile-inst { font-weight: 600; }
  .tier-badge {
    font-size: 0.75rem;
    padding: 0.15em 0.6em;
    border-radius: 4px;
    background: var(--bg-info);
    color: var(--color-info);
  }
  .agent-type { font-size: 0.75rem; color: var(--text-dim); }
  .profile-disciplines { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 0.75rem; }
  .disc-chip {
    background: var(--bg-alt);
    color: var(--text-label);
    font-size: 0.78rem;
    padding: 0.2em 0.6em;
    border-radius: 4px;
  }
  .profile-actions { display: flex; justify-content: flex-end; }

  .actions-row { margin-bottom: 1.5rem; }

  /* ── Claims ────────────────────────────────────────────────────────────── */
  .claim-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.5rem; }
  .claim-item {
    background: var(--bg-inset);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.65rem 0.9rem;
    font-size: 0.875rem;
    color: var(--text-muted);
  }

  /* ── Request list ──────────────────────────────────────────────────────── */
  .request-list { display: flex; flex-direction: column; gap: 1rem; }
  .request-card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1rem 1.25rem;
  }
  .rcard-header { display: flex; gap: 0.5rem; margin-bottom: 0.5rem; }
  .discipline-tag {
    background: var(--bg-info);
    color: var(--color-info);
    font-size: 0.78rem;
    padding: 0.2em 0.6em;
    border-radius: 4px;
  }
  .tier-tag { font-size: 0.78rem; padding: 0.2em 0.6em; border-radius: 4px; }
  .tier-basic { background: var(--tier-basic-bg); color: var(--lime-text); }
  .tier-enhanced { background: var(--tier-enhanced-bg); color: var(--indigo-text); }
  .tier-comprehensive { background: var(--tier-comprehensive-bg); color: var(--purple-text); }
  .rcard-url { font-size: 0.875rem; margin-bottom: 0.5rem; }
  .rcard-url a { color: var(--accent); text-decoration: none; word-break: break-all; }
  .rcard-meta {
    display: flex;
    justify-content: space-between;
    font-size: 0.8rem;
    color: var(--text-dim);
    margin-bottom: 0.5rem;
  }
  .rcard-meta a { color: var(--accent); text-decoration: none; }
  .rcard-actions { display: flex; justify-content: flex-end; }

  /* ── Profile form ──────────────────────────────────────────────────────── */
  .profile-form { display: flex; flex-direction: column; gap: 1rem; }

  /* ── Attestation form ──────────────────────────────────────────────────── */
  .attest-form { display: flex; flex-direction: column; gap: 1.5rem; }
  .attest-context {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-size: 0.875rem;
    flex-wrap: wrap;
  }
  .dim { color: var(--text-dim); }
  .attest-context a { color: var(--accent); text-decoration: none; word-break: break-all; }
  .time-breakdown {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
  }
  .checkbox-row { display: flex; flex-wrap: wrap; gap: 1rem; margin-bottom: 0.75rem; }

  /* ── Outcome labels ────────────────────────────────────────────────────── */
  .outcome-label { font-weight: 600; }
  .outcome-reproduced { color: var(--color-success); }
  .outcome-partiallyreproduced { color: var(--color-warning); }
  .outcome-failedtoreproduce { color: var(--color-error); }
  .outcome-unabletoassess { color: var(--text-muted); }

  /* ── Shared controls ───────────────────────────────────────────────────── */
  .discipline-group { display: flex; flex-direction: column; gap: 0.5rem; }
  .discipline-chips { display: flex; flex-wrap: wrap; gap: 0.4rem; }
  .disc-toggle {
    background: var(--bg-alt);
    border: 1px solid var(--border-input);
    color: var(--text-muted);
    padding: 0.3em 0.8em;
    border-radius: 20px;
    cursor: pointer;
    font-size: 0.82rem;
    font-family: var(--font-body);
    transition: all 0.15s;
  }
  .disc-toggle.selected { background: var(--bg-info); border-color: var(--border-selected); color: var(--color-info); }

  fieldset {
    border: 1px solid var(--border);
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
    color: var(--text-muted);
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    font-size: 0.9rem;
    color: var(--text-label);
  }
  .label { font-size: 0.9rem; color: var(--text-label); }
  .checkbox-label { flex-direction: row; align-items: center; gap: 0.4rem; }
  label input,
  label select,
  label textarea {
    background: var(--bg-inset);
    border: 1px solid var(--border-input);
    color: var(--text);
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
    font-size: 0.9rem;
    outline: none;
    font-family: var(--font-body);
    transition: border-color 0.15s;
  }
  label input:focus,
  label select:focus,
  label textarea:focus { border-color: var(--accent); }

  .hint { font-size: 0.78rem; color: var(--text-dim); }
  .req { color: var(--req); }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.75rem;
    padding-top: 0.5rem;
  }

  .mono { font-family: var(--font-mono); }

  .loading-row { display: flex; align-items: center; gap: 0.75rem; color: var(--text-dim); padding: 2rem 0; }
  .spinner {
    width: 24px;
    height: 24px;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .btn-primary {
    background: var(--accent-solid);
    color: #fff;
    border: none;
    padding: 0.5rem 1.2rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 500;
    font-family: var(--font-body);
    transition: background 0.15s;
  }
  .btn-primary:hover:not(:disabled) { background: var(--accent-solid-hover); }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-ghost {
    background: none;
    border: 1px solid var(--border-input);
    color: var(--text-muted);
    padding: 0.5rem 1.2rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.9rem;
    font-family: var(--font-body);
    transition: border-color 0.15s, color 0.15s;
  }
  .btn-ghost:hover { border-color: var(--accent); color: var(--text); }
</style>

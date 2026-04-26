<script lang="ts">
  import { onMount } from "svelte";
  import { callZome, shortHash, externalHashFromHex } from "./holochain.js";
  import { harmonyRecords, notify } from "./store.js";
  import type {
    HarmonyRecord,
    Discipline,
    AgreementLevel,
    AttestationOutcome,
    HolochainRecord,
    BadgeType,
  } from "./types.js";
  import { disciplineLabel, entryFromRecord, hashFromRecord } from "./types.js";
  import type { ActionHash } from "@holochain/client";

  let loading = false;
  let filterDiscipline: string = "all";

  const DISCIPLINES = [
    { value: "all", label: "All disciplines" },
    { value: "ComputationalBiology", label: "Computational Biology" },
    { value: "ClimateScience", label: "Climate Science" },
    { value: "SocialScience", label: "Social Science" },
    { value: "Economics", label: "Economics" },
    { value: "Psychology", label: "Psychology" },
    { value: "Neuroscience", label: "Neuroscience" },
    { value: "MachineLearning", label: "Machine Learning" },
  ];

  onMount(loadRecords);

  async function loadRecords() {
    loading = true;
    try {
      if (filterDiscipline === "all") {
        // No "get all" endpoint — iterate disciplines and merge
        const results: HolochainRecord<HarmonyRecord>[] = [];
        for (const d of DISCIPLINES.slice(1)) {
          const disc: Discipline = { type: d.value as Discipline["type"] };
          const recs = await callZome<HolochainRecord<HarmonyRecord>[]>(
            "governance",
            "get_harmony_records_by_discipline",
            disc,
          );
          results.push(...recs);
        }
        // deduplicate by hash
        const seen = new Set<string>();
        harmonyRecords.set(
          results.filter((r) => {
            const k = JSON.stringify(Array.from(hashFromRecord(r)));
            if (seen.has(k)) return false;
            seen.add(k);
            return true;
          }),
        );
      } else {
        const disc: Discipline = { type: filterDiscipline as Discipline["type"] };
        const recs = await callZome<HolochainRecord<HarmonyRecord>[]>(
          "governance",
          "get_harmony_records_by_discipline",
          disc,
        );
        harmonyRecords.set(recs);
      }
    } catch (err) {
      notify("error", `Failed to load records: ${err}`);
    } finally {
      loading = false;
    }
  }

  async function changeFilter(disc: string) {
    filterDiscipline = disc;
    await loadRecords();
  }

  // ── Badge evaluation (mirrors governance_coordinator::evaluate_badge) ────────
  // Gold ≥7 ExactMatch, Silver ≥5 ExactMatch|WithinTolerance, Bronze ≥3 any positive,
  // Failed ≥3 Divergent|UnableToAssess

  function inferBadge(record: HarmonyRecord): BadgeType | null {
    const n = record.participating_validators.length;
    const ag = record.agreement_level;
    if (n >= 7 && ag === "ExactMatch") return "Gold";
    if (n >= 5 && (ag === "ExactMatch" || ag === "WithinTolerance")) return "Silver";
    if (n >= 3 && (ag === "ExactMatch" || ag === "WithinTolerance" || ag === "DirectionalMatch"))
      return "Bronze";
    if (n >= 3 && (ag === "Divergent" || ag === "UnableToAssess")) return "Failed";
    return null;
  }

  function outcomeLabel(o: AttestationOutcome): string {
    if (o.type === "Reproduced") return "Reproduced";
    if (o.type === "PartiallyReproduced") return "Partially reproduced";
    if (o.type === "FailedToReproduce") return "Failed to reproduce";
    return "Unable to assess";
  }

  function agreementLabel(a: AgreementLevel): string {
    const map: Record<AgreementLevel, string> = {
      ExactMatch: "Exact match",
      WithinTolerance: "Within tolerance",
      DirectionalMatch: "Directional match",
      Divergent: "Divergent",
      UnableToAssess: "Unable to assess",
    };
    return map[a] ?? a;
  }

  function formatDuration(secs: number): string {
    if (secs < 3600) return `${Math.round(secs / 60)}m`;
    const h = Math.floor(secs / 3600);
    const m = Math.round((secs % 3600) / 60);
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  }

  function badgeEmoji(badge: BadgeType | null): string {
    if (badge === "Gold") return "🥇";
    if (badge === "Silver") return "🥈";
    if (badge === "Bronze") return "🥉";
    if (badge === "Failed") return "✗";
    return "—";
  }

  function badgeClass(badge: BadgeType | null): string {
    if (badge === "Gold") return "badge-gold";
    if (badge === "Silver") return "badge-silver";
    if (badge === "Bronze") return "badge-bronze";
    if (badge === "Failed") return "badge-failed";
    return "badge-none";
  }

  // ── force_finalize_round ──────────────────────────────────────────────────────
  // System coordinator only — manually close a timed-out round with partial
  // attestations. Idempotent: returns null if HarmonyRecord already exists.

  let finalizeHex = "";
  let finalizeLoading = false;

  async function finalizeRound() {
    if (finalizeHex.length !== 64) {
      notify("error", "Enter a 64-character hex SHA-256 (the study's data_hash / request_ref)");
      return;
    }
    finalizeLoading = true;
    try {
      const requestRef = externalHashFromHex(finalizeHex);
      const hash = await callZome<ActionHash | null>("governance", "force_finalize_round", requestRef);
      if (hash) {
        notify("success", `HarmonyRecord written — ${shortHash(hash)}`);
        finalizeHex = "";
        await loadRecords();
      } else {
        notify("info", "Round already finalised — HarmonyRecord already exists for this study");
      }
    } catch (err) {
      notify("error", `Finalize failed: ${err}`);
    } finally {
      finalizeLoading = false;
    }
  }
</script>

<div class="governance">
  <div class="topbar">
    <h1>Governance — HarmonyRecords</h1>
    <button class="btn-ghost" on:click={loadRecords} disabled={loading}>
      {loading ? "Loading…" : "↻ Refresh"}
    </button>
  </div>

  <p class="description">
    HarmonyRecords are the permanent, public outcomes of completed validation rounds. They show
    whether a study's results were independently reproduced — not whether the results are correct.
  </p>

  <!-- ── Discipline filter ──────────────────────────────────────────────── -->
  <div class="filter-row">
    {#each DISCIPLINES as d}
      <button
        class="filter-btn"
        class:active={filterDiscipline === d.value}
        on:click={() => changeFilter(d.value)}
      >
        {d.label}
      </button>
    {/each}
  </div>

  <!-- ── Force finalise (system coordinator) ──────────────────────────── -->
  <details class="finalize-panel">
    <summary>Force finalise a timed-out round</summary>
    <div class="finalize-body">
      <p>
        Use this when a validation round has passed its timeout and some validators did not reveal.
        Only the system coordinator key can successfully write a HarmonyRecord via this path.
      </p>
      <div class="finalize-row">
        <input
          type="text"
          bind:value={finalizeHex}
          placeholder="64-char hex SHA-256 (study data_hash / request_ref)"
          maxlength="64"
          class="mono"
        />
        <button class="btn-finalize" on:click={finalizeRound} disabled={finalizeLoading}>
          {finalizeLoading ? "Finalising…" : "Force finalise"}
        </button>
      </div>
    </div>
  </details>

  <!-- ── Records ────────────────────────────────────────────────────────── -->
  {#if loading}
    <div class="loading-row"><div class="spinner"></div> Loading HarmonyRecords…</div>
  {:else if $harmonyRecords.length === 0}
    <div class="empty-state">
      <p>No HarmonyRecords found for this discipline yet.</p>
      <p class="sub">
        Records appear here after a validation round is complete and finalised on the Governance
        DHT.
      </p>
    </div>
  {:else}
    <div class="records-grid">
      {#each $harmonyRecords as record}
        {@const entry = entryFromRecord(record)}
        {@const hash = hashFromRecord(record)}
        {#if entry}
          {@const badge = inferBadge(entry)}
          <div class="harmony-card" class:card-failed={badge === "Failed"}>
            <!-- Badge -->
            <div class="badge-row">
              <span class="badge {badgeClass(badge)}">{badgeEmoji(badge)}</span>
              <span class="discipline-tag">{disciplineLabel(entry.discipline)}</span>
              <span class="hash-label">{shortHash(hash)}</span>
            </div>

            <!-- Outcome -->
            <div class="outcome-row">
              <span class="outcome-label outcome-{entry.outcome.type.toLowerCase()}">
                {outcomeLabel(entry.outcome)}
              </span>
              <span class="agreement-label">
                {agreementLabel(entry.agreement_level)}
              </span>
            </div>

            <!-- Stats -->
            <div class="stats-row">
              <div class="stat">
                <span class="stat-value">{entry.participating_validators.length}</span>
                <span class="stat-label">validators</span>
              </div>
              <div class="stat">
                <span class="stat-value">{formatDuration(entry.validation_duration_secs)}</span>
                <span class="stat-label">max time</span>
              </div>
            </div>

            <!-- Validator types breakdown -->
            {#if entry.validator_types.some((t) => t !== null)}
              <div class="vtype-row">
                {#each entry.validator_types as vt}
                  <span class="vtype-chip vtype-{(vt ?? 'individual').toLowerCase()}">
                    {vt ?? "—"}
                  </span>
                {/each}
              </div>
            {/if}
          </div>
        {/if}
      {/each}
    </div>
  {/if}
</div>

<style>
  .governance {
    max-width: 1000px;
  }

  .topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
  }
  h1 {
    margin: 0;
    font-size: 1.5rem;
  }

  .description {
    color: #9ca3af;
    font-size: 0.9rem;
    margin: 0 0 1.5rem;
    max-width: 680px;
    line-height: 1.6;
  }

  .filter-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-bottom: 1.5rem;
  }
  .filter-btn {
    background: #1f2937;
    border: 1px solid #374151;
    color: #9ca3af;
    padding: 0.3em 0.8em;
    border-radius: 20px;
    cursor: pointer;
    font-size: 0.82rem;
    transition: all 0.15s;
  }
  .filter-btn:hover {
    border-color: #7c8fdb;
    color: #e2e8f0;
  }
  .filter-btn.active {
    background: #1e3a5f;
    border-color: #3b82f6;
    color: #93c5fd;
  }

  .loading-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    color: #6b7280;
    padding: 2rem 0;
  }
  .spinner {
    width: 24px;
    height: 24px;
    border: 2px solid #2d3148;
    border-top-color: #7c8fdb;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .empty-state {
    text-align: center;
    padding: 4rem 2rem;
    color: #6b7280;
  }
  .empty-state p { margin: 0 0 0.5rem; }
  .empty-state .sub { font-size: 0.85rem; }

  .records-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1rem;
  }

  .harmony-card {
    background: #1a1d27;
    border: 1px solid #2d3148;
    border-radius: 12px;
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  .card-failed {
    border-color: #7f1d1d;
  }

  /* Badge */
  .badge-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .badge {
    font-size: 1.25rem;
    line-height: 1;
  }
  .badge-gold  { filter: drop-shadow(0 0 4px gold); }
  .badge-silver { filter: drop-shadow(0 0 4px silver); }
  .badge-bronze { filter: drop-shadow(0 0 4px #cd7f32); }
  .badge-failed { color: #f87171; font-size: 1rem; font-weight: 700; }

  .discipline-tag {
    background: #1e3a5f;
    color: #93c5fd;
    font-size: 0.75rem;
    padding: 0.2em 0.6em;
    border-radius: 4px;
    flex: 1;
  }
  .hash-label {
    font-family: monospace;
    font-size: 0.75rem;
    color: #4b5563;
  }

  /* Outcome */
  .outcome-row {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .outcome-label {
    font-weight: 600;
    font-size: 0.95rem;
  }
  .outcome-reproduced { color: #86efac; }
  .outcome-partiallyreproduced { color: #fde68a; }
  .outcome-failedtoreproduce { color: #fca5a5; }
  .outcome-unabletoassess { color: #9ca3af; }
  .agreement-label {
    font-size: 0.8rem;
    color: #9ca3af;
  }

  /* Stats */
  .stats-row {
    display: flex;
    gap: 1.5rem;
  }
  .stat {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
  }
  .stat-value {
    font-size: 1.1rem;
    font-weight: 700;
    color: #e2e8f0;
  }
  .stat-label {
    font-size: 0.72rem;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  /* Validator types */
  .vtype-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
  }
  .vtype-chip {
    font-size: 0.7rem;
    padding: 0.15em 0.5em;
    border-radius: 3px;
  }
  .vtype-individual { background: #1f2937; color: #9ca3af; }
  .vtype-institution { background: #1c1f2e; color: #818cf8; }
  .vtype-automatedtool { background: #1c2014; color: #a3e635; }

  .btn-ghost {
    background: none;
    border: 1px solid #374151;
    color: #9ca3af;
    padding: 0.4rem 1rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.875rem;
    transition: border-color 0.15s, color 0.15s;
  }
  .btn-ghost:hover:not(:disabled) { border-color: #7c8fdb; color: #e2e8f0; }
  .btn-ghost:disabled { opacity: 0.5; cursor: not-allowed; }

  /* ── Force finalise panel ──────────────────────────────────────────────── */
  .finalize-panel {
    border: 1px solid #2d3148;
    border-radius: 8px;
    margin-bottom: 1.5rem;
  }
  .finalize-panel summary {
    padding: 0.65rem 1rem;
    cursor: pointer;
    font-size: 0.85rem;
    color: #9ca3af;
    list-style: none;
    user-select: none;
  }
  .finalize-panel summary::-webkit-details-marker { display: none; }
  .finalize-panel summary::before { content: "▶ "; font-size: 0.7rem; }
  .finalize-panel[open] summary::before { content: "▼ "; }
  .finalize-panel summary:hover { color: #e2e8f0; }

  .finalize-body {
    padding: 0 1rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  .finalize-body p {
    font-size: 0.82rem;
    color: #6b7280;
    margin: 0;
    line-height: 1.5;
  }
  .finalize-row {
    display: flex;
    gap: 0.75rem;
  }
  .finalize-row input {
    flex: 1;
    background: #111827;
    border: 1px solid #374151;
    color: #e2e8f0;
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
    font-size: 0.85rem;
    font-family: "JetBrains Mono", "Fira Code", monospace;
    outline: none;
  }
  .finalize-row input:focus { border-color: #7c8fdb; }
  .btn-finalize {
    background: #78350f;
    color: #fde68a;
    border: 1px solid #92400e;
    padding: 0.5rem 1rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.875rem;
    font-weight: 600;
    white-space: nowrap;
    transition: background 0.15s;
  }
  .btn-finalize:hover:not(:disabled) { background: #92400e; }
  .btn-finalize:disabled { opacity: 0.5; cursor: not-allowed; }
</style>

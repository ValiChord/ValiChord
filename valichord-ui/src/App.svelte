<script lang="ts">
  import { onMount } from "svelte";
  import { connect, callZome, getMyPubKey, onSignal } from "./lib/holochain.js";
  import {
    connectState,
    isConnected,
    myPubKey,
    activeRole,
    myValidatorProfile,
    notifications,
    notify,
    addPendingReveal,
    type AppRole,
  } from "./lib/store.js";
  import type { ValidatorProfile, RevealOpenSignal } from "./lib/types.js";
  import type { HolochainRecord } from "./lib/types.js";
  import ResearcherView from "./lib/ResearcherView.svelte";
  import ValidatorView from "./lib/ValidatorView.svelte";
  import GovernanceView from "./lib/GovernanceView.svelte";

  // Holochain app port — Launcher injects via URL hash, fallback to 8888
  function resolveWsUrl(): string | undefined {
    const hash = window.location.hash.slice(1);
    const params = new URLSearchParams(hash);
    const port = params.get("APP_PORT");
    if (port) return `ws://localhost:${port}`;
    if (import.meta.env.VITE_HC_PORT) return `ws://localhost:${import.meta.env.VITE_HC_PORT}`;
    return undefined; // let client use its default (Launcher env)
  }

  onMount(async () => {
    connectState.set({ status: "connecting" });
    try {
      const wsUrl = resolveWsUrl();
      await connect(wsUrl);
      const pubKey = await getMyPubKey();
      myPubKey.set(pubKey);
      connectState.set({ status: "connected" });

      // Global signal listener — RevealOpen notifies validators to reveal
      onSignal((signal) => {
        const payload = signal.payload as RevealOpenSignal | null;
        if (payload && "RevealOpen" in payload) {
          addPendingReveal(payload.RevealOpen.request_ref);
          notify("info", "Reveal phase open — you can now publish your attestation");
        }
      });

      // Role detection — check whether we have a ValidatorProfile
      try {
        const record = await callZome<HolochainRecord<ValidatorProfile> | null>(
          "attestation",
          "get_validator_profile",
          pubKey,
        );
        myValidatorProfile.set(record ?? undefined);
        if (record) activeRole.set("validator");
      } catch {
        myValidatorProfile.set(undefined);
      }
    } catch (err) {
      connectState.set({
        status: "error",
        message: String(err),
      });
    }
  });

  const TABS: { id: AppRole; label: string }[] = [
    { id: "researcher", label: "Researcher" },
    { id: "validator", label: "Validator" },
    { id: "governance", label: "Governance" },
  ];
</script>

<div class="app">
  <!-- ── Header ─────────────────────────────────────────────────────────── -->
  <header>
    <div class="brand">
      <span class="logo">◈</span>
      <span class="name">ValiChord</span>
      <span class="tagline">Reproducibility Validation Protocol</span>
    </div>
    {#if $isConnected}
      <nav>
        {#each TABS as tab}
          <button
            class="tab"
            class:active={$activeRole === tab.id}
            on:click={() => activeRole.set(tab.id)}
          >
            {tab.label}
          </button>
        {/each}
      </nav>
    {/if}
  </header>

  <!-- ── Notifications ──────────────────────────────────────────────────── -->
  <div class="notifications">
    {#each $notifications as n (n.id)}
      <div class="notif notif-{n.type}">{n.message}</div>
    {/each}
  </div>

  <!-- ── Main content ───────────────────────────────────────────────────── -->
  <main>
    {#if $connectState.status === "idle" || $connectState.status === "connecting"}
      <div class="splash">
        <div class="spinner"></div>
        <p>Connecting to Holochain conductor…</p>
      </div>
    {:else if $connectState.status === "error"}
      <div class="error-pane">
        <h2>Connection failed</h2>
        <p>{$connectState.message}</p>
        <p class="hint">
          Ensure the Holochain conductor is running and the app is installed.<br />
          Set <code>VITE_HC_PORT</code> in <code>.env</code> to override the port (default: Launcher
          auto-detect).
        </p>
      </div>
    {:else if $activeRole === "researcher"}
      <ResearcherView />
    {:else if $activeRole === "validator"}
      <ValidatorView />
    {:else}
      <GovernanceView />
    {/if}
  </main>
</div>

<style>
  :global(*) {
    box-sizing: border-box;
  }
  :global(body) {
    margin: 0;
    font-family: "Inter", system-ui, sans-serif;
    background: #0f1117;
    color: #e2e8f0;
    min-height: 100vh;
  }

  .app {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 2rem;
    height: 56px;
    background: #1a1d27;
    border-bottom: 1px solid #2d3148;
    position: sticky;
    top: 0;
    z-index: 100;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .logo {
    font-size: 1.4rem;
    color: #7c8fdb;
  }
  .name {
    font-weight: 700;
    font-size: 1.05rem;
    letter-spacing: 0.02em;
  }
  .tagline {
    font-size: 0.72rem;
    color: #6b7280;
    margin-left: 0.25rem;
  }

  nav {
    display: flex;
    gap: 0.25rem;
  }
  .tab {
    background: none;
    border: none;
    color: #9ca3af;
    padding: 0.35rem 0.9rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.88rem;
    transition: background 0.15s, color 0.15s;
  }
  .tab:hover {
    background: #2d3148;
    color: #e2e8f0;
  }
  .tab.active {
    background: #2d3148;
    color: #a5b4fc;
    font-weight: 600;
  }

  .notifications {
    position: fixed;
    bottom: 1.5rem;
    right: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    z-index: 999;
  }
  .notif {
    padding: 0.65rem 1rem;
    border-radius: 8px;
    font-size: 0.875rem;
    max-width: 320px;
    animation: slideIn 0.2s ease;
  }
  .notif-success {
    background: #14532d;
    color: #86efac;
    border: 1px solid #166534;
  }
  .notif-error {
    background: #450a0a;
    color: #fca5a5;
    border: 1px solid #7f1d1d;
  }
  .notif-info {
    background: #1e3a5f;
    color: #93c5fd;
    border: 1px solid #1d4ed8;
  }
  @keyframes slideIn {
    from {
      transform: translateX(100%);
      opacity: 0;
    }
    to {
      transform: translateX(0);
      opacity: 1;
    }
  }

  main {
    flex: 1;
    padding: 2rem;
    max-width: 1100px;
    margin: 0 auto;
    width: 100%;
  }

  .splash {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 50vh;
    gap: 1rem;
    color: #6b7280;
  }
  .spinner {
    width: 36px;
    height: 36px;
    border: 3px solid #2d3148;
    border-top-color: #7c8fdb;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .error-pane {
    background: #1a0a0a;
    border: 1px solid #7f1d1d;
    border-radius: 12px;
    padding: 2rem;
    max-width: 560px;
    margin: 4rem auto;
  }
  .error-pane h2 {
    color: #fca5a5;
    margin: 0 0 0.75rem;
  }
  .error-pane .hint {
    font-size: 0.85rem;
    color: #9ca3af;
    margin-top: 1rem;
  }
  code {
    background: #1f2937;
    padding: 0.15em 0.4em;
    border-radius: 4px;
    font-size: 0.85em;
  }
</style>

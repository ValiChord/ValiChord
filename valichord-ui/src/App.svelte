<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { connect, callZome, getMyPubKey, onSignal } from "./lib/holochain.js";
  import { initTabCoordinator } from "./lib/tabCoordinator.js";
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
  import type { ValidatorProfile, AppHcSignal } from "./lib/types.js";
  import type { HolochainRecord } from "./lib/types.js";
  import ResearcherView from "./lib/ResearcherView.svelte";
  import ValidatorView from "./lib/ValidatorView.svelte";
  import GovernanceView from "./lib/GovernanceView.svelte";

  // Holochain app port — Launcher injects via URL hash, dev mode uses Vite proxy.
  // In Codespace, the page is served from a forwarded https:// URL, so ws://localhost
  // resolves to the user's machine (not the Codespace).  Route via Vite's /hc-ws proxy
  // instead so the WebSocket stays inside the Codespace tunnel.
  function resolveWsUrl(): string | undefined {
    const hash = window.location.hash.slice(1);
    const params = new URLSearchParams(hash);
    const port = params.get("APP_PORT");
    if (port) return `ws://localhost:${port}`;
    if (import.meta.env.VITE_HC_PORT) {
      // Use same host/protocol as the page so the Vite proxy handles the upgrade.
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      return `${proto}//${window.location.host}/hc-ws`;
    }
    return undefined; // let client use its default (Launcher env)
  }

  let unsubscribeSignal: (() => void) | undefined;
  let stopTabCoordinator: (() => void) | undefined;

  onDestroy(() => {
    unsubscribeSignal?.();
    stopTabCoordinator?.();
  });

  onMount(async () => {
    stopTabCoordinator = initTabCoordinator();
    connectState.set({ status: "connecting" });
    try {
      const wsUrl = resolveWsUrl();
      await connect(wsUrl);
      const pubKey = await getMyPubKey();
      myPubKey.set(pubKey);
      connectState.set({ status: "connected" });

      // Global signal listener.  Signal enum uses adjacent-tag serde, so the
      // msgpack payload arrives as { type: "RevealOpen", content: { ... } }.
      // Capture unsubscribe so onDestroy can clean up if the component remounts.
      unsubscribeSignal = onSignal((signal) => {
        const payload = signal.payload as AppHcSignal | null;
        if (!payload || typeof payload !== "object") return;
        if (payload.type === "RevealOpen") {
          addPendingReveal(payload.content.request_ref);
          notify("info", "Reveal phase open — you can now publish your attestation");
        } else if (payload.type === "FinalizationFailed") {
          notify("error", "Round finalisation failed — the attestation was written but the HarmonyRecord could not be created. Try force-finalising the round from the Governance tab.");
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
      <img src="/valichord-logo.jpeg" alt="ValiChord" class="logo-img" />
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
    <a
      class="demo-link"
      href="https://valichord-demo.onrender.com/demo"
      target="_blank"
      rel="noopener noreferrer"
    >
      ✦ Live Demo
    </a>
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
    font-family: var(--font-body);
    background: var(--bg-base);
    color: var(--text);
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
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 100;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }
  .logo-img {
    height: 38px;
    width: auto;
    border-radius: 6px;
    display: block;
  }
  .tagline {
    font-size: 0.72rem;
    color: var(--text-dim);
  }

  .demo-link {
    margin-left: auto;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--accent-bright);
    text-decoration: none;
    padding: 0.3rem 0.75rem;
    border: 1px solid var(--accent);
    border-radius: 6px;
    white-space: nowrap;
    transition: background 0.15s, color 0.15s;
  }
  .demo-link:hover {
    background: var(--accent);
    color: #fff;
  }

  nav {
    display: flex;
    gap: 0.25rem;
  }
  .tab {
    background: none;
    border: none;
    color: var(--text-muted);
    padding: 0.35rem 0.9rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.88rem;
    font-family: var(--font-body);
    transition: background 0.15s, color 0.15s;
  }
  .tab:hover {
    background: var(--border);
    color: var(--text);
  }
  .tab.active {
    background: var(--border);
    color: var(--accent-bright);
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
    background: var(--bg-success-notif);
    color: var(--color-success);
    border: 1px solid var(--border-success);
  }
  .notif-error {
    background: var(--bg-error-notif);
    color: var(--color-error);
    border: 1px solid var(--border-error);
  }
  .notif-info {
    background: var(--bg-info);
    color: var(--color-info);
    border: 1px solid var(--border-info-notif);
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
    color: var(--text-dim);
  }
  .spinner {
    width: 36px;
    height: 36px;
    border: 3px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .error-pane {
    background: var(--bg-error);
    border: 1px solid var(--border-error);
    border-radius: 12px;
    padding: 2rem;
    max-width: 560px;
    margin: 4rem auto;
  }
  .error-pane h2 {
    color: var(--color-error);
    margin: 0 0 0.75rem;
  }
  .error-pane .hint {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-top: 1rem;
  }
  code {
    background: var(--bg-alt);
    padding: 0.15em 0.4em;
    border-radius: 4px;
    font-size: 0.85em;
    font-family: var(--font-mono);
  }
</style>

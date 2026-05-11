// Tab leader election via BroadcastChannel.
//
// Only the leader tab should do active conductor polling. Signal listeners
// run on every tab regardless (they are push-based from the conductor).
//
// Protocol (ported from flux/app/src/composables/useTabCoordinator.ts):
//   claim     — "I want to be leader"
//   hb        — heartbeat from current leader (keeps followers from claiming)
//   resign    — leader is unloading; followers should claim
//
// Tiebreak: higher UUID string wins. This prevents infinite ping-pong when
// two tabs claim simultaneously — exactly one will yield after the exchange.
//
// Usage:
//   const stop = initTabCoordinator();   // call from App.svelte onMount
//   onDestroy(stop);
//   // then gate polling with: if (get(isLeaderTab)) { ... }

import { writable } from "svelte/store";

const CHANNEL_NAME = "valichord-tab";
const HEARTBEAT_MS = 5_000;
const TIMEOUT_MS = 15_000;

// True only in the tab that currently holds conductor-polling leadership.
export const isLeaderTab = writable(false);

export function initTabCoordinator(): () => void {
  if (typeof BroadcastChannel === "undefined") {
    // SSR or browser without BroadcastChannel — assume leader.
    isLeaderTab.set(true);
    return () => {};
  }

  const myId = crypto.randomUUID();
  const ch = new BroadcastChannel(CHANNEL_NAME);
  let leader = false;
  let hbTimer: ReturnType<typeof setInterval> | undefined;
  let toTimer: ReturnType<typeof setTimeout> | undefined;

  const post = (type: string) => ch.postMessage({ type, id: myId });

  function startLeading() {
    leader = true;
    isLeaderTab.set(true);
    clearTimeout(toTimer);
    hbTimer = setInterval(() => post("hb"), HEARTBEAT_MS);
  }

  function startFollowing() {
    leader = false;
    isLeaderTab.set(false);
    clearInterval(hbTimer);
    armTimeout();
  }

  // If no heartbeat arrives within TIMEOUT_MS, assume the leader is gone
  // and claim leadership.
  function armTimeout() {
    clearTimeout(toTimer);
    toTimer = setTimeout(() => {
      post("claim");
      startLeading();
    }, TIMEOUT_MS);
  }

  ch.onmessage = ({ data }) => {
    if (!data || data.id === myId) return;
    const { type, id } = data as { type: string; id: string };

    if (type === "hb") {
      if (!leader) {
        armTimeout(); // existing leader alive — reset claim timer
      } else if (id > myId) {
        startFollowing(); // higher-priority leader exists — yield
      }
    } else if (type === "claim") {
      if (leader) {
        if (id > myId) {
          startFollowing(); // other tab wins tiebreak
        } else {
          post("hb"); // we win tiebreak — reassert with heartbeat
        }
      }
    } else if (type === "resign") {
      if (!leader) {
        clearTimeout(toTimer);
        post("claim");
        startLeading();
      }
    }
  };

  // Optimistically claim leadership on mount. If an existing leader is
  // running it will respond: hb → we yield (if their id > ours) or ignore
  // (if ours > theirs, and they have already yielded to our claim).
  post("claim");
  startLeading();

  function cleanup() {
    if (leader) post("resign");
    clearInterval(hbTimer);
    clearTimeout(toTimer);
    ch.close();
  }
  window.addEventListener("beforeunload", cleanup);

  return () => {
    cleanup();
    window.removeEventListener("beforeunload", cleanup);
  };
}

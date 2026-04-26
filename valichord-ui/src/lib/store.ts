import { writable, derived } from "svelte/store";
import type { AgentPubKey } from "@holochain/client";
import type { ValidatorProfile, HarmonyRecord, ValidationRequest } from "./types.js";
import type { HolochainRecord } from "./types.js";

// ── Connection state ──────────────────────────────────────────────────────────

export type ConnectState =
  | { status: "idle" }
  | { status: "connecting" }
  | { status: "connected" }
  | { status: "error"; message: string };

export const connectState = writable<ConnectState>({ status: "idle" });

export const isConnected = derived(
  connectState,
  ($s) => $s.status === "connected",
);

// ── Identity ──────────────────────────────────────────────────────────────────

export const myPubKey = writable<AgentPubKey | null>(null);

// ── Role detection ────────────────────────────────────────────────────────────
// Role is inferred from ValidatorProfile presence, not from the app bundle.

export type AppRole = "researcher" | "validator" | "governance";

export const activeRole = writable<AppRole>("researcher");

// Null = not yet fetched; undefined = fetched and none exists
export const myValidatorProfile = writable<HolochainRecord<ValidatorProfile> | null | undefined>(
  null,
);

// Derived: true when the user has a validator profile
export const isValidator = derived(
  myValidatorProfile,
  ($p) => $p !== null && $p !== undefined,
);

// ── Flash notifications ───────────────────────────────────────────────────────

export type NotificationType = "success" | "error" | "info";

export interface Notification {
  id: number;
  type: NotificationType;
  message: string;
}

let _notifId = 0;
const _notifications = writable<Notification[]>([]);

export const notifications = { subscribe: _notifications.subscribe };

export function notify(type: NotificationType, message: string, durationMs = 4000) {
  const id = ++_notifId;
  _notifications.update((ns) => [...ns, { id, type, message }]);
  setTimeout(() => {
    _notifications.update((ns) => ns.filter((n) => n.id !== id));
  }, durationMs);
}

// ── Caches (avoids redundant DHT reads within a session) ──────────────────────

// Pending validation requests in the current discipline
export const pendingRequests = writable<HolochainRecord<ValidationRequest>[]>([]);

// HarmonyRecords fetched for the governance view
export const harmonyRecords = writable<HolochainRecord<HarmonyRecord>[]>([]);

// My claimed studies (validator view)
export const myClaims = writable<HolochainRecord<unknown>[]>([]);

// Pending RevealOpen signals — list of request_ref hashes awaiting reveal
export const pendingReveals = writable<Uint8Array[]>([]);

export function addPendingReveal(requestRef: Uint8Array) {
  pendingReveals.update((rs) => {
    // deduplicate by byte content
    const already = rs.some(
      (r) => r.length === requestRef.length && r.every((b, i) => b === requestRef[i]),
    );
    return already ? rs : [...rs, requestRef];
  });
}

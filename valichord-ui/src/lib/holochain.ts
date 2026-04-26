import {
  AppWebsocket,
  type AppClient,
  type Signal,
  SignalType,
  type AppSignal,
  encodeHashToBase64,
  decodeHashFromBase64,
  type HoloHashB64,
  HoloHashType,
  hashFrom32AndType,
} from "@holochain/client";

export { encodeHashToBase64, decodeHashFromBase64 };

// ── Zome routing ─────────────────────────────────────────────────────────────

const ZOME_NAMES: Record<string, string> = {
  attestation: "attestation_coordinator",
  researcher_repository: "researcher_repository_coordinator",
  validator_workspace: "validator_workspace_coordinator",
  governance: "governance_coordinator",
};

// ── Singleton client ──────────────────────────────────────────────────────────

let _client: AppClient | null = null;
let _signalHandlers: Array<(signal: AppSignal) => void> = [];

export async function connect(url?: string): Promise<AppClient> {
  if (_client) return _client;
  _client = await AppWebsocket.connect(url ? { url: new URL(url) } : undefined);
  (_client as AppWebsocket).on("signal", (signal: Signal) => {
    if (signal.type === SignalType.App) {
      for (const h of _signalHandlers) h(signal.value);
    }
  });
  return _client;
}

export function getClient(): AppClient {
  if (!_client) throw new Error("Holochain client not connected");
  return _client;
}

export function onSignal(handler: (signal: AppSignal) => void): () => void {
  _signalHandlers.push(handler);
  return () => {
    _signalHandlers = _signalHandlers.filter((h) => h !== handler);
  };
}

// ── callZome helper ───────────────────────────────────────────────────────────

export async function callZome<T>(
  role: string,
  fn_name: string,
  payload: unknown = null,
): Promise<T> {
  const client = getClient();
  const zome_name = ZOME_NAMES[role];
  if (!zome_name) throw new Error(`Unknown role: ${role}`);
  return client.callZome({ role_name: role, zome_name, fn_name, payload }) as Promise<T>;
}

// ── Hash utilities ────────────────────────────────────────────────────────────

export function hashToBase64(hash: Uint8Array): string {
  return encodeHashToBase64(hash);
}

export function base64ToHash(b64: string): Uint8Array {
  return decodeHashFromBase64(b64 as HoloHashB64);
}

export function hashesEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}

export function shortHash(hash: Uint8Array): string {
  const b64 = hashToBase64(hash);
  return `${b64.slice(0, 8)}…${b64.slice(-4)}`;
}

// ── ExternalHash construction ─────────────────────────────────────────────────
// ExternalHash is a 39-byte Holochain HoloHash with External type prefix.
// hashFrom32AndType produces the correct 4-byte checksum via blake2b.

export function externalHashFromBytes(core32: Uint8Array): Uint8Array {
  return hashFrom32AndType(core32, HoloHashType.External);
}

export function externalHashFromHex(hex: string): Uint8Array {
  const bytes = new Uint8Array(32);
  for (let i = 0; i < 32; i++) {
    bytes[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }
  return externalHashFromBytes(bytes);
}

// ── My pubkey ─────────────────────────────────────────────────────────────────

export async function getMyPubKey(): Promise<Uint8Array> {
  return (getClient() as AppWebsocket).myPubKey;
}

import {
  AppWebsocket,
  type AppClient,
  type Signal,
  SignalType,
  type AppSignal,
  encodeHashToBase64,
  decodeHashFromBase64,
  setSigningCredentials,
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

function resolveToken(): number[] | undefined {
  // Launcher injects token via URL hash; dev mode reads VITE_HC_TOKEN (base64)
  const hash = window.location.hash.slice(1);
  const params = new URLSearchParams(hash);
  const hashToken = params.get("TOKEN");
  if (hashToken) return Array.from(atob(hashToken), c => c.charCodeAt(0));
  const envToken = import.meta.env.VITE_HC_TOKEN as string | undefined;
  if (envToken) return Array.from(atob(envToken), c => c.charCodeAt(0));
  return undefined;
}

// ── Dev-mode signing credentials ─────────────────────────────────────────────
// In Launcher, signing credentials are injected automatically. For a raw
// conductor (dev.sh), dev-setup.mjs pre-generates per-cell key pairs, grants
// them via the admin API, and serializes them into VITE_HC_SIGNING_CREDENTIALS.
// We register them here so callZome can sign requests without Launcher.

interface DevCellCred {
  dnaHash: string;
  agentKey: string;
  capSecret: string; // base64
  signingKey: string;
  pubKey: string;    // base64
  privKey: string;   // base64
}

function loadDevSigningCredentials() {
  const raw = import.meta.env.VITE_HC_SIGNING_CREDENTIALS as string | undefined;
  if (!raw) return;
  try {
    const creds: DevCellCred[] = JSON.parse(atob(raw));
    for (const c of creds) {
      const cellId: [Uint8Array, Uint8Array] = [
        decodeHashFromBase64(c.dnaHash as HoloHashB64),
        decodeHashFromBase64(c.agentKey as HoloHashB64),
      ];
      setSigningCredentials(cellId, {
        capSecret: Uint8Array.from(atob(c.capSecret), ch => ch.charCodeAt(0)),
        signingKey: decodeHashFromBase64(c.signingKey as HoloHashB64),
        keyPair: {
          publicKey: Uint8Array.from(atob(c.pubKey), ch => ch.charCodeAt(0)),
          privateKey: Uint8Array.from(atob(c.privKey), ch => ch.charCodeAt(0)),
        },
      });
    }
  } catch (e) {
    console.warn("Failed to load dev signing credentials:", e);
  }
}

export async function connect(url?: string): Promise<AppClient> {
  if (_client) return _client;
  loadDevSigningCredentials();
  const token = resolveToken();
  _client = await AppWebsocket.connect(
    url || token ? { url: url ? new URL(url) : undefined, token } : undefined,
  );
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

import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';
import {
  AppWebsocket,
  decodeHashFromBase64,
  setSigningCredentials,
  hashFrom32AndType,
  HoloHashType,
  type HoloHashB64,
} from '@holochain/client';
import { readTestEnv } from '../setup/conductor-manager.js';

export const UI_PORT = process.env.E2E_UI_PORT ?? '5178';

/**
 * Builds the app URL with #APP_PORT=&TOKEN=&CREDS= hash params — the same
 * channel Holochain Launcher uses to inject connection details, which
 * App.svelte/holochain.ts already read. Values are URI-encoded so base64
 * '+'/'=' survive URLSearchParams decoding.
 */
export function holochainUrl(path = '/'): string {
  const { appPort, tokenB64, credsB64 } = readTestEnv();
  const hash =
    `APP_PORT=${appPort}` +
    `&TOKEN=${encodeURIComponent(tokenB64)}` +
    `&CREDS=${encodeURIComponent(credsB64)}`;
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `http://localhost:${UI_PORT}${cleanPath}#${hash}`;
}

/** Navigate to the app and wait for the conductor connection to establish. */
export async function gotoApp(page: Page): Promise<void> {
  // Surface browser-side failures in the test output — zome-call errors land
  // in a 4-second toast (store.ts notify) that failure screenshots miss.
  page.on('pageerror', (err) => console.log(`[browser pageerror] ${err.message}`));
  page.on('console', (msg) => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      console.log(`[browser ${msg.type()}] ${msg.text()}`);
    }
  });
  await page.goto(holochainUrl('/'));
  await waitForConnection(page);
}

/**
 * Connected = the splash spinner is gone and the role tabs have rendered.
 * Generous timeout: the first connection after install can hit WASM JIT.
 */
export async function waitForConnection(page: Page, timeoutMs = 180_000): Promise<void> {
  await expect(page.getByRole('button', { name: 'Researcher' })).toBeVisible({
    timeout: timeoutMs,
  });
}

// ── Node-side zome client (for seeding data outside the browser) ─────────────

const ZOME_NAMES: Record<string, string> = {
  attestation: 'attestation_coordinator',
  researcher_repository: 'researcher_repository_coordinator',
  validator_workspace: 'validator_workspace_coordinator',
  governance: 'governance_coordinator',
};

interface SerializedCellCred {
  dnaHash: string;
  agentKey: string;
  capSecret: string;
  signingKey: string;
  pubKey: string;
  privKey: string;
}

export interface TestClient {
  callZome<T>(role: string, fnName: string, payload?: unknown): Promise<T>;
  close(): Promise<void>;
}

/**
 * AppWebsocket with the globalSetup-issued token and signing credentials —
 * lets specs seed protocol state via direct zome calls, then assert on it
 * through the real UI (the hybrid pattern from requests-and-offers).
 */
export async function createTestClient(): Promise<TestClient> {
  const { appPort, tokenB64, credsB64 } = readTestEnv();

  const creds = JSON.parse(
    Buffer.from(credsB64, 'base64').toString('utf-8'),
  ) as SerializedCellCred[];
  for (const c of creds) {
    const cellId: [Uint8Array, Uint8Array] = [
      decodeHashFromBase64(c.dnaHash as HoloHashB64),
      decodeHashFromBase64(c.agentKey as HoloHashB64),
    ];
    setSigningCredentials(cellId, {
      capSecret: Uint8Array.from(Buffer.from(c.capSecret, 'base64')),
      signingKey: decodeHashFromBase64(c.signingKey as HoloHashB64),
      keyPair: {
        keyType: 'ed25519',
        publicKey: Uint8Array.from(Buffer.from(c.pubKey, 'base64')),
        privateKey: Uint8Array.from(Buffer.from(c.privKey, 'base64')),
      },
    });
  }

  const client = await AppWebsocket.connect({
    url: new URL(`ws://localhost:${appPort}`),
    token: Array.from(Buffer.from(tokenB64, 'base64')),
    wsClientOptions: { origin: 'e2e-spec' },
    defaultTimeout: 120_000,
  });

  return {
    async callZome<T>(role: string, fnName: string, payload: unknown = null): Promise<T> {
      const zome_name = ZOME_NAMES[role];
      if (!zome_name) throw new Error(`Unknown role: ${role}`);
      return client.callZome({
        role_name: role,
        zome_name,
        fn_name: fnName,
        payload,
      }) as Promise<T>;
    },
    async close() {
      await client.client.close();
    },
  };
}

/** 64-char hex → 39-byte ExternalHash (mirror of holochain.ts externalHashFromHex). */
export function externalHashFromHex(hex: string): Uint8Array {
  const bytes = new Uint8Array(32);
  for (let i = 0; i < 32; i++) {
    bytes[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }
  return hashFrom32AndType(bytes, HoloHashType.External);
}

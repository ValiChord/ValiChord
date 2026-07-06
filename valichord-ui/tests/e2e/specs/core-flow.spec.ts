import { test, expect } from '@playwright/test';
import {
  gotoApp,
  createTestClient,
  externalHashFromHex,
  type TestClient,
} from '../utils/helpers.js';

// ============================================================================
// CORE E2E FLOW — one real conductor, one agent, all four DNAs.
//
// globalSetup starts exactly ONE conductor for the whole run, so every test
// here shares the same agent identity and DHT state. Later tests depend on
// state created by earlier ones (profile → request → browse), so the file
// runs as a single serial story: a failure skips the rest instead of
// cascading into misleading errors.
//
// Scope: UI ↔ conductor wiring across the three role views — connection,
// form → zome call → DHT, zome-seeded data → UI render. The commit-reveal
// protocol itself is covered by sweettest/Tryorama; this layer catches what
// they can't: serde drift at the msgpack boundary, broken signing-credential
// bootstrap, and views that no longer render real records.
// ============================================================================

const FORM_HASH_HEX = 'a3f2'.repeat(16); // 64-char hex, submitted via the UI form
const SEED_HASH_HEX = 'b7e1'.repeat(16); // 64-char hex, seeded via direct zome call
const FORM_DEPOSIT_URL = 'https://example.org/e2e-form-deposit.zip';
const SEED_DEPOSIT_URL = 'https://example.org/e2e-seeded-deposit.zip';

test.describe.serial('ValiChord core flow', () => {
  let client: TestClient;

  test.beforeAll(async () => {
    client = await createTestClient();
  });

  test.afterAll(async () => {
    await client?.close();
  });

  test('app loads and connects to the conductor', async ({ page }) => {
    await gotoApp(page);

    // Connection splash resolved into the role tab nav — not the error pane.
    await expect(page.getByText('Connection failed')).toBeHidden();
    await expect(page.getByRole('button', { name: 'Validator' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Governance' })).toBeVisible();
  });

  test('validator sets up a profile through the UI', async ({ page }) => {
    await gotoApp(page);
    await page.getByRole('button', { name: 'Validator' }).click();

    await page.getByRole('button', { name: 'Create profile' }).click();
    await page.getByRole('button', { name: 'Computational Biology' }).click();
    await page.getByRole('textbox', { name: /^Institution/ }).fill('E2E Validator Institute');
    await page.getByRole('button', { name: 'Save profile' }).click();

    await expect(page.getByText('Validator profile saved')).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole('button', { name: 'Browse pending requests' })).toBeVisible();
  });

  test('researcher submits a validation request through the form', async ({ page }) => {
    await gotoApp(page);
    await page.getByRole('button', { name: 'Researcher', exact: true }).click();

    await page.getByRole('button', { name: '+ New Request' }).click();
    await page.getByLabel(/Deposit URL/).fill(FORM_DEPOSIT_URL);
    await page.getByLabel(/Data hash/).fill(FORM_HASH_HEX);
    await page.getByLabel('Number of validators required').fill('1');
    await page.getByLabel('Your institution').fill('E2E Researcher University');
    await page.getByRole('button', { name: 'Submit request' }).click();

    // On success the view returns to the dashboard (durable state — the
    // success toast auto-dismisses after 4 s and is unreliable to assert on).
    await expect(page.getByRole('heading', { name: 'Researcher Dashboard' })).toBeVisible({
      timeout: 60_000,
    });
  });

  test('the submitted request appears in the validator browse list', async ({ page }) => {
    await gotoApp(page);
    await page.getByRole('button', { name: 'Validator' }).click();
    await page.getByRole('button', { name: 'Browse pending requests' }).click();

    await expect(page.getByText(FORM_DEPOSIT_URL)).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole('button', { name: 'Claim this study' }).first()).toBeVisible();
  });

  test('a zome-seeded request renders in the UI', async ({ page }) => {
    // Seed through the conductor directly — the r-n-o hybrid pattern: fast,
    // typed setup via zome call, then assert the UI renders the real record.
    await client.callZome('attestation', 'submit_validation_request', {
      data_hash: externalHashFromHex(SEED_HASH_HEX),
      data_access_url: SEED_DEPOSIT_URL,
      deposit_access_type: 'PublicUrl',
      deposit_token: null,
      protocol_ref: null,
      protocol_access_url: null,
      num_validators_required: 1,
      validation_tier: 'Basic',
      discipline: { type: 'ComputationalBiology' },
      researcher_institution: 'E2E Seed University',
    });

    await gotoApp(page);
    await page.getByRole('button', { name: 'Validator' }).click();
    await page.getByRole('button', { name: 'Browse pending requests' }).click();

    // Both the form-submitted and the seeded request are pending.
    await expect(page.getByText(SEED_DEPOSIT_URL)).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(FORM_DEPOSIT_URL)).toBeVisible();
  });

  test('governance view renders', async ({ page }) => {
    await gotoApp(page);
    await page.getByRole('button', { name: 'Governance' }).click();

    await expect(page.getByRole('heading', { name: /Governance/ })).toBeVisible();
    // No HarmonyRecords exist yet — the view must settle without erroring.
    await expect(page.getByRole('button', { name: /Refresh/ })).toBeEnabled({
      timeout: 60_000,
    });
  });
});

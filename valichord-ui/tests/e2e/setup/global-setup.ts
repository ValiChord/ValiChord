import { startConductor, setupHapp } from './conductor-manager.js';

export default async function globalSetup() {
  await startConductor();
  await setupHapp();
}

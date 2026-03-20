import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // Tryorama spins up a real Holochain conductor + loads ~30 MB of WASMs.
    // Longest observed passing test: ~152 s (3-player dhtSync).
    // 5 min ceiling catches conductor crashes without cutting off slow-but-live tests.
    testTimeout: 300_000,
    hookTimeout: 120_000,
    // Run tests serially: each test claims ports, avoids conflicts.
    pool: "forks",
    poolOptions: {
      forks: { singleFork: true },
    },
  },
});

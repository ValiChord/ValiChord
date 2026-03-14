import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // Tryorama spins up a real Holochain conductor + loads ~30 MB of WASMs.
    // Codespaces JIT-compiles 8 WASMs per player: allow 15 min per test.
    testTimeout: 900_000,
    hookTimeout: 120_000,
    // Run tests serially: each test claims ports, avoids conflicts.
    pool: "forks",
    poolOptions: {
      forks: { singleFork: true },
    },
  },
});

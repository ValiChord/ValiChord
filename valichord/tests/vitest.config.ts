import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // Tryorama spins up a real Holochain conductor — give it time.
    testTimeout: 120_000,
    hookTimeout: 60_000,
    // Run tests serially: each test claims ports, avoids conflicts.
    pool: "forks",
    poolOptions: {
      forks: { singleFork: true },
    },
  },
});

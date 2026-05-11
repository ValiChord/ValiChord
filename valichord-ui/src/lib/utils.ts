// ── asyncFilter ───────────────────────────────────────────────────────────────
// Runs async predicates in parallel then filters. Drop-in for sequential
// filter loops over validator lists and DHT record arrays.
// Ported from flux/packages/utils/src/asyncFilter.ts.

export async function asyncFilter<T>(
  arr: T[],
  callback: (item: T) => Promise<boolean>,
): Promise<T[]> {
  const pairs = await Promise.all(
    arr.map(async (item) => ({ item, keep: await callback(item) })),
  );
  return pairs.filter((p) => p.keep).map((p) => p.item);
}

// ── upsertByHash ──────────────────────────────────────────────────────────────
// Immutable upsert for arrays of Holochain records keyed by ActionHash
// (Uint8Array). Adapted from flux's upsertById — uses byte comparison rather
// than string equality because ActionHash is a Uint8Array, not a string.

export function upsertByHash<T>(
  items: readonly T[],
  next: T,
  getHash: (item: T) => Uint8Array,
): T[] {
  const nextHash = getHash(next);
  const index = items.findIndex((item) => {
    const h = getHash(item);
    return h.length === nextHash.length && h.every((b, i) => b === nextHash[i]);
  });
  if (index === -1) return [...items, next];
  const clone = items.slice();
  clone[index] = next;
  return clone;
}

#!/usr/bin/env python3
"""
ValiChord DNA/hApp bundle packer.

Replicates the behaviour of:
  hc dna pack dnas/attestation -o workdir/attestation.dna
  hc app pack .              -o workdir/valichord.happ

Bundle format (mr_bundle crate):
  pack(data)  = gzip( rmp_serde::to_vec_named(data) )
  Bundle<M>   = { "manifest": M, "resources": BTreeMap<str, bytes> }

The manifest's zome/dna "path" fields are replaced in-place by their
resource_id (= the file's basename), which then becomes the key in the
resources map.

Usage:
  python3 pack_dna.py
"""

import gzip
import os
import sys
from pathlib import Path

import msgpack

WORKSPACE = Path(__file__).parent.resolve()
TARGET    = WORKSPACE / "target" / "wasm32-unknown-unknown" / "release"
WORKDIR   = WORKSPACE / "workdir"
DNA_YAML  = WORKSPACE / "dnas" / "attestation" / "dna.yaml"
HAPP_YAML = WORKSPACE / "happ.yaml"


def resource_id_for_path(path: str) -> str:
    """Mirrors mr_bundle::resource_id_for_path — returns the file's basename."""
    return os.path.basename(path)


def pack(data) -> bytes:
    """Mirrors mr_bundle::pack: named msgpack → gzip."""
    mp = msgpack.packb(data, use_bin_type=True)
    return gzip.compress(mp)


def build_dna_bundle() -> bytes:
    """
    Pack the Attestation DNA.

    Reads dna.yaml, loads the two WASM blobs, and produces a gzip'd
    named-msgpack bundle compatible with mr_bundle::Bundle<ValidatedDnaManifest>.
    """
    import yaml  # pyyaml

    with open(DNA_YAML) as f:
        manifest = yaml.safe_load(f)

    resources = {}

    # --- integrity zomes ---
    for zome in manifest.get("integrity", {}).get("zomes", []):
        path  = zome["path"]
        rid   = resource_id_for_path(path)
        # Resolve path relative to dna.yaml's directory
        wasm  = (DNA_YAML.parent / path).resolve()
        if not wasm.exists():
            sys.exit(f"ERROR: WASM not found: {wasm}\nDid you run `cargo build --target wasm32-unknown-unknown --release` first?")
        resources[rid] = wasm.read_bytes()
        zome["path"] = rid          # replace in manifest (mirrors generate_resource_ids)

    # --- coordinator zomes ---
    for zome in manifest.get("coordinator", {}).get("zomes", []):
        path  = zome["path"]
        rid   = resource_id_for_path(path)
        wasm  = (DNA_YAML.parent / path).resolve()
        if not wasm.exists():
            sys.exit(f"ERROR: WASM not found: {wasm}")
        resources[rid] = wasm.read_bytes()
        zome["path"] = rid

    bundle = {"manifest": manifest, "resources": resources}
    return pack(bundle)


def build_happ_bundle(dna_bytes: bytes) -> bytes:
    """
    Pack the hApp bundle.

    Reads happ.yaml, embeds the already-packed DNA bytes, and produces a
    gzip'd named-msgpack bundle.
    """
    import yaml

    with open(HAPP_YAML) as f:
        manifest = yaml.safe_load(f)

    resources = {}

    for role in manifest.get("roles", []):
        dna_section = role.get("dna", {})
        path = dna_section.get("path")
        if path is None:
            continue
        rid = resource_id_for_path(path)
        resources[rid] = dna_bytes
        dna_section["path"] = rid   # replace in manifest

    bundle = {"manifest": manifest, "resources": resources}
    return pack(bundle)


def main():
    # Check pyyaml is available
    try:
        import yaml
    except ImportError:
        sys.exit("ERROR: pyyaml not installed. Run: pip3 install pyyaml")

    WORKDIR.mkdir(parents=True, exist_ok=True)

    print("Packing DNA…")
    dna_bytes = build_dna_bundle()
    dna_out = WORKDIR / "attestation.dna"
    dna_out.write_bytes(dna_bytes)
    print(f"  → {dna_out}  ({len(dna_bytes):,} bytes)")

    print("Packing hApp…")
    happ_bytes = build_happ_bundle(dna_bytes)
    happ_out = WORKDIR / "valichord.happ"
    happ_out.write_bytes(happ_bytes)
    print(f"  → {happ_out}  ({len(happ_bytes):,} bytes)")

    print("Done.")


if __name__ == "__main__":
    main()

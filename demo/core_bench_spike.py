#!/usr/bin/env python3
"""Phase-0 capsule-selection helper. Runs ONE capsule through the validator
eval with one model, in hard mode, and prints the produced value + wall-clock
time. Use it to confirm a candidate reproduces clean (<5 min, no GPU) before
wiring it into the demo.

    export ANTHROPIC_API_KEY=sk-ant-...
    python3 demo/core_bench_spike.py --capsule capsule-5507257 \
        --model anthropic/claude-opus-4-8
"""
import argparse
import time

from core_bench_validator import run_validator_eval


def main(argv=None):
    p = argparse.ArgumentParser(description="CORE-Bench capsule spike")
    p.add_argument("--capsule", required=True)
    p.add_argument("--model", default="anthropic/claude-opus-4-8")
    args = p.parse_args(argv)

    print(f"[spike] running {args.capsule} with {args.model} (hard mode)...")
    t0 = time.time()
    report = run_validator_eval(args.capsule, args.model)
    elapsed = time.time() - t0
    print(f"[spike] elapsed: {elapsed:.0f}s")
    if not report:
        print("[spike] RESULT: no report.json produced -> did NOT reproduce")
        return 1
    print(f"[spike] RESULT: report.json = {report}")
    print(f"[spike] reproduced in {elapsed:.0f}s -> "
          f"{'GOOD demo candidate' if elapsed < 300 else 'TOO SLOW for <5min target'}")

    from capsule_blinding_gate import load_retained_capsule_text, find_answer_leaks
    # spike claim is a single deterministic value with a zero-width band; widen for the report
    claim = {k: {"value": v, "lower": v, "upper": v, "basis": "spike"} for k, v in report.items()}
    leaks = find_answer_leaks(load_retained_capsule_text(args.capsule), claim)
    if leaks:
        print("  ⚠ BLINDING LEAK — answer readable from retained inputs:")
        for lk in leaks:
            print(f"      {lk.file}: '{lk.token}' ({lk.signal})")
    else:
        print("  ✓ blinding: target not found in retained inputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

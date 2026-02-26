#!/usr/bin/env python3
"""
ValiChord Auto-Generate
Research Repository Cleaning Tool
v1.0 — implementing ValiChord Specification v15

Usage:
    python valichord.py <repository.zip>

Output:
    valichord_output_<reponame>.zip
"""

import sys
import os
import zipfile
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

from detectors.failure_modes_simple import run_simple_detectors
from generators.report import generate_cleaning_report
from generators.drafts import generate_all_drafts


def main():
    # ── argument check ──────────────────────────────────────────────
    if len(sys.argv) < 2:
        print("Usage: python valichord.py <repository.zip>")
        sys.exit(1)

    zip_path = Path(sys.argv[1])

    if not zip_path.exists():
        print(f"Error: File not found — {zip_path}")
        sys.exit(1)

    if not zipfile.is_zipfile(zip_path):
        print(f"Error: Not a valid ZIP file — {zip_path}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  ValiChord Auto-Generate")
    print(f"  Processing: {zip_path.name}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    # ── extract to temp directory ────────────────────────────────────
    work_dir = Path(tempfile.mkdtemp(prefix="valichord_"))
    repo_dir = work_dir / "repository"
    output_dir = work_dir / "output"
    corrections_dir = output_dir / "proposed_corrections"

    repo_dir.mkdir()
    output_dir.mkdir()
    corrections_dir.mkdir()

    print(f"Extracting repository...")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(repo_dir)

    # ── safety check: size ───────────────────────────────────────────
    total_size_mb = sum(
        f.stat().st_size for f in repo_dir.rglob('*') if f.is_file()
    ) / (1024 * 1024)

    if total_size_mb > 50:
        print(f"  WARNING: Repository is {total_size_mb:.1f}MB "
              f"(limit 50MB). Data files will be inventoried "
              f"but not fully analysed.")

    # ── recursively extract nested zips ────────────────────────────
    # Track extracted zips so detect_NZ can report them even after deletion.
    _nested_zip_records = []

    def extract_nested_zips(directory, depth=0):
        if depth > 3:
            return
        for nested in list(directory.rglob("*.zip")):
            if nested.stat().st_size > 100 * 1024 * 1024:
                continue  # skip anything over 100MB
            try:
                dest = nested.parent / nested.stem
                dest.mkdir(exist_ok=True)
                with zipfile.ZipFile(nested, "r") as zf:
                    zf.extractall(dest)
                _nested_zip_records.append({
                    'path': str(nested.relative_to(repo_dir)),
                    'size': nested.stat().st_size,
                })
                nested.unlink()
                print(f"  Extracted nested: {nested.name}")
                extract_nested_zips(dest, depth + 1)
            except Exception:
                pass

    extract_nested_zips(repo_dir)

    if _nested_zip_records:
        import json as _json
        (repo_dir / '.valichord_nested_zips.json').write_text(
            _json.dumps(_nested_zip_records), encoding='utf-8'
        )

    print(f"  Repository size: {total_size_mb:.1f}MB")

    # ── inventory all files ──────────────────────────────────────────
    all_files = [
        f for f in repo_dir.rglob('*')
        if f.is_file()
        and '.git' not in f.parts
        and '__pycache__' not in f.parts
        and '__MACOSX' not in f.parts       # macOS zip metadata directory
        and not f.name.startswith('._')     # macOS resource-fork sidecar files
        and f.name not in {'.DS_Store', 'Thumbs.db', 'desktop.ini',
                            '.valichord_nested_zips.json'}
    ]

    print(f"  Files found: {len(all_files)}")
    print()

    # ── run detectors ────────────────────────────────────────────────
    print("Running detectors...")
    findings = run_simple_detectors(repo_dir, all_files)

    # count by severity
    critical = sum(1 for f in findings if f['severity'] == 'CRITICAL')
    significant = sum(1 for f in findings if f['severity'] == 'SIGNIFICANT')
    low = sum(1 for f in findings if f['severity'] == 'LOW CONFIDENCE')

    print(f"  CRITICAL:         {critical}")
    print(f"  SIGNIFICANT:      {significant}")
    print(f"  LOW CONFIDENCE:   {low}")
    print()

    # ── generate output files ────────────────────────────────────────
    print("Generating output files...")
    generate_all_drafts(repo_dir, all_files, findings, output_dir)
    generate_cleaning_report(
        zip_path.name, repo_dir, all_files, findings, output_dir
    )

    # ── copy original files to output ────────────────────────────────
    original_copy = output_dir / "original_repository"
    shutil.copytree(repo_dir, original_copy)

    # ── package output as ZIP ────────────────────────────────────────
    output_name = f"valichord_output_{zip_path.stem}"
    output_zip = Path("output") / f"{output_name}.zip"
    Path("output").mkdir(exist_ok=True)

    print(f"Packaging output...")
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in output_dir.rglob('*'):
            if f.is_file():
                zf.write(f, f.relative_to(output_dir))

    # ── clean up temp ────────────────────────────────────────────────
    shutil.rmtree(work_dir)

    print(f"\n{'='*60}")
    print(f"  Complete.")
    print(f"  Output: {output_zip}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
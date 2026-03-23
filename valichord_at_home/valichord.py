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
from detectors.claude_semantic import run_claude_analysis
from generators.report import generate_cleaning_report
from generators.drafts import generate_all_drafts
from generators.log import generate_valichord_log


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

    # ── record nested archives BEFORE extraction (zips will be deleted) ──
    # Scan first while the files definitely exist, write sidecar for detect_NZ.
    import json as _json
    _archive_exts = {'.zip', '.rar', '.7z', '.tar', '.gz', '.tgz', '.bz2'}
    _nested_archive_records = []
    for _af in repo_dir.rglob('*'):
        if not (_af.is_file() and _af.suffix.lower() in _archive_exts
                and _af.stat().st_size <= 100 * 1024 * 1024):
            continue
        _rec = {'path': str(_af.relative_to(repo_dir)), 'size': _af.stat().st_size}
        if _af.suffix.lower() == '.zip':
            try:
                with zipfile.ZipFile(_af, 'r') as _z:
                    _znames = [n for n in _z.namelist() if not n.endswith('/')]
                    _zcount = len(_znames)
                    _zexts = sorted({Path(n).suffix.lower().lstrip('.')
                                     for n in _znames if Path(n).suffix})[:3]
                    _rec['contents_note'] = (
                        f' — {_zcount} files'
                        + (f' ({", ".join(_zexts)})' if _zexts else '')
                    )
            except Exception:
                pass
        _nested_archive_records.append(_rec)
    if _nested_archive_records:
        (repo_dir / '.valichord_nested_archives.json').write_text(
            _json.dumps(_nested_archive_records), encoding='utf-8'
        )

    # ── recursively extract nested zips ────────────────────────────
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
                nested.unlink()
                print(f"  Extracted nested: {nested.name}")
                extract_nested_zips(dest, depth + 1)
            except Exception:
                pass

    extract_nested_zips(repo_dir)

    print(f"  Repository size: {total_size_mb:.1f}MB")

    # ── inventory all files ──────────────────────────────────────────
    all_files = sorted(
        (
            f for f in repo_dir.rglob('*')
            if f.is_file()
            and '.git' not in f.parts
            and '__pycache__' not in f.parts
            and '__MACOSX' not in f.parts       # macOS zip metadata directory
            and not f.name.startswith('._')     # macOS resource-fork sidecar files
            and f.name not in {'.DS_Store', 'Thumbs.db', 'desktop.ini',
                                '.valichord_nested_archives.json'}
            # Exclude ValiChord-generated output files so they don't confuse
            # detectors when a previous output zip is re-uploaded as input.
            and f.name not in {'ASSESSMENT.md', 'CLEANING_REPORT.md'}
            and not (f.name.endswith('_DRAFT.md') or f.name.endswith('_DRAFT.txt'))
        ),
        key=lambda f: str(f),
    )

    print(f"  Files found: {len(all_files)}")
    print()

    # ── run detectors ────────────────────────────────────────────────
    print("Running detectors...")
    findings = run_simple_detectors(repo_dir, all_files, zip_name=zip_path.name)

    # count by severity
    critical = sum(1 for f in findings if f['severity'] == 'CRITICAL')
    significant = sum(1 for f in findings if f['severity'] == 'SIGNIFICANT')
    low = sum(1 for f in findings if f['severity'] == 'LOW CONFIDENCE')

    print(f"  CRITICAL:         {critical}")
    print(f"  SIGNIFICANT:      {significant}")
    print(f"  LOW CONFIDENCE:   {low}")
    print()

    # ── semantic analysis (Claude) — silent if no API key ────────────
    print("Running semantic analysis...")
    claude_findings, enhanced_details = run_claude_analysis(
        repo_dir, all_files, findings
    )
    if claude_findings:
        findings = findings + claude_findings
        critical    = sum(1 for f in findings if f['severity'] == 'CRITICAL')
        significant = sum(1 for f in findings if f['severity'] == 'SIGNIFICANT')
        low         = sum(1 for f in findings if f['severity'] == 'LOW CONFIDENCE')
        print(f"  CRITICAL:         {critical}")
        print(f"  SIGNIFICANT:      {significant}")
        print(f"  LOW CONFIDENCE:   {low}")
    else:
        print("  (no API key — semantic analysis skipped)")
    print()

    # ── generate output files ────────────────────────────────────────
    print("Generating output files...")
    generate_all_drafts(repo_dir, all_files, findings, output_dir)
    generate_cleaning_report(
        zip_path.name, repo_dir, all_files, findings, output_dir,
        enhanced_details=enhanced_details,
    )
    generate_valichord_log(zip_path.name, repo_dir, all_files, findings, output_dir)

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
"""
ValiChord Auto-Generate
Machine-readable feature log (VALICHORD_LOG.json)

Internal instrument for Phase 0 data collection — not a researcher deliverable.
Always written even if other output files fail.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path


VALICHORD_VERSION = "v15"

# All detector codes evaluated in a standard run, in registration order.
# Used to compute detectors_suppressed = ALL_DETECTOR_CODES - detectors_fired.
ALL_DETECTOR_CODES = [
    "BQ", "A", "B", "C", "D", "N", "Z", "W", "BJ", "BK", "BL",
    "G", "H", "K", "P", "PAP", "V", "I", "J", "M", "L", "O", "Q",
    "R", "S", "T", "X", "Y", "AA", "AB", "AC", "AD", "AE", "AF",
    "AG", "AH", "AI", "AJ", "AK", "AL", "AM", "AN", "AO", "AP",
    "AQ", "AR", "AS", "AT", "AU", "AV", "AW", "AX", "AY", "AZ",
    "BA", "BB", "BC", "BD", "BE", "BF", "BG", "BH", "BI", "BM",
    "BP", "BR", "BS", "BT", "FD", "BU", "BV", "BW", "BX", "BY",
    "BZ", "CA", "CB", "CC", "CD", "CE", "CR", "CF", "CG", "BN",
    "E", "F", "U", "CH", "CI", "CJ", "CK", "CL", "CM", "CN", "CO",
    "CP", "CQ", "CS", "CU", "CV", "CW", "CX", "CY", "CZ", "DA",
    "DB", "DC", "DD", "DE", "DF", "DG", "SP", "EP", "DZ", "NZ",
    "DUP", "3D", "ND", "FW", "UE", "NX", "NN", "IC", "IC2", "TV",
    "FL", "HS",
]

_CODE_EXTENSIONS = {
    '.py', '.r', '.rmd', '.qmd', '.jl', '.m', '.sh', '.bash',
    '.smk', '.nf', '.groovy', '.do', '.sas', '.ado',
    '.c', '.cpp', '.f', '.f90', '.sql', '.rs', '.go',
    '.java', '.js', '.ts', '.ipynb',
}

_DATA_EXTENSIONS = {
    '.csv', '.tsv', '.xlsx', '.xls', '.json', '.jsonl', '.ndjson',
    '.parquet', '.feather', '.arrow',
    '.rds', '.rda', '.rdata', '.dta', '.sav', '.por', '.zsav',
    '.sas7bdat', '.xpt', '.mat', '.pkl', '.npy', '.npz',
    '.hdf5', '.h5', '.nc', '.dif', '.gdt',
    '.shp', '.dbf', '.shx', '.prj', '.cpg', '.sbn', '.sbx',
    '.geojson', '.gpkg', '.kml', '.kmz',
}

_README_NAMES = {'readme.md', 'readme.txt', 'readme.rst', 'readme'}

_LICENCE_NAMES = {
    'licence', 'license', 'licence.md', 'license.md',
    'licence.txt', 'license.txt', 'copying', 'copying.md',
}

_CODEBOOK_FILENAMES = {
    'metadata.csv', 'metadata.xlsx', 'metadata.txt',
    'data_dictionary.csv', 'data_dictionary.xlsx',
    'codebook.csv', 'codebook.xlsx', 'codebook.txt',
    'variables.csv', 'variables.txt',
    'column_descriptions.csv', 'field_descriptions.csv',
}

_DEPENDENCY_FILES = {
    'requirements.txt', 'requirements_extra.txt',
    'environment.yml', 'environment.yaml',
    'pipfile', 'pipfile.lock', 'poetry.lock', 'setup.py',
    'pyproject.toml', 'setup.cfg', 'conda-lock.yml',
    'description', 'renv.lock', 'packrat.lock',
    'cargo.toml', 'cargo.lock', 'go.mod', 'go.sum',
    'package.json', 'package-lock.json', 'yarn.lock',
    'pom.xml', 'build.gradle', 'project.toml', 'manifest.toml',
}

_CHECKSUM_NAMES = {
    'checksums.md', 'checksums.txt', 'checksums.sha256',
    'md5sums.txt', 'sha256sums.txt', 'checksums',
}

_SESSION_INFO_PAT = re.compile(
    r'sessionInfo\(\)|sessioninfo::session_info\(\)|devtools::session_info\(\)',
    re.IGNORECASE,
)


def _detect_platform(zip_name: str) -> str:
    """Infer deposit platform from the zip filename."""
    if not zip_name:
        return "unknown"
    zn = zip_name.lower()
    if "dataverse_files" in zn or "dataverse" in zn:
        return "dataverse"
    if "zenodo" in zn:
        return "zenodo"
    if "figshare" in zn:
        return "figshare"
    if "dryad" in zn or "datadryad" in zn:
        return "dryad"
    if "osfstorage" in zn or re.search(r'(?<![a-z])osf(?![a-z])', zn):
        return "osf"
    if "mendeley" in zn:
        return "mendeley"
    return "unknown"


def _detect_language(all_files) -> str:
    """Return the dominant programming language based on code file extensions."""
    lang_exts = {
        'r':      {'.r', '.rmd', '.qmd'},
        'python': {'.py', '.ipynb'},
        'julia':  {'.jl'},
        'stata':  {'.do', '.ado'},
        'matlab': {'.m', '.mlx'},
        'sas':    {'.sas'},
        'shell':  {'.sh', '.bash'},
    }
    counts = {lang: 0 for lang in lang_exts}
    for f in all_files:
        ext = f.suffix.lower()
        for lang, exts in lang_exts.items():
            if ext in exts:
                counts[lang] += 1
    if not any(counts.values()):
        return "unknown"
    return max(counts, key=counts.get)


def _surface_features(repo_dir, all_files, findings) -> dict:
    """Compute surface-level boolean/numeric features for the log."""
    file_names_lower = {f.name.lower() for f in all_files}

    has_readme      = bool(file_names_lower & _README_NAMES)
    has_licence     = bool(file_names_lower & _LICENCE_NAMES)
    has_renv_lock   = 'renv.lock' in file_names_lower
    has_requirements = bool(file_names_lower & _DEPENDENCY_FILES)
    has_makefile    = bool({'makefile', 'gnumakefile'} & file_names_lower)
    has_citation_cff = 'citation.cff' in file_names_lower
    _CODEBOOK_STEM_KEYWORDS = (
        'codebook', 'data_dictionary', 'data-dictionary',
        'column_description', 'field_description',
    )
    has_codebook    = (
        bool(file_names_lower & _CODEBOOK_FILENAMES)
        or any(kw in name for kw in _CODEBOOK_STEM_KEYWORDS for name in file_names_lower)
    )
    has_checksums   = bool(file_names_lower & _CHECKSUM_NAMES)

    has_run_all = any(
        re.search(r'run.?all', f.name, re.IGNORECASE)
        for f in all_files
        if f.suffix.lower() in {'.sh', '.bash', '.py', '.r', '.bat', '.cmd', '.ps1'}
    )

    has_sessioninfo = False
    for f in all_files:
        if f.suffix.lower() in {'.r', '.rmd', '.qmd'}:
            try:
                content = f.read_text(encoding='utf-8', errors='ignore')
                if _SESSION_INFO_PAT.search(content):
                    has_sessioninfo = True
                    break
            except Exception:
                pass

    # Count evidence items from specific detector findings
    abs_paths_count = sum(
        len(fi.get('evidence', [])) for fi in findings if fi.get('mode') == 'C'
    )
    spaces_count = sum(
        len(fi.get('evidence', [])) for fi in findings if fi.get('mode') == 'BT'
    )
    missing_refs = sum(
        len(fi.get('evidence', [])) for fi in findings if fi.get('mode') == 'L'
    )

    prop_sw: list = []
    for fi in findings:
        if fi.get('mode') == 'SP':
            prop_sw.extend(fi.get('evidence', []))

    code_file_count = sum(1 for f in all_files if f.suffix.lower() in _CODE_EXTENSIONS)
    data_file_count = sum(1 for f in all_files if f.suffix.lower() in _DATA_EXTENSIONS)

    try:
        total_size_kb = round(
            sum(f.stat().st_size for f in all_files if f.is_file()) / 1024, 1
        )
    except Exception:
        total_size_kb = 0

    return {
        "has_readme":               has_readme,
        "has_licence":              has_licence,
        "has_renv_lock":            has_renv_lock,
        "has_requirements":         has_requirements,
        "has_makefile":             has_makefile,
        "has_run_all":              has_run_all,
        "has_sessioninfo":          has_sessioninfo,
        "has_checksums":            has_checksums,
        "has_codebook":             has_codebook,
        "has_citation_cff":         has_citation_cff,
        "absolute_paths_found":     abs_paths_count,
        "files_with_spaces":        spaces_count,
        "missing_referenced_files": missing_refs,
        "proprietary_software":     prop_sw,
        "code_file_count":          code_file_count,
        "data_file_count":          data_file_count,
        "total_size_kb":            total_size_kb,
    }


def generate_valichord_log(repo_name, repo_dir, all_files, findings, output_dir):
    """Write VALICHORD_LOG.json to output_dir.

    Internal instrument for Phase 0 data collection.
    Not a researcher deliverable — do not show in Generated Files table.
    Always written even if other output files fail.
    """
    try:
        # Only non-INFO findings contribute to fired/suppressed tracking
        non_info = [f for f in findings if f.get('severity') != 'INFO']
        fired_codes = sorted({f['mode'] for f in non_info})
        fired_set = set(fired_codes)
        suppressed_codes = [c for c in ALL_DETECTOR_CODES if c not in fired_set]

        critical    = sum(1 for f in non_info if f.get('severity') == 'CRITICAL')
        significant = sum(1 for f in non_info if f.get('severity') == 'SIGNIFICANT')
        low         = sum(1 for f in non_info if f.get('severity') == 'LOW CONFIDENCE')

        log = {
            "valichord_version":  VALICHORD_VERSION,
            "timestamp":          datetime.now().isoformat(timespec='seconds'),
            "repository_name":    repo_name,
            "file_count":         len(all_files),
            "platform_detected":  _detect_platform(repo_name),
            "language_detected":  _detect_language(all_files),
            "findings": {
                "critical":       critical,
                "significant":    significant,
                "low_confidence": low,
                "total":          critical + significant + low,
            },
            "detectors_fired":      fired_codes,
            "detectors_suppressed": suppressed_codes,
            "surface_features":     _surface_features(repo_dir, all_files, findings),
        }

        out = output_dir / 'VALICHORD_LOG.json'
        out.write_text(json.dumps(log, indent=2), encoding='utf-8')
        print("  → VALICHORD_LOG.json")
    except Exception as e:
        print(f"[ValiChord WARNING] Failed to write VALICHORD_LOG.json: {e}",
              file=sys.stderr)

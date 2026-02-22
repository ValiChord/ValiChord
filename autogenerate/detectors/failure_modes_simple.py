"""
ValiChord Auto-Generate
Simple (pattern-matching) failure mode detectors
Implements failure modes from ValiChord Specification v15
"""

import re
from pathlib import Path


# ── file classification helpers ──────────────────────────────────────────────

CODE_EXTENSIONS = {
    '.py', '.r', '.rmd', '.qmd', '.jl', '.m', '.sh', '.bash', '.smk',
    '.do', '.sas', '.ado', '.c', '.cpp', '.f', '.f90',
    '.sql', '.rs', '.go', '.java', '.js', '.ts'
}

NOTEBOOK_EXTENSIONS = {'.ipynb', '.mlx', '.rmd', '.qmd'}

DATA_EXTENSIONS = {
    '.csv', '.tsv', '.xlsx', '.xls', '.json', '.parquet',
    '.feather', '.rds', '.rdata', '.dta', '.sav', '.sas7bdat',
    '.mat', '.pkl', '.npy', '.npz', '.hdf5', '.h5', '.nc'
}

ENCRYPTED_EXTENSIONS = {'.gpg', '.enc', '.secret', '.age', '.asc'}

DEPENDENCY_FILES = {
    'requirements.txt', 'environment.yml', 'environment.yaml',
    'pipfile', 'pipfile.lock', 'poetry.lock', 'setup.py',
    'pyproject.toml', 'setup.cfg', 'conda-lock.yml',
    'description', 'renv.lock', 'packrat.lock',
    'cargo.toml', 'cargo.lock', 'go.mod', 'go.sum',
    'package.json', 'package-lock.json', 'yarn.lock',
    'pom.xml', 'build.gradle',
    'project.toml', 'manifest.toml',
    'manifest-v1.6.toml', 'manifest-v1.7.toml',
    'manifest-v1.8.toml', 'manifest-v1.9.toml',
    'manifest-v1.10.toml', 'manifest-v1.11.toml',

}

README_NAMES = {'readme.md', 'readme.txt', 'readme.rst', 'readme'}

LICENCE_NAMES = {
    'licence', 'license', 'licence.md', 'license.md',
    'licence.txt', 'license.txt'
}


def finding(mode, severity, title, detail, evidence=None):
    """Create a standardised finding dictionary."""
    return {
        'mode': mode,
        'severity': severity,
        'title': title,
        'detail': detail,
        'evidence': evidence or []
    }


def read_file_safe(path):
    """Read a file, trying utf-8 then latin-1. Return empty string on failure."""
    for encoding in ('utf-8', 'latin-1'):
        try:
            return path.read_text(encoding=encoding)
        except Exception:
            pass
    return ''


# ── individual detectors ─────────────────────────────────────────────────────

def detect_A_no_readme(repo_dir, all_files):
    """Failure Mode A: No README or inadequate README."""
    findings = []
    names = {f.name.lower() for f in all_files}

    root_readme = [f for f in all_files if f.name.lower() in README_NAMES and len(f.relative_to(repo_dir).parts) <= 2]
    if not root_readme:
        findings.append(finding(
            'A', 'CRITICAL',
            'No README file found',
            'Every research repository requires a README. '
            'README_DRAFT.md will be generated.',
            ['No README.md, README.txt, or README.rst found in repository']
        ))
    else:
        # check if readme is too short to be useful
        for f in all_files:
            if f.name.lower() in README_NAMES and len(f.relative_to(repo_dir).parts) <= 2:
                content = read_file_safe(f)
                if len(content.strip()) < 200:
                    findings.append(finding(
                        'A', 'SIGNIFICANT',
                        'README is present but appears inadequate',
                        f'README is only {len(content.strip())} characters. '
                        'A useful README requires study identification, '
                        'system requirements, installation instructions, '
                        'and execution instructions.',
                        [f'Evidence: {f.name} ({len(content.strip())} chars)']
                    ))
    return findings


def detect_B_no_dependencies(repo_dir, all_files):
    """Failure Mode B: Unpinned or missing dependencies."""
    findings = []
    names_lower = {f.name.lower() for f in all_files}

    code_files = [f for f in all_files
                  if f.suffix.lower() in CODE_EXTENSIONS]

    has_dep_file = bool(names_lower.intersection(DEPENDENCY_FILES))
    # R install scripts are valid dependency specifications
    if not has_dep_file:
        has_dep_file = any(
            bool(re.match(r'(install|setup).*\.r$', f.name.lower()))
            for f in all_files
        )
    # Also check for install_packages.R style names explicitly
    if not has_dep_file:
        has_dep_file = any(
            'install' in f.name.lower() and f.suffix.lower() == '.r'
            for f in all_files
        )
    # Modern Pluto notebooks embed deps as PLUTO_PROJECT_TOML_CONTENTS — treat as dep file
    if not has_dep_file:
        for f in all_files:
            if f.suffix.lower() == '.jl':
                try:
                    if 'PLUTO_PROJECT_TOML_CONTENTS' in f.read_text(encoding='utf-8', errors='ignore'):
                        has_dep_file = True
                        break
                except Exception:
                    pass
    has_code = bool(code_files)

    has_draft_only = "requirements_draft.txt" in names_lower and not has_dep_file
    if has_code and not has_dep_file and not has_draft_only:
        findings.append(finding(
            'B', 'CRITICAL',
            'No dependency specification found',
            'Code files are present but no dependency file was found. '
            'A requirements_DRAFT.txt will be generated from import '
            'statements with all versions marked UNKNOWN.',
            [f'Code files found: {len(code_files)}',
             'No requirements.txt, environment.yml, renv.lock, '
             'or equivalent found']
        ))
    elif has_code and has_draft_only:
        # prior run left a requirements_DRAFT.txt — check if versions are pinned
        draft_file = next(f for f in all_files if f.name.lower() == "requirements_draft.txt")
        draft_content = read_file_safe(draft_file)
        has_pinned = any("==" in l for l in draft_content.splitlines() if l.strip() and not l.strip().startswith("#"))
        findings.append(finding(
            'B', 'SIGNIFICANT',
            'requirements_DRAFT.txt found from prior run but not yet finalised',
            'A requirements_DRAFT.txt exists but has not been completed and renamed '
            'to requirements.txt. Pin all version numbers and rename before deposit.',
            ['Action: complete version numbers in requirements_DRAFT.txt and rename to requirements.txt']
        ))
    elif has_dep_file:
        # check for unpinned dependencies in requirements.txt
        for f in all_files:
            if f.name.lower() == 'requirements.txt':
                content = read_file_safe(f)
                unpinned = []
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '==' not in line and '>=' not in line \
                                and '<=' not in line and '~=' not in line:
                            if not line.startswith('-'):
                                unpinned.append(line)
                if unpinned:
                    findings.append(finding(
                        'B', 'SIGNIFICANT',
                        'requirements.txt contains unpinned dependencies',
                        'Package names without exact version numbers '
                        'will install the latest version, which may '
                        'differ from what was used at publication.',
                        [f'Unpinned: {", ".join(unpinned[:10])}']
                        + (['...and more' ]if len(unpinned) > 10 else [])
                    ))
    return findings


def detect_C_absolute_paths(repo_dir, all_files):
    """Failure Mode C: Absolute paths that only work on researcher machine."""
    findings = []
    code_files = [f for f in all_files
                  if f.suffix.lower() in CODE_EXTENSIONS]

    # Also scan Jupyter notebook cell sources
    notebook_sources = []
    import json as _json
    for nb in all_files:
        if nb.suffix.lower() == '.ipynb':
            try:
                data = _json.loads(nb.read_text(encoding='utf-8', errors='ignore'))
                for cell in data.get('cells', []):
                    src = ''.join(cell.get('source', []))
                    if src:
                        notebook_sources.append((nb, src))
            except Exception:
                pass

    abs_pattern = re.compile(
        r'(/Users/[a-zA-Z][a-zA-Z0-9_\-]{1,}/)'
        r'|(/home/[a-zA-Z][a-zA-Z0-9_\-]{1,}/)'
        r'|(/root/[a-zA-Z])'
        r'|([A-Z]:\\[A-Za-z][A-Za-z0-9_\- ]{1,}\\)'
        r'|([A-Z]:/[A-Za-z][A-Za-z0-9_\- ]{1,}/)'
    )

    for f in code_files:
        content_f = read_file_safe(f)
        for i, line in enumerate(content_f.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            if stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            if abs_pattern.search(line):
                snippet = stripped[:80]
                findings.append(finding(
                    'C', 'SIGNIFICANT',
                    f'Absolute path detected in {f.name}',
                    'Absolute paths break reproducibility — they only '
                    "work on the researcher's machine. A corrected "
                    "copy with relative paths will be generated in "
                    '/proposed_corrections/.',
                    [f'Evidence: {f.name} line {i}: {snippet}']
                ))
    # Scan notebook cell sources for absolute paths
    for nb, src in notebook_sources:
        for i, line in enumerate(src.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            if abs_pattern.search(line):
                snippet = stripped[:80]
                findings.append(finding(
                    'C', 'SIGNIFICANT',
                    f'Absolute path detected in notebook cell: {nb.name}',
                    'Absolute paths in notebook cells break reproducibility — '
                    "they only work on the researcher's machine.",
                    [f'Evidence: {nb.name} cell line {i}: {snippet}']
                ))
    return findings


def detect_D_no_entry_point(repo_dir, all_files):
    """Failure Mode D: No execution order or entry point."""
    findings = []
    names_lower = {f.name.lower() for f in all_files}

    has_run_all = any('run_all' in n or 'run_all' in n
                      for n in names_lower
                      if n.endswith('.sh') or n.endswith('.py'))

    has_makefile = 'makefile' in names_lower

    has_numbered = any(
        re.match(r'^0*[0-9]+[_\-]', f.name)
        for f in all_files
        if f.suffix.lower() in CODE_EXTENSIONS
    )

    code_count = sum(
        1 for f in all_files
        if f.suffix.lower() in CODE_EXTENSIONS
    )

    if code_count > 1 and not has_run_all \
            and not has_makefile and not has_numbered:
        findings.append(finding(
            'D', 'SIGNIFICANT',
            'No clear execution entry point or order',
            f'{code_count} code files found but no run_all script, '
            'Makefile, or numbered script sequence detected. '
            'A QUICKSTART_DRAFT.md will be generated.',
            [f'Code files: {code_count}',
             'No run_all.sh, Makefile, or 01_/02_/03_ numbering found']
        ))

    return findings


def detect_N_no_licence(repo_dir, all_files):
    """Failure Mode N: No licence file."""
    findings = []
    names_lower = {f.name.lower() for f in all_files}

    if not names_lower.intersection(LICENCE_NAMES):
        findings.append(finding(
            'N', 'SIGNIFICANT',
            'No licence file found',
            'Without a licence, validators have no legal clarity '
            'on whether they can use, reproduce, or share this work. '
            'A LICENCE_DRAFT.txt will be generated.',
            ['No LICENCE, LICENSE, licence.md, or license.txt found']
        ))

    return findings


def detect_Z_no_commit_hash(repo_dir, all_files):
    """Failure Mode Z: No commit hash or version tag in README."""
    findings = []

    for f in all_files:
        if f.name.lower() in README_NAMES and len(f.relative_to(repo_dir).parts) <= 2:
            content = read_file_safe(f)
            # look for commit hash (40 hex chars) or version tag
            has_hash = bool(re.search(r'\b[0-9a-f]{40}\b', content))
            has_tag = bool(re.search(
                r'v\d+\.\d+[\.\d]*|version\s+\d+\.\d+',
                content, re.IGNORECASE
            ))
            if not has_hash and not has_tag:
                findings.append(finding(
                    'Z', 'SIGNIFICANT',
                    'No commit hash or version tag in README',
                    'Without a commit hash or version tag, validators '
                    'cannot confirm they have the exact version of code '
                    'used to produce the published results.',
                    [f'Evidence: {f.name} — no 40-char hex hash or '
                     'version tag found']
                ))

    return findings


def detect_BJ_encrypted_files(repo_dir, all_files):
    """Failure Mode BJ: Encrypted or high-entropy data files."""
    findings = []

    for f in all_files:
        if f.suffix.lower() in ENCRYPTED_EXTENSIONS:
            findings.append(finding(
                'BJ', 'CRITICAL',
                f'Encrypted file detected: {f.name}',
                'This file appears to be encrypted and cannot be used '
                'by validators without a decryption key that is not '
                'present in this repository.',
                [f'Evidence: {f.name} has encryption extension '
                 f'{f.suffix}']
            ))

        # check for git-crypt magic bytes in data-like files
        elif f.suffix.lower() in DATA_EXTENSIONS:
            try:
                header = f.read_bytes()[:16]
                if header[:10] == b'\x00GITCRYPT':
                    findings.append(finding(
                        'BJ', 'CRITICAL',
                        f'Git-crypt encrypted file: {f.name}',
                        'This file is encrypted with git-crypt. '
                        'Validators cannot read it without the '
                        'symmetric key.',
                        [f'Evidence: {f.name} contains git-crypt '
                         f'magic bytes']
                    ))
            except Exception:
                pass

    return findings


def detect_BL_git_history_dependency(repo_dir, all_files):
    """Failure Mode BL: Shallow clone / missing git history dependency."""
    findings = []

    for f in all_files:
        if f.name.lower() in {'setup.py', 'setup.cfg', 'pyproject.toml'}:
            content = read_file_safe(f)
            if 'setuptools_scm' in content or 'setuptools-scm' in content:
                findings.append(finding(
                    'BL', 'CRITICAL',
                    f'setuptools_scm detected in {f.name}',
                    'This package uses git history to determine its '
                    'version number. When downloaded as a ZIP from '
                    'Zenodo, Figshare, or GitHub, the .git directory '
                    'is absent and the package will fail to import. '
                    'Pin the version explicitly: __version__ = "1.0.0"',
                    [f'Evidence: {f.name} — setuptools_scm reference']
                ))
            if 'versioneer' in content:
                findings.append(finding(
                    'BL', 'CRITICAL',
                    f'versioneer detected in {f.name}',
                    'versioneer uses git history to determine version '
                    'numbers. ZIP downloads strip the .git directory '
                    'and this will fail immediately.',
                    [f'Evidence: {f.name} — versioneer reference']
                ))

        # check shell scripts and Makefiles for git describe
        if f.suffix.lower() in {'.sh', '.bash', ''} \
                or f.name.lower() == 'makefile':
            content = read_file_safe(f)
            if 'git describe' in content or 'git log' in content:
                findings.append(finding(
                    'BL', 'SIGNIFICANT',
                    f'git describe/log call in {f.name}',
                    'This script calls git commands that require '
                    '.git history. ZIP downloads will not have this '
                    'and the script will fail.',
                    [f'Evidence: {f.name} — git describe or git log']
                ))

    return findings


def detect_BK_system_clock(repo_dir, all_files):
    """Failure Mode BK: System clock dependency."""
    findings = []
    code_files = [f for f in all_files
                  if f.suffix.lower() in CODE_EXTENSIONS]

    clock_in_filename = re.compile(
        r'(datetime\.now|datetime\.today|time\.time)\s*\(\s*\)'
        r'[^\n]{0,50}(f["\']|format|str|%)'
    )
    clock_as_seed = re.compile(
        r'(seed|random)\s*\([^\n]{0,80}(datetime\.now|time\.time)'
    )

    clock_in_logic = re.compile(
        r'(datetime\.now|datetime\.today|time\.time)\s*\(\s*\)'
    )
    clock_in_logic = re.compile(
        r'(datetime\.now|datetime\.today|time\.time)\s*\(\s*\)'
    )
    clock_in_logic = re.compile(
        r'(datetime\.now|datetime\.today|time\.time)\s*\(\s*\)'
    )
    for f in code_files:
        src = read_file_safe(f)
        if clock_in_filename.search(src):
            findings.append(finding(
                'BK', 'SIGNIFICANT',
                f'System clock used in filename generation: {f.name}',
                'Output filenames derived from datetime.now() or '
                'time.time() will differ between runs.',
                [f'Evidence: {f.name} - clock-based filename pattern']
            ))
        if clock_as_seed.search(src):
            findings.append(finding(
                'BK', 'SIGNIFICANT',
                f'System clock used as random seed: {f.name}',
                'Seeds derived from the system clock change every run.',
                [f'Evidence: {f.name} - clock-based seed pattern']
            ))
        elif clock_in_logic.search(src) and not clock_in_filename.search(src):
            findings.append(finding(
                'BK', 'SIGNIFICANT',
                f'System clock used in conditional logic: {f.name}',
                'Code behaviour depends on current date or time. '
                'Results may differ if run in a different month or year.',
                [f'Evidence: {f.name} - clock-based logic pattern']
            ))
    return findings


def detect_W_git_lfs(repo_dir, all_files):
    """Failure Mode W: Git LFS pointer files."""
    findings = []

    for f in all_files:
        if f.suffix.lower() in DATA_EXTENSIONS \
                or f.suffix.lower() in {'.png', '.jpg', '.pdf'}:
            try:
                header = f.read_bytes()[:128].decode('utf-8', errors='ignore')
                if 'version https://git-lfs.github.com' in header:
                    findings.append(finding(
                        'W', 'CRITICAL',
                        f'Git LFS pointer file: {f.name}',
                        'This file is a Git LFS pointer, not the '
                        'actual data. The real file must be retrieved '
                        'using git lfs pull. Validators downloading '
                        'this repository as a ZIP will get the pointer '
                        'file only.',
                        [f'Evidence: {f.name} — Git LFS pointer header']
                    ))
            except Exception:
                pass

    return findings


# ── main entry point ─────────────────────────────────────────────────────────

def run_simple_detectors(repo_dir, all_files):
    """Run all simple pattern-matching detectors. Return list of findings."""

    print("  [A]  README check...")
    print("  [B]  Dependency check...")
    print("  [C]  Absolute path check...")
    print("  [D]  Entry point check...")
    print("  [N]  Licence check...")
    print("  [Z]  Commit hash check...")
    print("  [W]  Git LFS check...")
    print("  [BJ] Encrypted file check...")
    print("  [BK] System clock check...")
    print("  [BL] Git history dependency check...")
    print("  [F]  Random seed check...")
    print("  [U]  Environment variable check...")
    all_findings = []
    # prior run detection
    prior_report = next((f for f in all_files if f.name.lower() == "cleaning_report.md"), None)
    if prior_report:
        try:
            prior_content = prior_report.read_text(encoding="utf-8", errors="ignore")
            import re as _re
            version_match = _re.search(r"v(\d+\.\d+\.\d+)", prior_content)
            date_match = _re.search(r"(\d{4}-\d{2}-\d{2})", prior_content)
            version_str = version_match.group(0) if version_match else "unknown version"
            date_str = date_match.group(0) if date_match else "unknown date"
            all_findings.append(finding(
                "BQ", "SIGNIFICANT",
                f"Prior ValiChord report detected ({version_str}, {date_str})",
                "A previous ValiChord cleaning report was found in this repository. "
                "This appears to be a re-run. Review prior findings before actioning new ones.",
                [f"Prior report: {prior_report.name} ({version_str}, {date_str})"]
            ))
        except Exception:
            pass
    all_findings += detect_A_no_readme(repo_dir, all_files)
    all_findings += detect_B_no_dependencies(repo_dir, all_files)
    all_findings += detect_C_absolute_paths(repo_dir, all_files)
    all_findings += detect_D_no_entry_point(repo_dir, all_files)
    all_findings += detect_N_no_licence(repo_dir, all_files)
    all_findings += detect_Z_no_commit_hash(repo_dir, all_files)
    all_findings += detect_W_git_lfs(repo_dir, all_files)
    all_findings += detect_BJ_encrypted_files(repo_dir, all_files)
    all_findings += detect_BK_system_clock(repo_dir, all_files)
    all_findings += detect_BL_git_history_dependency(repo_dir, all_files)
    print("  [G]  README adequacy check...")
    all_findings += detect_G_inadequate_readme(repo_dir, all_files)
    print("  [H]  Hardcoded versions check...")
    all_findings += detect_H_hardcoded_versions(repo_dir, all_files)
    print("  [K]  Compute environment check...")
    all_findings += detect_K_compute_environment(repo_dir, all_files)
    print("  [P]  Pre-registration check...")
    all_findings += detect_P_preregistration(repo_dir, all_files)
    print("  [V]  Virtual environment check...")
    all_findings += detect_V_virtual_environment(repo_dir, all_files, all_findings)
    print("  [I]  Intermediate files check...")
    all_findings += detect_I_intermediate_files(repo_dir, all_files)
    print("  [J]  Notebook execution order check...")
    all_findings += detect_J_notebook_order(repo_dir, all_files)
    print("  [M]  Python version check...")
    all_findings += detect_M_python_version_conflict(repo_dir, all_files)
    print("  [L]  Missing file references check...")
    all_findings += detect_L_large_files_missing(repo_dir, all_files)
    print("  [O]  Committed outputs check...")
    all_findings += detect_O_output_not_committed(repo_dir, all_files)
    print("  [Q]  Configuration files check...")
    all_findings += detect_Q_config_files(repo_dir, all_files)
    print("  [R]  Statistical assumptions check...")
    all_findings += detect_R_statistical_tests_undocumented(repo_dir, all_files)
    print("  [S]  Software citations check...")
    all_findings += detect_S_software_citations_missing(repo_dir, all_files)
    print("  [T]  Test coverage check...")
    all_findings += detect_T_test_coverage(repo_dir, all_files)
    print("  [X]  Containerisation check...")
    all_findings += detect_X_no_container(repo_dir, all_files)
    print("  [Y]  Data source check...")
    all_findings += detect_Y_data_source_missing(repo_dir, all_files)
    print("  [AA] Figure reproducibility check...")
    all_findings += detect_AA_figure_reproducibility(repo_dir, all_files)
    print("  [AB] Parallel determinism check...")
    all_findings += detect_AB_parallel_no_seed(repo_dir, all_files)
    print("  [AC] Deprecated functions check...")
    all_findings += detect_AC_deprecated_functions(repo_dir, all_files)
    print("  [AD] Gitignore check...")
    all_findings += detect_AD_missing_gitignore(repo_dir, all_files)
    print("  [AE] Mixed languages check...")
    all_findings += detect_AE_mixed_languages(repo_dir, all_files)
    print("  [AF] Output format check...")
    all_findings += detect_AF_output_format_undocumented(repo_dir, all_files)
    print("  [AG] Hardcoded credentials check...")
    all_findings += detect_AG_api_keys_in_code(repo_dir, all_files)
    print("  [AH] Changelog check...")
    all_findings += detect_AH_no_changelog(repo_dir, all_files)
    print("  [AI] Print debugging check...")
    all_findings += detect_AI_print_debugging(repo_dir, all_files)
    print("  [AJ] Magic numbers check...")
    all_findings += detect_AJ_hardcoded_sample_size(repo_dir, all_files)
    print("  [AK] External URLs check...")
    all_findings += detect_AK_external_urls(repo_dir, all_files)
    print("  [AL] Data privacy check...")
    all_findings += detect_AL_data_privacy(repo_dir, all_files)
    print("  [AM] Pipeline automation check...")
    all_findings += detect_AM_makefile_missing(repo_dir, all_files)
    print("  [AN] Commented code check...")
    all_findings += detect_AN_commented_code(repo_dir, all_files)
    print("  [AO] R-specific check...")
    all_findings += detect_AO_r_specific_issues(repo_dir, all_files)
    print("  [AP] Stata-specific check...")
    all_findings += detect_AP_stata_specific(repo_dir, all_files)
    print("  [AQ] Model files check...")
    all_findings += detect_AQ_large_model_files(repo_dir, all_files)
    print("  [AR] Encoding check...")
    all_findings += detect_AR_encoding_issues(repo_dir, all_files)
    print("  [AS] Network calls check...")
    all_findings += detect_AS_network_calls(repo_dir, all_files)
    print("  [AT] Database dependency check...")
    all_findings += detect_AT_database_dependency(repo_dir, all_files)
    print("  [AU] Cloud storage check...")
    all_findings += detect_AU_cloud_storage(repo_dir, all_files)
    print("  [AV] Hardcoded dates check...")
    all_findings += detect_AV_hardcoded_dates(repo_dir, all_files)
    print("  [AW] DOI check...")
    all_findings += detect_AW_missing_doi(repo_dir, all_files)
    print("  [AX] Container check...")
    all_findings += detect_AX_container_not_tested(repo_dir, all_files)
    print("  [AY] Workflow file check...")
    all_findings += detect_AY_workflow_file(repo_dir, all_files)
    print("  [AZ] Figure format check...")
    all_findings += detect_AZ_figure_format(repo_dir, all_files)
    print("  [BA] Checksums check...")
    all_findings += detect_BA_missing_checksums(repo_dir, all_files)
    print("  [BB] Script permissions check...")
    all_findings += detect_BB_script_permissions(repo_dir, all_files)
    print("  [BC] Line endings check...")
    all_findings += detect_BC_mixed_line_endings(repo_dir, all_files)
    print("  [BD] Contact info check...")
    all_findings += detect_BD_missing_contact(repo_dir, all_files)
    print("  [BE] Compiled files check...")
    all_findings += detect_BE_pyc_files(repo_dir, all_files)
    print("  [BF] Notebook outputs check...")
    all_findings += detect_BF_notebook_outputs_missing(repo_dir, all_files)
    print("  [BG] Funding acknowledgement check...")
    all_findings += detect_BG_missing_acknowledgements(repo_dir, all_files)
    print("  [BH] Archive files check...")
    all_findings += detect_BH_zip_bomb_risk(repo_dir, all_files)
    print("  [BI] Unicode paths check...")
    all_findings += detect_BI_unicode_in_paths(repo_dir, all_files)
    all_findings += detect_BM_citation_cff(repo_dir, all_files)
    all_findings += detect_BO_codebook_reference_mismatch(repo_dir, all_files)
    all_findings += detect_BP_licence_in_readme_only(repo_dir, all_files)
    all_findings += detect_BR_credentials_exposed(repo_dir, all_files)
    all_findings += detect_BS_archive_code_present(repo_dir, all_files)
    all_findings += detect_BT_spaces_in_filenames(repo_dir, all_files)
    print("  [BU] Conda channel priority check...")
    all_findings += detect_BU_conda_channel_priority(repo_dir, all_files)
    print("  [BV] Shell error handling check...")
    all_findings += detect_BV_shell_no_set_e(repo_dir, all_files)
    print("  [BX] Pluto manifest check...")
    all_findings += detect_BX_pluto_empty_manifest(repo_dir, all_files)
    print("  [BY] Julia manifest check...")
    all_findings += detect_BY_julia_missing_manifest(repo_dir, all_files)
    print("  [BZ] MATLAB v7.3 format check...")
    all_findings += detect_BZ_matlab_v73_format(repo_dir, all_files)
    print("  [CA] README script reference check...")
    all_findings += detect_CA_readme_script_missing(repo_dir, all_files)
    print("  [CB] Snakemake environment isolation check...")
    all_findings += detect_CB_snakemake_no_env_isolation(repo_dir, all_files)
    print("  [CD] Dockerfile build order check...")
    all_findings += detect_CD_dockerfile_run_before_copy(repo_dir, all_files)
    print("  [CC] External tool versions check...")
    all_findings += detect_CC_undocumented_external_tools(repo_dir, all_files)
    print("  [CE] Unpinned GitHub R packages check...")
    all_findings += detect_CE_unpinned_github_packages(repo_dir, all_files)
    print("  [CR] CRLF line endings check...")
    all_findings += detect_CR_crlf_line_endings(repo_dir, all_files)
    print("  [CF] Notebook committed outputs check...")
    all_findings += detect_CF_notebook_outputs_committed(repo_dir, all_files)
    print("  [BN] Codebook reference check...")
    all_findings += detect_BN_codebook_reference_mismatch(repo_dir, all_files)

    print("  [E]  Data documentation check...")
    all_findings += detect_E_missing_data_documentation(repo_dir, all_files)
    all_findings += detect_F_missing_seeds(repo_dir, all_files)
    all_findings += detect_U_environment_variables(repo_dir, all_files)
    return all_findings

def detect_F_missing_seeds(repo_dir, all_files):
    """Failure Mode F: Undocumented stochasticity / missing random seeds."""
    findings = []
    code_files = [f for f in all_files
                  if f.suffix.lower() in CODE_EXTENSIONS]

    rng_imports = {
        'numpy': 'np.random.seed()',
        'random': 'random.seed()',
        'torch': 'torch.manual_seed()',
        'tensorflow': 'tf.random.set_seed()',
        'sklearn': 'random_state= parameter',
        # scipy removed — scipy.stats functions are deterministic; only scipy.stats.distributions random sampling needs seeding
        'lightgbm': 'random_state= parameter',
        'xgboost': 'seed= parameter',
    }

    seed_patterns = re.compile(
        r'(random\.seed|np\.random\.seed|numpy\.random\.seed'
        r'|torch\.manual_seed|tf\.random\.set_seed'
        r'|random_state\s*='
        r'|jax\.random\.PRNGKey|jax\.random\.key'
        r'|set_seed\s*\('
        r'|default_rng\s*\()',
        re.IGNORECASE
    )

    jax_import_pattern = re.compile(r'import jax|from jax')
    jax_key_pattern = re.compile(
        r'jax\.random\.PRNGKey|jax\.random\.key\s*\('
    )

    for f in code_files:
        if f.suffix.lower() not in {'.py', '.r', '.rmd', '.jl'}:
            continue
        content = read_file_safe(f)
        imported_rngs = []
        for lib, seed_fn in rng_imports.items():
            if re.search(rf'\bimport\s+{lib}\b|from\s+{lib}\s+import'
                         rf'|library\s*\(\s*["\']?{lib}',
                         content, re.IGNORECASE):
                # numpy only stochastic if np.random actually called
                import re as _re
                if lib == 'numpy' and not _re.search(r'np\.random\.|numpy\.random\.', content):
                    continue
                imported_rngs.append((lib, seed_fn))
        if imported_rngs and not seed_patterns.search(content):
            libs = ', '.join(lib for lib, _ in imported_rngs)
            findings.append(finding(
                'F', 'SIGNIFICANT',
                f'No random seed set in {f.name}',
                f'This file imports stochastic libraries ({libs}) '
                f'but no random seed was detected. Results will '
                f'differ between runs.',
                [f'Evidence: {f.name} imports {libs} without seed']
            ))
        if jax_import_pattern.search(content):
            if not jax_key_pattern.search(content):
                findings.append(finding(
                    'F', 'SIGNIFICANT',
                    f'JAX imported without PRNG key management: {f.name}',
                    'JAX uses a separate random number system from numpy. '
                    'np.random.seed() does NOT control JAX randomness. '
                    'Use jax.random.PRNGKey() or jax.random.key().',
                    [f'Evidence: {f.name} imports jax without PRNGKey']
                ))
    return findings


def detect_U_environment_variables(repo_dir, all_files):
    """Failure Mode U: Undocumented environment variables and credentials."""
    findings = []
    code_files = [f for f in all_files
                  if f.suffix.lower() in CODE_EXTENSIONS]

    credential_patterns = re.compile(
        r'os\.environ\.get\s*\(\s*["\']([^"\']*'
        r'(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|PWD|AUTH|API_KEY)'
        r'[^"\']*)["\']'
        r'|os\.getenv\s*\(\s*["\']([^"\']*'
        r'(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|PWD|AUTH|API_KEY)'
        r'[^"\']*)["\']',
        re.IGNORECASE
    )

    config_patterns = re.compile(
        r'os\.environ\.get\s*\(\s*["\']([^"\']+)["\']'
        r'|os\.getenv\s*\(\s*["\']([^"\']+)["\']'
        r'|os\.environ\s*\[\s*["\']([^"\']+)["\']',
        re.IGNORECASE
    )

    has_env_example = any(
        f.name.lower() in {'.env.example', '.env.sample', '.env.template'}
        for f in all_files
    )

    found_credentials = set()
    found_config = set()

    for f in code_files:
        content = read_file_safe(f)
        for match in credential_patterns.finditer(content):
            var_name = match.group(1) or match.group(2)
            if var_name:
                found_credentials.add(var_name.upper())
        for match in config_patterns.finditer(content):
            var_name = (match.group(1) or match.group(2)
                        or match.group(3))
            if var_name:
                found_config.add(var_name.upper())

    found_config -= found_credentials

    if found_credentials:
        findings.append(finding(
            'U', 'CRITICAL',
            'Credential environment variables detected',
            'This repository uses environment variables that appear '
            'to be credentials. Document in .env.example with '
            'placeholder values only.',
            [f'Variables: {", ".join(sorted(found_credentials))}']
        ))

    if found_config and not has_env_example:
        findings.append(finding(
            'U', 'SIGNIFICANT',
            'Environment variables used but no .env.example found',
            'Validators cannot know what variables to set. '
            'A .env.example will be generated.',
            [f'Variables: {", ".join(sorted(list(found_config)[:10]))}']
        ))

    return findings


def detect_E_missing_data_documentation(repo_dir, all_files):
    """Failure Mode E: Data files present but no data documentation."""
    findings = []

    data_extensions = {
        '.csv', '.tsv', '.xlsx', '.xls', '.parquet', '.rds',
        '.rdata', '.dta', '.sav', '.mat', '.pkl', '.npy',
        '.npz', '.hdf5', '.h5', '.feather', '.arrow', '.json',
        '.xml', '.db', '.sqlite'
    }

    data_files = [
        f for f in all_files
        if f.suffix.lower() in data_extensions
    ]

    if not data_files:
        return findings

    doc_indicators = [
        'codebook', 'data_dictionary', 'data-dictionary',
        'metadata', 'data_readme', 'data-readme',
        'variables', 'schema'
    ]

    all_names_lower = [f.name.lower() for f in all_files]
    all_stems_lower = [f.stem.lower() for f in all_files]

    has_data_doc = any(
        any(ind in name for ind in doc_indicators)
        for name in all_names_lower + all_stems_lower
    )

    readme_mentions_data = False
    for f in all_files:
        if f.name.lower() in {'readme.md', 'readme.txt', 'readme.rst'}:
            try:
                content = f.read_text(encoding='utf-8', errors='ignore')
                content_lower = content.lower()
                if any(phrase in content_lower for phrase in [
                    'data source', 'dataset', 'data description',
                    'variables', 'data dictionary', 'codebook',
                    'data collection', 'data format'
                ]):
                    readme_mentions_data = True
            except Exception:
                pass

    if not has_data_doc and not readme_mentions_data:
        data_names = [f.name for f in data_files[:5]]
        extra = f' (and {len(data_files)-5} more)' if len(data_files) > 5 else ''
        findings.append(finding(
            'E', 'SIGNIFICANT',
            f'{len(data_files)} data file(s) present but no data documentation found',
            'Data files are present but no codebook, data dictionary, '
            'or data description was found. Validators cannot assess '
            'whether the data matches what the paper describes.',
            [f'Data files: {", ".join(data_names)}{extra}',
             'Missing: codebook, data dictionary, or README data section']
        ))
    elif data_files and not has_data_doc:
        findings.append(finding(
            'E', 'LOW CONFIDENCE',
            'No dedicated data documentation file found',
            'Data files are present but no dedicated codebook or '
            'data dictionary file was found.',
            [f'Data files found: {len(data_files)}']
        ))

    return findings


def detect_G_inadequate_readme(repo_dir, all_files):
    """Failure Mode G: README exists but missing critical sections."""
    findings = []
    # skip installation/execution checks for data-only repos
    has_code = any(f.suffix.lower() in CODE_EXTENSIONS or f.name == 'Snakefile' for f in all_files)

    readme_file = None
    for f in all_files:
        if f.name.lower() in {'readme.md', 'readme.txt', 'readme.rst'} and len(f.relative_to(repo_dir).parts) <= 2:
            readme_file = f
            break

    if not readme_file:
        return findings  # A detector handles missing README

    try:
        content = readme_file.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return findings

    content_lower = content.lower()

    # sections we expect in a reproducible research README
    if has_code:
        required_sections = {
            'installation': [
                'install', 'setup', 'getting started', 'requirements',
                'dependencies', 'environment', 'pip install', 'conda'
            ],
            'execution': [
                'how to run', 'usage', 'running', 'execute', 'run the',
                'to reproduce', 'reproduc', 'quickstart', 'quick start',
                'steps to', 'instructions'
            ],
            'expected outputs': [
                'expected output', 'results', 'figures', 'tables',
                'what to expect', 'output files', 'produces',
                'generates', 'successful reproduction', 'success'
            ],
            'data': [
                'data', 'dataset', 'download', 'source', 'input'
            ],
        }
    else:
        required_sections = {
            'data description': [
                'data', 'dataset', 'variable', 'column', 'field'
            ],
            'access conditions': [
                'access', 'download', 'licence', 'license', 'embargo',
                'available', 'request'
            ],
            'collection methodology': [
                'collected', 'survey', 'method', 'source', 'provenance'
            ],
        }

    missing = []
    for section, keywords in required_sections.items():
        if not any(kw in content_lower for kw in keywords):
            missing.append(section)

    if len(missing) >= 3:
        findings.append(finding(
            'G', 'LOW CONFIDENCE',
            f'README is missing critical sections: {", ".join(missing)}',
            'A README exists but is missing sections that validators '
            'need to reproduce the work. Without installation '
            'instructions, execution steps, and expected outputs, '
            'validators cannot proceed systematically.',
            [f'Missing sections: {", ".join(missing)}',
             f'README length: {len(content)} characters']
        ))
    elif len(missing) >= 1:
        findings.append(finding(
            'G', 'LOW CONFIDENCE',
            f'README may be missing sections: {", ".join(missing)}',
            'The README appears to be missing some recommended '
            'sections. This may be intentional if the information '
            'is elsewhere, but validators may struggle to find it.',
            [f'Possibly missing: {", ".join(missing)}']
        ))

    # check for definition of successful reproduction
    success_indicators = [
        'successful reproduction', 'reproduction is successful',
        'expected result', 'should produce', 'should see',
        'tolerance', 'within', 'match', 'identical'
    ]
    has_success_definition = any(
        ind in content_lower for ind in success_indicators
    )

    if not has_success_definition and len(content) > 200:
        findings.append(finding(
            'G', 'SIGNIFICANT',
            'README does not define what successful reproduction looks like',
            'Without a definition of successful reproduction, '
            'validators cannot determine whether their results '
            'match the original. This is the single most important '
            'missing element in most research READMEs. '
            'What should a validator see when they have succeeded?',
            ['Missing: definition of successful reproduction',
             'Required: expected values, tolerance bands, or '
             'explicit comparison criteria']
        ))

    # If SIGNIFICANT fires, suppress LOW CONFIDENCE to avoid double-reporting [G]
    if any(f['severity'] == 'SIGNIFICANT' for f in findings):
        findings = [f for f in findings if f['severity'] != 'LOW CONFIDENCE']

    return findings


def detect_H_hardcoded_versions(repo_dir, all_files):
    """Failure Mode H: Version numbers hardcoded in code not requirements."""
    findings = []
    code_files = [f for f in all_files
                  if f.suffix.lower() in CODE_EXTENSIONS]

    version_in_code = re.compile(
        r'(pandas|numpy|scipy|sklearn|matplotlib|torch|tensorflow'
        r'|keras|statsmodels|seaborn|plotly|xgboost|lightgbm'
        r'|transformers|datasets|huggingface)[=><!\s]+[\d]+\.[\d]',
        re.IGNORECASE
    )

    for f in code_files:
        content = read_file_safe(f)
        matches = version_in_code.findall(content)
        if matches:
            findings.append(finding(
                'H', 'LOW CONFIDENCE',
                f'Version constraint hardcoded in {f.name}',
                'Version constraints found inside code rather than '
                'in a dependency specification file. This can cause '
                'conflicts and makes dependency management harder. '
                'Move version constraints to requirements.txt or '
                'equivalent.',
                [f'Evidence: {f.name} — {", ".join(set(matches))[:80]}']
            ))
    return findings


def detect_K_compute_environment(repo_dir, all_files):
    """Failure Mode K: Compute environment not documented."""
    findings = []
    # skip for data-only repos
    if not any(f.suffix.lower() in CODE_EXTENSIONS for f in all_files):
        return findings

    readme_file = None
    for f in all_files:
        if f.name.lower() in {'readme.md', 'readme.txt', 'readme.rst'}:
            readme_file = f
            break

    if not readme_file:
        return findings

    try:
        content = readme_file.read_text(
            encoding='utf-8', errors='ignore'
        ).lower()
    except Exception:
        return findings

    # check for compute environment documentation
    os_indicators = [
        'ubuntu', 'windows', 'macos', 'linux', 'operating system',
        'os:', 'tested on', 'platform'
    ]
    ram_indicators = [
        'ram', 'memory', 'gb', 'gigabyte', 'minimum'
    ]
    gpu_indicators = [
        'gpu', 'cuda', 'nvidia', 'a100', 'v100', 'rtx',
        'graphics card', 'accelerator'
    ]
    runtime_indicators = [
        'runtime', 'running time', 'minutes', 'hours',
        'approximately', 'takes', 'estimated'
    ]

    missing = []
    if not any(ind in content for ind in os_indicators):
        missing.append('operating system')
    if not any(ind in content for ind in ram_indicators):
        missing.append('RAM/memory requirements')
    if not any(ind in content for ind in runtime_indicators):
        missing.append('estimated runtime')

    # GPU check only relevant if GPU libraries present
    has_gpu_libs = any(
        f.name.lower() in {'requirements.txt', 'environment.yml'}
        for f in all_files
    )
    if has_gpu_libs:
        code_content = ''
        for f in all_files:
            if f.suffix.lower() == '.py':
                code_content += read_file_safe(f).lower()
        uses_gpu = any(g in code_content for g in [
            'cuda', 'torch.cuda', '.to("cuda")', '.gpu',
            'tf.device', 'jax.devices'
        ])
        if uses_gpu and not any(
            ind in content for ind in gpu_indicators
        ):
            missing.append('GPU specification')

    if len(missing) >= 2:
        findings.append(finding(
            'K', 'SIGNIFICANT',
            f'Compute environment not documented: {", ".join(missing)}',
            'Validators need to know what hardware and software '
            'environment is required to reproduce results. Without '
            'this, they may spend hours on environment issues before '
            'discovering the code requires more RAM or a GPU than '
            'they have available.',
            [f'Missing from README: {", ".join(missing)}']
        ))
    elif len(missing) == 1:
        findings.append(finding(
            'K', 'LOW CONFIDENCE',
            f'Compute environment partially documented — missing: '
            f'{missing[0]}',
            'Most compute environment details are present but '
            f'{missing[0]} is not mentioned.',
            [f'Missing: {missing[0]}']
        ))

    return findings


def detect_P_preregistration(repo_dir, all_files):
    """Failure Mode P: Pre-registration mentioned but no link provided."""
    findings = []

    text_files = [
        f for f in all_files
        if f.suffix.lower() in {'.md', '.txt', '.rst', '.html'}
    ]

    prereg_mentioned = False
    prereg_link = False

    prereg_terms = [
        'pre-registr', 'preregistr', 'registered report',
        'osf.io', 'aspredicted', 'clinicaltrials',
        'protocol registration', 'pre-analysis plan',
        'preanalysis plan'
    ]

    link_pattern = re.compile(
        r'osf\.io/[a-z0-9]+|aspredicted\.org|clinicaltrials\.gov'
        r'|protocols\.io|zenodo\.org|doi\.org',
        re.IGNORECASE
    )

    for f in text_files:
        content = read_file_safe(f).lower()
        if any(term in content for term in prereg_terms):
            prereg_mentioned = True
        if link_pattern.search(content):
            prereg_link = True

    if prereg_mentioned and not prereg_link:
        findings.append(finding(
            'P', 'SIGNIFICANT',
            'Pre-registration mentioned but no link found',
            'The documentation mentions pre-registration or a '
            'registered report but no link to the pre-registration '
            'record was found. Validators cannot verify that the '
            'analysis matches the pre-registered protocol without '
            'this link.',
            ['Pre-registration terms found in documentation',
             'Missing: OSF, AsPredicted, or ClinicalTrials link']
        ))

    return findings


def detect_V_virtual_environment(repo_dir, all_files, existing_findings=None):
    """Failure Mode V: No virtual environment specification."""
    findings = []
    # suppress if [B] already fired — same issue at higher severity
    if existing_findings and any(f.get('mode') == 'B' for f in existing_findings):
        return findings

    has_venv_spec = any(
        f.name.lower() in {
            'environment.yml', 'environment.yaml',
            'pipfile', 'pipfile.lock',
            'poetry.lock', 'pyproject.toml',
            '.python-version', 'runtime.txt',
            'conda-lock.yml', 'setup.py', 'setup.cfg'
        }
        for f in all_files
    )

    has_requirements = any(
        f.name.lower() == 'requirements.txt'
        for f in all_files
    )

    has_python = any(
        f.suffix.lower() == '.py'
        for f in all_files
    )

    if not has_python:
        return findings

    if not has_venv_spec and not has_requirements:
        findings.append(finding(
            'V', 'SIGNIFICANT',
            'No virtual environment or dependency specification found',
            'Python code is present but no virtual environment '
            'specification (environment.yml, Pipfile, pyproject.toml) '
            'or requirements.txt was found. Validators will be forced '
            'to guess which packages to install and may encounter '
            'version conflicts with their existing Python environment.',
            ['Missing: requirements.txt, environment.yml, or Pipfile']
        ))
    elif has_requirements and not has_venv_spec:
        # check if README mentions virtual environment
        readme_mentions_venv = False
        for f in all_files:
            if f.name.lower() in {'readme.md', 'readme.txt'}:
                content = read_file_safe(f).lower()
                if any(term in content for term in [
                    'venv', 'virtualenv', 'conda', 'virtual environment',
                    'python -m venv', 'conda create'
                ]):
                    readme_mentions_venv = True

        if not readme_mentions_venv:
            findings.append(finding(
                'V', 'LOW CONFIDENCE',
                'requirements.txt present but no virtual environment '
                'setup instructions found',
                'A requirements.txt exists but the README does not '
                'mention creating a virtual environment before '
                'installing. Installing into a global Python '
                'environment risks conflicts and unreproducible '
                'behaviour.',
                ['Recommendation: add venv or conda setup instructions '
                 'to README']
            ))

    return findings


def detect_I_intermediate_files(repo_dir, all_files):
    """Failure Mode I: Intermediate files committed but not regenerable."""
    findings = []

    intermediate_extensions = {
        '.pkl', '.npy', '.npz', '.rds', '.rdata',
        '.feather', '.arrow', '.parquet', '.hdf5', '.h5'
    }

    intermediate_files = [
        f for f in all_files
        if f.suffix.lower() in intermediate_extensions
    ]

    if not intermediate_files:
        return findings

    # check if these files are generated by the code
    code_content = ''
    for f in all_files:
        if f.suffix.lower() in CODE_EXTENSIONS:
            code_content += read_file_safe(f)

    untraced = []
    for f in intermediate_files:
        stem = f.stem.lower()
        name = f.name.lower()
        # check if any code writes this file
        if not any(
            ref in code_content.lower()
            for ref in [stem, name, f.suffix.lower()]
        ):
            untraced.append(f.name)

    if intermediate_files and not untraced:
        # files exist and are referenced in code - still flag
        findings.append(finding(
            'I', 'LOW CONFIDENCE',
            f'{len(intermediate_files)} intermediate data file(s) committed',
            'Intermediate files are committed to the repository. '
            'If these are generated by the pipeline, validators '
            'need to know whether to regenerate them or use the '
            'committed versions. Committed intermediates can mask '
            'reproducibility failures if the generation step is skipped.',
            [f'Intermediate files: '
             f'{", ".join(f.name for f in intermediate_files[:5])}',
             'Clarify in README: should validators regenerate these?']
        ))
    elif untraced:
        findings.append(finding(
            'I', 'SIGNIFICANT',
            f'Intermediate files present with no apparent generation code',
            'Intermediate data files are committed but no code that '
            'generates them was found. Validators cannot reproduce '
            'these files from scratch, creating a gap in the '
            'reproducibility chain.',
            [f'Untraced files: {", ".join(untraced[:5])}']
        ))

    return findings


def detect_J_notebook_order(repo_dir, all_files):
    """Failure Mode J: Notebooks with unclear or non-linear execution order."""
    findings = []

    notebooks = [
        f for f in all_files
        if f.suffix.lower() == '.ipynb'
    ]

    if not notebooks:
        return findings

    for nb in notebooks:
        try:
            import json as _json
            content = nb.read_text(encoding='utf-8', errors='ignore')
            data = _json.loads(content)
            cells = data.get('cells', [])

            # check execution counts
            exec_counts = []
            for cell in cells:
                if cell.get('cell_type') == 'code':
                    ec = cell.get('execution_count')
                    if ec is not None:
                        exec_counts.append(ec)

            if not exec_counts:
                findings.append(finding(
                    'J', 'SIGNIFICANT',
                    f'Notebook has no execution counts: {nb.name}',
                    'This notebook has never been run top-to-bottom '
                    'with saved outputs, or outputs were cleared before '
                    'sharing. Validators cannot verify what the original '
                    'outputs looked like.',
                    [f'Evidence: {nb.name} — all execution counts null']
                ))
            else:
                # check for non-linear execution
                non_none = [e for e in exec_counts if e is not None]
                if non_none != sorted(non_none):
                    findings.append(finding(
                        'J', 'SIGNIFICANT',
                        f'Notebook cells executed out of order: {nb.name}',
                        'Cell execution counts are not sequential, '
                        'meaning the notebook was not run top-to-bottom. '
                        'Results may depend on a specific non-linear '
                        'execution order that is not documented.',
                        [f'Evidence: {nb.name} — execution order: '
                         f'{non_none[:10]}']
                    ))
        except Exception:
            continue

    return findings


def detect_M_python_version_conflict(repo_dir, all_files):
    """Failure Mode M: Multiple or conflicting Python versions referenced."""
    findings = []
    # skip if no Python files present
    if not any(f.suffix.lower() == '.py' for f in all_files):
        return findings

    version_pattern = re.compile(r'(?<![a-zA-Z])python\s*[=><!\s]+\s*(\d+\.\d+)', re.IGNORECASE)
    versions_found = {}

    check_files = [
        f for f in all_files
        if f.name.lower() in {
            'requirements.txt', 'environment.yml', 'environment.yaml',
            'pipfile', 'pyproject.toml', 'setup.py', 'setup.cfg',
            'runtime.txt', '.python-version', 'readme.md', 'readme.txt'
        }
    ]

    for f in check_files:
        content = read_file_safe(f)
        matches = version_pattern.findall(content)
        if matches:
            versions_found[f.name] = matches

    all_versions = set(
        v for versions in versions_found.values() for v in versions
    )

    if len(all_versions) > 1:
        findings.append(finding(
            'M', 'SIGNIFICANT',
            f'Conflicting Python versions referenced: '
            f'{", ".join(sorted(all_versions))}',
            'Different files specify different Python versions. '
            'This creates ambiguity about which version was used '
            'to produce the published results. Validators will '
            'not know which to install.',
            [f'{fname}: {", ".join(v)}'
             for fname, v in versions_found.items()]
        ))
    elif len(all_versions) == 0:
        findings.append(finding(
            'M', 'LOW CONFIDENCE',
            'Python version not specified anywhere',
            'No Python version requirement was found in any '
            'configuration file. Validators will install their '
            'default Python version which may not match what '
            'was used for the original analysis.',
            ['Recommendation: add python=3.x to environment.yml '
             'or add .python-version file']
        ))

    return findings


def detect_L_large_files_missing(repo_dir, all_files):
    """Failure Mode L: Code references files that appear to be missing."""
    findings = []
    code_files = [f for f in all_files
                  if f.suffix.lower() in CODE_EXTENSIONS]

    all_filenames = {f.name.lower() for f in all_files}
    all_stems = {f.stem.lower() for f in all_files}

    read_pattern = re.compile(
        r'(?:pd\.read_csv|pd\.read_parquet|pd\.read_excel'
        r'|pd\.read_stata|pd\.read_sas|pd\.read_feather'
        r'|np\.load|open|read_csv|read_parquet|loadtxt'
        r'|readRDS|read\.csv|read_dta|haven::read'
        r'|SeqIO\.parse|read\.FASTA|read\.alignment|nib\.load|nibabel\.load|load)'
        r'\s*\(\s*["\']([^"\']+)["\']',
        re.IGNORECASE
    )

    # build set of files generated by the code (intermediate outputs)
    write_pattern = re.compile(
        r'(?:to_csv|to_parquet|to_excel|to_stata|savetxt|save|write_csv|saveRDS|write\.csv'
        r'|write\.table|fwrite|writeMat|csvwrite)'
        r'\s*\(\s*f?["\']([^"\']+)["\']',
        re.IGNORECASE
    )
    # R-style: write.csv(data, 'filename') — filename is second argument
    write_pattern_r = re.compile(
        r'(?:write\.csv|write\.table|saveRDS|fwrite)'
        r'\s*\([^,]+,\s*f?["\']([^"\']+)["\']',
        re.IGNORECASE
    )
    # also catch filenames assigned to variables then passed to write functions
    varname_pattern = re.compile(
        r'([\w_]+)\s*=\s*["\']([^"\']*\.(?:csv|dta|xlsx|parquet|rds))["\']\s*\n'
        r'.*?\1',
        re.IGNORECASE | re.DOTALL
    )
    generated_files = set()
    for f in code_files:
        content = read_file_safe(f)
        # resolve one level of variable assignment
        var_assign = re.findall(
            r'([A-Z_][A-Z0-9_]*)\s*=\s*["\']([^"\']*\.(?:csv|dta|xlsx|parquet|rds))["\']\s*',
            content
        )
        var_map = {v: p for v, p in var_assign}
        # check for to_csv(VAR) patterns
        for var, path in var_map.items():
            if re.search(r'to_csv\s*\(\s*' + var + r'[,)]', content):
                fname = path.replace('\\', '/').split('/')[-1].lower()
                if fname and '.' in fname:
                    generated_files.add(fname)
        for match in write_pattern.finditer(content):
            filepath = match.group(1)
            fname = filepath.replace('\\', '/').split('/')[-1].lower()
            if fname and '.' in fname:
                generated_files.add(fname)
        for match in write_pattern_r.finditer(content):
            filepath = match.group(1)
            fname = filepath.replace('\\', '/').split('/')[-1].lower()
            if fname and '.' in fname:
                generated_files.add(fname)
    # Also scan shell scripts for output files (redirect > or -o flag)
    shell_write = re.compile(
        r'(?:>\s*|(?:-o|--out(?:put)?)\s+)([\w./\-]+\.(?:txt|csv|tsv|bam|sam|vcf|gz|pdf|png|svg|html))',
        re.IGNORECASE
    )
    for f in all_files:
        if f.suffix.lower() in {'.sh', '.bash'}:
            try:
                sh_content = f.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                sh_content = ''
            for m in shell_write.finditer(sh_content):
                fname = m.group(1).replace('\\', '/').split('/')[-1].lower()
                if fname and '.' in fname:
                    generated_files.add(fname)

    # Also scan notebook cell sources for quoted file paths
    import json as _json
    for nb in all_files:
        if nb.suffix.lower() == '.ipynb':
            try:
                nb_data = _json.loads(nb.read_text(encoding='utf-8', errors='ignore'))
                for cell in nb_data.get('cells', []):
                    src = ''.join(cell.get('source', []))
                    for match in read_pattern.finditer(src):
                        fpath = match.group(1)
                        fname = fpath.replace('\\', '/').split('/')[-1].lower()
                        if fname and '.' in fname:
                            # check if file exists
                            if not any(f.name.lower() == fname for f in all_files):
                                missing_refs.add(fname)
                    # Also catch string literals with data file extensions
                    for m in re.finditer(r'["\']([^"\']+\.(?:nii|nii\.gz|npy|npz|mat|csv|tsv|fasta|fastq|gz|bam|vcf))["\']', src, re.IGNORECASE):
                        fpath = m.group(1)
                        fname = fpath.replace('\\', '/').split('/')[-1].lower()
                        if fname and not any(f.name.lower() == fname for f in all_files):
                            missing_refs.add(fname)
            except Exception:
                pass
    for f in code_files:
        content = read_file_safe(f)
        for match in read_pattern.finditer(content):
            filepath = match.group(1)
            fname = filepath.replace('\\', '/').split('/')[-1].lower()
            stem = fname.rsplit('.', 1)[0] if '.' in fname else fname
            if fname and '.' in fname:
                if (fname not in all_filenames
                        and fname not in generated_files
                        and stem not in all_stems
                        and not filepath.startswith(('http', 'ftp', '$', '{'))):
                    missing_refs.add(fname)

    if missing_refs:
        sample = sorted(missing_refs)[:5]
        extra = f' (and {len(missing_refs)-5} more)' if len(missing_refs) > 5 else ''
        findings.append(finding(
            'L', 'SIGNIFICANT',
            f'Code references {len(missing_refs)} file(s) not found in repository',
            'The code attempts to read files that are not present '
            'in the repository. These may be large data files that '
            'were excluded, external downloads, or files that were '
            'accidentally omitted. Validators cannot run the code '
            'without these files.',
            [f'Missing files referenced: {", ".join(sample)}{extra}',
             'Add download instructions or data access information '
             'to README']
        ))

    return findings


def detect_O_output_not_committed(repo_dir, all_files):
    """Failure Mode O: No committed outputs to compare against."""
    findings = []

    output_extensions = {
        '.txt', '.csv', '.xlsx', '.html', '.pdf',
        '.png', '.jpg', '.svg', '.eps', '.tex'
    }

    # look for results/output directories
    result_dir_names = {
        'results', 'output', 'outputs', 'figures',
        'tables', 'plots', 'charts'
    }

    all_dirs = {f.parent.name.lower() for f in all_files}
    has_results_dir = bool(result_dir_names & all_dirs)

    output_files = [
        f for f in all_files
        if f.suffix.lower() in output_extensions
        and f.parent.name.lower() in result_dir_names
    ]

    has_python = any(f.suffix.lower() == '.py' for f in all_files)

    if has_python and not output_files and not has_results_dir:
        findings.append(finding(
            'O', 'SIGNIFICANT',
            'No committed outputs found for comparison',
            'No result files, figures, or tables were found in '
            'standard output directories. Without committed outputs, '
            'validators have no reference to compare their results '
            'against. Even a single representative output file '
            'significantly improves reproducibility verification.',
            ['Missing: results/, output/, or figures/ directory '
             'with committed outputs',
             'Recommendation: commit key tables and figures from '
             'the paper']
        ))
    elif has_python and output_files:
        findings.append(finding(
            'O', 'LOW CONFIDENCE',
            f'{len(output_files)} output file(s) committed — '
            f'verify these match paper',
            'Output files are committed. Validators will compare '
            'their results against these. Ensure these files were '
            'generated by the committed code, not manually edited.',
            [f'Output files: '
             f'{", ".join(f.name for f in output_files[:5])}']
        ))

    return findings


def detect_Q_config_files(repo_dir, all_files):
    """Failure Mode Q: Configuration files missing or undocumented."""
    findings = []
    code_files = [f for f in all_files
                  if f.suffix.lower() in CODE_EXTENSIONS]

    config_read_pattern = re.compile(
        r'(?:configparser|yaml\.load|yaml\.safe_load'
        r'|json\.load|toml\.load|dotenv|load_dotenv'
        r'|argparse|click\.option'
        r'|config\[|cfg\[|params\[)',
        re.IGNORECASE
    )

    config_file_pattern = re.compile(
        r'["\']([^"\']+\.(?:yaml|yml|json|toml|ini|cfg|conf))["\']',
        re.IGNORECASE
    )

    all_filenames_lower = {f.name.lower() for f in all_files}
    uses_config = False
    missing_configs = set()

    for f in code_files:
        content = read_file_safe(f)
        if config_read_pattern.search(content):
            uses_config = True
        for match in config_file_pattern.finditer(content):
            cfg_file = match.group(1).split('/')[-1].lower()
            if cfg_file not in all_filenames_lower:
                missing_configs.add(cfg_file)

    if missing_configs:
        findings.append(finding(
            'Q', 'SIGNIFICANT',
            f'Configuration files referenced but not found: '
            f'{", ".join(sorted(missing_configs)[:5])}',
            'The code references configuration files that are not '
            'present in the repository. Validators cannot run the '
            'code with the same settings used in the original analysis.',
            [f'Missing configs: {", ".join(sorted(missing_configs)[:5])}']
        ))
    elif uses_config:
        findings.append(finding(
            'Q', 'LOW CONFIDENCE',
            'Code uses configuration loading but no config file issues detected',
            'The code uses configuration file loading patterns. '
            'Verify that all required configuration files are '
            'committed and documented.',
            ['Config loading detected — manual verification recommended']
        ))

    return findings


def detect_R_statistical_tests_undocumented(repo_dir, all_files):
    """Failure Mode R: Statistical tests used but assumptions not documented."""
    findings = []
    code_files = [f for f in all_files
                  if f.suffix.lower() in CODE_EXTENSIONS]

    stat_patterns = re.compile(
        r'\b(OLS|WLS|GLS|2SLS|IV|GMM|logit|probit|tobit'
        r'|t\.test|chi\.sq|anova|kruskal|wilcox|mann.whitney'
        r'|LinearRegression|LogisticRegression|statsmodels'
        r'|smf\.ols|sm\.OLS|ivreg|feols|felm'
        r'|fixed.effect|random.effect|panel)\b',
        re.IGNORECASE
    )

    assumption_patterns = re.compile(
        r'\b(heteroskedastic|robust|cluster|bootstrap'
        r'|standard.error|HAC|Newey.West|White'
        r'|vif|multicollin|autocorrelation|serial.correlation'
        r'|hausman|endogeneit)\b',
        re.IGNORECASE
    )

    stat_methods_found = set()
    assumptions_documented = False

    for f in code_files:
        content = read_file_safe(f)
        methods = stat_patterns.findall(content)
        if methods:
            stat_methods_found.update(methods)
        if assumption_patterns.search(content):
            assumptions_documented = True

    if stat_methods_found and not assumptions_documented:
        findings.append(finding(
            'R', 'LOW CONFIDENCE',
            f'Statistical methods detected with no assumption checks found',
            'The code uses statistical methods that have assumptions '
            '(normality, homoskedasticity, independence, etc.) but '
            'no assumption-checking code was detected. Validators '
            'cannot verify that the methods were appropriately applied.',
            [f'Methods detected: '
             f'{", ".join(sorted(stat_methods_found)[:8])}',
             'Recommendation: document assumption checks or '
             'reference where they appear in the paper']
        ))

    return findings


def detect_S_software_citations_missing(repo_dir, all_files):
    """Failure Mode S: Key software used but not cited."""
    findings = []

    major_packages = {
        'numpy', 'pandas', 'scipy', 'matplotlib', 'sklearn',
        'scikit-learn', 'statsmodels', 'torch', 'pytorch',
        'tensorflow', 'keras', 'stata', 'matlab'
    }

    readme_file = None
    for f in all_files:
        if f.name.lower() in {'readme.md', 'readme.txt', 'readme.rst'}:
            readme_file = f
            break

    if not readme_file:
        return findings

    try:
        readme_content = readme_file.read_text(
            encoding='utf-8', errors='ignore'
        ).lower()
    except Exception:
        return findings

    has_citations = any(term in readme_content for term in [
        'citation', 'cite', 'reference', 'bibliography',
        'doi:', 'zenodo', 'joss', 'journal of open source'
    ])

    if not has_citations:
        # check what packages are used
        imports_found = set()
        for f in all_files:
            if f.suffix.lower() == '.py':
                content = read_file_safe(f).lower()
                for pkg in major_packages:
                    if f'import {pkg}' in content or f'from {pkg}' in content:
                        imports_found.add(pkg)

        if imports_found:
            findings.append(finding(
                'S', 'LOW CONFIDENCE',
                'No software citations found in README',
                'Major software packages are used but no citations '
                'or references section was found in the README. '
                'Software citation is increasingly required by '
                'journals and supports reproducibility by '
                'identifying exact software versions.',
                [f'Packages used: {", ".join(sorted(imports_found))}',
                 'Recommendation: add citations for key packages']
            ))

    return findings


def detect_T_test_coverage(repo_dir, all_files):
    """Failure Mode T: No tests present for analysis code."""
    findings = []

    has_python = any(f.suffix.lower() == '.py' for f in all_files)
    if not has_python:
        return findings

    test_indicators = [
        'test_', '_test.py', 'tests/', 'test/', 'spec/',
        'pytest', 'unittest', 'nose'
    ]

    has_tests = any(
        any(ind in f.name.lower() or ind in str(f).lower()
            for ind in test_indicators)
        for f in all_files
    )

    code_files = [
        f for f in all_files
        if f.suffix.lower() == '.py'
        and not any(t in f.name.lower() for t in ['test_', '_test'])
    ]

    if not has_tests and len(code_files) > 3:
        findings.append(finding(
            'T', 'LOW CONFIDENCE',
            'No test files found',
            'No automated tests were found for the analysis code. '
            'Tests are not required for reproducibility but their '
            'absence means there is no automated way to verify '
            'that helper functions produce expected outputs. '
            'Even simple smoke tests significantly improve '
            'validator confidence.',
            [f'Python files without tests: {len(code_files)}',
             'Recommendation: add pytest tests for key functions']
        ))

    return findings


def detect_X_no_container(repo_dir, all_files):
    """Failure Mode X: No containerisation or environment isolation."""
    findings = []

    container_files = {
        'dockerfile', 'docker-compose.yml', 'docker-compose.yaml',
        'singularity', 'singularity.def', 'apptainer.def',
        '.devcontainer', 'devcontainer.json'
    }

    has_container = any(
        f.name.lower() in container_files
        for f in all_files
    )

    has_environment_yml = any(
        f.name.lower() in {'environment.yml', 'environment.yaml'}
        for f in all_files
    )

    has_python = any(f.suffix.lower() == '.py' for f in all_files)

    if has_python and not has_container and not has_environment_yml:
        findings.append(finding(
            'X', 'LOW CONFIDENCE',
            'No containerisation or conda environment found',
            'No Dockerfile, Docker Compose, Singularity, or '
            'conda environment file was found. Without environment '
            'isolation, dependency conflicts between the validator\'s '
            'system and the required packages may prevent reproduction. '
            'A conda environment.yml or Dockerfile is the most '
            'reliable way to ensure environment reproducibility.',
            ['Recommendation: add environment.yml or Dockerfile',
             'Minimum: ensure requirements.txt has pinned versions']
        ))

    return findings


def detect_Y_data_source_missing(repo_dir, all_files):
    """Failure Mode Y: Data files present but no source or provenance."""
    findings = []

    data_extensions = {
        '.csv', '.tsv', '.xlsx', '.xls', '.parquet',
        '.dta', '.sav', '.rds', '.rdata'
    }

    data_files = [
        f for f in all_files
        if f.suffix.lower() in data_extensions
    ]

    if not data_files:
        return findings

    # look for source/provenance documentation
    source_indicators = [
        'download', 'source', 'obtain', 'access',
        'available at', 'retrieved from', 'collected from',
        'provided by', 'doi:', 'url:', 'http', 'database',
        'data availability', 'data access'
    ]

    readme_file = None
    for f in all_files:
        if f.name.lower() in {'readme.md', 'readme.txt', 'readme.rst'}:
            readme_file = f
            break

    has_source = False
    if readme_file:
        try:
            content = readme_file.read_text(
                encoding='utf-8', errors='ignore'
            ).lower()
            has_source = any(ind in content for ind in source_indicators)
        except Exception:
            pass

    if not has_source:
        findings.append(finding(
            'Y', 'SIGNIFICANT',
            f'Data files present but no data source documented',
            'Data files are present but no information about where '
            'the data came from was found in the README. Validators '
            'cannot verify data provenance, check for updates, or '
            'understand data access restrictions without this '
            'information.',
            [f'Data files: '
             f'{", ".join(f.name for f in data_files[:5])}',
             'Required: data source, URL, DOI, or access instructions']
        ))

    return findings


def detect_AA_figure_reproducibility(repo_dir, all_files):
    """Failure Mode AA: Figures committed but no figure generation code."""
    findings = []

    figure_extensions = {'.png', '.jpg', '.jpeg', '.svg', '.eps', '.pdf'}
    figure_files = [
        f for f in all_files
        if f.suffix.lower() in figure_extensions
        and f.parent.name.lower() in {
            'figures', 'figure', 'figs', 'fig',
            'plots', 'plot', 'images', 'results'
        }
    ]

    if not figure_files:
        return findings

    # look for figure generation code
    plot_patterns = re.compile(
        r'(plt\.|ggplot|plot\(|savefig|ggsave|matplotlib'
        r'|seaborn|plotly|bokeh|altair)',
        re.IGNORECASE
    )

    has_plot_code = False
    for f in all_files:
        if f.suffix.lower() in CODE_EXTENSIONS:
            content = read_file_safe(f)
            if plot_patterns.search(content):
                has_plot_code = True
                break

    if figure_files and not has_plot_code:
        findings.append(finding(
            'AA', 'SIGNIFICANT',
            f'{len(figure_files)} figure(s) committed but no figure generation code found',
            'Figure files are committed but no code that generates '
            'figures was detected. Validators cannot reproduce the '
            'figures from scratch. If figures are generated by the '
            'analysis scripts, ensure the plotting code is included.',
            [f'Figures: {", ".join(f.name for f in figure_files[:5])}']
        ))
    elif figure_files and has_plot_code:
        findings.append(finding(
            'AA', 'LOW CONFIDENCE',
            f'{len(figure_files)} figure(s) committed — verify generation code produces matching output',
            'Figures are committed and plotting code exists. '
            'Validators should verify that running the code '
            'reproduces figures that match the committed versions '
            'and the published paper.',
            [f'Figures to verify: '
             f'{", ".join(f.name for f in figure_files[:5])}']
        ))

    return findings


def detect_AB_parallel_no_seed(repo_dir, all_files):
    """Failure Mode AB: Parallelisation without determinism controls."""
    findings = []
    code_files = [f for f in all_files
                  if f.suffix.lower() in CODE_EXTENSIONS]

    parallel_patterns = re.compile(
        r'(multiprocessing|concurrent\.futures|joblib|dask'
        r'|ray\.|\bPool\b|ProcessPool|ThreadPool'
        r'|n_jobs\s*=|parallel\s*=\s*True'
        r'|mp\.Pool|futures\.ProcessPoolExecutor)',
        re.IGNORECASE
    )

    determinism_patterns = re.compile(
        r'(worker_init_fn|pl\.seed_everything'
        r'|torch\.use_deterministic_algorithms'
        r'|PYTHONHASHSEED|random_state\s*=\s*\d'
        r'|initializer\s*=)',
        re.IGNORECASE
    )

    uses_parallel = False
    has_determinism = False

    for f in code_files:
        content = read_file_safe(f)
        if parallel_patterns.search(content):
            uses_parallel = True
        if determinism_patterns.search(content):
            has_determinism = True

    if uses_parallel and not has_determinism:
        findings.append(finding(
            'AB', 'SIGNIFICANT',
            'Parallelisation used without determinism controls',
            'The code uses parallel processing but no determinism '
            'controls were found. Parallel execution order is '
            'non-deterministic by default. Results may vary between '
            'runs depending on scheduling. Set PYTHONHASHSEED and '
            'use worker initialisation functions to ensure '
            'reproducible parallel execution.',
            ['Parallel patterns detected without worker seeds',
             'Recommendation: set PYTHONHASHSEED=0 and use '
             'worker_init_fn or equivalent']
        ))

    return findings


def detect_AC_deprecated_functions(repo_dir, all_files):
    """Failure Mode AC: Use of deprecated functions likely to break."""
    findings = []
    code_files = [f for f in all_files
                  if f.suffix.lower() == '.py']

    deprecated = {
        'np.bool': 'np.bool_',
        'np.int': 'np.int_',
        'np.float': 'np.float64',
        'np.complex': 'np.complex128',
        'np.object': 'np.object_',
        'np.str': 'np.str_',
        'sklearn.cross_validation': 'sklearn.model_selection',
        'from sklearn.externals': 'install joblib directly',
        'pd.Panel': 'pd.DataFrame (Panel removed)',
        'DataFrame.ix[': 'DataFrame.loc[ or .iloc[',
        'tensorflow.compat.v1': 'TensorFlow 2.x API',
    }

    for f in code_files:
        content = read_file_safe(f)
        found = []
        for old, new in deprecated.items():
            if old in content:
                found.append(f'{old} → {new}')
        if found:
            findings.append(finding(
                'AC', 'SIGNIFICANT',
                f'Deprecated functions detected in {f.name}',
                'This file uses functions that have been removed or '
                'deprecated in recent package versions. Running this '
                'code with current package versions will likely '
                'produce errors.',
                [f'Deprecated: {d}' for d in found[:5]]
            ))

    return findings


def detect_AD_missing_gitignore(repo_dir, all_files):
    """Failure Mode AD: No .gitignore — sensitive or junk files may be committed."""
    findings = []

    has_gitignore = any(
        f.name == '.gitignore' for f in all_files
    )

    has_python = any(f.suffix.lower() == '.py' for f in all_files)

    if has_python and not has_gitignore:
        # check for files that should be ignored
        junk_files = [
            f for f in all_files
            if f.suffix.lower() in {'.pyc', '.pyo'}
            or f.name in {'.DS_Store', 'Thumbs.db', 'desktop.ini'}
            or '__pycache__' in str(f)
        ]

        if junk_files:
            findings.append(finding(
                'AD', 'SIGNIFICANT',
                'No .gitignore and junk files detected in repository',
                'No .gitignore file was found and system or compiled '
                'files are present in the repository. These files '
                'bloat the repository, may contain system-specific '
                'paths, and suggest the repository was not cleaned '
                'before sharing.',
                [f'Junk files found: '
                 f'{", ".join(f.name for f in junk_files[:5])}']
            ))
        else:
            findings.append(finding(
                'AD', 'LOW CONFIDENCE',
                'No .gitignore file found',
                'No .gitignore file was found. Without one, compiled '
                'files, credentials, and system files may be '
                'accidentally committed in future.',
                ['Recommendation: add a .gitignore file']
            ))

    return findings


def detect_AE_mixed_languages(repo_dir, all_files):
    """Failure Mode AE: Multiple languages used without integration docs."""
    findings = []

    language_extensions = {
        'Python': {'.py'},
        'R': {'.r', '.rmd', '.qmd'},
        'Julia': {'.jl'},
        'Stata': {'.do', '.ado'},
        'MATLAB': {'.m', '.mlx'},
        'Shell': {'.sh', '.bash'},
        'SQL': {'.sql'},
    }

    languages_found = {}
    for lang, exts in language_extensions.items():
        files = [f for f in all_files if f.suffix.lower() in exts]
        if files:
            languages_found[lang] = len(files)

    if len(languages_found) >= 3:
        readme_file = None
        for f in all_files:
            if f.name.lower() in {'readme.md', 'readme.txt'}:
                readme_file = f
                break

        integration_documented = False
        if readme_file:
            try:
                content = readme_file.read_text(
                    encoding='utf-8', errors='ignore'
                ).lower()
                if any(lang.lower() in content
                       for lang in languages_found):
                    integration_documented = True
            except Exception:
                pass

        if not integration_documented:
            langs = ', '.join(
                f'{l} ({n} files)'
                for l, n in languages_found.items()
            )
            findings.append(finding(
                'AE', 'SIGNIFICANT',
                f'Multiple languages used without integration documentation',
                'This repository uses multiple programming languages '
                'but the README does not explain how they fit together. '
                'Validators need to know the execution order across '
                'languages and any data handoffs between them.',
                [f'Languages: {langs}',
                 'Required: explain how languages interact in README']
            ))

    return findings


def detect_AF_output_format_undocumented(repo_dir, all_files):
    """Failure Mode AF: Output format not documented."""
    findings = []

    code_files = [f for f in all_files
                  if f.suffix.lower() in CODE_EXTENSIONS]

    write_patterns = re.compile(
        r'(to_csv|to_excel|to_parquet|to_stata|to_latex'
        r'|savefig|to_html|write_csv|fwrite|write\.csv'
        r'|saveRDS|save\.image|np\.save|pickle\.dump'
        r'|\.write\s*\()',
        re.IGNORECASE
    )

    has_write_code = False
    for f in code_files:
        content = read_file_safe(f)
        if write_patterns.search(content):
            has_write_code = True
            break

    if not has_write_code:
        return findings

    readme_file = None
    for f in all_files:
        if f.name.lower() in {'readme.md', 'readme.txt'}:
            readme_file = f
            break

    if readme_file:
        try:
            content = readme_file.read_text(
                encoding='utf-8', errors='ignore'
            ).lower()
            output_documented = any(term in content for term in [
                'output', 'result', 'produces', 'generates',
                'will create', 'will produce', 'expected'
            ])
            if not output_documented:
                findings.append(finding(
                    'AF', 'LOW CONFIDENCE',
                    'Code writes output files but outputs not documented in README',
                    'The code generates output files but the README '
                    'does not describe what outputs to expect. '
                    'Validators cannot verify successful completion '
                    'without knowing what files should be produced.',
                    ['Recommendation: list expected output files '
                     'in README']
                ))
        except Exception:
            pass

    return findings


def detect_AG_api_keys_in_code(repo_dir, all_files):
    """Failure Mode AG: API keys or tokens hardcoded in source files."""
    findings = []
    code_files = [f for f in all_files
                  if f.suffix.lower() in CODE_EXTENSIONS]

    key_patterns = re.compile(
        r'[A-Z_]*(?:KEY|SECRET|TOKEN|PASSWORD|AUTH|CREDENTIAL|API)[A-Z_]*'
        r'\s*=\s*["\'][a-zA-Z0-9_\-]{16,}["\']',
        re.IGNORECASE
    )

    for f in code_files:
        content = read_file_safe(f)
        matches = key_patterns.findall(content)
        if matches:
            # Extract variable names from matches for evidence
            var_names = []
            for m in matches:
                var = m.split('=')[0].strip().split('\n')[-1].strip()
                if var and var not in var_names:
                    var_names.append(var)
            evidence_lines = [f'Hardcoded credential: {v}' for v in var_names[:5]]
            evidence_lines.append('Action required: rotate these credentials immediately if real')
            findings.append(finding(
                'AG', 'CRITICAL',
                f'Possible hardcoded credentials in {f.name}: {", ".join(var_names[:3])}',
                'What appears to be an API key or token is hardcoded '
                'in source code. If real, this is a security issue — '
                'credentials committed to a repository should be '
                'considered compromised. Replace with environment '
                'variables immediately.',
                evidence_lines
            ))

    return findings


def detect_AH_no_changelog(repo_dir, all_files):
    """Failure Mode AH: No changelog or version history."""
    findings = []

    changelog_names = {
        'changelog', 'changelog.md', 'changelog.txt',
        'changes', 'changes.md', 'history.md',
        'news.md', 'releases.md'
    }

    has_changelog = any(
        f.name.lower() in changelog_names
        for f in all_files
    )

    has_readme = any(
        f.name.lower() in {'readme.md', 'readme.txt'}
        for f in all_files
    )

    # only flag if there's a substantial codebase
    py_files = [f for f in all_files if f.suffix.lower() == '.py']

    if len(py_files) > 5 and not has_changelog and has_readme:
        findings.append(finding(
            'AH', 'LOW CONFIDENCE',
            'No changelog or version history found',
            'No changelog file was found. For research code, a '
            'changelog helps validators understand what changed '
            'between versions and whether the committed code matches '
            'the version used to generate the published results.',
            ['Recommendation: add CHANGELOG.md noting the version '
             'used for publication']
        ))

    return findings


def detect_AI_print_debugging(repo_dir, all_files):
    """Failure Mode AI: Excessive print debugging suggests unfinished code."""
    findings = []
    code_files = [f for f in all_files
                  if f.suffix.lower() == '.py']

    for f in code_files:
        content = read_file_safe(f)
        lines = content.splitlines()

        print_count = sum(
            1 for line in lines
            if re.search(r'^\s*print\s*\(', line)
            and not re.search(r'#.*print', line)
        )

        total_lines = len([l for l in lines if l.strip()])

        if total_lines > 0 and print_count / total_lines > 0.1:
            findings.append(finding(
                'AI', 'LOW CONFIDENCE',
                f'High density of print statements in {f.name}',
                f'{print_count} print statements in {total_lines} '
                f'lines of code suggests debugging output was not '
                f'cleaned up before publication. This does not affect '
                f'reproducibility but suggests the code may not be '
                f'in its final form.',
                [f'Evidence: {print_count} prints in {total_lines} '
                 f'non-blank lines ({print_count*100//total_lines}%)']
            ))

    return findings


def detect_AJ_hardcoded_sample_size(repo_dir, all_files):
    """Failure Mode AJ: Sample sizes or thresholds hardcoded without explanation."""
    findings = []
    code_files = [f for f in all_files
                  if f.suffix.lower() in {'.py', '.r', '.rmd'}]

    magic_number_pattern = re.compile(
        r'(?:head|sample|nrow|iloc|[:]\s*)\s*\(\s*(\d{3,})\s*\)'
        r'|n\s*=\s*(\d{3,})\b'
        r'|threshold\s*=\s*(0\.\d+)'
        r'|cutoff\s*=\s*(0\.\d+)',
        re.IGNORECASE
    )

    for f in code_files:
        content = read_file_safe(f)
        matches = magic_number_pattern.findall(content)
        flat = [m for group in matches for m in group if m]

        if len(flat) >= 3:
            findings.append(finding(
                'AJ', 'LOW CONFIDENCE',
                f'Multiple hardcoded numerical thresholds in {f.name}',
                'Several hardcoded numbers that appear to be sample '
                'sizes, thresholds, or cutoffs were found without '
                'explanatory comments. Validators cannot determine '
                'if these match the values described in the paper '
                'without documentation.',
                [f'Values found: {", ".join(sorted(set(flat))[:8])}',
                 'Recommendation: add comments explaining each value']
            ))

    return findings


def detect_AK_external_urls(repo_dir, all_files):
    """Failure Mode AK: External URLs that may become unavailable."""
    findings = []
    code_files = [f for f in all_files
                  if f.suffix.lower() in CODE_EXTENSIONS | {'.md', '.txt'}]

    url_pattern = re.compile(
        r'https?://(?!github\.com|zenodo\.org|doi\.org|arxiv\.org'
        r'|pypi\.org|anaconda\.org|conda\.io)[^\s\'")\]>]+',
        re.IGNORECASE
    )

    urls_found = set()
    for f in code_files:
        content = read_file_safe(f)
        matches = url_pattern.findall(content)
        urls_found.update(matches[:3])

    if urls_found:
        sample = list(urls_found)[:5]
        findings.append(finding(
            'AK', 'LOW CONFIDENCE',
            f'External URLs detected — may become unavailable',
            'The code or documentation references external URLs. '
            'If these URLs go offline, validators will be unable '
            'to access required resources. Use DOIs or archived '
            'URLs where possible.',
            [f'URLs: {", ".join(sample)[:200]}']
        ))

    return findings


def detect_AL_data_privacy(repo_dir, all_files):
    """Failure Mode AL: Potential personal or sensitive data indicators."""
    findings = []

    sensitive_patterns = re.compile(
        r'\b(ssn|social.security|date.of.birth|dob'
        r'|phone.number|email.address|home.address'
        r'|medical.record|patient.id|participant.id'
        r'|subject.id|ip.address|passport'
        r'|national.insurance|nin\b|nhs.number)\b',
        re.IGNORECASE
    )

    data_files = [
        f for f in all_files
        if f.suffix.lower() in {'.csv', '.tsv', '.xlsx', '.xls'}
    ]

    flagged = []
    for f in data_files:
        content = read_file_safe(f)
        if sensitive_patterns.search(content[:2000]):
            flagged.append(f.name)

    if flagged:
        findings.append(finding(
            'AL', 'SIGNIFICANT',
            f'Potential sensitive data indicators in: '
            f'{", ".join(flagged[:3])}',
            'Data files contain column names or values that suggest '
            'personally identifiable or sensitive information. '
            'Verify that data sharing complies with IRB approval, '
            'GDPR, and journal data sharing policies before '
            'publishing this repository.',
            [f'Files with sensitive indicators: {", ".join(flagged)}',
             'Required: data anonymisation or access restriction '
             'documentation']
        ))

    return findings


def detect_AM_makefile_missing(repo_dir, all_files):
    """Failure Mode AM: Complex pipeline with no automation."""
    findings = []

    pipeline_indicators = [
        f for f in all_files
        if f.suffix.lower() == '.py'
        and re.match(r'^\d+_', f.name)
    ]

    has_automation = any(
        f.name.lower() in {
            'makefile', 'dodo.py', 'snakefile',
            'workflow.py', 'pipeline.py', 'run_all.py',
            'run_all.sh', 'main.py', 'reproduce.py',
            'reproduce.sh'
        }
        for f in all_files
    )

    if len(pipeline_indicators) >= 4 and not has_automation:
        findings.append(finding(
            'AM', 'SIGNIFICANT',
            f'{len(pipeline_indicators)} numbered scripts with no pipeline automation',
            'The repository has multiple numbered scripts suggesting '
            'a sequential pipeline, but no automation file '
            '(Makefile, Snakefile, run_all.py) was found. '
            'Validators must manually execute each script in order. '
            'A single entry point that runs the full pipeline '
            'significantly improves reproducibility.',
            [f'Scripts: '
             f'{", ".join(f.name for f in pipeline_indicators[:6])}',
             'Recommendation: add run_all.py or Makefile']
        ))

    return findings


def detect_AN_commented_code(repo_dir, all_files):
    """Failure Mode AN: Large blocks of commented-out code."""
    findings = []
    code_files = [f for f in all_files
                  if f.suffix.lower() == '.py']

    for f in code_files:
        content = read_file_safe(f)
        lines = content.splitlines()

        commented = sum(
            1 for line in lines
            if line.strip().startswith('#')
            and len(line.strip()) > 5
            and not line.strip().startswith('#!/')
        )
        total = len([l for l in lines if l.strip()])

        if total > 20 and commented / total > 0.25:
            findings.append(finding(
                'AN', 'LOW CONFIDENCE',
                f'High proportion of commented code in {f.name}',
                f'{commented} of {total} non-blank lines are comments '
                f'({commented*100//total}%). Large blocks of commented '
                f'code suggest earlier versions of the analysis may '
                f'be present. This is not a reproducibility error but '
                f'may indicate the committed code is not the final '
                f'version.',
                [f'Evidence: {commented*100//total}% commented lines '
                 f'in {f.name}']
            ))

    return findings


def detect_AO_r_specific_issues(repo_dir, all_files):
    findings = []
    r_files = [f for f in all_files if f.suffix.lower() in {'.r', '.rmd', '.qmd'}]
    if not r_files:
        return findings
    has_renv = any(f.name.lower() in {'renv.lock', 'packrat.lock'} for f in all_files)
    session_info_files = {'session_info.txt', 'session_info.log', 'sessioninfo.txt',
                          'r_session_info.txt', 'session-info.txt'}
    has_session_info = (
        any('sessionInfo()' in read_file_safe(f) for f in r_files) or
        any(f.name.lower() in session_info_files for f in all_files)
    )
    if not has_renv:
        findings.append(finding('AO', 'SIGNIFICANT',
            'R code present but no renv.lock found',
            'Without renv.lock validators cannot install exact package versions.',
            ['Missing: renv.lock', 'Run renv::init() and renv::snapshot()']))
    if not has_session_info:
        findings.append(finding('BN', 'LOW CONFIDENCE',
            'No sessionInfo() call found in R scripts',
            'sessionInfo() documents exact R and package versions used.',
            ['Recommendation: add sessionInfo() at end of main script']))
    return findings

def detect_AP_stata_specific(repo_dir, all_files):
    findings = []
    stata_files = [f for f in all_files if f.suffix.lower() in {'.do', '.ado'}]
    if not stata_files:
        return findings
    has_version = any(
        re.search(r'version\s+\d+', read_file_safe(f), re.MULTILINE)
        for f in stata_files
    )
    if not has_version:
        findings.append(finding('AP', 'SIGNIFICANT',
            'Stata do-files missing version declaration',
            'Without version declaration Stata behaviour differs between versions.',
            ['Missing: version XX at top of do-files']))
    return findings

def detect_AQ_large_model_files(repo_dir, all_files):
    return []

def detect_AR_encoding_issues(repo_dir, all_files):
    findings = []
    py_files = [f for f in all_files if f.suffix.lower() == '.py']
    bad = []
    for f in py_files:
        content = read_file_safe(f)
        if re.search(r'open\s*\(', content) and 'encoding=' not in content:
            bad.append(f.name)
    if len(bad) >= 2:
        findings.append(finding('AR', 'LOW CONFIDENCE',
            f'open() without encoding in {len(bad)} files',
            'open() without encoding behaves differently on Windows vs Linux/Mac.',
            [f'Files: {chr(44).join(bad[:5])}', 'Fix: add encoding="utf-8"']))
    return findings


def detect_AS_network_calls(repo_dir, all_files):
    findings = []
    code_files = [f for f in all_files if f.suffix.lower() in CODE_EXTENSIONS]
    net_pattern = re.compile(r'(requests\.|urllib\.|http\.client|wget\.|curl\.|httpx\.|aiohttp\.)', re.IGNORECASE)
    files_with_network = []
    for f in code_files:
        content = read_file_safe(f)
        if net_pattern.search(content):
            files_with_network.append(f.name)
    if files_with_network:
        findings.append(finding('AS', 'SIGNIFICANT',
            f'Network calls detected in {len(files_with_network)} file(s)',
            'Code makes network requests at runtime. These will fail without internet access or if remote resources move. Validators in restricted environments cannot reproduce results.',
            [f'Files: {", ".join(files_with_network[:5])}',
             'Recommendation: document all external dependencies and provide offline fallback']))
    return findings


def detect_AT_database_dependency(repo_dir, all_files):
    findings = []
    code_files = [f for f in all_files if f.suffix.lower() in CODE_EXTENSIONS]
    db_pattern = re.compile(r'(psycopg2|pymysql|sqlalchemy|sqlite3\.connect|pymongo|cx_Oracle|pyodbc|ibm_db|snowflake\.connector)', re.IGNORECASE)
    db_files = []
    for f in code_files:
        content = read_file_safe(f)
        if db_pattern.search(content):
            db_files.append(f.name)
    if db_files:
        findings.append(finding('AT', 'SIGNIFICANT',
            f'Database connections detected in {len(db_files)} file(s)',
            'Code connects to external databases. Validators cannot reproduce results without access to these databases. Document connection requirements and provide sample data or database dumps.',
            [f'Files with DB connections: {", ".join(db_files[:5])}',
             'Required: connection documentation or sample data export']))
    return findings


def detect_AU_cloud_storage(repo_dir, all_files):
    findings = []
    code_files = [f for f in all_files if f.suffix.lower() in CODE_EXTENSIONS]
    cloud_pattern = re.compile(r'(boto3|s3fs|gcsfs|azure\.storage|google\.cloud\.storage|gs://|s3://|azure://)', re.IGNORECASE)
    cloud_files = []
    for f in code_files:
        content = read_file_safe(f)
        if cloud_pattern.search(content):
            cloud_files.append(f.name)
    if cloud_files:
        findings.append(finding('AU', 'SIGNIFICANT',
            f'Cloud storage access detected in {len(cloud_files)} file(s)',
            'Code reads from or writes to cloud storage (S3, GCS, Azure). Validators require cloud credentials and access permissions to reproduce results.',
            [f'Files: {", ".join(cloud_files[:5])}',
             'Required: document storage buckets, access method, and credentials process']))
    return findings


def detect_AW_missing_doi(repo_dir, all_files):
    findings = []
    text_files = [f for f in all_files if f.suffix.lower() in {'.md', '.txt', '.rst'}]
    has_doi = False
    for f in text_files:
        content = read_file_safe(f).lower()
        if 'doi:' in content or 'doi.org' in content or 'zenodo' in content:
            has_doi = True
            break
    if not has_doi:
        findings.append(finding('AW', 'LOW CONFIDENCE',
            'No DOI or persistent identifier found in documentation',
            'No DOI, Zenodo link, or other persistent identifier was found. A DOI ensures the repository remains citable and accessible long-term.',
            ['Recommendation: deposit on Zenodo to get a DOI',
             'Add DOI badge to README']))
    return findings


def detect_AX_container_not_tested(repo_dir, all_files):
    findings = []
    has_dockerfile = any(f.name.lower() == 'dockerfile' for f in all_files)
    if not has_dockerfile:
        return findings
    dockerfile = next(f for f in all_files if f.name.lower() == 'dockerfile')
    content = read_file_safe(dockerfile)
    issues = []
    if 'COPY . .' in content or 'COPY ./' in content:
        if 'WORKDIR' not in content:
            issues.append('No WORKDIR set before COPY')
    if 'latest' in content.lower():
        issues.append('Base image uses :latest tag — pin to specific version')
    if 'RUN pip install' in content and 'requirements' not in content.lower():
        issues.append('pip install without requirements file — not reproducible')
    if issues:
        findings.append(finding('AX', 'SIGNIFICANT',
            'Dockerfile has reproducibility issues',
            'The Dockerfile contains patterns that may cause different builds on different runs.',
            issues))
    return findings


def detect_AY_workflow_file(repo_dir, all_files):
    findings = []
    has_python = any(f.suffix.lower() == '.py' for f in all_files)
    if not has_python:
        return findings
    ci_files = [f for f in all_files if f.suffix.lower() in {'.yml', '.yaml'}
                and any(ci in str(f).lower() for ci in ['github', 'gitlab', 'circle', 'travis', 'actions'])]
    if ci_files:
        findings.append(finding('AY', 'LOW CONFIDENCE',
            f'CI/CD workflow file(s) found — verify they test reproducibility',
            'Continuous integration workflows are present. Ensure they test that the full analysis pipeline runs successfully, not just code style checks.',
            [f'Workflow files: {", ".join(f.name for f in ci_files[:3])}']))
    return findings


def detect_AZ_figure_format(repo_dir, all_files):
    findings = []
    code_files = [f for f in all_files if f.suffix.lower() == '.py']
    bitmap_save = re.compile(r'savefig\s*\([^)]*\.(png|jpg|jpeg)[^)]*\)', re.IGNORECASE)
    vector_save = re.compile(r'savefig\s*\([^)]*\.(svg|eps|pdf)[^)]*\)', re.IGNORECASE)
    saves_bitmap = False
    saves_vector = False
    for f in code_files:
        content = read_file_safe(f)
        if bitmap_save.search(content):
            saves_bitmap = True
        if vector_save.search(content):
            saves_vector = True
    if saves_bitmap and not saves_vector:
        findings.append(finding('AZ', 'LOW CONFIDENCE',
            'Figures saved as bitmap only (PNG/JPG) — consider vector format',
            'Figures are saved as bitmap images. Vector formats (SVG, EPS, PDF) scale without quality loss and are preferred by journals. Bitmap figures may appear different at different resolutions.',
            ['Recommendation: save figures as SVG or PDF in addition to PNG']))
    return findings


def detect_BA_missing_checksums(repo_dir, all_files):
    findings = []
    data_files = [f for f in all_files if f.suffix.lower() in {'.csv', '.parquet', '.xlsx', '.dta'}]
    if len(data_files) < 2:
        return findings
    has_checksums = any(
        'checksum' in f.name.lower() or 'hash' in f.name.lower() or 'md5' in f.name.lower()
        for f in all_files
    )
    readme_has_checksums = False
    for f in all_files:
        if f.name.lower() in {'readme.md', 'readme.txt'}:
            content = read_file_safe(f).lower()
            if any(term in content for term in ['checksum', 'md5', 'sha256', 'hash']):
                readme_has_checksums = True
    if not has_checksums and not readme_has_checksums:
        findings.append(finding('BA', 'LOW CONFIDENCE',
            f'{len(data_files)} data files with no checksums documented',
            'No file checksums were found. Checksums allow validators to verify they have identical copies of the data files, ruling out download corruption as a source of discrepancy.',
            ['Recommendation: add MD5 or SHA256 checksums to README for key data files']))
    return findings


def detect_BB_script_permissions(repo_dir, all_files):
    findings = []
    shell_files = [f for f in all_files if f.suffix.lower() in {'.sh', '.bash'}]
    if not shell_files:
        return findings
    import stat as _stat
    non_executable = []
    for f in shell_files:
        try:
            mode = f.stat().st_mode
            if not (mode & _stat.S_IXUSR):
                non_executable.append(f.name)
        except Exception:
            pass
    if non_executable:
        findings.append(finding('BB', 'SIGNIFICANT',
            f'Shell scripts not marked executable: {", ".join(non_executable[:5])}',
            'Shell scripts exist but are not marked executable. Validators running these scripts will get permission denied errors.',
            [f'Fix: chmod +x {" ".join(non_executable[:5])}']))
    return findings


def detect_BC_mixed_line_endings(repo_dir, all_files):
    return []

def detect_BD_missing_contact(repo_dir, all_files):
    findings = []
    readme_file = None
    for f in all_files:
        if f.name.lower() in {'readme.md', 'readme.txt'}:
            readme_file = f
            break
    if not readme_file:
        return findings
    content = read_file_safe(readme_file).lower()
    has_contact = any(term in content for term in ['contact', 'author', 'email', 'correspondence', 'maintainer', '@'])
    if not has_contact:
        findings.append(finding('BD', 'LOW CONFIDENCE',
            'No contact information found in README',
            'No author contact information was found. Validators who encounter problems have no way to reach the researcher for clarification.',
            ['Recommendation: add author name and contact email to README']))
    return findings


def detect_BE_pyc_files(repo_dir, all_files):
    findings = []
    pyc_files = [f for f in all_files if f.suffix.lower() in {'.pyc', '.pyo'} or '__pycache__' in str(f)]
    if pyc_files:
        findings.append(finding('BE', 'SIGNIFICANT',
            f'{len(pyc_files)} compiled Python file(s) committed',
            'Compiled .pyc files are committed. These are system-specific and will cause import errors on different Python versions or operating systems. Add *.pyc and __pycache__/ to .gitignore.',
            [f'Files: {", ".join(f.name for f in pyc_files[:5])}',
             'Fix: git rm --cached **/*.pyc and add to .gitignore']))
    return findings


def detect_BF_notebook_outputs_missing(repo_dir, all_files):
    findings = []
    notebooks = [f for f in all_files if f.suffix.lower() == '.ipynb']
    if not notebooks:
        return findings
    import json as _json
    for nb in notebooks:
        try:
            data = _json.loads(nb.read_text(encoding='utf-8', errors='ignore'))
            cells = data.get('cells', [])
            has_outputs = any(
                cell.get('outputs') for cell in cells
                if cell.get('cell_type') == 'code'
            )
            if not has_outputs:
                findings.append(finding('BF', 'SIGNIFICANT',
                    f'Notebook has no saved outputs: {nb.name}',
                    'This notebook has no saved cell outputs. Validators cannot see what the original results looked like without running the notebook themselves.',
                    [f'Evidence: {nb.name} — all output cells empty']))
        except Exception:
            continue
    return findings


def detect_BG_missing_acknowledgements(repo_dir, all_files):
    findings = []
    readme_file = None
    for f in all_files:
        if f.name.lower() in {'readme.md', 'readme.txt'}:
            readme_file = f
            break
    if not readme_file:
        return findings
    content = read_file_safe(readme_file).lower()
    code_files = [f for f in all_files if f.suffix.lower() == '.py']
    if len(code_files) > 5:
        has_funding = any(term in content for term in ['grant', 'funded', 'funding', 'acknowledge', 'nsf', 'nih', 'esrc', 'ukri', 'erc', 'support'])
        if not has_funding:
            findings.append(finding('BG', 'LOW CONFIDENCE',
                'No funding acknowledgement found',
                'No funding acknowledgement was found. Most funders require acknowledgement in associated code repositories.',
                ['Recommendation: add funding source to README']))
    return findings


def detect_BH_zip_bomb_risk(repo_dir, all_files):
    findings = []
    zip_files = [f for f in all_files if f.suffix.lower() in {'.zip', '.gz', '.tar', '.bz2', '.7z'}]
    if zip_files:
        findings.append(finding('BH', 'LOW CONFIDENCE',
            f'{len(zip_files)} compressed archive(s) committed',
            'Compressed archives are committed. Validators need to know what these contain and whether to extract them as part of the pipeline.',
            [f'Archives: {", ".join(f.name for f in zip_files[:5])}',
             'Document: should validators extract these, and what do they contain?']))
    return findings


def detect_BI_unicode_in_paths(repo_dir, all_files):
    return []

def detect_AV_hardcoded_dates(repo_dir, all_files):
    return []


def detect_BM_citation_cff(repo_dir, all_files):
    """Check CITATION.cff exists and has required fields."""
    findings = []
    cff_files = [f for f in all_files if f.name.lower() == 'citation.cff']
    if not cff_files:
        findings.append(finding(
            'BM', 'LOW CONFIDENCE',
            'No CITATION.cff found',
            'A CITATION.cff file makes your repository directly citable '
            'and is increasingly expected by journals and data archives.',
            ['Recommendation: create CITATION.cff — see https://citation-file-format.github.io/']
        ))
        return findings
    # validate required fields
    try:
        content_cff = cff_files[0].read_text(encoding='utf-8', errors='ignore')
        # strip commented lines before checking
        active_lines = [l for l in content_cff.splitlines() if not l.strip().startswith('#')]
        active_content = '\n'.join(active_lines)
        required = ['title:', 'authors:', 'version:', 'date-released:']
        missing_fields = [f for f in required if f not in active_content]
        if missing_fields:
            findings.append(finding(
                'BJ', 'SIGNIFICANT',
                'CITATION.cff is missing required fields',
                'CITATION.cff was found but is incomplete. '
                'Missing fields will prevent automated citation tools from working correctly.',
                [f'Missing fields: {", ".join(missing_fields)}']
            ))
    except Exception:
        pass
    return findings


def detect_BN_codebook_reference_mismatch(repo_dir, all_files):
    """Check if README references a codebook file that doesn't exist."""
    findings = []
    readme_file = None
    for f in all_files:
        if f.name.lower() in {'readme.md', 'readme.txt', 'readme.rst'}:
            readme_file = f
            break
    if not readme_file:
        return findings
    try:
        content = readme_file.read_text(encoding='utf-8', errors='ignore').lower()
    except Exception:
        return findings
    import re as _re
    codebook_refs = _re.findall(r'codebook[\w\-]*\.\w+', content)
    all_names = {f.name.lower() for f in all_files}
    for ref in codebook_refs:
        if ref not in all_names:
            findings.append(finding(
                'BO', 'LOW CONFIDENCE',
                f'README references {ref} but file not found',
                'The README mentions a codebook or data dictionary file '
                'that does not appear to be present in the repository.',
                [f'Referenced: {ref}', f'Files present: {", ".join(n for n in all_names if "codebook" in n or "dict" in n) or "none"}']
            ))
    return findings


def detect_BP_licence_in_readme_only(repo_dir, all_files):
    """Check if licence is stated in README but no LICENCE file exists."""
    findings = []
    has_licence_file = any(
        f.name.lower() in {'licence', 'license', 'licence.md',
                           'license.md', 'licence.txt', 'license.txt'}
        for f in all_files
    )
    if has_licence_file:
        return findings
    readme_file = None
    for f in all_files:
        if f.name.lower() in {'readme.md', 'readme.txt', 'readme.rst'}:
            readme_file = f
            break
    if not readme_file:
        return findings
    try:
        content = readme_file.read_text(encoding='utf-8', errors='ignore').lower()
    except Exception:
        return findings
    licence_terms = ['cc by', 'cc-by', 'mit license', 'apache 2', 'gpl', 'creative commons']
    if any(term in content for term in licence_terms):
        findings.append(finding(
            'BP', 'LOW CONFIDENCE',
            'Licence stated in README but no LICENCE file found',
            'The README mentions a licence but no dedicated LICENCE file '
            'exists. A separate LICENCE file is standard practice and '
            'required by many repositories and journals.',
            ['Recommendation: create a LICENCE file with the full licence text']
        ))
    return findings


def detect_BO_codebook_reference_mismatch(repo_dir, all_files):
    """Check if README references a codebook file that does not exist."""
    findings = []
    readme_file = None
    for f in all_files:
        if f.name.lower() in {"readme.md", "readme.txt", "readme.rst"}:
            readme_file = f
            break
    if not readme_file:
        return findings
    try:
        content = readme_file.read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        return findings
    import re as _re
    codebook_refs = _re.findall(r"codebook[\w\-]*\.\w+", content)
    all_names = {f.name.lower() for f in all_files}
    for ref in codebook_refs:
        if ref not in all_names:
            findings.append(finding(
                "BO", "LOW CONFIDENCE",
                f"README references {ref} but file not found",
                "The README mentions a codebook file that is not present.",
                [f"Referenced: {ref}"]
            ))
    return findings


def detect_BP_licence_in_readme_only(repo_dir, all_files):
    """Check if licence stated in README but no LICENCE file exists."""
    findings = []
    has_licence_file = any(
        f.name.lower() in {"licence", "license", "licence.md",
                           "license.md", "licence.txt", "license.txt"}
        for f in all_files
    )
    if has_licence_file:
        return findings
    readme_file = None
    for f in all_files:
        if f.name.lower() in {"readme.md", "readme.txt", "readme.rst"}:
            readme_file = f
            break
    if not readme_file:
        return findings
    try:
        content = readme_file.read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        return findings
    if any(t in content for t in ["cc by", "cc-by", "mit license", "apache 2", "gpl", "creative commons"]):
        findings.append(finding(
            "BP", "LOW CONFIDENCE",
            "Licence stated in README but no LICENCE file found",
            "The README mentions a licence but no dedicated LICENCE file exists.",
            ["Recommendation: create a LICENCE file with the full licence text"]
        ))
    return findings


def detect_BR_credentials_exposed(repo_dir, all_files):
    """Check for exposed credentials, API keys, or passwords."""
    findings = []
    import re as _re
    cred_patterns = _re.compile(
        r'(password|passwd|api_key|api_secret|secret_key|token|auth_token'
        r'|private_key|access_key|client_secret|database_url)\s*[=:]\s*\S+',
        _re.IGNORECASE
    )
    env_files = [f for f in all_files if f.name.lower() in {
        '.env', '.env.local', '.env.production', '.env.development',
        'secrets.yml', 'secrets.yaml', 'credentials.json', 'credentials.yml'
    }]
    flagged = []
    evidence = []
    # always flag .env files present
    for f in env_files:
        flagged.append(f.name)
        evidence.append(f"Sensitive file present: {f.name}")
    # scan non-code config/secrets files for credential patterns
    # Source code (.py/.r/.jl) is handled by [AG] — avoid duplication
    code_exts = {'.py', '.r', '.rmd', '.jl', '.m'}
    check_exts = {'.yaml', '.yml', '.json', '.toml', '.cfg', '.ini', '.txt', '.md'}
    for f in all_files:
        if f.name.lower() in {ef.name.lower() for ef in env_files}:
            continue
        if f.suffix.lower() in code_exts:
            continue  # [AG] handles source code credentials
        if f.suffix.lower() not in check_exts:
            continue
        try:
            content = f.read_text(encoding='utf-8', errors='ignore')
            matches = cred_patterns.findall(content)
            if matches:
                flagged.append(f.name)
                # matches[0] is the captured group (key name), not a tuple
                key_name = matches[0] if isinstance(matches[0], str) else matches[0][0]
                evidence.append(f"{f.name}: credential pattern found ({key_name})")
        except Exception:
            pass
    if flagged:
        findings.append(finding(
            'BR', 'CRITICAL',
            f'Potential credentials or secrets detected in: {", ".join(flagged[:3])}',
            'Files containing passwords, API keys, or secrets must NEVER '
            'be published. Remove these files and rotate any exposed credentials '
            'immediately. Add .env to .gitignore before any further commits.',
            evidence[:5]
        ))
    return findings


def detect_BS_archive_code_present(repo_dir, all_files):
    """Check for vestigial code in archive/old directories."""
    findings = []
    archive_dirs = {"old", "archive", "deprecated", "unused", "backup", "old_versions"}
    archive_files = [
        f for f in all_files
        if f.suffix.lower() in CODE_EXTENSIONS
        and any(p.name.lower() in archive_dirs for p in f.parents)
    ]
    if archive_files:
        findings.append(finding(
            'BS', 'LOW CONFIDENCE',
            f'Vestigial code files found in archive directories: {", ".join(f.name for f in archive_files[:3])}',
            'Code files in old/, archive/, or deprecated/ directories suggest '
            'version history managed by file duplication rather than git. '
            'Remove these before deposit to avoid confusion about which files '
            'are part of the active pipeline.',
            [f'Archive file: {f.relative_to(repo_dir)}' for f in archive_files[:5]]
        ))
    return findings


def detect_BT_spaces_in_filenames(repo_dir, all_files):
    """Check for spaces in code or data filenames."""
    findings = []
    problem_files = [
        f for f in all_files
        if ' ' in f.name and f.suffix.lower() in CODE_EXTENSIONS | {'.csv', '.tsv', '.xlsx'}
    ]
    if problem_files:
        findings.append(finding(
            'BT', 'LOW CONFIDENCE',
            f'Spaces in filenames: {", ".join(f.name for f in problem_files[:3])}',
            'Filenames with spaces cause shell execution failures unless quoted. '
            'Replace spaces with underscores before deposit.',
            [f'Problem file: {f.name}' for f in problem_files[:5]]
        ))
    return findings










def detect_CR_crlf_line_endings(repo_dir, all_files):
    """Failure Mode CR: Shell script has Windows CRLF line endings — will fail on Linux/macOS."""
    findings = []
    shell_files = [f for f in all_files if f.suffix.lower() in {'.sh', '.bash'}
                   or (f.suffix == '' and f.name.lower() in {'makefile'})]
    for f in shell_files:
        try:
            raw = f.read_bytes()
            if b'\r\n' in raw:
                findings.append(finding(
                    'CR', 'SIGNIFICANT',
                    f'Shell script has Windows CRLF line endings — will fail on Linux/macOS: {f.name}',
                    f'{f.name} contains Windows-style CRLF (\\r\\n) line endings. '
                    'On Linux/macOS, bash interprets the \\r as part of the interpreter '
                    'path, causing: /bin/bash^M: bad interpreter: No such file or directory.',
                    [f'File: {f.name} — CRLF endings detected',
                     'Fix: run dos2unix ' + f.name,
                     'Or: sed -i \'s/\\r//\' ' + f.name]
                ))
        except Exception:
            pass
    return findings


def detect_CF_notebook_outputs_committed(repo_dir, all_files):
    """Failure Mode CF: Jupyter notebook has committed cell outputs — may contain sensitive data or large blobs."""
    findings = []
    import json as _json
    notebooks = [f for f in all_files if f.suffix.lower() == '.ipynb']
    for nb in notebooks:
        try:
            data = _json.loads(nb.read_text(encoding='utf-8', errors='ignore'))
            cells = data.get('cells', [])
            output_cells = []
            large_output = False
            for i, cell in enumerate(cells):
                if cell.get('cell_type') == 'code':
                    outputs = cell.get('outputs', [])
                    if outputs:
                        output_cells.append(i + 1)
                        for out in outputs:
                            # Check for embedded images (large base64 blobs)
                            data_block = out.get('data', {})
                            if 'image/png' in data_block or 'image/jpeg' in data_block:
                                large_output = True
            if output_cells:
                findings.append(finding(
                    'CF', 'LOW CONFIDENCE',
                    f'Notebook has committed cell outputs: {nb.name}',
                    'Cell outputs are embedded in the notebook file. This inflates '
                    'repository size, may contain sensitive data (file paths, user info '
                    'in tracebacks), and makes diffs unreadable. Best practice is to '
                    'strip outputs before committing and regenerate by running the notebook.',
                    [f'Cells with outputs: {len(output_cells)} cells',
                     'Contains embedded images: ' + ('Yes' if large_output else 'No'),
                     'Fix: jupyter nbconvert --ClearOutputPreprocessor.enabled=True '
                     '--to notebook --inplace ' + nb.name]
                ))
        except Exception:
            continue
    return findings

def detect_CE_unpinned_github_packages(repo_dir, all_files):
    """Failure Mode CE: devtools::install_github() calls without commit/tag pin."""
    findings = []
    r_files = [f for f in all_files if f.suffix.lower() in {'.r', '.rmd'}]
    github_pattern = re.compile(
        r'(?:devtools|remotes)::install_github\s*\(\s*["\'][^"\']+/([\w.-]+)["\'][^)]*\)',
        re.IGNORECASE
    )
    unpinned = []
    for f in r_files:
        try:
            src = f.read_text(encoding='utf-8', errors='ignore')
            for m in github_pattern.finditer(src):
                pkg = m.group(1)
                # Pinned if @ present (commit sha or tag)
                if '@' not in pkg:
                    unpinned.append(pkg)
        except Exception:
            pass
    if unpinned:
        findings.append(finding(
            'CE', 'SIGNIFICANT',
            f'GitHub R packages installed without commit or version pin: {", ".join(unpinned[:4])}',
            'devtools::install_github() calls found with no @commit or @tag specified. '
            'These will always install the current HEAD — a different version than '
            'what was used in the original analysis. Results may not be reproducible.',
            [f'Unpinned: {p}' for p in unpinned[:5]] +
            ['Fix: pin each call, e.g. install_github("YuLab-SMU/ggtree@a1b2c3d")',
             'Or use renv to lock all package versions including GitHub sources']
        ))
    return findings

def detect_CD_dockerfile_run_before_copy(repo_dir, all_files):
    """Failure Mode CD: Dockerfile has RUN pip install before COPY — build will fail."""
    findings = []
    dockerfiles = [f for f in all_files if f.name.lower() == 'dockerfile']
    for df in dockerfiles:
        try:
            raw = df.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        if not raw:
            continue
        # Strip comment lines and blank lines for analysis but keep original for evidence
        orig_lines = raw.splitlines()
        # Find index of first COPY or ADD instruction
        first_copy_idx = None
        for i, line in enumerate(orig_lines):
            s = line.strip()
            if s.startswith('#') or not s:
                continue
            if s.upper().startswith('COPY') or s.upper().startswith('ADD '):
                first_copy_idx = i
                break
        if first_copy_idx is None:
            continue
        # Check if any pip/conda install RUN appears before first COPY
        for i, line in enumerate(orig_lines):
            if i >= first_copy_idx:
                break
            s = line.strip()
            if s.startswith('#') or not s:
                continue
            su = s.upper()
            if su.startswith('RUN') and ('PIP INSTALL' in su or 'CONDA INSTALL' in su or 'PIP3 INSTALL' in su):
                findings.append(finding(
                    'CD', 'SIGNIFICANT',
                    'Dockerfile has RUN pip install before COPY — build will fail',
                    f'The RUN pip install command on line {i+1} executes before '
                    f'the COPY instruction on line {first_copy_idx+1}. '
                    'The requirements file does not yet exist in the container '
                    'at build time, causing an immediate build failure.',
                    [f'Line {i+1}: {orig_lines[i].strip()}',
                     f'Line {first_copy_idx+1}: {orig_lines[first_copy_idx].strip()}',
                     'Fix: add "COPY requirements.txt ." before the RUN pip install line']
                ))
                break
    return findings

def detect_CB_snakemake_no_env_isolation(repo_dir, all_files):
    """Failure Mode CB: Snakemake workflow has no per-rule environment isolation."""
    findings = []
    snake_files = [f for f in all_files
                   if f.name == 'Snakefile' or f.suffix.lower() == '.smk']
    if not snake_files:
        return findings
    for f in snake_files:
        content = read_file_safe(f)
        if not content:
            continue
        # Count rules
        rules = re.findall(r'^rule\s+\w+', content, re.MULTILINE)
        if not rules:
            continue
        has_conda = 'conda:' in content
        has_container = 'container:' in content or 'singularity:' in content
        if not has_conda and not has_container:
            findings.append(finding(
                'CB', 'SIGNIFICANT',
                f'Snakemake workflow has no per-rule environment isolation: {f.name}',
                f'No rule in {f.name} has a conda: or container: directive. '
                'Without these, the workflow depends on tools being available '
                'on PATH with no version control. Different tool versions '
                'will produce different results.',
                [f'Rules found: {", ".join(r.split()[1] for r in rules[:5])}',
                 'Fix: add conda: directives with environment YAML files to each rule,',
                 'or use container: with a Docker/Singularity image']
            ))
    return findings


def detect_CC_undocumented_external_tools(repo_dir, all_files):
    """Failure Mode CC: README mentions external tools on PATH with no version specified."""
    findings = []
    # Scan README and shell scripts for tool references
    scan_files = [f for f in all_files
                  if f.name.lower() in {'readme.md', 'readme.txt', 'readme.rst'}
                  and len(f.relative_to(repo_dir).parts) <= 2]
    scan_files += [f for f in all_files if f.suffix.lower() in {'.sh', '.bash'}]
    if not scan_files:
        return findings
    content = '\n'.join(read_file_safe(f) or '' for f in scan_files)
    if not content:
        return findings
    # Common bioinformatics/scientific CLI tools
    tool_pattern = re.compile(
        r'\b(bwa|samtools|gatk|bcftools|bowtie2|hisat2|star|kallisto|salmon'
        r'|bedtools|picard|trimmomatic|fastqc|multiqc|varscan|snpeff'
        r'|minimap2|blastn|blastp|makeblastdb|cellranger|seqkit'
        r'|trim_galore|featurecounts|subread|rsem|deseq2|edger|bismark'
        r'|bamtools|deeptools|macs2|homer|stringtie|cufflinks)\b',
        re.IGNORECASE
    )
    tools_found = sorted(set(m.group(1).lower() for m in tool_pattern.finditer(content)))
    if not tools_found:
        return findings
    # Check if versions are mentioned near tool names
    unversioned = []
    for tool in tools_found:
        # Look for version number near tool mention
        tool_ctx = re.search(rf'\b{tool}\b.{{0,80}}', content, re.IGNORECASE)
        if tool_ctx:
            ctx = tool_ctx.group(0)
            if not re.search(r'v?\d+\.\d+', ctx):
                unversioned.append(tool)
    if unversioned:
        findings.append(finding(
            'CC', 'SIGNIFICANT',
            f'External tools required but versions not specified: {", ".join(unversioned[:5])}',
            'The README references external tools that must be on PATH, but no '
            'version numbers are specified. Different versions of these tools '
            '(e.g. GATK v3 vs v4) have completely different command-line interfaces '
            'and may produce different results.',
            [f'Unversioned tools: {", ".join(unversioned)}',
             'Fix: specify exact versions in README System Requirements section']
        ))
    return findings

def detect_CA_readme_script_missing(repo_dir, all_files):
    """Failure Mode CA: Script referenced in README does not exist in repository."""
    findings = []
    # Scan README and shell scripts for tool references
    scan_files = [f for f in all_files
                  if f.name.lower() in {'readme.md', 'readme.txt', 'readme.rst'}
                  and len(f.relative_to(repo_dir).parts) <= 2]
    scan_files += [f for f in all_files if f.suffix.lower() in {'.sh', '.bash'}]
    if not scan_files:
        return findings
    content = '\n'.join(read_file_safe(f) or '' for f in scan_files)
    if not content:
        return findings
    # Find references to script files in README
    script_pattern = re.compile(
        r'(?:python|Rscript|julia|bash|sh|matlab)\s+([\w/.-]+\.(?:py|r|jl|sh|m|do))\b',
        re.IGNORECASE
    )
    all_file_paths = {str(f.relative_to(repo_dir)).replace('\\', '/') for f in all_files}
    all_file_names = {f.name.lower() for f in all_files}
    missing = []
    for m in script_pattern.finditer(content):
        ref = m.group(1)
        ref_name = ref.split('/')[-1].lower()
        # Check if referenced file exists anywhere in repo
        if ref_name not in all_file_names and ref not in all_file_paths:
            if ref not in missing:
                missing.append(ref)
    if missing:
        findings.append(finding(
            'CA', 'SIGNIFICANT',
            f'Script(s) referenced in README not found in repository: {", ".join(missing)}',
            'The README describes running scripts that do not exist in the repository. '
            'Validators following the README instructions will immediately encounter '
            'file-not-found errors. Either the script was accidentally omitted from '
            'the deposit or the README refers to an outdated filename.',
            [f'Missing: {s}' for s in missing] +
            ['Fix: add the missing script(s) to the repository or update the README']
        ))
    return findings

def detect_BZ_matlab_v73_format(repo_dir, all_files):
    """Failure Mode BZ: MATLAB .mat file saved with -v7.3 flag (HDF5) — version compatibility risk."""
    findings = []
    v73_pattern = re.compile(r'v7\.3|-v7\.3|HDF5|R2011b', re.IGNORECASE)
    flagged = []
    for f in all_files:
        if f.suffix.lower() in {'.m', '.txt', '.md', '.rst'}:
            try:
                content = read_file_safe(f)
                if v73_pattern.search(content):
                    flagged.append(f.name)
            except Exception:
                pass
    if flagged:
        findings.append(finding(
            'BZ', 'SIGNIFICANT',
            'MATLAB data file uses v7.3 (HDF5) format — version compatibility risk',
            'One or more .mat files appear to have been saved with the -v7.3 flag '
            '(HDF5 format). This requires MATLAB R2011b or later to load. '
            'Validators using older versions will be unable to read the data. '
            'Document this version requirement explicitly in your README.',
            [f'Evidence found in: {", ".join(flagged)}',
             'Fix: add "Requires MATLAB R2011b or later" to README System Requirements']
        ))
    return findings

def detect_BY_julia_missing_manifest(repo_dir, all_files):
    """Failure Mode BY: Julia repo has Project.toml but no Manifest.toml."""
    findings = []
    names_lower = {f.name.lower() for f in all_files}
    if 'project.toml' not in names_lower:
        return findings
    if 'manifest.toml' in names_lower:
        return findings
    findings.append(finding(
        'BY', 'SIGNIFICANT',
        'Julia Manifest.toml missing',
        'Project.toml found but no Manifest.toml present. Without a manifest, '
        'julia --project=. -e "using Pkg; Pkg.instantiate()" resolves packages '
        'to the latest compatible versions, not the exact versions used at '
        'publication. Validators may get different package versions than you used.',
        ['Project.toml present — compat bounds specified',
         'Manifest.toml absent — exact versions unspecified',
         'Fix: run julia --project=. -e "using Pkg; Pkg.resolve(); Pkg.instantiate()" '
         'then commit the generated Manifest.toml']
    ))
    return findings

def detect_BX_pluto_empty_manifest(repo_dir, all_files):
    """Failure Mode BX: Pluto notebook has PLUTO_MANIFEST_TOML_CONTENTS but it is empty."""
    findings = []
    for f in all_files:
        if f.suffix.lower() != '.jl':
            continue
        try:
            content = read_file_safe(f)
            if not content:
                continue
            if 'PLUTO_PROJECT_TOML_CONTENTS' not in content:
                continue
            # Check manifest
            manifest_match = re.search(
                r'PLUTO_MANIFEST_TOML_CONTENTS\s*=\s*"([^"]*)"', content, re.DOTALL)
            if manifest_match and len(manifest_match.group(1).strip()) == 0:
                findings.append(finding(
                    'BX', 'SIGNIFICANT',
                    f'Pluto notebook has empty manifest: {f.name}',
                    'PLUTO_MANIFEST_TOML_CONTENTS is present but empty. '
                    'Without a populated manifest, Pluto resolves packages '
                    'to the latest compatible versions rather than the exact '
                    'versions used at publication. Open the notebook in Pluto, '
                    'allow it to resolve dependencies, then save to populate '
                    'the manifest before depositing.',
                    [f'File: {f.name}',
                     'PLUTO_MANIFEST_TOML_CONTENTS = "" (empty)',
                     'Fix: open in Pluto and save — manifest will be populated automatically']
                ))
        except Exception:
            pass
    return findings

def detect_BU_conda_channel_priority(repo_dir, all_files):
    """Failure Mode BU: Conda environment.yml mixes channels without strict priority."""
    findings = []
    env_files = [f for f in all_files
                 if f.name.lower() in {'environment.yml', 'environment.yaml'}]
    for f in env_files:
        txt = read_file_safe(f)
        if not txt or 'channels:' not in txt:
            continue
        import re as _re2
        m = _re2.search(r'channels:\s*\n((?:\s*-[^\n]+\n)*)', txt)
        if not m:
            continue
        channel_lines = _re2.findall(r'-\s*(\S+)', m.group(1))
        if len(channel_lines) < 2:
            continue
        if 'channel_priority: strict' not in txt:
            findings.append(finding(
                'BU', 'SIGNIFICANT',
                f'Conda channels mixed without strict priority in {f.name}',
                f'Mixing channels ({", ".join(channel_lines)}) without '
                f'channel_priority: strict causes non-deterministic package '
                f'resolution. Conda may silently install packages from '
                f'unexpected channels, producing different environments on '
                f'different machines.',
                [f'Channels listed: {", ".join(channel_lines)}',
                 f'Fix: add "channel_priority: strict" to {f.name} above the channels: block']
            ))
    return findings


def detect_BV_shell_no_set_e(repo_dir, all_files):
    """Failure Mode BV: Shell pipeline script has no error handling (set -e missing)."""
    findings = []
    shell_files = [f for f in all_files if f.suffix.lower() in {'.sh', '.bash'}]
    for f in shell_files:
        txt = read_file_safe(f)
        if not txt or not txt.startswith('#!'):
            continue
        lines = [l for l in txt.splitlines() if l.strip() and not l.strip().startswith('#')]
        if len(lines) < 3:
            continue
        if 'set -e' not in txt and 'set -o errexit' not in txt:
            findings.append(finding(
                'BV', 'SIGNIFICANT',
                f'Shell pipeline has no error handling: {f.name}',
                'Without set -e, the pipeline will continue executing '
                'even if a step fails. Later steps may run on missing '
                'or corrupt inputs without any error being raised, '
                'producing silent garbage output.',
                [f'File: {f.name}',
                 'Fix: add "set -e" on the line immediately after the shebang (#!)',
                 'Optionally also add "set -o pipefail" to catch pipeline errors']
            ))
    return findings

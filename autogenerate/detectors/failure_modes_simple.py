"""
ValiChord Auto-Generate
Simple (pattern-matching) failure mode detectors
Implements failure modes from ValiChord Specification v15
"""

import re
from pathlib import Path


# ── file classification helpers ──────────────────────────────────────────────

CODE_EXTENSIONS = {
    '.py', '.r', '.rmd', '.qmd', '.jl', '.m', '.sh', '.bash',
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

    if not names.intersection(README_NAMES):
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
            if f.name.lower() in README_NAMES:
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
    has_code = bool(code_files)

    if has_code and not has_dep_file:
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
                break
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
        if f.name.lower() in README_NAMES:
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
        r'.*?(f["\']|format|str|%)',
        re.DOTALL
    )
    clock_as_seed = re.compile(
        r'(seed|random)\s*\(.*?(datetime\.now|time\.time)',
        re.DOTALL
    )

    for f in code_files:
        content = read_file_safe(f)
        if clock_in_filename.search(content):
            findings.append(finding(
                'BK', 'SIGNIFICANT',
                f'System clock used in filename generation: {f.name}',
                'Output filenames derived from datetime.now() or '
                'time.time() will differ between runs, making '
                'comparison of researcher and validator outputs '
                'impossible.',
                [f'Evidence: {f.name} — clock-based filename pattern']
            ))
        elif clock_as_seed.search(content):
            findings.append(finding(
                'BK', 'SIGNIFICANT',
                f'System clock used as random seed: {f.name}',
                'Seeds derived from the system clock change with '
                'every run, producing different results each time.',
                [f'Evidence: {f.name} — clock-based seed pattern']
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
    all_findings += detect_V_virtual_environment(repo_dir, all_files)
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
        'scipy': 'np.random.seed()',
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

    readme_file = None
    for f in all_files:
        if f.name.lower() in {'readme.md', 'readme.txt', 'readme.rst'}:
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

    missing = []
    for section, keywords in required_sections.items():
        if not any(kw in content_lower for kw in keywords):
            missing.append(section)

    if len(missing) >= 3:
        findings.append(finding(
            'G', 'SIGNIFICANT',
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


def detect_V_virtual_environment(repo_dir, all_files):
    """Failure Mode V: No virtual environment specification."""
    findings = []

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

    version_pattern = re.compile(r'python\s*[=><!\s]+\s*(\d+\.\d+)', re.IGNORECASE)
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
        r'|readRDS|read\.csv|read_dta|haven::read)'
        r'\s*\(\s*["\']([^"\']+)["\']',
        re.IGNORECASE
    )

    missing_refs = set()
    for f in code_files:
        content = read_file_safe(f)
        for match in read_pattern.finditer(content):
            filepath = match.group(1)
            fname = filepath.replace('\\', '/').split('/')[-1].lower()
            stem = fname.rsplit('.', 1)[0] if '.' in fname else fname
            if fname and '.' in fname:
                if (fname not in all_filenames
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
        'tensorflow', 'keras', 'r', 'stata', 'matlab'
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

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
    """Failure Mode C: Absolute paths in code."""
    findings = []
    code_files = [f for f in all_files
                  if f.suffix.lower() in CODE_EXTENSIONS]

    # patterns for absolute paths
    abs_path_patterns = [
        r'["\']C:\\\\[^"\']+["\']',           # Windows C:\
        r'["\']C:/[^"\']+["\']',              # Windows C:/
        r'["\'][D-Z]:/[^"\']+["\']',          # Windows other drives
        r'["\'][D-Z]:\\\\[^"\']+["\']',
        r'["\']["\']',
        r'["\']/Users/[^"\']+["\']',          # macOS home
        r'["\']/home/[^"\']+["\']',           # Linux home
        r'["\']/mnt/[^"\']+["\']',            # Linux mount
    ]

    combined = re.compile('|'.join(abs_path_patterns))

    for f in code_files:
        content = read_file_safe(f)
        for i, line in enumerate(content.splitlines(), 1):
            if combined.search(line):
                # skip comment lines
                stripped = line.strip()
                if not stripped.startswith('#') \
                        and not stripped.startswith('//'):
                    findings.append(finding(
                        'C', 'SIGNIFICANT',
                        f'Absolute path detected in {f.name}',
                        'Absolute paths break reproducibility — '
                        'they only work on the researcher\'s machine. '
                        'A corrected copy with relative paths will be '
                        'generated in /proposed_corrections/.',
                        [f'Evidence: {f.name} line {i}: '
                         f'{line.strip()[:80]}']
                    ))
                    break  # one finding per file is enough

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

    return all_findings
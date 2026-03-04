"""
ValiChord Auto-Generate
Draft File Generator
Produces all _DRAFT output files per ValiChord Specification v15
"""

from pathlib import Path
import re
from datetime import datetime
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..'))
from detectors.failure_modes_simple import (
    DATA_EXTENSIONS as _DATA_EXTENSIONS,
    ARCHIVE_EXTENSIONS as _ARCHIVE_EXTENSIONS,
    _inspect_archive,
    _is_single_file_compressed,
    CODEBOOK_FILENAMES as _CODEBOOK_FILENAMES,
    _looks_like_codebook,
    _researcher_r_files,
)


CODE_EXTENSIONS = {
    '.py', '.r', '.rmd', '.qmd', '.jl', '.m', '.sh', '.bash', '.smk', '.nf', '.groovy',
    '.do', '.sas', '.ado', '.c', '.cpp', '.f', '.f90',
    '.sql', '.rs', '.go', '.java', '.js', '.ts'
}

NOTEBOOK_EXTENSIONS = {'.ipynb', '.mlx', '.rmd', '.qmd'}

# Gretl script/model files — classified as Code in inventory but not subject to
# pip/conda dependency checks (Gretl manages its own environment)
GRETL_EXTENSIONS = {'.inp', '.gfn'}

_ALL_CODE_EXTENSIONS = CODE_EXTENSIONS | GRETL_EXTENSIONS

README_NAMES = {'readme.md', 'readme.txt', 'readme.rst', 'readme'}

# Vendored / third-party directories excluded from QUICKSTART script listing
VENDOR_DIRS_QS = {'weka', 'vendor', 'lib', 'dist', 'node_modules', 'target'}

# Bioconductor packages — must be installed via BiocManager::install(), NOT install.packages().
# Putting these inside install.packages() silently fails.
BIOCONDUCTOR_PACKAGES = frozenset({
    'DESeq2', 'edgeR', 'limma', 'BiocGenerics', 'GenomicRanges',
    'GenomicFeatures', 'Biostrings', 'IRanges', 'S4Vectors',
    'SummarizedExperiment', 'SingleCellExperiment', 'scran', 'scater',
    'phyloseq', 'microbiome', 'metagenomeSeq',
    'DADA2', 'dada2',
    'clusterProfiler', 'fgsea', 'enrichplot', 'pathview',
    'VariantAnnotation', 'BSgenome', 'AnnotationDbi',
    'org.Hs.eg.db', 'org.Mm.eg.db', 'biomaRt', 'GEOquery',
    'mzR', 'xcms', 'MSnbase', 'mixOmics', 'WGCNA',
    'ComplexHeatmap', 'EnhancedVolcano', 'ggbio', 'Gviz',
    'tximport', 'DEXSeq', 'sva', 'ChIPseeker', 'DiffBind',
    'Rsamtools', 'GenomicAlignments', 'ShortRead',
})
# Case-insensitive lookup set
_BIOC_LOWER = frozenset(p.lower() for p in BIOCONDUCTOR_PACKAGES)

# Packages believed to be GitHub-only (not on CRAN or Bioconductor).
# These need devtools::install_github(); install command must be verified.
GITHUB_LIKELY_PACKAGES = frozenset({'HTSSIP', 'SIPmg', 'qsip', 'microbiomeutilities',
                                     'rnaturalearthhires'})
_GITHUB_LIKELY_LOWER = frozenset(p.lower() for p in GITHUB_LIKELY_PACKAGES)

# Known GitHub repo slugs for common GitHub-only packages
_GITHUB_KNOWN_SLUGS = {
    'htssip':               'buckleylab/HTSSIP',
    'sipmg':                'mcallaghanTU/SIPmg',
    'qsip':                 'bramstone/qsip',
    'microbiomeutilities':  'microsud/microbiomeutilities',
    'rnaturalearthhires':   'ropensci/rnaturalearthhires',
}

# Packages removed or retired from CRAN — require special handling.
# Key: lowercase package name. Value: explanation + suggested replacement.
REMOVED_FROM_CRAN = {
    'tsoutliers':         'removed from CRAN in 2022 — use forecast::tsoutliers() instead, or install from archive: devtools::install_version("tsoutliers", version="0.1-2")',
    'reshape':            'superseded — use reshape2 or tidyr instead',
    'rgdal':              'retired 2023 — use sf or terra instead',
    'rgeos':              'retired 2023 — use sf or geos instead',
    'maptools':           'retired 2023 — use sf instead',
    'userfriendlyscience':'superseded around 2019 — split into rosetta, psych, and other packages; may only be available from archive',
    'lsmeans':            'superseded by emmeans — still on CRAN as a thin wrapper but generates deprecation warnings; use emmeans instead',
}
_REMOVED_CRAN_LOWER = {k.lower(): v for k, v in REMOVED_FROM_CRAN.items()}

# Per-package README warning lines for removed-from-CRAN packages
_REMOVED_CRAN_README_LINES = {
    'tsoutliers': [
        '# tsoutliers was removed from CRAN in 2022.',
        '# Use forecast::tsoutliers() as a replacement, or install from archive:',
        '# devtools::install_version("tsoutliers", version = "0.1-2", repos = "http://cran.r-project.org")',
    ],
    'reshape': [
        '# reshape was superseded — use reshape2 or tidyr instead:',
        '# install.packages("reshape2")  # or: install.packages("tidyr")',
    ],
    'rgdal': [
        '# rgdal was retired in 2023 — use sf or terra instead:',
        '# install.packages("sf")  # or: install.packages("terra")',
    ],
    'rgeos': [
        '# rgeos was retired in 2023 — use sf or geos instead:',
        '# install.packages("sf")  # or: install.packages("geos")',
    ],
    'maptools': [
        '# maptools was retired in 2023 — use sf instead:',
        '# install.packages("sf")',
    ],
    'userfriendlyscience': [
        '# userfriendlyscience was superseded around 2019 — split into multiple packages.',
        '# Use rosetta or psych as replacements, or install from archive:',
        '# devtools::install_version("userfriendlyscience", repos = "http://cran.r-project.org")',
    ],
    'lsmeans': [
        '# lsmeans is superseded by emmeans (still on CRAN as wrapper but deprecated):',
        '# install.packages("emmeans")  # recommended replacement',
    ],
}

# Frontend-directory detection — mirrors the constants in failure_modes_simple.py.
# A dir is frontend if it has JS/HTML/CSS AND no analysis-code extension.
# We do NOT require all extensions to be in an allowlist so that dirs with
# .sb3, .wav, .mp3, etc. are still correctly identified as frontend dirs.
_FRONTEND_MARKERS_QS = frozenset({'.js', '.html', '.css', '.jsx', '.ts', '.tsx', '.vue'})
_ANALYSIS_CODE_EXTS_QS = frozenset({
    '.py', '.r', '.do', '.jl', '.m', '.sas', '.ipynb',
    '.rmd', '.qmd', '.sh', '.bash', '.f90', '.f', '.cpp', '.c',
    '.java', '.nf', '.smk', '.ado', '.rs', '.go', '.scala', '.sql',
})


def _is_minified_qs(f):
    """Return True if a file appears to be a minified or bundled frontend asset."""
    name_lower = f.name.lower()
    stem_lower = f.stem.lower()
    return (
        name_lower.endswith('.min.js') or name_lower.endswith('.min.css')
        or stem_lower in {'lib.min', 'vendor.min', 'bundle.min'}
        or stem_lower.startswith('chunk')
    )

DEPENDENCY_FILES = {
    'requirements.txt', 'requirements_extra.txt', 'environment.yml', 'environment.yaml',
    'pipfile.lock', 'poetry.lock', 'setup.py', 'pyproject.toml',
    'renv.lock', 'cargo.toml', 'package.json'
}

# Base-R packages that ship with every R installation — silently excluded from
# requirements_DRAFT.txt (they are not CRAN packages to be installed).
_BASE_R_PACKAGES = {
    'base', 'methods', 'utils', 'stats', 'graphics', 'grDevices', 'datasets',
    'tools', 'grid', 'parallel', 'splines', 'tcltk', 'compiler',
    'translations', 'Matrix',
    # Base R function names that appear as quoted strings (e.g. column names)
    # and are not installable packages.
    'names', 'length', 'class', 'typeof', 'dim', 'nrow', 'ncol',
    'colnames', 'rownames', 'levels', 'labels', 'attr', 'attributes',
}

# Well-known CRAN packages (case-sensitive as registered on CRAN).
# Packages here get a clean '  # version unknown' line; others are checked
# against the suspicious-name heuristic.
_KNOWN_CRAN = {
    # Core tidyverse
    'ggplot2', 'dplyr', 'tidyr', 'readr', 'purrr', 'tibble', 'stringr', 'forcats',
    'lubridate', 'hms', 'glue', 'rlang', 'vctrs', 'pillar', 'cli', 'crayon',
    'tidyverse', 'tidyselect', 'broom', 'tidymodels', 'tidylog',
    # Data manipulation
    'data.table', 'reshape2', 'plyr', 'dtplyr', 'dbplyr', 'janitor', 'skimr',
    # Modelling
    'lme4', 'nlme', 'mgcv', 'MASS', 'car', 'glmnet', 'caret', 'randomForest',
    'survival', 'rms', 'emmeans', 'lmerTest', 'multcomp', 'sandwich', 'lmtest',
    'gam', 'gamm4', 'brms', 'rstanarm', 'bayesplot', 'posterior', 'rstan',
    'MCMCglmm', 'glmmTMB',
    'arm', 'AER', 'ivreg', 'logistf', 'geepack', 'VGAM',
    # Visualisation
    'scales', 'ggthemes', 'ggrepel', 'cowplot', 'patchwork', 'ggridges',
    'lattice', 'gridExtra', 'RColorBrewer', 'viridis', 'viridisLite', 'colorspace',
    'plotly', 'ggpubr', 'ggcorrplot', 'corrplot', 'GGally', 'pheatmap',
    # IO
    'readxl', 'writexl', 'haven', 'foreign', 'jsonlite', 'xml2', 'httr', 'httr2',
    'curl', 'openxlsx', 'DBI', 'RSQLite', 'RPostgres', 'RMySQL',
    # Statistics
    'psych', 'DescTools', 'Hmisc', 'PerformanceAnalytics', 'effectsize',
    'rstatix', 'coin', 'boot', 'rsample', 'yardstick', 'pwr', 'ROCR', 'pROC',
    'irr', 'vcd', 'exact2x2', 'BayesFactor', 'MCMCpack',
    # ML / predictive modelling
    'xgboost', 'lightgbm', 'keras', 'reticulate', 'ranger', 'e1071', 'kernlab',
    'nnet', 'neuralnet', 'parsnip', 'tune', 'recipes', 'workflows', 'stacks',
    # Spatial
    'sf', 'sp', 'raster', 'terra', 'leaflet',
    'tmap', 'ggmap', 'maps', 'mapdata', 'spdep', 'spatstat',
    # Text / NLP
    'tm', 'tidytext', 'quanteda', 'text2vec', 'wordcloud', 'topicmodels',
    'stm', 'textrank', 'udpipe', 'sentimentr', 'tokenizers',
    # Bioinformatics (Bioconductor)
    'DESeq2', 'edgeR', 'limma', 'Biobase', 'BiocGenerics', 'GenomicRanges',
    'ggbio', 'clusterProfiler', 'enrichplot', 'pathview', 'ComplexHeatmap',
    'Seurat', 'scater', 'SingleCellExperiment', 'scran', 'scuttle',
    # Reporting / Shiny
    'knitr', 'rmarkdown', 'shiny', 'shinydashboard', 'DT', 'reactable',
    'flexdashboard', 'bookdown', 'distill', 'gt', 'flextable', 'kableExtra',
    'htmltools', 'htmlwidgets', 'crosstalk',
    # Utilities
    'here', 'fs', 'withr', 'usethis', 'devtools', 'remotes', 'renv', 'pak',
    'doParallel', 'foreach', 'future', 'furrr', 'progressr', 'R.utils',
    'R6', 'proto', 'magrittr', 'zeallot', 'assertthat', 'checkmate',
    # Time series
    'zoo', 'xts', 'forecast', 'tseries', 'fable', 'feasts', 'tsibble',
    # Short legitimate names
    'ks', 'mvtnorm', 'AUC',
    # Tables / reporting
    'xtable',
    # Post-hoc / non-parametric tests
    'PMCMRplus',
}
_KNOWN_CRAN_LOWER = {p.lower() for p in _KNOWN_CRAN}


def _check_cran_package(name: str) -> str:
    """Return 'found', 'not_found', or 'unknown' for an R package name.

    Queries crandb.r-pkg.org.  Network errors and unexpected status codes
    return 'unknown' so callers only warn when the package is definitively absent.
    """
    try:
        import requests as _req
        resp = _req.get(f'https://crandb.r-pkg.org/{name}', timeout=5)
        if resp.status_code == 200:
            return 'found'
        elif resp.status_code == 404:
            return 'not_found'
        else:
            return 'unknown'
    except Exception:
        return 'unknown'


def _make_guard(src_file) -> str:
    """Return a language-appropriate anti-execution guard line."""
    ext = src_file.suffix.lower()
    msg = 'VALICHORD PROPOSED CORRECTION: Remove this after verifying the corrections above.'
    if ext in {'.r', '.rmd', '.qmd'}:
        return f'stop("{msg}")\n'
    elif ext == '.py':
        return f'raise RuntimeError("{msg}")\n'
    elif ext == '.jl':
        return f'error("{msg}")\n'
    elif ext in {'.do', '.ado'}:
        return f'display as error "{msg}"\n' + 'exit 1\n'
    elif ext == '.m':
        return f'error("{msg}")\n'
    else:
        return f'# ERROR: {msg}\n'


def _r_pkg_suspicious(name: str) -> bool:
    """Return True if an R package name looks garbled or non-real.

    Two heuristics:
    1. Five or more consecutive non-vowel letters (treating y as a vowel)
       catches random strings like 'sfgtrehet' (run: sfgtr = 5).
    2. Fewer than 3 characters and not in any known-good set — single or
       two-letter package names are almost always variable names extracted
       from unquoted library() calls.
    """
    letters = re.sub(r'[0-9._\-]', '', name)
    if not letters:
        return False
    if re.search(r'[^aeiouyAEIOUY]{5,}', letters):
        return True
    if len(name) < 3 and name.lower() not in _KNOWN_CRAN_LOWER:
        return True
    return False


def generate_all_drafts(repo_dir, all_files, findings, output_dir):
    """Generate all _DRAFT files."""

    modes_found = {f['mode'] for f in findings}

    has_code = any(f.suffix.lower() in CODE_EXTENSIONS or f.suffix.lower() in {'.ipynb', '.nf'} or _is_code_txt(f) for f in all_files)
    _cad_exts     = {'.step', '.stp', '.stl', '.igs', '.iges', '.f3d', '.obj'}
    _tabular_exts = {'.csv', '.tsv', '.xlsx', '.xls', '.dta', '.sav',
                     '.parquet', '.feather', '.arrow', '.dif'}
    is_cad_deposit = (
        any(f.suffix.lower() in _cad_exts for f in all_files)
        and not has_code
        and not any(f.suffix.lower() in _tabular_exts for f in all_files)
    )
    _generate_inventory(repo_dir, all_files, output_dir)
    _generate_readme_draft(repo_dir, all_files, findings, output_dir)
    if has_code:
        _generate_requirements_draft(repo_dir, all_files,
                                      findings, output_dir)
        _generate_quickstart_draft(repo_dir, all_files,
                                    findings, output_dir)
    _licence_names = {'licence', 'license', 'licence.md', 'license.md',
                      'licence.txt', 'license.txt', 'copying', 'copying.md'}
    _has_licence = any(f.name.lower() in _licence_names for f in all_files)
    if not _has_licence:
        _generate_licence_draft(output_dir, all_files, is_cad=is_cad_deposit)
    generate_proposed_corrections(repo_dir, all_files, findings, output_dir)


# ── INVENTORY_DRAFT.md ───────────────────────────────────────────────────────

def _generate_inventory(repo_dir, all_files, output_dir):
    """Generate INVENTORY_DRAFT.md — full file listing."""

    _cad_exts     = {'.step', '.stp', '.stl', '.igs', '.iges', '.f3d', '.obj'}
    _tabular_exts = {'.csv', '.tsv', '.xlsx', '.xls', '.dta', '.sav',
                     '.parquet', '.feather', '.arrow', '.dif'}
    _is_cad_deposit = (
        any(f.suffix.lower() in _cad_exts for f in all_files)
        and not any(f.suffix.lower() in CODE_EXTENSIONS
                    or f.suffix.lower() in {'.ipynb', '.nf'}
                    or f.name in {'Snakefile', 'main.nf'}
                    or _is_code_txt(f)
                    for f in all_files)
        and not any(f.suffix.lower() in _tabular_exts for f in all_files)
    )

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [
        '# ValiChord Repository Readiness Check — File Inventory',
        '',
        f'**Generated:** {now}',
        f'**Total files:** {len(all_files)}',
        '',
        '> This inventory was generated by automated analysis.',
        '> File purpose descriptions are structural only — '
        'derived from',
        '> code evidence where available. Semantic descriptions',
        '> are not inferred from filenames.',
        '',
        '---',
        '',
        '## File Listing',
        '',
        '| File | Type | Size | Notes |',
        '|---|---|---|---|',
    ]

    for f in sorted(all_files, key=lambda x: str(x)):
        rel = f.relative_to(repo_dir)
        size = f.stat().st_size
        size_str = (f'{size:,} bytes' if size < 10240
                    else f'{size/1024:.1f} KB')
        ftype = _classify_file(f, is_cad=_is_cad_deposit)
        notes = _file_notes(f)
        lines.append(f'| `{rel}` | {ftype} | {size_str} | {notes} |')

    lines += [
        '',
        '---',
        '',
        f'*Generated by ValiChord Repository Readiness Check — v15 — {now}*',
    ]

    out = output_dir / 'INVENTORY_DRAFT.md'
    out.write_text('\n'.join(lines), encoding='utf-8-sig')
    print(f"  → INVENTORY_DRAFT.md ({len(all_files)} files)")


def _is_model_artifact_file(f):
    """Return True if this file is a trained model binary or model config, not research data."""
    _model_name_indicators = {'model', 'clf', 'classifier', 'regressor', 'estimator',
                              'pipeline', 'weights', 'tokenizer', 'vocab', 'checkpoint'}
    _model_dirs = {'models', 'model', 'checkpoints', 'saved_model'}
    name_lower = f.name.lower()
    ext = f.suffix.lower()
    in_model_dir = any(part.lower() in _model_dirs for part in f.parts)
    has_model_name = any(ind in name_lower for ind in _model_name_indicators)
    if ext in {'.pkl', '.pickle', '.pt', '.pth', '.onnx', '.safetensors', '.bin'}:
        return has_model_name or in_model_dir
    if ext == '.json':
        return (has_model_name or in_model_dir)
    return False


_CODE_TXT_STEM_KEYWORDS = frozenset({
    'code', 'script', 'analysis', 'replication', 'pipeline', 'main', 'run'
})
_CODE_TXT_CONTENT_RE = re.compile(
    r'library\s*\(|import\s+\w|^\s*def\s+\w|\bfunction\s*\(|\bcd\s+|\buse\s+',
    re.MULTILINE
)


def _is_code_txt(f):
    """Return True if a .txt file's stem and content suggest it is actually code."""
    if f.suffix.lower() != '.txt':
        return False
    if not any(kw in f.stem.lower() for kw in _CODE_TXT_STEM_KEYWORDS):
        return False
    try:
        with f.open('rb') as fh:
            raw = fh.read(2 * 1024 * 1024)  # 2 MB cap
        content = raw.decode('utf-8', errors='ignore')
    except Exception:
        return False
    return bool(_CODE_TXT_CONTENT_RE.search(content))


def _classify_file(f, is_cad=False):
    ext = f.suffix.lower()
    if ext in _ALL_CODE_EXTENSIONS:
        return 'Code'
    if ext in NOTEBOOK_EXTENSIONS:
        return 'Notebook'
    if ext == '.txt' and _is_code_txt(f):
        return 'Code'
    if ext in {'.md', '.txt', '.rst', '.html', '.tex'}:
        return 'Documentation'
    if ext == '.docx' and f.stem.lower() in {'readme', 'read me', 'read_me'}:
        return 'Documentation'
    if f.name.lower().startswith('readme'):
        return 'Documentation'
    if _is_model_artifact_file(f):
        return 'Model artifact'
    if f.name.lower() in _CODEBOOK_FILENAMES:
        return 'Documentation'
    if ext in {'.csv', '.tsv'} and _looks_like_codebook(f):
        return 'Documentation'
    if ext in _DATA_EXTENSIONS:
        return 'Data'
    if is_cad and ext == '.pdf':
        return 'Engineering Drawing'
    if ext in {'.png', '.jpg', '.jpeg', '.pdf', '.svg', '.tif'}:
        return 'Figure/Image'
    if f.name.lower() == 'citation.cff':
        return 'Citation'
    if f.name.lower() in DEPENDENCY_FILES:
        return 'Dependency spec'
    if ext in {'.yml', '.yaml', '.toml', '.ini', '.cfg'}:
        return 'Configuration'
    if ext in {'.sh', '.bash'}:
        return 'Shell script'
    if ext in {'.gpg', '.enc', '.secret', '.age', '.asc'}:
        return '⚠️ POSSIBLY ENCRYPTED'
    if f.name == 'Snakefile' or f.suffix.lower() == '.smk':
        return 'Workflow'
    if ext == '.asv':
        return 'MATLAB autosave artefact'
    if ext in _ARCHIVE_EXTENSIONS:
        if _is_single_file_compressed(f):
            return 'Data'
        return 'Archive'
    return 'Other'


def _file_notes(f):
    name = f.name.lower()
    ext = f.suffix.lower()
    if ext == '.asv':
        return 'MATLAB autosave — consider removing before deposit'
    if ext == '.docx' and f.stem.lower() in {'readme', 'read me', 'read_me'}:
        return 'README (Word format)'
    if ext in {'.gpg', '.enc', '.secret', '.age', '.asc'}:
        return '🔴 POSSIBLY ENCRYPTED — may be unusable without key'
    if name == 'citation.cff':
        return 'CITATION.cff — check all required fields are complete'
    if 'codebook' in name or 'data_dictionary' in name or 'data_dict' in name:
        return 'Codebook / data dictionary'
    if name.startswith('readme'):
        return 'README'
    if name in {'licence', 'license', 'licence.md',
                'license.md', 'licence.txt', 'license.txt'}:
        return 'Licence file'
    import re as _ren
    if _ren.match(r'requirements.*\.txt$', name):
        return 'Dependency specification'
    if name == 'dockerfile':
        return 'Container definition'
    _m = re.match(r'^(\d+)(?:[.\-](\d+))?(?:[_\-]|\.(?!\d))', f.name)
    if _m and ext in _ALL_CODE_EXTENSIONS and len(_m.group(1)) <= 4:
        # Only flag as numbered script if: (a) it's actually a code file,
        # and (b) the leading number is ≤4 digits.  A 5+ digit prefix
        # (e.g. 2026222_, 54720782_) is a date-stamp or dataset ID, not
        # an execution sequence number.  Data files (.xlsx, .csv, …) with
        # numeric prefixes are never execution scripts.
        return 'Numbered script — execution order implied'
    if f.suffix.lower() == '.txt' and _is_code_txt(f):
        return 'code stored as plain text — consider renaming to .R, .py, .do etc.'
    if ext in _ARCHIVE_EXTENSIONS:
        if _is_single_file_compressed(f):
            inner_name = Path(f.stem).name
            return f'Compressed data file — contains {inner_name}'
        note = _inspect_archive(f)
        if note and 'not inspectable' not in note:
            return f'Archive{note} — extract contents before deposit'
        return 'Archive — extract contents before deposit'
    return ''


# ── README_DRAFT.md ──────────────────────────────────────────────────────────

_SHP_EXTENSIONS = {'.shp', '.dbf', '.shx', '.prj', '.cpg', '.sbn', '.sbx'}


def _group_shapefiles(data_files):
    """Group shapefile components sharing a stem into a single representative entry.

    e.g. FRA_adm2.shp + .dbf + .shx + .prj → one row for FRA_adm2.shp
    Non-shapefile files are returned unchanged.
    """
    from collections import defaultdict as _dd
    shp_groups = _dd(list)
    non_shp = []
    for f in data_files:
        if f.suffix.lower() in _SHP_EXTENSIONS:
            shp_groups[f.parent / f.stem].append(f)
        else:
            non_shp.append(f)
    representatives = []
    for _base, files in sorted(shp_groups.items(), key=lambda x: str(x[0])):
        # Prefer the actual .shp file as representative; fall back to synthetic path
        rep = next((f for f in files if f.suffix.lower() == '.shp'), None)
        if rep is None:
            rep = files[0].with_suffix('.shp')
        representatives.append(rep)
    return representatives + non_shp


def _data_file_format(f):
    """Human-readable format label for a data file in README tables."""
    ext = f.suffix.lower()
    if ext == '.shp':
        return 'Shapefile'
    if ext in _ARCHIVE_EXTENSIONS:
        note = _inspect_archive(f)
        base = ext.upper().lstrip('.')
        if note and 'not inspectable' not in note:
            return f'{base} archive{note}'
        return f'{base} archive'
    return ext.upper().lstrip('.')


def _readme_install_block(all_files, r_packages=None, github_pkgs=None):
    """Return language-appropriate installation instructions for README_DRAFT."""
    if github_pkgs is None:
        github_pkgs = {}
    suffixes = {f.suffix.lower() for f in all_files}
    if any(f.name == 'Snakefile' for f in all_files):
        suffixes.add('.smk')
    names = {f.name.lower() for f in all_files}
    # data-only deposit — no code present
    has_code = any(s in suffixes for s in {".py", ".r", ".jl", ".do", ".m", ".rmd", ".smk", ".ipynb", ".nf", ".groovy"}) or any(_is_code_txt(f) for f in all_files)
    if not has_code:
        codebook = next((f.name for f in all_files if "codebook" in f.name.lower() or "data_dict" in f.name.lower() or "readme_variable" in f.name.lower()), None)
        return [
            "# This is a data-only deposit. No code execution is required.",
            "# Files are provided in standard formats (CSV, Excel, etc.)",
            f"# See {codebook} for variable descriptions." if codebook else "# See the codebook for variable descriptions.",
        ]
    # conda repo — takes precedence over all language-specific checks
    if 'environment.yml' in names or 'environment.yaml' in names:
        env_file = 'environment.yml' if 'environment.yml' in names else 'environment.yaml'
        env_name = 'myenv'
        env_path = min((f for f in all_files if f.name.lower() == env_file),
                       key=lambda x: len(x.parts), default=None)
        if env_path:
            import re as _re
            m = _re.search(r'^name:\s*(\S+)', env_path.read_text(encoding='utf-8', errors='ignore'), _re.MULTILINE)
            if m:
                env_name = m.group(1)
        return [
            '# 1. Clone or download this repository',
            '# 2. Create and activate the conda environment',
            f'conda env create -f {env_file}',
            f'conda activate {env_name}',
        ]
    # Docker repo — takes priority over language-specific blocks
    if 'dockerfile' in names:
        return [
            '# 1. Build the Docker image',
            'docker build -t my-analysis .',
            '# 2. Run the container (mount data directory)',
            'docker run -v $(pwd)/data:/app/data my-analysis',
            '# Or with an interactive shell:',
            '# docker run -it -v $(pwd)/data:/app/data my-analysis bash',
        ]
    if '.jl' in suffixes:
        if 'project.toml' in names:
            return [
                '# 1. Clone or download this repository',
                '# 2. Install Julia dependencies',
                'julia --project=. -e "using Pkg; Pkg.instantiate()"',
            ]
        else:
            # Check for embedded Pluto manifest — if present, just open in Pluto
            pluto_files = [f for f in all_files if f.suffix.lower() == '.jl']
            has_pluto_deps = any(
                'PLUTO_PROJECT_TOML_CONTENTS' in f.read_text(encoding='utf-8', errors='ignore')
                for f in pluto_files
            )
            if has_pluto_deps:
                return [
                    '# 1. Clone or download this repository',
                    '# 2. Open the notebook in Pluto — dependencies are embedded',
                    '# julia -e \'using Pkg; Pkg.add(\"Pluto\"); using Pluto; Pluto.run()\'',
                    '# Then open the .jl notebook file — Pluto will install dependencies automatically',
                ]
            # No Pluto, no Project.toml — extract packages dynamically
            import re as _re
            julia_stdlib_set = {'Random','Statistics','LinearAlgebra','Dates','Printf',
                                'Base','Core','Main','Pkg','Test','Logging','REPL',
                                'InteractiveUtils','Distributed','Serialization',
                                'Markdown','Unicode','DelimitedFiles','SparseArrays'}
            jl_pkgs = sorted({
                pkg.strip()
                for f in pluto_files
                for line in f.read_text(encoding='utf-8', errors='ignore').splitlines()
                for m in [_re.match(r'^using\s+([\w,\s]+)', line.strip())]
                if m
                for pkg in _re.split(r'[,\s]+', m.group(1))
                if pkg.strip() and pkg.strip() not in julia_stdlib_set
            })
            if jl_pkgs:
                pkg_list = ', '.join(f'\"{p}\"' for p in jl_pkgs)
                return [
                    '# 1. Clone or download this repository',
                    '# 2. Create Project.toml and Manifest.toml (recommended):',
                    f'#    julia --project=. -e \'using Pkg; Pkg.add([{pkg_list}]); Pkg.resolve()\'',
                    '#    Then commit Project.toml and Manifest.toml',
                    '# Or to install without pinning (not recommended for reproducibility):',
                    f'#    julia -e \'using Pkg; Pkg.add([{pkg_list}])\'',
                ]
            return ['2. Create Project.toml and Manifest.toml to pin package versions.',
                    '   Run: julia --project=. -e "using Pkg; Pkg.add([\"PackageName\"]); Pkg.resolve()"  ',
                    '   Then commit Project.toml and Manifest.toml']
    if '.r' in suffixes or '.rmd' in suffixes:
        has_python = '.py' in suffixes
        if 'renv.lock' in names:
            if has_python:
                return [
                    '# 1. Clone or download this repository',
                    '# 2. Set up Python environment',
                    'python -m venv venv',
                    'source venv/bin/activate  # Windows: venv\\Scripts\\activate',
                    'pip install -r requirements.txt',
                    '# 3. Restore R environment',
                    'Rscript -e "renv::restore()"',
                ]
            return [
                '# 1. Clone or download this repository',
                '# 2. Restore R environment',
                'Rscript -e "renv::restore()"',
            ]
        pkgs = r_packages or ['dplyr', 'ggplot2']
        # Partition packages into CRAN / Bioconductor / GitHub-likely / known-GitHub / removed-from-CRAN
        gh_only      = [p for p in pkgs if p.lower() in github_pkgs]
        gh_likely    = [p for p in pkgs if p.lower() not in github_pkgs
                        and p.lower() in _GITHUB_LIKELY_LOWER]
        bioc_pkgs    = [p for p in pkgs if p.lower() not in github_pkgs
                        and p.lower() not in _GITHUB_LIKELY_LOWER
                        and p.lower() in _BIOC_LOWER]
        removed_pkgs = [p for p in pkgs if p.lower() not in github_pkgs
                        and p.lower() not in _GITHUB_LIKELY_LOWER
                        and p.lower() not in _BIOC_LOWER
                        and p.lower() in _REMOVED_CRAN_LOWER]
        cran_pkgs    = [p for p in pkgs if p.lower() not in github_pkgs
                        and p.lower() not in _GITHUB_LIKELY_LOWER
                        and p.lower() not in _BIOC_LOWER
                        and p.lower() not in _REMOVED_CRAN_LOWER]
        block = ['# 1. Clone or download this repository']
        if has_python:
            block += ['# 2. Set up Python environment',
                      'python -m venv venv',
                      'source venv/bin/activate  # Windows: venv\\Scripts\\activate',
                      'pip install -r requirements.txt']
            step = 3
        else:
            step = 2
        if cran_pkgs:
            pkg_str = ', '.join("'" + p + "'" for p in cran_pkgs)
            block.append(f'# {step}. Install CRAN packages')
            block.append(f'Rscript -e "install.packages(c({pkg_str}))"')
            step += 1
        if bioc_pkgs:
            bioc_str = ', '.join("'" + p + "'" for p in bioc_pkgs)
            block.append(f'# {step}. Install Bioconductor packages')
            block.append('Rscript -e "if (!require(\'BiocManager\', quietly=TRUE)) install.packages(\'BiocManager\')"')
            block.append(f'Rscript -e "BiocManager::install(c({bioc_str}))"')
            step += 1
        if gh_likely:
            block.append(f'# {step}. Install possible GitHub-only packages (verify sources before running)')
            for p in gh_likely:
                slug = _GITHUB_KNOWN_SLUGS.get(p.lower(), f'.../{p}')
                block.append(f'# Rscript -e "devtools::install_github(\'{slug}\')"  # verify this is correct')
            step += 1
        if gh_only:
            block.append(f'# {step}. Install GitHub packages')
            for p in gh_only:
                repo = github_pkgs.get(p.lower(), p).strip("'").strip('"')
                block.append(f'Rscript -e "devtools::install_github(\'{repo}\')"')
        if removed_pkgs:
            block += ['', '# ⚠️ WARNING: the following packages are no longer on CRAN:']
            for p in removed_pkgs:
                hint_lines = _REMOVED_CRAN_README_LINES.get(
                    p.lower(),
                    [f'# {p} was removed from CRAN — check for an alternative package.'],
                )
                block += hint_lines
        return block
    if '.do' in suffixes or '.ado' in suffixes:
        return [
            '# 1. Clone or download this repository',
            '# 2. Install required Stata packages via ssc install',
        ]
    if '.m' in suffixes:
        eeglab_fns = {'pop_epoch', 'pop_autorej', 'pop_resample', 'pop_eegfiltnew',
                      'eeglab', 'pop_loadset', 'pop_saveset', 'runica'}
        has_eeglab = any(
            any(fn in f.read_text(encoding='utf-8', errors='ignore') for fn in eeglab_fns)
            for f in all_files if f.suffix.lower() == '.m'
        )
        block = [
            '# 1. Open MATLAB (see README for required version)',
            '# 2. Ensure required toolboxes are licensed and installed',
        ]
        if has_eeglab:
            block += [
                '# 3. Add EEGLAB folder to your MATLAB path',
                '#    addpath(genpath("/path/to/eeglab"))',
                '# 4. Open and run the main script',
            ]
        else:
            block.append('# 3. Open and run the main script')
        return block
    # conda repo — environment.yml present
    if 'environment.yml' in names or 'environment.yaml' in names:
        env_file = 'environment.yml' if 'environment.yml' in names else 'environment.yaml'
        # Try to extract conda env name
        env_name = 'myenv'
        env_path = min((f for f in all_files if f.name.lower() == env_file),
                       key=lambda x: len(x.parts), default=None)
        if env_path:
            import re as _re
            m = _re.search(r'^name:\s*(\S+)', env_path.read_text(encoding='utf-8', errors='ignore'), _re.MULTILINE)
            if m:
                env_name = m.group(1)
        return [
            '# 1. Clone or download this repository',
            '# 2. Create and activate the conda environment',
            f'conda env create -f {env_file}',
            f'conda activate {env_name}',
        ]
    # Nextflow pipeline
    if '.nf' in suffixes or any(f.name.lower() == 'main.nf' for f in all_files):
        return [
            '# 1. Clone or download this repository',
            '# 2. Install Nextflow (if not already installed)',
            'curl -s https://get.nextflow.io | bash',
            '# Or via conda: conda install -c bioconda nextflow',
        ]
    # default Python
    import re as _re_iblk
    _data_url_pat = _re_iblk.compile(
        r'https?://(?:zenodo\.org|figshare\.com|osf\.io|datadryad\.org'  
        r'|dataverse\.harvard\.edu|data\.mendeley\.com)',
        _re_iblk.IGNORECASE)
    _has_external_data = any(
        _data_url_pat.search(f.read_text(encoding='utf-8', errors='ignore'))
        for f in all_files if f.name.lower() in {'readme.md','readme.txt','readme.rst'})
    return [
        *(['# 0. Download required data',
           '# [YOU MUST COMPLETE — add wget/curl or manual download instructions]',
           '# Example: wget -O data/dataset.tif https://zenodo.org/record/.../files/dataset.tif',
           '# Verify checksum: sha256sum data/dataset.tif',
           ''] if _has_external_data else []),
        '# 1. Clone or download this repository',
        '# 2. Create a virtual environment',
        'python -m venv venv',
        'source venv/bin/activate  # Windows: venv\\Scripts\\activate',
        '',
        '# 3. Install dependencies',
        '# First ensure all version numbers are pinned in requirements.txt',
        'pip install -r requirements.txt',
    ]

def _generate_readme_draft(repo_dir, all_files, findings, output_dir):
    """Generate README_DRAFT.md."""

    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    # try to find existing readme content — prefer root-level README over subfolder
    existing_readme = ''
    existing_readme_file = None
    for f in sorted(all_files, key=lambda x: len(x.relative_to(repo_dir).parts)):
        if f.name.lower() in README_NAMES:
            try:
                existing_readme = f.read_text(encoding='utf-8', errors='ignore')
                existing_readme_file = f
            except Exception:
                pass
            break  # sorted by depth, so first match is shallowest

    # assess whether existing readme is adequate
    readme_adequate = False
    if existing_readme and len(existing_readme.strip()) > 500:
        key_sections = [
            'installation', 'usage', 'data', 'run', 'reproduce',
            'requirement', 'depend', 'import', 'abstract', 'author',
            'method', 'result', 'how to', 'getting started', 'setup',
        ]
        sections_found = sum(1 for s in key_sections if s in existing_readme.lower())
        if sections_found >= 2:
            readme_adequate = True

    if readme_adequate:
        # existing README is reasonable — just note what's missing.
        # Exclude [A] "no readme" findings since we did find one to show.
        readme_findings = [f for f in findings
                           if f.get('mode') in ('A', 'G', 'Z', 'K', 'N', 'E', 'Y')
                           and 'No README file found' not in f.get('title', '')]
        lines = [
            '# README Review Notes',
            '',
            '> ⚠️ **README_DRAFT.md** — Your existing README appears adequate.',
            '> This file only lists items that may need attention.',
            '> Your original README has been preserved — do not replace it with this file.',
            '',
            '---',
            '',
            '## Items to check in your existing README',
            '',
        ]
        if readme_findings:
            for f in readme_findings:
                lines.append(f'- {f.get("title", "")}')
        else:
            lines.append('- No specific README gaps detected.')
        lines += [
            '',
            '---',
            '',
            '## Your existing README (for reference)',
            '',
            existing_readme,
        ]
        out = output_dir / 'README_DRAFT.md'
        out.write_text('\n'.join(lines), encoding='utf-8-sig')
        print(f"  → README_DRAFT.md (existing README adequate)")
        return

    # extract R packages for install block
    r_pkgs = set()
    github_pkgs = {}  # pkg_name_lower -> 'owner/repo'
    lib_pat = re.compile(r'(?:library|require)\s*\(\s*["\']?([\w\.]+)["\']?\s*\)')
    vec_pkg_pat = re.compile(
        r'(?i)(?:packages?|pkgs?|libs?|required[\w]*|deps?|dep_list)\s*<-\s*c\s*\(([^)]+)\)'
    )
    pacman_pat_rd = re.compile(r'(?:pacman::)?p_load\s*\(([^)]+)\)')
    github_pat = re.compile(r'(?:devtools|remotes)::install_github\s*\(\s*["\']([^"\'/]+/([\w.-]+))["\']', re.IGNORECASE)
    _named_arg_kws = {'package', 'lib.loc', 'quietly', 'warn.conflicts', 'verbose',
                      'character.only', 'logical.return', 'mask.ok', 'exclude',
                      'include.only', 'attach.required'}
    for rf in _researcher_r_files(all_files, repo_dir):
        src = rf.read_text(encoding='utf-8', errors='ignore')
        for m in lib_pat.finditer(src):
            pkg = m.group(1)
            if pkg.lower() not in _named_arg_kws:
                r_pkgs.add(pkg)
        for m in vec_pkg_pat.finditer(src):
            for pkg in re.findall(r'["\']+([\w\.]+)["\']', m.group(1)):
                r_pkgs.add(pkg)
        for m in pacman_pat_rd.finditer(src):
            for pkg in re.findall(r'["\']?([\w\.]+)["\']?', m.group(1)):
                if pkg and not pkg.startswith('#'):
                    r_pkgs.add(pkg)
    # Exclude base-R packages — they ship with R and need no installation
    r_pkgs -= {p for p in r_pkgs if p.lower() in {b.lower() for b in _BASE_R_PACKAGES}}
    for rf in all_files:
        if re.match(r'(install|setup).*\.r$', rf.name.lower()):
            try:
                src = rf.read_text(encoding='utf-8', errors='ignore')
                for m in github_pat.finditer(src):
                    github_pkgs[m.group(2).lower()] = m.group(1)
            except Exception:
                pass
    has_code = any(f.suffix.lower() in CODE_EXTENSIONS or f.suffix.lower() in {'.ipynb', '.nf'} or f.name in {'Snakefile', 'main.nf'} or _is_code_txt(f) for f in all_files)

    _CAD_EXTENSIONS = {'.step', '.stp', '.stl', '.igs', '.iges', '.f3d', '.obj'}
    _TABULAR_EXTENSIONS = {'.csv', '.tsv', '.xlsx', '.xls', '.dta', '.sav',
                           '.parquet', '.feather', '.arrow', '.dif'}

    has_cad = any(f.suffix.lower() in _CAD_EXTENSIONS for f in all_files)
    has_tabular = any(f.suffix.lower() in _TABULAR_EXTENSIONS for f in all_files)

    if has_cad and not has_code and not has_tabular:
        date_str = datetime.now().strftime('%Y-%m-%d')
        _cad_format_info = {
            '.step': ('ISO 10303 STEP',      'Neutral 3D CAD exchange format — recommended for import into any CAD software'),
            '.stp':  ('ISO 10303 STEP',      'Neutral 3D CAD exchange format — recommended for import into any CAD software'),
            '.stl':  ('Stereolithography mesh', 'Tessellated surface geometry — suitable for 3D printing and visualisation'),
            '.igs':  ('IGES',                'Initial Graphics Exchange Specification — legacy neutral CAD exchange format'),
            '.iges': ('IGES',                'Initial Graphics Exchange Specification — legacy neutral CAD exchange format'),
            '.f3d':  ('Fusion 360 archive',  'Autodesk Fusion 360 project file'),
            '.obj':  ('Wavefront OBJ',       'Polygon mesh — widely supported for visualisation and 3D printing'),
        }
        # Build format rows, deduplicating aliases (.stp/.step, .igs/.iges)
        seen_formats: set = set()
        fmt_rows = []
        for ext in ['.step', '.stp', '.stl', '.igs', '.iges', '.f3d', '.obj']:
            if any(f.suffix.lower() == ext for f in all_files):
                fmt_name, fmt_desc = _cad_format_info[ext]
                if fmt_name not in seen_formats:
                    seen_formats.add(fmt_name)
                    fmt_rows.append(f'| `{ext.upper()}` | {fmt_name} | {fmt_desc} |')
        if any(f.suffix.lower() == '.pdf' for f in all_files):
            fmt_rows.append('| `.PDF` | Engineering drawing | Dimensioned technical drawings for manufacturing reference |')

        lines = [
            '# [TITLE OF DESIGN PACKAGE — YOU MUST COMPLETE THIS]',
            '',
            '> ⚠️ **README_DRAFT.md** — Generated by ValiChord. Complete all sections then rename to `README.md`.',
            '',
            '---',
            '',
            '## Design Package Identification',
            '',
            '- **Package title:** [YOU MUST COMPLETE THIS]',
            '- **Authors/designers:** [YOU MUST COMPLETE THIS]',
            '- **Associated paper or report DOI:** [YOU MUST COMPLETE THIS]',
            f'- **Date of deposit:** {date_str}',
            '- **Licence:** [e.g. CC BY 4.0]',
            '',
            '---',
            '',
            '## Overview',
            '',
            '[YOU MUST COMPLETE THIS — describe what physical artefact or system this CAD package represents, its purpose, and what research or engineering work it supports.]',
            '',
            '---',
            '',
            '## File Formats',
            '',
            '| Extension | Format | Description |',
            '|---|---|---|',
            *fmt_rows,
            '',
            '[YOU MUST COMPLETE THIS — add or remove rows as appropriate for your deposit.]',
            '',
            '---',
            '',
            '## File Listing',
            '',
            '[YOU MUST COMPLETE THIS — describe what each file or variant represents. For example: full assembly, simplified assembly, individual components, with/without specific features.]',
            '',
            '---',
            '',
            '## Design Provenance',
            '',
            '[YOU MUST COMPLETE THIS — describe the origin of this design. Is it an original design, a modification of an existing design, or a reproduction? Cite any prior work.]',
            '',
            '---',
            '',
            '## Intended Use',
            '',
            '[YOU MUST COMPLETE THIS — describe the intended use of these files. For example: CFD meshing, physical manufacture, validation against experimental results, 3D printing.]',
            '',
            '---',
            '',
            '## Software Compatibility',
            '',
            '[YOU MUST COMPLETE THIS — list CAD software known to import these files correctly. Note any version-specific issues.]',
            '',
            '---',
            '',
            '## File Integrity',
            '',
            '| File | SHA-256 |',
            '|---|---|',
            '',
            '[YOU MUST COMPLETE THIS — provide checksums for all files.]',
            '',
            '---',
            '',
            f'*Generated by ValiChord Repository Readiness Check — {now}*',
        ]
        if existing_readme:
            lines += ['', '---', '', '## Original README (for reference)', '', existing_readme]
        out = output_dir / 'README_DRAFT.md'
        out.write_text('\n'.join(lines), encoding='utf-8-sig')
        print('  → README_DRAFT.md (CAD/artefact template)')
        return

    # ── Web application / experiment template ────────────────────────────────
    # Condition: has JS files (outside vendor dirs) + an HTML entry point,
    # and no statistical analysis language (Python/R/Julia/Stata/MATLAB).
    _JS_EXTS = frozenset({'.js', '.ts', '.jsx', '.tsx', '.vue', '.mjs'})
    _STAT_EXTS = frozenset({'.py', '.r', '.do', '.jl', '.m', '.sas', '.ipynb',
                             '.rmd', '.qmd', '.ado'})
    _WEBAPP_VENDOR = {'vendor', 'lib', 'dist', 'node_modules', 'target',
                      'bower_components'}

    def _non_vendor(f):
        return not any(p.lower() in _WEBAPP_VENDOR for p in f.parts)

    has_js = any(f.suffix.lower() in _JS_EXTS and _non_vendor(f) for f in all_files)
    has_html = any(f.suffix.lower() == '.html' for f in all_files)
    has_stat_lang = any(f.suffix.lower() in _STAT_EXTS for f in all_files)

    if has_js and has_html and not has_stat_lang:
        _html_entry = next(
            (f.name for f in sorted(all_files, key=lambda x: len(x.parts))
             if f.suffix.lower() == '.html'),
            'index.html'
        )
        _has_pkg_json = any(f.name == 'package.json' for f in all_files)
        _install_block = (
            'npm install  # or: yarn install'
            if _has_pkg_json else
            '# No package.json found — dependencies may need manual setup'
        )
        _run_block = (
            'npm start  # or open index.html directly in a browser'
            if _has_pkg_json else
            f'# Open {_html_entry} in a browser (no build step required)'
        )
        webapp_lines = [
            '# [TITLE OF WEB APPLICATION / EXPERIMENT — YOU MUST COMPLETE THIS]',
            '',
            '> ⚠️ **README_DRAFT.md** — Generated by ValiChord. '
            'Complete all sections then rename to `README.md`.',
            '',
            '---',
            '',
            '## Application Identification',
            '',
            '- **Application title:** [YOU MUST COMPLETE THIS]',
            '- **Authors:** [YOU MUST COMPLETE THIS]',
            '- **Associated paper DOI:** [YOU MUST COMPLETE THIS]',
            '- **Date of deposit:** ' + datetime.now().strftime('%Y-%m-%d'),
            '- **Licence:** [e.g. MIT / CC BY 4.0]',
            '',
            '---',
            '',
            '## Overview',
            '',
            '[YOU MUST COMPLETE THIS — describe what this web application does, '
            'what experiment it runs, or what interactive tool it provides.]',
            '',
            '---',
            '',
            '## System Requirements',
            '',
            '- **Browser:** [e.g. Chrome 120+, Firefox 121+, Safari 17+]',
            '- **Server required:** [Yes/No — if yes, specify Node.js version]',
            '- **Internet connection required:** [Yes/No]',
            '',
            '---',
            '',
            '## Setup & Running',
            '',
            '```bash',
            _install_block,
            _run_block,
            '```',
            '',
            f'Open `{_html_entry}` in a browser to run the experiment/application.',
            '',
            '---',
            '',
            '## File Structure',
            '',
            '[YOU MUST COMPLETE THIS — describe the purpose of each file or directory.]',
            '',
            '---',
            '',
            '## Stimuli / Assets',
            '',
            '[YOU MUST COMPLETE THIS — if this application presents stimuli to participants, '
            'describe the stimuli, their source, and any copyright or licensing constraints.]',
            '',
            '---',
            '',
            '## Data Collection',
            '',
            '[YOU MUST COMPLETE THIS — describe what data this application collects, '
            'where it is stored, and how to export/access collected data.]',
            '',
            '---',
            '',
            f'*Generated by ValiChord Repository Readiness Check — '
            f'{datetime.now().strftime("%Y-%m-%d %H:%M")}*',
        ]
        if existing_readme:
            webapp_lines += ['', '---', '',
                             '## Original README (for reference)', '', existing_readme]
        out = output_dir / 'README_DRAFT.md'
        out.write_text('\n'.join(webapp_lines), encoding='utf-8-sig')
        print('  → README_DRAFT.md (web-app/experiment template)')
        return

    _SOFTWARE_EXTS = {'.jar', '.exe', '.dll', '.so', '.dylib', '.class', '.app'}
    is_software_deposit = (
        any(f.suffix.lower() in _SOFTWARE_EXTS for f in all_files)
        and not has_code
    )
    if is_software_deposit:
        # Deduplicate by filename — keep shallowest copy (double-zip produces dupes)
        _sw_seen: set = set()
        _sw_files = []
        for _f in sorted(all_files, key=lambda x: len(x.parts)):
            if _f.suffix.lower() in _SOFTWARE_EXTS and _f.name not in _sw_seen:
                _sw_seen.add(_f.name)
                _sw_files.append(_f)
        _has_jar = any(f.suffix.lower() == '.jar' for f in all_files)
        _has_exe = any(f.suffix.lower() in {'.exe', '.app'} for f in all_files)
        _run_example = (
            f'java -jar {_sw_files[0].name} <input_file>'
            if _has_jar else
            f'./{_sw_files[0].name} <input_file>'
            if _has_exe else
            f'# See usage instructions below'
        )
        sw_lines = [
            '# [NAME OF TOOL — YOU MUST COMPLETE THIS]',
            '',
            '> ⚠️ **README_DRAFT.md** — Generated by ValiChord. Complete all sections then rename to `README.md`.',
            '',
            '---',
            '',
            '## Software Identification',
            '',
            '- **Tool name:** [YOU MUST COMPLETE THIS]',
            '- **Version:** [YOU MUST COMPLETE THIS]',
            '- **Authors:** [YOU MUST COMPLETE THIS]',
            '- **Associated paper DOI:** [YOU MUST COMPLETE THIS]',
            '- **Licence:** [e.g. MIT, GPL-3.0, Apache-2.0]',
            '',
            '---',
            '',
            '## Purpose',
            '',
            '[YOU MUST COMPLETE THIS — describe what this tool does and what research it supports.]',
            '',
            '---',
            '',
            '## Runtime Requirements',
            '',
            *(['- **Java version:** [e.g. Java 11+]',
               '- **OS:** [Windows / macOS / Linux — specify if platform-specific]']
              if _has_jar else
              ['- **OS:** [Windows / macOS / Linux — specify if platform-specific]',
               '- **Runtime:** [e.g. .NET 6+, libc 2.31+]']),
            '',
            '---',
            '',
            '## Installation',
            '',
            '[YOU MUST COMPLETE THIS — describe any installation or setup steps, e.g. extracting the archive, setting PATH, placing input files.]',
            '',
            '---',
            '',
            '## Usage',
            '',
            '```bash',
            _run_example,
            '```',
            '',
            '| Argument | Description | Example |',
            '|---|---|---|',
            '| `<input_file>` | [YOU MUST COMPLETE THIS] | `example_input.xml` |',
            '',
            '---',
            '',
            '## Distributed Files',
            '',
            '| File | Description |',
            '|---|---|',
            *[f'| `{f.name}` | [YOU MUST COMPLETE THIS] |' for f in _sw_files],
            '',
            '---',
            '',
            '## Expected Output',
            '',
            '[YOU MUST COMPLETE THIS — describe what output files or console messages a user should expect when the tool runs correctly.]',
            '',
            '---',
            '',
            f'*Generated by ValiChord Repository Readiness Check — {datetime.now().strftime("%Y-%m-%d %H:%M")}*',
        ]
        if existing_readme:
            sw_lines += ['', '---', '', '## Original README (for reference)', '', existing_readme]
        out = output_dir / 'README_DRAFT.md'
        out.write_text('\n'.join(sw_lines), encoding='utf-8-sig')
        print('  → README_DRAFT.md (software/tool template)')
        return

    if not has_code:
        # data-only deposit — use data-focused template
        _raw_data_files = [f for f in all_files
                           if (f.suffix.lower() in _DATA_EXTENSIONS
                               or f.suffix.lower() in _ARCHIVE_EXTENSIONS)
                           and not f.name.lower().startswith('readme')]
        data_files = _group_shapefiles(_raw_data_files)
        codebook = next((f.name for f in all_files if "codebook" in f.name.lower() or "data_dict" in f.name.lower() or "readme_variable" in f.name.lower()), None)
        lines = [
            '# [TITLE OF DATASET — YOU MUST COMPLETE THIS]',
            '',
            '> ⚠️ **README_DRAFT.md** — Generated by ValiChord. Complete all sections then rename to `README.md`.',
            '',
            '---',
            '',
            '## Dataset Identification',
            '',
            '- **Dataset title:** [YOU MUST COMPLETE THIS]',
            '- **Authors/collectors:** [YOU MUST COMPLETE THIS]',
            '- **Associated paper DOI:** [YOU MUST COMPLETE THIS]',
            '- **Date of deposit:** ' + datetime.now().strftime('%Y-%m-%d'),
            '- **Licence:** [e.g. CC BY 4.0]',
            '',
            '---',
            '',
            '## Dataset Overview',
            '',
            '[YOU MUST COMPLETE THIS — describe what this dataset contains, how it was collected, and what research it supports.]',
            '',
            '---',
            '',
            '## Data Files',
            '',
            '| File | Format | Description | Rows | Variables |',
            '|---|---|---|---|---|',
            *[f'| `{f.relative_to(repo_dir)}` | {_data_file_format(f)} | [YOU MUST COMPLETE THIS] | | |' for f in data_files],
            '',
            '---',
            '',
            '## Variables',
            '',
            f'See `{codebook}` for full variable descriptions.' if codebook else '[YOU MUST COMPLETE THIS — list all variables or reference your codebook.]',
            '',
            '---',
            '',
            '## Collection Methodology',
            '',
            '[YOU MUST COMPLETE THIS — describe how data was collected, survey instruments, sampling strategy, dates of collection.]',
            '',
            '---',
            '',
            '## Access Conditions',
            '',
            '[YOU MUST COMPLETE THIS — state whether data is open access, restricted, or embargoed. If restricted, who to contact.]',
            '',
            '---',
            '',
            '## File Integrity',
            '',
            '[YOU MUST COMPLETE THIS — provide SHA-256 checksums for all data files.]',
            '',
            '| File | SHA-256 |',
            '|---|---|',
            *[f'| `{f.relative_to(repo_dir)}` | [checksum] |' for f in data_files],
            '',
            '---',
            '',
            f'*Generated by ValiChord Repository Readiness Check — {datetime.now().strftime("%Y-%m-%d %H:%M")}*',
        ]
        if existing_readme:
            lines += ["", "---", "", "## Original README (for reference)", "", existing_readme]
        out = output_dir / "README_DRAFT.md"
        out.write_text("\n".join(lines), encoding="utf-8-sig")
        print("  → README_DRAFT.md (data-only template)")
        return
    _variables_file = next((f.name for f in all_files if "codebook" in f.name.lower() or "data_dict" in f.name.lower() or "readme_variable" in f.name.lower()), None)
    lines = [
        '# [TITLE OF PAPER — YOU MUST COMPLETE THIS]',
        '',
        '> ⚠️ **README_DRAFT.md** — This file was generated by '
        'ValiChord Repository Readiness Check.',
        '> All sections marked [YOU MUST COMPLETE THIS] require '
        'your input.',
        '> Verify all content, then rename to `README.md`.',
        '',
        '---',
        '',
        '## Study Identification',
        '',
        '- **Paper title:** [YOU MUST COMPLETE THIS]',
        '- **Authors:** [YOU MUST COMPLETE THIS]',
        '- **DOI / URL:** [YOU MUST COMPLETE THIS]',
        '- **Date of deposit:** '
        f'{datetime.now().strftime("%Y-%m-%d")}',
        '- **Commit hash / version tag:** '
        '[YOU MUST COMPLETE THIS — e.g. git rev-parse HEAD]',
        '',
        '---',
        '',
        '## Study Overview',
        '',
        '[YOU MUST COMPLETE THIS — 2 to 5 sentences describing '
        'what this repository does and what paper it supports. '
        'This cannot be generated automatically.]',
        '',
        '---',
        '',
        '## System Requirements',
        '',
        '- **Operating system:** [e.g. Ubuntu 22.04 / macOS 13 '
        '/ Windows 11]',
        '- **Programming language:** [e.g. Python 3.11.2]',
        '- **RAM required:** [e.g. 16GB minimum]',
        '- **GPU required:** [Yes/No — if yes, specify model]',
        '- **Estimated runtime:** [e.g. 2 hours on 8-core laptop]',
        '- **HPC required:** [Yes/No — if yes, specify nodes/cores]',
        '',
        '---',
        '',
        '## Installation',
        '',
        '```bash',
        *_readme_install_block(all_files, sorted(r_pkgs) if r_pkgs else None, github_pkgs=github_pkgs),
        '```',
        '',
        '[YOU MUST COMPLETE THIS — add any additional '
        'installation steps]',
        '',
        '---',
        '',
        '## Execution',
        '',
        '[YOU MUST COMPLETE THIS — describe the steps to run '
        'your analysis]',
        '',
        'See `QUICKSTART_DRAFT.md` for an inferred execution '
        'order (verify before using).',
        '',
        '---',
        '',
        '## Data',
        '',
        '- **Data location:** [describe where data files are]',
        '- **Data source:** [YOU MUST COMPLETE THIS]',
        '- **Data version:** [YOU MUST COMPLETE THIS — '
        'exact version/date of any external dataset]',
        '- **Anonymised/synthetic:** [Yes/No — if yes, '
        'describe transformation]',
        *([f'- **Variable definitions:** See `{_variables_file}` for variable descriptions.']
          if _variables_file else
          ['- **Variable definitions:** [reference your codebook or list key variables]']),
        '',
        '---',
        '',
        '## Expected Outputs',
        '',
        '[YOU MUST COMPLETE THIS — describe what a validator '
        'should see after running your code]',
        '',
        '### Figure to file mapping',
        '',
        '[YOU MUST COMPLETE THIS — the tool cannot infer '
        'which scripts produce which figures]',
        '',
        '| Paper Figure | Generated File | Producing Script |',
        '|---|---|---|',
        '| Figure 1 | | |',
        '| Figure 2 | | |',
        '',
        '---',
        '',
        '## Definition of Successful Reproduction',
        '',
        '> ⚠️ **YOU MUST COMPLETE THIS SECTION.**',
        '> State exactly what constitutes successful reproduction.',
        '> Include numerical values and tolerance bands.',
        '',
        '[YOU MUST COMPLETE THIS]',
        '',
        '---',
        '',
        '## Known Issues and Limitations',
        '',
        '[YOU MUST COMPLETE THIS — document any platform '
        'sensitivity, stochasticity, or known reproduction '
        'limitations]',
        '',
        '---',
        '',
        '## Licence',
        '',
        'See `LICENCE_DRAFT.txt` (verify and rename to LICENCE).',
        '',
        '---',
        '',
        '## Contact',
        '',
        '[YOU MUST COMPLETE THIS — who should validators '
        'contact if reproduction fails?]',
        '',
        '---',
        '',
        f'*README_DRAFT.md generated by ValiChord Repository Readiness Check v15 — {now}*',
        '*Verify all content before removing _DRAFT from filename.*',
    ]

    # append original readme if it existed but was inadequate
    if existing_readme and len(existing_readme.strip()) > 50:
        lines += [
            '',
            '---',
            '',
            '## Original README Content (for reference)',
            '',
            '> The following is the original README content.',
            '> Use it to fill in the sections above.',
            '',
            existing_readme,
        ]

    out = output_dir / 'README_DRAFT.md'
    out.write_text('\n'.join(lines), encoding='utf-8-sig')
    print(f"  → README_DRAFT.md")


# ── requirements_DRAFT.txt ───────────────────────────────────────────────────

def _generate_requirements_draft(repo_dir, all_files,
                                   findings, output_dir):
    """Generate requirements_DRAFT.txt from import statements."""

    # preserve existing requirements_DRAFT.txt from prior run
    prior_draft = next((f for f in all_files if f.name.lower() == "requirements_draft.txt"), None)
    if prior_draft:
        prior_content = prior_draft.read_text(encoding="utf-8", errors="ignore")
        out = output_dir / "requirements_DRAFT.txt"
        out.write_text(
            "# Prior requirements_DRAFT.txt preserved from previous ValiChord run.\n"
            "# Review and pin all versions before renaming to requirements.txt.\n"
            "#\n" + prior_content, encoding="utf-8-sig")
        print("  -> requirements_DRAFT.txt (preserved from prior run)")
        return
    # Collect all requirements*.txt files to handle requirements_extra.txt etc.
    import re as _re2
    req_files_all = sorted(
        [f for f in all_files if _re2.match(r'requirements.*\.txt$', f.name.lower())],
        key=lambda x: x.name
    )
    if req_files_all:
        combined_lines = []
        for rf in req_files_all:
            try:
                rf_lines = rf.read_text(encoding='utf-8', errors='ignore').splitlines()
                combined_lines.append(f'# --- {rf.name} ---')
                combined_lines += rf_lines
            except Exception:
                pass
        combined = '\n'.join(combined_lines)
        pinned = [l for l in combined_lines if '==' in l and not l.strip().startswith('#')]
        unpinned_git = [l for l in combined_lines if l.strip().startswith('git+')]
        loose = [l for l in combined_lines if _re2.match(r'[\w.-]+\s*[><!]=', l.strip()) and '==' not in l]
        # packages with no version spec at all (bare package names)
        unpinned_bare = [l for l in combined_lines
                         if l.strip() and not l.strip().startswith('#')
                         and not l.strip().startswith('-')
                         and not l.strip().startswith('git+')
                         and '==' not in l and not _re2.match(r'[\w.-]+\s*[><!]=', l.strip())
                         and _re2.match(r'^[\w.-]+$', l.strip())]
        has_issues = unpinned_git or loose or unpinned_bare
        out = output_dir / 'requirements_DRAFT.txt'
        file_list = ', '.join(f.name for f in req_files_all)
        if pinned and not has_issues:
            header = [
                f'# Source: {file_list}',
                f'# {len(pinned)} packages — all pinned to exact versions.',
                '# Verify these versions match your environment before deposit.',
                '#',
            ]
            msg = '\n'.join(header) + '\n' + combined
            out.write_text(msg, encoding='utf-8-sig')
            return
        elif combined_lines:
            header = [f'# Source: {file_list}']
            if unpinned_git:
                header.append('# WARNING: git+ URLs present — pin to commit SHA before deposit')
            if loose:
                header.append('# WARNING: loose constraints (>=, !=) found — change to == before deposit')
            if unpinned_bare:
                header.append(f'# ACTION NEEDED: {len(unpinned_bare)} package(s) have no version — add ==X.Y.Z')
            header.append('#')
            # annotate unpinned lines inline
            annotated = []
            for l in combined_lines:
                s = l.strip()
                if s and not s.startswith('#') and not s.startswith('-') and '==' not in s:
                    annotated.append(l + '  # <-- pin version: packagename==X.Y.Z')
                else:
                    annotated.append(l)
            msg = '\n'.join(header) + '\n' + '\n'.join(annotated)
            out.write_text(msg, encoding='utf-8-sig')
            return
    # conda repo — handle environment.yml before generic dep file loop
    _env_file = min((f for f in all_files if f.name.lower() in {'environment.yml', 'environment.yaml'}),
                    key=lambda x: len(x.parts), default=None)
    if _env_file:
        try:
            import re as _renv
            _env_src = _env_file.read_text(encoding='utf-8', errors='ignore')
            _pkgs = []
            _in_deps = False
            for _line in _env_src.splitlines():
                _s = _line.strip()
                if _s.startswith('dependencies:'):
                    _in_deps = True
                    continue
                if _in_deps and _s and not _s.startswith('-') and not _s.startswith('#') and ':' in _s:
                    _in_deps = False
                if not _in_deps or not _s.startswith('-'):
                    continue
                _pkg = _s.lstrip('- ').strip()
                if _pkg and _pkg != 'pip' and not _pkg.startswith('pip:') and not _pkg.startswith('{'):
                    _pkgs.append(_pkg)
            _unpinned = [p for p in _pkgs if not _renv.match(r'^[\w\-\.]+=\d', p)]
            out = output_dir / 'requirements_DRAFT.txt'
            _lines = [
                f'# Source: {_env_file.name}',
                '# conda environment detected.',
                '# To capture exact pinned versions, run in your original environment:',
                '#   conda env export --no-builds > environment.yml',
                '#',
                '# Packages listed in environment.yml:',
                '',
            ]
            for _p in _pkgs:
                _lines.append(f'  {_p}')
            if _unpinned:
                _lines += [
                    '',
                    f'# WARNING: {len(_unpinned)} package(s) are unpinned or loosely pinned:',
                    f'#   {", ".join(_unpinned[:8])}',
                    '# Pin all packages with exact conda syntax: packagename=X.Y.Z',
                ]
            out.write_text('\n'.join(_lines), encoding='utf-8-sig')
            print('  -> requirements_DRAFT.txt (from environment.yml)')
            return
        except Exception:
            pass

    for dep_file in all_files:
        if dep_file.name.lower() in DEPENDENCY_FILES:
            try:
                existing = dep_file.read_text(encoding="utf-8", errors="ignore")
                pinned = [l for l in existing.splitlines() if "==" in l and not l.strip().startswith("#")]
                if pinned:
                    out = output_dir / "requirements_DRAFT.txt"
                    msg = ("# Existing file: " + dep_file.name + "\n"
                           "# " + str(len(pinned)) + " pinned packages found - no DRAFT needed.\n"
                           "# Verify versions are correct before deposit.\n#\n" + existing)
                    out.write_text(msg, encoding="utf-8-sig")
                    return
                else:
                    # existing file found but versions unpinned
                    if dep_file.name.lower() == "pyproject.toml":
                        # extract only dependencies from [project] section
                        import re as _re
                        dep_section = _re.search(
                            r'dependencies\s*=\s*\[([^\]]+)\]', existing, _re.DOTALL)
                        if dep_section:
                            raw_deps = dep_section.group(1)
                            pkgs = _re.findall(r'["\']([a-zA-Z][a-zA-Z0-9_\-\.]*)', raw_deps)
                            bounds = _re.findall(r'["\']([a-zA-Z][^"\']*)["\']\s*,?', raw_deps)
                            out = output_dir / "requirements_DRAFT.txt"
                            lines_out = [
                                "# pyproject.toml detected — dependencies extracted from [project] dependencies",
                                "# These have minimum version bounds but need exact pinning for reproducibility.",
                                "#", ""]
                            for b in bounds:
                                b = b.strip()
                                if b and not b.startswith("#"):
                                    lines_out.append(b + "  # pin to exact version")
                            out.write_text("\n".join(lines_out), encoding="utf-8-sig")
                            return
                    packages = [l.strip() for l in existing.splitlines()
                                if l.strip() and not l.strip().startswith("#")
                                and "=" in l and "[" not in l and "]" not in l]
                    if packages:
                        out = output_dir / "requirements_DRAFT.txt"
                        lines_out = ["# Existing " + dep_file.name + " found but versions are NOT pinned.",
                                     "# Add exact version numbers (e.g. pandas==2.1.3) before deposit.",
                                     "#", "# Current contents:", ""]
                        # Try to extract version bounds from embedded Pluto TOML
                        pluto_versions = {}
                        for jl_f in all_files:
                            if jl_f.suffix.lower() == '.jl':
                                jl_src = jl_f.read_text(encoding='utf-8', errors='ignore')
                                compat_m = re.search(r'\[compat\](.*?)(?:\[|$)', jl_src, re.DOTALL)
                                if compat_m:
                                    for vm in re.finditer(r'^(\w[\w\.]+)\s*=\s*"([^"]+)"', compat_m.group(1), re.MULTILINE):
                                        pluto_versions[vm.group(1).lower()] = vm.group(2)
                        def _pin_or_unknown(p):
                            if "==" in p or p.startswith("#"):
                                return p
                            pkg_name = p.split("==")[0].split(">=")[0].split("~=")[0].strip()
                            ver = pluto_versions.get(pkg_name.lower())
                            if ver:
                                return f"{pkg_name}>={ver.lstrip('~^')}  # from embedded Pluto compat block"
                            return p + "==UNKNOWN"
                        lines_out += [_pin_or_unknown(p) for p in packages]
                        out.write_text("\n".join(lines_out), encoding="utf-8-sig")
                        return
            except Exception:
                pass
    # Identify .txt files that contain code and classify their language
    _ctxt_r_pat = re.compile(r'library\s*\(|require\s*\(', re.IGNORECASE)
    _ctxt_stata_pat = re.compile(r'^\s*(?:use|cd|ssc\s+install|insheet|infile)\s', re.MULTILINE)
    _ctxt_py_pat = re.compile(r'^(?:import|from)\s+\w', re.MULTILINE)
    _code_txt_langs = {}
    for _ctf in all_files:
        if not _is_code_txt(_ctf):
            continue
        try:
            _ctf_src = _ctf.read_text(encoding='utf-8', errors='ignore')
            if _ctxt_r_pat.search(_ctf_src):
                _code_txt_langs[_ctf] = 'r'
            elif _ctxt_stata_pat.search(_ctf_src):
                _code_txt_langs[_ctf] = 'stata'
            elif _ctxt_py_pat.search(_ctf_src):
                _code_txt_langs[_ctf] = 'python'
            else:
                _code_txt_langs[_ctf] = 'unknown'
        except Exception:
            _code_txt_langs[_ctf] = 'unknown'

    imports = set()

    import ast as _ast
    # scan .ipynb notebooks for imports
    import json as _json
    for f in all_files:
        if f.suffix.lower() == '.ipynb':
            try:
                nb = _json.loads(f.read_text(encoding='utf-8', errors='ignore'))
                for cell in nb.get('cells', []):
                    if cell.get('cell_type') == 'code':
                        src = ''.join(cell.get('source', []))
                        for line in src.splitlines():
                            line = line.strip()
                            m = re.match(r'^import\s+([\w]+)', line)
                            if m: imports.add(m.group(1))
                            m = re.match(r'^from\s+([\w]+)', line)
                            if m: imports.add(m.group(1))
            except Exception:
                pass
    for f in all_files:
        if f.suffix.lower() == '.py':
            try:
                src = f.read_text(encoding='utf-8', errors='ignore')
                try:
                    tree = _ast.parse(src)
                    for node in _ast.walk(tree):
                        if isinstance(node, _ast.Import):
                            for alias in node.names:
                                imports.add(alias.name.split('.')[0])
                        elif isinstance(node, _ast.ImportFrom):
                            if node.module:
                                imports.add(node.module.split('.')[0])
                except SyntaxError:
                    for line in src.splitlines():
                        line = line.strip()
                        m = re.match(r'^import\s+([\w]+)', line)
                        if m:
                            imports.add(m.group(1))
                        m = re.match(r'^from\s+([\w]+)', line)
                        if m:
                            imports.add(m.group(1))
            except Exception:
                pass
    # also scan .txt code files detected as Python
    for _ctf in [f for f, lang in _code_txt_langs.items() if lang == 'python']:
        try:
            src = _ctf.read_text(encoding='utf-8', errors='ignore')
            for line in src.splitlines():
                line = line.strip()
                m = re.match(r'^import\s+([\w]+)', line)
                if m:
                    imports.add(m.group(1))
                m = re.match(r'^from\s+([\w]+)', line)
                if m:
                    imports.add(m.group(1))
        except Exception:
            pass

    # scan .jl / Pluto notebooks for 'using' statements
    julia_stdlib = {'Random', 'Statistics', 'LinearAlgebra', 'Dates', 'Printf',
                    'Base', 'Core', 'Main', 'Pkg', 'Test', 'Logging', 'REPL',
                    'InteractiveUtils', 'Distributed', 'Serialization',
                    'Markdown', 'Unicode', 'DelimitedFiles', 'SparseArrays',
                    'SharedArrays', 'Mmap', 'Profile', 'FileWatching'}
    julia_imports = set()
    for f in all_files:
        if f.suffix.lower() in {'.jl'}:
            try:
                src = f.read_text(encoding='utf-8', errors='ignore')
                for line in src.splitlines():
                    line = line.strip()
                    m = re.match(r'^using\s+([\w,\s]+)', line)
                    if m:
                        for pkg in re.split(r'[,\s]+', m.group(1)):
                            pkg = pkg.strip()
                            if pkg and pkg not in julia_stdlib:
                                julia_imports.add(pkg)
            except Exception:
                pass
    # Julia imports added after Python stdlib filter (see below)
    # filter out stdlib and local modules
    stdlib = {
        'os', 'sys', 're', 'math', 'json', 'csv', 'io',
        'time', 'datetime', 'pathlib', 'shutil', 'tempfile',
        'collections', 'itertools', 'functools', 'operator',
        'string', 'random', 'copy', 'abc', 'typing',
        'dataclasses', 'enum', 'warnings', 'logging',
        'unittest', 'subprocess', 'threading', 'multiprocessing',
        'argparse', 'configparser', 'hashlib', 'base64',
        'urllib', 'http', 'email', 'html', 'xml', 'sqlite3',
        'pickle', 'struct', 'array', 'queue', 'socket',
        'ssl', 'uuid', 'platform', 'inspect', 'importlib',
        'ast', 'dis', 'traceback', 'contextlib', 'weakref',
        'gc', 'ctypes', 'builtins', 'types', 'textwrap',
        'pprint', 'glob', 'fnmatch', 'stat', 'pwd', 'grp',
        'zipfile', 'tarfile', 'gzip', 'bz2', 'lzma',
        'zlib', 'binascii', 'codecs',
        'locale', 'statistics', 'signal',
    }

    # local python files in repo
    local_modules = {
        f.stem.lower() for f in all_files
        if f.suffix.lower() == '.py'
    }

    external = sorted(
        imp for imp in imports
        if imp.lower() not in stdlib
        and imp.lower() not in local_modules
        and not imp.startswith('_')
    )
    # Merge Julia imports after Python stdlib filter so CSV etc. aren't excluded
    external = sorted(set(external) | {pkg for pkg in julia_imports if not pkg.startswith('_')})

    # Second-pass: any name whose lowercase form matches the stem of a file
    # in the repository is treated as a local module.  Checking all files
    # (not just .py) catches data/script filenames with date suffixes or
    # unusual capitalisation that appear as import names (e.g.
    # Training_geometries_Amazonia_20040401_20050401).  The valid-identifier
    # guard avoids false suppression from data files whose names contain
    # spaces, hyphens, or other characters that can't be Python identifiers.
    import re as _re_mod
    _all_stems = {
        f.stem.lower() for f in all_files
        if _re_mod.match(r'^[A-Za-z_][A-Za-z0-9_]*$', f.stem)
    }
    external = [pkg for pkg in external if pkg.lower() not in _all_stems]

    # Third-pass: heuristic patterns for local module names that may not have
    # a matching file in the deposit (e.g. the file lives on the researcher's
    # machine but was imported in a notebook shipped without it).  Any import
    # whose name matches these patterns is almost certainly a local script, not
    # a PyPI package — real packages never carry 8-digit date suffixes.
    _LOCAL_MODULE_PATTERNS = [
        r'.*_\d{8}_\d{8}$',  # e.g. Training_geometries_Amazonia_20040401_20050401
        r'.*_\d{8}$',         # e.g. Training_geometries_Amazonia_20040401
        r'.*_\d{6,}$',        # any trailing 6+-digit run (YYYYMM, YYYYMMDD…)
    ]
    _local_pat = _re_mod.compile('|'.join(f'(?:{p})' for p in _LOCAL_MODULE_PATTERNS))
    external = [pkg for pkg in external if not _local_pat.match(pkg)]

    # Known import aliases and proprietary API handles that are NOT PyPI packages.
    # These appear as top-level import names but resolve to sub-modules of an
    # existing package or to a vendor/tool-specific API that cannot be pip-installed.
    _import_false_positives = {
        'cmap',         # matplotlib.cm aliased at call site (e.g. import matplotlib.cm as cmap)
        'func_module',  # COMSOL Python API internal module, not on PyPI
        'mpl_toolkits', # part of matplotlib — no separate pip install needed
    }
    external = [pkg for pkg in external if pkg.lower() not in _import_false_positives]

    # Scan .py files for inline version comments, e.g.:
    #   import numpy as np  # Package version: 1.21.6
    #   import pandas        # version: 1.4.3
    _INLINE_VERSION_RE = re.compile(
        r'(?:import|from)\s+([\w.]+).*#\s*(?:Package\s+)?[Vv]ersion[:\s]+(\d[\d.]+)',
        re.IGNORECASE
    )
    _inline_versions: dict = {}
    for _ivf in all_files:
        if _ivf.suffix.lower() == '.py':
            try:
                _iv_src = _ivf.read_text(encoding='utf-8', errors='ignore')
                for _ivm in _INLINE_VERSION_RE.finditer(_iv_src):
                    _iv_name = _ivm.group(1).split('.')[0].lower()
                    if _iv_name not in _inline_versions:
                        _inline_versions[_iv_name] = _ivm.group(2)
            except Exception:
                pass

    # Determine whether all externally-detected packages have inline versions.
    # _inline_versions is keyed by import name — no PyPI alias lookup needed.
    _all_have_inline = bool(external) and all(
        pkg.lower() in _inline_versions for pkg in external
    )

    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    if _all_have_inline:
        _version_notice = [
            '# - Version numbers sourced from inline comments in code files',
            '#   Verify these match your actual environment before deposit.',
            '#   Generate a formal requirements.txt for long-term reproducibility.',
        ]
    else:
        _version_notice = [
            '# - ALL VERSION NUMBERS ARE UNKNOWN',
            '#   You must supply exact versions before this file',
            '#   can be used for reproduction',
        ]

    lines = [
        '# ============================================================',
        '# DEPENDENCY EXTRACTION NOTICE',
        '# Generated by ValiChord Repository Readiness Check v15',
        '#',
        '# These package names were inferred from import statements',
        '# by static analysis. This list is NOT authoritative.',
        '#',
        '# - Local module names have been excluded',
        '# - Standard library modules have been excluded',
    ] + _version_notice + [
        '# - This list may include optional or unused packages',
        '# - This list may miss dynamically imported packages',
        '#',
        f'# Generated: {now}',
        '# ============================================================',
        '',
    ]

    # detect language-specific dependency systems
    all_suffixes = {f.suffix.lower() for f in all_files}
    if any(f.name == 'Snakefile' for f in all_files):
        all_suffixes.add('.smk')
    # augment with virtual suffixes from code-txt language detection
    for _ctf, _lang in _code_txt_langs.items():
        if _lang == 'r':
            all_suffixes.add('.r')
        elif _lang == 'stata':
            all_suffixes.add('.do')
        elif _lang == 'python':
            all_suffixes.add('.py')
    all_names = {f.name.lower() for f in all_files}

    # Extract version bounds from Project.toml [compat] or embedded Pluto TOML
    pluto_compat = {}
    # Standard Project.toml
    for toml_f in all_files:
        if toml_f.name.lower() == 'project.toml':
            try:
                toml_src = toml_f.read_text(encoding='utf-8', errors='ignore')
                compat_m = re.search(r'\[compat\](.*?)(?:\[|$)', toml_src, re.DOTALL)
                if compat_m:
                    for vm in re.finditer(r'^(\w[\w.]+)\s*=\s*"([^"]+)"', compat_m.group(1), re.MULTILINE):
                        pluto_compat[vm.group(1).lower()] = vm.group(2).lstrip('~^')
            except Exception:
                pass
    # Embedded Pluto TOML (overrides if present)
    for jl_f in all_files:
        if jl_f.suffix.lower() == '.jl':
            try:
                jl_src = jl_f.read_text(encoding='utf-8', errors='ignore')
                compat_m = re.search(r'\[compat\](.*?)(?:\[|$)', jl_src, re.DOTALL)
                if compat_m:
                    for vm in re.finditer(r'^(\w[\w.]+)\s*=\s*"([^"]+)"', compat_m.group(1), re.MULTILINE):
                        pluto_compat[vm.group(1).lower()] = vm.group(2).lstrip('~^')
            except Exception:
                pass
    # Maps import name (lowercase) → PyPI install name when they differ.
    # Packages listed here will appear in requirements_DRAFT.txt with the
    # correct pip-installable name rather than the import name.
    _import_to_pypi = {
        'sklearn':               'scikit-learn',
        'skimage':               'scikit-image',
        'cv2':                   'opencv-python',
        'pil':                   'Pillow',
        'yaml':                  'PyYAML',
        'dotenv':                'python-dotenv',
        'dateutil':              'python-dateutil',
        'bs4':                   'beautifulsoup4',
        'umap':                  'umap-learn',
        'sentence_transformers': 'sentence-transformers',
        # Google Earth Engine / Google API
        'ee':                    'earthengine-api',
        'apiclient':             'google-api-python-client',
    }

    # Well-known PyPI packages where import name == install name.
    # Entries here get a clean "pkg==UNKNOWN" line without a warning.
    _known_pypi = {
        # scientific core
        'numpy', 'scipy', 'pandas', 'matplotlib', 'seaborn', 'plotly', 'bokeh',
        'statsmodels', 'sympy', 'networkx',
        # ML / deep learning
        'tensorflow', 'torch', 'torchvision', 'torchaudio', 'keras',
        'transformers', 'xgboost', 'lightgbm', 'catboost', 'pymc', 'arviz',
        'hdbscan', 'shap', 'hyperopt',
        # data / IO
        'sqlalchemy', 'pymongo', 'redis', 'h5py', 'tables', 'xlrd', 'openpyxl',
        'pyarrow', 'fastparquet',
        # scientific data formats
        'xarray', 'rioxarray', 'netcdf4',
        # image / vision
        'imageio',
        # web / networking / scraping
        'requests', 'flask', 'django', 'fastapi', 'aiohttp', 'httpx', 'urllib3',
        'google_play_scraper', 'app_store_scraper', 'scrapy', 'mechanize',
        'httplib2', 'oauth2client',
        # text / NLP
        'nltk', 'spacy', 'gensim', 'textblob', 'langdetect',
        # common utilities
        'click', 'rich', 'tqdm', 'tabulate', 'pydantic', 'attrs', 'pytest', 'joblib',
        'psutil', 'dask', 'numba', 'lxml', 'cryptography', 'paramiko',
        'celery', 'packaging', 'six',
        # serialisation / config
        'toml',
        # geo / spatial
        'geopandas', 'shapely', 'pyproj', 'rasterio', 'fiona',
        'cartopy', 'rioxarray', 'rasterstats', 'pyogrio', 'geemap',
        # visualisation extras
        'holoviews', 'hvplot', 'altair',
        'adjusttext', 'distinctipy',
        # stats / analysis
        'pymannkendall',
    }

    _draft_pkg_count = len(external)
    if external:
        _is_julia_repo = '.jl' in all_suffixes and '.py' not in all_suffixes
        for pkg in external:
            ver = pluto_compat.get(pkg.lower())
            if ver:
                lines.append(f'{pkg}>={ver}  # from Project.toml or Pluto [compat] — not an exact pin')
            elif _is_julia_repo:
                lines.append(f'{pkg}  # Julia package — add to Project.toml instead of pinning here')
            else:
                _pkg_lower = pkg.lower()
                _pypi_name = _import_to_pypi.get(_pkg_lower)
                # Inline version: check by import name first, then by PyPI alias
                _inline_ver = (
                    _inline_versions.get(_pkg_lower)
                    or (_pypi_name and _inline_versions.get(_pypi_name.lower().replace('-', '_')))
                    or None
                )
                _ver = _inline_ver or 'UNKNOWN'
                if _pypi_name:
                    # Known alias: emit the correct pip-installable name
                    lines.append(f'{_pypi_name}=={_ver}')
                elif _pkg_lower in _known_pypi:
                    # Import name == PyPI name
                    lines.append(f'{pkg}=={_ver}')
                elif _pkg_lower == 'google':
                    # Ambiguous top-level namespace — many google.* packages exist
                    lines.append(
                        f'# google.*==UNKNOWN'
                        f'  # WARNING: "google" is an ambiguous namespace — could be'
                        f' google-cloud, google-auth, google-api-python-client, etc.'
                        f' Check which google.* sub-package you import and list it explicitly.'
                    )
                elif _pkg_lower in ('osgeo', 'osgeo_utils'):
                    # GDAL Python bindings — not on PyPI under the import name
                    lines.append(
                        f'# {pkg}  # installed via GDAL:'
                        f' pip install gdal  (or: conda install -c conda-forge gdal)'
                    )
                else:
                    lines.append(
                        f'{pkg}=={_ver}'
                        f'  # WARNING: not found on PyPI — verify this is a real dependency'
                    )
    elif 'project.toml' in all_names and '.jl' in all_suffixes:
        lines += [
            '# Julia repository detected.',
            '# NOTE: Julia uses Project.toml + Manifest.toml for version pinning,',
            '# not requirements.txt. Packages below are for reference only.',
            '# Fix: julia --project=. -e "using Pkg; Pkg.add([...]); Pkg.resolve()" then commit Project.toml + Manifest.toml.',
            '# Dependencies are managed by Project.toml and Manifest.toml.',
            '# No requirements_DRAFT.txt needed.',
            '# To install: julia --project=. -e "using Pkg; Pkg.instantiate()"',
        ]
    elif 'renv.lock' in all_names or bool(all_suffixes & {'.r', '.rmd', '.qmd'}):
        # If renv.lock present, extract exact versions
        if 'renv.lock' in all_names:
            renv_file = min((f for f in all_files if f.name.lower() == 'renv.lock'),
                            key=lambda x: len(x.parts), default=None)
            if renv_file:
                try:
                    import json as _rjson
                    renv_data = _rjson.loads(renv_file.read_text(encoding='utf-8', errors='ignore'))
                    pkgs = renv_data.get('Packages', {})
                    r_ver = renv_data.get('R', {}).get('Version', 'unknown')
                    lines += [f'# renv.lock present — R {r_ver}',
                              '# Exact versions locked. Run: Rscript -e "renv::restore()"',
                              '# Packages in renv.lock:', '']
                    for pname, pinfo in sorted(pkgs.items()):
                        ver = pinfo.get('Version', 'unknown')
                        src = pinfo.get('Source', 'CRAN')
                        lines.append(f'{pname}  # {ver}  ({src})')
                    out = output_dir / 'requirements_DRAFT.txt'
                    out.write_text('\n'.join(lines), encoding='utf-8-sig')
                    print('  -> requirements_DRAFT.txt (from renv.lock)')
                    return
                except Exception:
                    pass
        r_files = _researcher_r_files(all_files, repo_dir)
        r_files += [f for f, lang in _code_txt_langs.items() if lang == 'r']
        r_libs = set()
        # Named-argument keywords that are NOT package names
        _named_arg_kws = frozenset({'package', 'lib.loc', 'quietly', 'warn.conflicts',
                                    'verbose', 'character.only', 'logical.return',
                                    'mask.ok', 'exclude', 'include.only', 'attach.required'})
        # library(pkg) / require(pkg)
        lib_pat = re.compile(r'(?:library|require)\s*\(\s*["\']?([\w\.]+)')
        # pacman::p_load(pkg1, pkg2, ...) or p_load(pkg1, ...)
        pacman_pat = re.compile(r'(?:pacman::)?p_load\s*\(([^)]+)\)')
        # install.packages("pkg") or install.packages(c("pkg1","pkg2",...))
        install_single_pat = re.compile(r'install\.packages\s*\(\s*["\']?([\w\.]+)["\']?')
        install_vec_pat = re.compile(r'install\.packages\s*\(\s*c\s*\(([^)]+)\)')
        # ANY c("pkg1","pkg2",...) vector — catches any variable name pattern.
        # Only extract quoted strings that look like valid R package names.
        any_c_vec_pat = re.compile(r'\bc\s*\(([^)]{10,})\)')  # ≥10 chars to avoid c(1,2,3)

        def _extract_quoted_pkgs(text_fragment):
            return [p for p in re.findall(r'["\']+([\w\.]+)["\']', text_fragment)
                    if len(p) >= 2 and re.match(r'^[A-Za-z][\w\.]*$', p)
                    and p.lower() not in _named_arg_kws]

        # Sources to scan: all researcher R files + README code blocks
        _readme_src = ''
        for _rrf in all_files:
            if _rrf.name.lower() in {'readme.md', 'readme.txt', 'readme.rst'}:
                try:
                    _readme_src = _rrf.read_text(encoding='utf-8', errors='ignore')
                except Exception:
                    pass
                break
        _sources_to_scan = []
        for rf in r_files:
            try:
                _sources_to_scan.append((rf, rf.read_text(encoding='utf-8', errors='ignore')))
            except Exception:
                pass
        if _readme_src:
            _sources_to_scan.append((None, _readme_src))
        for _rf, src in _sources_to_scan:
            # library() / require()
            for m in lib_pat.finditer(src):
                pkg = m.group(1)
                if pkg.lower() not in _named_arg_kws:
                    r_libs.add(pkg)
            # pacman::p_load()
            for m in pacman_pat.finditer(src):
                for pkg in _extract_quoted_pkgs(m.group(1)):
                    r_libs.add(pkg)
                # Also catch unquoted p_load(tidyverse, ggplot2, ...)
                for pkg in re.findall(r'\b([A-Za-z][\w\.]+)\b', m.group(1)):
                    if len(pkg) >= 2 and pkg.lower() not in _named_arg_kws:
                        r_libs.add(pkg)
            # install.packages("pkg") or install.packages(c(...))
            for m in install_single_pat.finditer(src):
                pkg = m.group(1)
                if pkg.lower() not in _named_arg_kws and len(pkg) >= 2:
                    r_libs.add(pkg)
            for m in install_vec_pat.finditer(src):
                for pkg in _extract_quoted_pkgs(m.group(1)):
                    r_libs.add(pkg)
            # Any c("pkg1","pkg2",...) with quoted strings — catch vector patterns
            # regardless of variable name or context
            for m in any_c_vec_pat.finditer(src):
                fragment = m.group(1)
                # Only process if fragment looks like a package-name list
                # (has quoted strings, not a mix of numbers/formulas)
                quoted = _extract_quoted_pkgs(fragment)
                if quoted and len(quoted) >= 2:
                    # Context check: within 3 lines, is there library/require/lapply/install?
                    # Lookahead/lookbehind in source for context
                    start = max(0, m.start() - 200)
                    end = min(len(src), m.end() + 200)
                    ctx = src[start:end].lower()
                    if any(kw in ctx for kw in ('library', 'require', 'install',
                                                 'lapply', 'sapply', 'p_load')):
                        for pkg in quoted:
                            r_libs.add(pkg)
            # pkg:: namespace calls — catches packages used without library()
            # e.g. kableExtra::kbl(), dplyr::filter()
            for ns_m in re.finditer(r'\b([A-Za-z][A-Za-z0-9.]+)::[A-Za-z]', src):
                pkg = ns_m.group(1)
                if len(pkg) >= 2 and pkg.lower() not in _named_arg_kws:
                    r_libs.add(pkg)
        # Record scan count for the header note
        _r_files_scanned = len([s for s in _sources_to_scan if s[0] is not None])
        # Exclude base-R packages — they ship with R and need no installation
        r_libs -= {p for p in r_libs if p.lower() in {b.lower() for b in _BASE_R_PACKAGES}}
        # Build github_pkgs map and collect BiocManager/install.packages from install*.R
        _ghpat = re.compile(r'(?:devtools|remotes)::install_github\s*\(\s*["\']([^"\'/]+/([\w.-]+))["\']', re.IGNORECASE)
        _biocpat = re.compile(r'BiocManager::install\s*\(\s*c\s*\(([^)]+)\)', re.IGNORECASE)
        _ipat = re.compile(r'install\.packages\s*\(\s*c\s*\(([^)]+)\)', re.IGNORECASE)
        gh_map = {}
        extra_pkgs = set()
        for _rf in all_files:
            if re.match(r'(install|setup).*\.r$', _rf.name.lower()):
                try:
                    _rsrc = _rf.read_text(encoding='utf-8', errors='ignore')
                    for _m in _ghpat.finditer(_rsrc):
                        gh_map[_m.group(2).lower()] = _m.group(1)
                    for _bm in _biocpat.finditer(_rsrc):
                        for _pkg in re.findall(r'["\']([\w.]+)["\']', _bm.group(1)):
                            extra_pkgs.add(_pkg)
                    for _im in _ipat.finditer(_rsrc):
                        for _pkg in re.findall(r'["\']([\w.]+)["\']', _im.group(1)):
                            extra_pkgs.add(_pkg)
                except Exception:
                    pass
        r_libs = r_libs | extra_pkgs
        # Re-apply base-R exclusion after merging install-script packages —
        # install*.R files may explicitly install base packages that were
        # already removed from r_libs above.
        r_libs -= {p for p in r_libs if p.lower() in {b.lower() for b in _BASE_R_PACKAGES}}
        _draft_pkg_count = len(r_libs)
        if r_libs:
            gh_list        = [p for p in sorted(r_libs) if p.lower() in gh_map]
            gh_likely_list = [p for p in sorted(r_libs) if p.lower() not in gh_map
                               and p.lower() in _GITHUB_LIKELY_LOWER]
            bioc_list      = [p for p in sorted(r_libs) if p.lower() not in gh_map
                               and p.lower() not in _GITHUB_LIKELY_LOWER
                               and p.lower() in _BIOC_LOWER]
            removed_list   = [p for p in sorted(r_libs) if p.lower() not in gh_map
                               and p.lower() not in _GITHUB_LIKELY_LOWER
                               and p.lower() not in _BIOC_LOWER
                               and p.lower() in _REMOVED_CRAN_LOWER]
            cran_list      = [p for p in sorted(r_libs) if p.lower() not in gh_map
                               and p.lower() not in _GITHUB_LIKELY_LOWER
                               and p.lower() not in _BIOC_LOWER
                               and p.lower() not in _REMOVED_CRAN_LOWER]
            lines += ['# R repository detected.',
                      f'# Packages detected from {_r_files_scanned} R script(s) (library()/require()/install.packages()):',
                      '# Add version numbers before deposit.', '']
            if cran_list:
                lines.append('# CRAN packages — install with install.packages():')
                for pkg in cran_list:
                    if pkg.lower() in _KNOWN_CRAN_LOWER:
                        lines.append(f'{pkg}  # version unknown')
                    else:
                        _cran_status = _check_cran_package(pkg)
                        if _cran_status == 'not_found':
                            lines.append(
                                f'{pkg}  # WARNING: \'{pkg}\' not found on CRAN'
                                f' — verify this package name is correct'
                            )
                        else:
                            # 'found' or 'unknown' (network error) — no warning
                            lines.append(f'{pkg}  # version unknown')
            if bioc_list:
                if cran_list:
                    lines.append('')
                lines += [
                    '# Bioconductor packages — install with BiocManager::install():',
                    '# First run: install.packages("BiocManager")',
                ]
                for pkg in bioc_list:
                    lines.append(f'{pkg}  # version unknown')
            if gh_likely_list:
                if cran_list or bioc_list:
                    lines.append('')
                lines += [
                    '# Possible GitHub-only packages — verify install method:',
                    '# These may not be on CRAN or Bioconductor.',
                    '# Check package documentation for the correct install command.',
                ]
                for pkg in gh_likely_list:
                    slug = _GITHUB_KNOWN_SLUGS.get(pkg.lower(), f'.../{pkg}')
                    lines.append(f'{pkg}  # version unknown — possibly: devtools::install_github("{slug}")')
            if gh_list:
                if cran_list or bioc_list or gh_likely_list:
                    lines.append('')
                lines.append('# GitHub packages (no CRAN release -- pinning required):')
                for pkg in gh_list:
                    repo = gh_map.get(pkg.lower(), 'unknown/unknown')
                    lines.append(f'{pkg}  # GitHub: {repo} -- commit unknown')
            if removed_list:
                if cran_list or bioc_list or gh_likely_list or gh_list:
                    lines.append('')
                lines.append('# ⚠️ Removed or retired packages — require special handling:')
                for pkg in removed_list:
                    msg = _REMOVED_CRAN_LOWER.get(pkg.lower(), 'removed from CRAN — check for alternatives')
                    lines.append(f'{pkg}  # REMOVED FROM CRAN — {msg}')
        else:
            lines += [
                '# R repository detected.',
                '# If using renv: run renv::restore() to install dependencies.',
                '# If not using renv: add your R package dependencies manually.',
            ]
    elif '.do' in all_suffixes or '.ado' in all_suffixes:
        lines += [
            '# Stata repository detected.',
            '# List required Stata packages (ssc install) manually.',
        ]
    elif '.m' in all_suffixes:
        # Scan .m files for inline toolbox requirements
        toolbox_pattern = re.compile(r'[(%]?requires?\s+([\w\s]+(?:Toolbox|EEGLAB))', re.IGNORECASE)
        found_toolboxes = set()
        # Also scan README for toolbox requirements
        for rf in all_files:
            if rf.name.lower() in {'readme.md', 'readme.txt', 'readme.rst'}:
                try:
                    rsrc = rf.read_text(encoding='utf-8', errors='ignore')
                    for m in re.finditer(r'([\w\s]+Toolbox)', rsrc, re.IGNORECASE):
                        tb = m.group(1).strip()
                        if len(tb) < 60:
                            found_toolboxes.add(tb)
                except Exception:
                    pass
        eeglab_fns = {'pop_epoch', 'pop_autorej', 'pop_resample', 'pop_eegfiltnew',
                      'eeglab', 'pop_loadset', 'pop_saveset', 'runica'}
        found_eeglab = False
        for mf in all_files:
            if mf.suffix.lower() == '.m':
                try:
                    msrc = mf.read_text(encoding='utf-8', errors='ignore')
                    for m in toolbox_pattern.finditer(msrc):
                        tb = m.group(1).strip()
                        # Normalise abbreviated MathWorks names to full current names
                        if tb.lower() in {'statistics toolbox', 'statistics and machine learning toolbox'}:
                            tb = 'Statistics and Machine Learning Toolbox'
                        found_toolboxes.add(tb)
                    if any(fn in msrc for fn in eeglab_fns):
                        found_eeglab = True
                except Exception:
                    pass
        if found_eeglab:
            found_toolboxes.add('EEGLAB (third-party — download from sccn.ucsd.edu/eeglab)')
        if found_toolboxes:
            lines += ['# MATLAB repository detected.',
                      '# Required toolboxes detected from code comments:']
            for tb in sorted(found_toolboxes):
                lines.append(f'# - {tb}')
            lines += ['# Verify these are licensed and installed before running.', '']
        else:
            lines += [
                '# MATLAB repository detected.',
                '# List required MATLAB toolboxes manually.',
        ]
    else:
        lines += [
            '# No external imports detected.',
            '# Add your dependencies manually.',
        ]

    lines += [
        '',
        '# ============================================================',
        '# Local modules found in this repository (excluded above):',
    ]
    for m in sorted(local_modules):
        lines.append(f'# {m}')
    lines.append('# ============================================================')

    out = output_dir / 'requirements_DRAFT.txt'
    out.write_text('\n'.join(lines), encoding='utf-8-sig')
    print(f"  → requirements_DRAFT.txt "
          f"({_draft_pkg_count} packages detected)")


# ── QUICKSTART_DRAFT.md ──────────────────────────────────────────────────────


def _renumber_steps(steps):
    """Resequence numbered steps (lines starting with a digit and .) after deletions."""
    result = []
    n = 1
    for s in steps:
        import re as _re
        if _re.match(r'^\d+\.', s):
            s = _re.sub(r'^\d+\.', f'{n}.', s, count=1)
            n += 1
        elif s.startswith('N.'):
            s = s.replace('N.', f'{n}.', 1)
            n += 1
        result.append(s)
    return result


def _quickstart_step2(all_files, code_files):
    """Return language-appropriate step 2 for QUICKSTART."""
    suffixes = {f.suffix.lower() for f in code_files}
    if any(f.name == 'Snakefile' for f in all_files):
        suffixes.add('.smk')
    names = {f.name.lower() for f in all_files}
    # Docker repo — replace all install steps with build/run
    if 'dockerfile' in names:
        import re as _redock
        _img = 'my-analysis'
        _df = min((f for f in all_files if f.name == 'Dockerfile'),
                  key=lambda x: len(x.parts), default=None)
        if _df:
            try:
                _dsrc = _df.read_text(encoding='utf-8', errors='ignore')
                # try to derive image name from repo dir or LABEL
                _label = _redock.search(r'LABEL.*image[_-]?name[=\s]+["\']?([\w_-]+)', _dsrc, _redock.IGNORECASE)
                if _label:
                    _img = _label.group(1).lower()
                else:
                    # use parent directory name as image name
                    _img = _df.parent.name.lower().replace(' ', '-') or 'my-analysis'
            except Exception:
                pass
        return [
            '2. Build the Docker image: `docker build -t ' + _img + ' .`',
            '3. Run: `docker run -v $(pwd)/data:/app/data ' + _img + '`',
            '   (adjust volume mounts to match your data directory)',
        ]
    # conda repo takes priority — single env file replaces all other dep steps
    if 'environment.yml' in names or 'environment.yaml' in names:
        env_file = 'environment.yml' if 'environment.yml' in names else 'environment.yaml'
        env_name = 'myenv'
        env_path = min((f for f in all_files if f.name.lower() == env_file),
                       key=lambda x: len(x.parts), default=None)
        if env_path:
            import re as _re
            m = _re.search(r'^name:\s*(\S+)', env_path.read_text(encoding='utf-8', errors='ignore'), _re.MULTILINE)
            if m:
                env_name = m.group(1)
        return [f'2. Create and activate environment: `conda env create -f {env_file} && conda activate {env_name}`']
    if '.smk' in suffixes or any(f.name == 'Snakefile' for f in all_files):
        return ['2. Run the Snakemake workflow: `snakemake --cores all`',
                '   (add --use-conda if per-rule conda: directives are present)']
    if any(f.suffix.lower() == '.nf' for f in all_files):
        nf_main = next((f.name for f in all_files if f.name.lower() == 'main.nf'), 'main.nf')
        return ['2. Run the Nextflow pipeline:',
                f'   nextflow run {nf_main}',
                '   (add -with-docker or -with-conda if container/conda directives are present)']
    if '.r' in suffixes or '.rmd' in suffixes:
        # Check for reticulate — R calls Python at runtime, need both installs
        import re as _reretc
        _has_reticulate = any(
            _reretc.search(
                r'library\s*\(\s*reticulate|reticulate::',
                f.read_text(encoding='utf-8', errors='ignore')
            )
            for f in all_files if f.suffix.lower() in {'.r', '.rmd'}
        )
        _has_req = any(
            _reretc.match(r'requirements.*\.txt$', f.name.lower())
            for f in all_files
        )
        if _has_reticulate and _has_req:
            return [
                '2. Install Python dependencies: `pip install -r requirements.txt`',
                '3. Restore R environment: `Rscript -e "renv::restore()"`',
                '   (reticulate detected -- both R and Python environments required)',
            ]
        if 'renv.lock' in names:
            if _has_reticulate and _has_req:
                return ['2. Install Python dependencies: `pip install -r requirements.txt`',
                        '   Then restore R environment: `Rscript -e "renv::restore()"`',
                        '   (reticulate detected — both environments required)']
            return ['2. Restore R environment: `Rscript -e "renv::restore()"`',
                    '   (renv.lock present — exact package versions will be installed)']
        install_r = next((f.name for f in all_files
                         if re.match(r'install.*\.r$', f.name.lower())), None)
        if install_r:
            return ['2. Install R dependencies: `Rscript ' + install_r + '`']
        return ['2. Add version numbers to packages in `requirements_DRAFT.txt`, '
                'then run `renv::snapshot()` to create `renv.lock`']
    if '.jl' in suffixes:
        names = {f.name.lower() for f in all_files}
        if 'project.toml' in names:
            return ['2. Dependencies managed by `Project.toml` — run '
                    '`julia --project=. -e "using Pkg; Pkg.instantiate()"`']
        else:
            # No Project.toml — check for runtime Pkg.add() anti-pattern
            import re as _rejl
            _has_pkg_add = any(
                _rejl.search(r'Pkg\.add\s*\(', f.read_text(encoding='utf-8', errors='ignore'))
                for f in all_files if f.suffix.lower() == '.jl'
            )
            if _has_pkg_add:
                return ['2. Create Project.toml and Manifest.toml to lock package versions:',
                        '   julia --project=. -e "using Pkg; Pkg.add([\"Optim\", ...]); Pkg.resolve()"',
                        '   Then commit both Project.toml and Manifest.toml',
                        '   (see [CQ] finding — runtime Pkg.add() does not pin versions)']
            # No Project.toml — manually install detected packages
            jl_pkgs = sorted({
                pkg for f in all_files if f.suffix.lower() == '.jl'
                for line in f.read_text(encoding='utf-8', errors='ignore').splitlines()
                for m in [__import__('re').match(r'^using\s+([\w,\s]+)', line.strip())]
                if m
                for pkg in __import__('re').split(r'[,\s]+', m.group(1))
                if pkg.strip() and pkg.strip() not in {
                    'Random','Statistics','LinearAlgebra','Dates','Printf',
                    'Base','Core','Main','Pkg','Test','Logging','REPL',
                    'InteractiveUtils','Distributed','Serialization',
                    'Markdown','Unicode','DelimitedFiles','SparseArrays'}
            })
            if jl_pkgs:
                pkg_list = ', '.join(f'"{p}"' for p in jl_pkgs)
                return [f'2. Install required packages: `julia -e \'using Pkg; Pkg.add([{pkg_list}])\'`']
            return ['2. Install required Julia packages manually using `julia -e "using Pkg; Pkg.add(\"PackageName\")"`']
    # check for pyproject.toml package
    names = {f.name.lower() for f in all_files}
    if 'pyproject.toml' in names:
        return ['2. Install as editable package: `pip install -e .`']
    # Python — check if already pinned
    has_pinned = any(
        f.name.lower() in DEPENDENCY_FILES and
        any('==' in l for l in f.read_text(encoding='utf-8', errors='ignore').splitlines()
            if not l.strip().startswith('#'))
        for f in all_files if f.name.lower() in DEPENDENCY_FILES
    )
    has_requirements = any(f.name.lower() == 'requirements.txt' for f in all_files)
    if has_pinned:
        # Check if any requirements*.txt has git+ URLs or loose constraints
        import re as _reqs
        req_files_qs = [f for f in all_files if _reqs.match(r'requirements.*\.txt$', f.name.lower())]
        has_git_urls = any(
            any(l.strip().startswith('git+') for l in f.read_text(encoding='utf-8', errors='ignore').splitlines())
            for f in req_files_qs
        )
        extra_reqs = [f.name for f in req_files_qs if f.name.lower() != 'requirements.txt']
        if has_git_urls:
            cmds = ['pip install -r requirements.txt'] + [f'pip install -r {n}' for n in extra_reqs]
            cmd_lines = ['   ```bash'] + [f'   {c}' for c in cmds] + ['   ```']
            return ['2. Install dependencies (WARNING: git+ URLs in requirements_extra.txt need pinning before deposit):'] + cmd_lines
        elif extra_reqs:
            cmds = ['pip install -r requirements.txt'] + [f'pip install -r {n}' for n in extra_reqs]
            cmd_lines = ['   ```bash'] + [f'   {c}' for c in cmds] + ['   ```']
            return ['2. Install all dependencies:'] + cmd_lines
        # Check for known TF/numpy style conflicts in requirements
        import re as _recn
        _pinned = {}
        for _rf in all_files:
            if _recn.match(r'requirements.*\.txt$', _rf.name.lower()):
                try:
                    for _line in _rf.read_text(encoding='utf-8', errors='ignore').splitlines():
                        _m = _recn.match(r'^([\w.-]+)==([\d.]+)', _line.strip())
                        if _m: _pinned[_m.group(1).lower()] = _m.group(2)
                except Exception: pass
        def _ver(v, n=2): return tuple(int(x) for x in v.split('.')[:n])
        _has_conflict = (
            ('tensorflow' in _pinned and 'numpy' in _pinned and
             _ver(_pinned['tensorflow']) < (2,13) and _ver(_pinned['numpy']) >= (1,24))
            or ('torch' in _pinned and 'numpy' in _pinned and
                _ver(_pinned['torch']) < (2,0) and _ver(_pinned['numpy'],1) >= (2,))
        )
        if _has_conflict:
            return ['2. WARNING: version conflicts in requirements.txt — see [CN] finding.',
                    '   Fix conflicts before running: `pip install -r requirements.txt` will fail.']
        # Check for Python 2 syntax — pinned versions irrelevant if code won't run
        _has_py2 = any(
            re.search(r'^[ \t]*print\s+["\' \w]', f.read_text(encoding='utf-8', errors='ignore'), re.MULTILINE)
            for f in all_files if f.suffix.lower() == '.py'
        )
        if _has_py2:
            return ['2. WARNING: Python 2 syntax detected — see [CP] finding.',
                    '   Fix Python 2 syntax before installing: code will not run in Python 3.']
        _model_indicators = {'model', 'clf', 'classifier', 'regressor', 'estimator', 'pipeline', 'weights'}
        _has_model_pkl = any(
            f.suffix.lower() in {'.pkl', '.pickle'} and (
                any(ind in f.name.lower() for ind in _model_indicators) or
                any(part.lower() in {'models', 'model', 'checkpoints'} for part in f.parts)
            )
            for f in (all_files or [])
        )
        if _has_model_pkl:
            return ['2. Install dependencies: `pip install -r requirements.txt`',
                    '   NOTE: A committed model binary (.pkl) is present — see [CS] finding.',
                    '   Pickle files are version-specific; ensure your Python/library versions',
                    '   match those used to train the model, or retrain from scratch.']
        return ['2. Install dependencies: `pip install -r requirements.txt`']
    if '.m' in suffixes:
        import re as _rem2
        _tbs = []
        for _f in (all_files or []):
            if _f.name.lower() in {'readme.md', 'readme.txt', 'readme.rst'}:
                try:
                    for _tm in _rem2.finditer(r'([\w\s]+Toolbox)', _f.read_text(encoding='utf-8', errors='ignore'), _rem2.IGNORECASE):
                        _tb = _tm.group(1).strip()
                        if len(_tb) < 60: _tbs.append(_tb)
                except Exception: pass
        _tb_note = ('Toolboxes required: ' + ', '.join(sorted(set(_tbs)))) if _tbs else 'Check README for required toolboxes'
        return ['2. Ensure required MATLAB toolboxes are licensed and installed.',
                f'   {_tb_note}']
    if '.do' in suffixes or '.ado' in suffixes:
        return ['2. Open Stata and ensure required packages are installed']
    # JavaScript/web — detect from all_files because code_files excludes frontend dirs
    _JS_EXTS_QS = frozenset({'.js', '.ts', '.jsx', '.tsx', '.mjs', '.vue'})
    _STAT_EXTS_QS = frozenset({'.py', '.r', '.do', '.jl', '.m', '.sas', '.ipynb', '.rmd', '.qmd', '.ado'})
    _WEBAPP_VENDOR_QS = {'vendor', 'lib', 'dist', 'node_modules', 'target', 'bower_components'}
    if (any(f.suffix.lower() in _JS_EXTS_QS
            and not any(p.lower() in _WEBAPP_VENDOR_QS for p in f.parts)
            for f in all_files)
            and not any(f.suffix.lower() in _STAT_EXTS_QS for f in all_files)):
        _has_pkg_json_qs = any(f.name == 'package.json' for f in all_files)
        if _has_pkg_json_qs:
            return ['2. Install dependencies: `npm install  # or: yarn install`']
        return []  # No install step needed — open HTML entry point in browser
    if has_requirements:
        return ['2. Pin the version numbers in your existing `requirements.txt` (e.g. pandas==2.1.3)']
    return ['2. Add version numbers to `requirements_DRAFT.txt` and rename to `requirements.txt`']

_STDLIB_TOPS = frozenset({
    'abc', 'ast', 'asyncio', 'base64', 'binascii', 'builtins',
    'calendar', 'cmath', 'codecs', 'collections', 'concurrent',
    'contextlib', 'copy', 'csv', 'ctypes', 'dataclasses', 'datetime',
    'decimal', 'difflib', 'email', 'enum', 'errno', 'fnmatch', 'fractions',
    'functools', 'gc', 'glob', 'gzip', 'hashlib', 'heapq', 'hmac',
    'html', 'http', 'importlib', 'inspect', 'io', 'ipaddress',
    'itertools', 'json', 'keyword', 'linecache', 'locale', 'logging',
    'lzma', 'math', 'multiprocessing', 'numbers', 'operator', 'os',
    'pathlib', 'pickle', 'platform', 'pprint', 'queue', 'random',
    're', 'shlex', 'shutil', 'signal', 'socket', 'sqlite3',
    'ssl', 'stat', 'statistics', 'string', 'struct', 'subprocess',
    'sys', 'tarfile', 'tempfile', 'textwrap', 'threading', 'time',
    'timeit', 'traceback', 'typing', 'unicodedata', 'unittest',
    'urllib', 'uuid', 'warnings', 'weakref', 'xml', 'zipfile', 'zlib',
})


def _install_instructions(code_files, all_files=None):
    """Return language-appropriate install instructions."""
    suffixes = {f.suffix.lower() for f in code_files}
    # Stdlib-only trivial helper — no install step, just an informational note
    if len(code_files) == 1 and code_files[0].suffix.lower() == '.py':
        _cf = code_files[0]
        if (_cf.stat().st_size < 1024
                and any(kw in _cf.stem.lower()
                        for kw in {'reader', 'loader', 'parser', 'helper'})):
            _src = _cf.read_text(encoding='utf-8', errors='ignore')
            _mods = {
                m.group(1) or m.group(2)
                for m in re.finditer(
                    r'^\s*(?:import\s+(\w+)|from\s+(\w+)\s+import)',
                    _src, re.MULTILINE
                )
            }
            if _mods <= _STDLIB_TOPS:
                return ['3. No external dependencies — standard Python 3.6+ is sufficient.']
    # Docker repo — no separate install step needed
    if all_files and any(f.name == 'Dockerfile' for f in all_files):
        return []
    lines = []
    # conda repo — step 2 already covers install via _quickstart_step2; suppress step 3
    if all_files:
        names = {f.name.lower() for f in all_files}
        if 'environment.yml' in names or 'environment.yaml' in names:
            return []
    # Snakemake repo — step 2 is `snakemake --cores all`; suppress all further steps
    if all_files and any(f.name == 'Snakefile' or f.suffix.lower() == '.smk' for f in all_files):
        return []
    # Snakemake repo — step 2 is `snakemake --cores all`; suppress all further steps
    if all_files and any(f.name == 'Snakefile' or f.suffix.lower() == '.smk' for f in all_files):
        return []
    # Julia: step 2 already covers install via _quickstart_step2; suppress step 3
    if '.jl' in suffixes:
        return []  # handled in step 2
    if '.r' in suffixes or '.rmd' in suffixes:
        _all = all_files or []
        _names = {f.name.lower() for f in _all}
        if 'renv.lock' in _names:
            return lines  # step 2 already has renv::restore
        import re as _re3r
        if any(_re3r.match(r'install.*\.r$', fn) for fn in _names):
            return lines  # step 2 already has Rscript install_deps.R
        # No renv.lock — renv::restore() would fail; suggest install.packages instead
        _r_pkgs = []
        import re as _re3r2
        for _f in (all_files or []):
            if _re3r2.match(r'requirements.*\.txt$', _f.name.lower()):
                try:
                    for _line in _f.read_text(encoding='utf-8', errors='ignore').splitlines():
                        _pkg = _re3r2.split(r'[>=<!\[; ]', _line.strip())[0].strip()
                        if _pkg and not _pkg.startswith('#'): _r_pkgs.append(_pkg)
                except Exception: pass
        if _r_pkgs:
            _pkg_str = ', '.join(f"'{p}'" for p in _r_pkgs[:6])
            lines.append('3. Install R dependencies: '
                         f'`Rscript -e "install.packages(c({_pkg_str}))"` '
                         '(no renv.lock — see [AO] finding to create one)')
        else:
            lines.append('3. Install R dependencies (no renv.lock present — '
                         'see [AO] finding): `Rscript -e "renv::init(); renv::snapshot()"`')
    if '.do' in suffixes or '.ado' in suffixes:
        lines.append('3. Open Stata and run the master do-file listed above')
    if '.m' in suffixes:
        return lines  # MATLAB: step 2 covers toolbox check; step 3 not needed
    if '.py' in suffixes or (not lines and '.r' not in suffixes and '.rmd' not in suffixes
                              and '.nf' not in suffixes):
        # Only add step 3 pip install if step 2 didn't already cover it
        import re as _re3
        req_files_check = [f for f in (all_files or []) if _re3.match(r'requirements.*\.txt$', f.name.lower())]
        if not req_files_check:
            lines.append('3. Install dependencies: `pip install -r requirements.txt`')
    return lines

def _generate_quickstart_draft(repo_dir, all_files,
                                 findings, output_dir):
    """Generate QUICKSTART_DRAFT.md with inferred execution order."""

    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    archive_dirs = {"old", "archive", "deprecated", "unused", "backup", "old_versions"}
    _stata_lib_dirs = {'plus', 'personal', 'stbplus'}
    # Build frontend-dir exclusion set from all_files — immune to zip wrappers
    # and __MACOSX artefacts because all_files is already filtered.
    # Permissive check: has JS/HTML/CSS marker AND no analysis-code extension.
    _dir_exts_qs: dict = {}
    for _f in all_files:
        for _anc in _f.parents:
            if _anc == repo_dir:
                break
            _dir_exts_qs.setdefault(_anc, set()).add(_f.suffix.lower())
    _qs_frontend_dirs = {
        d for d, exts in _dir_exts_qs.items()
        if bool(exts & _FRONTEND_MARKERS_QS) and not bool(exts & _ANALYSIS_CODE_EXTS_QS)
    }
    code_files = [
        f for f in all_files
        if (f.suffix.lower() in CODE_EXTENSIONS or f.name == 'Snakefile' or _is_code_txt(f))
        and f.name not in {"__init__.py", "__main__.py"}
        and not _is_minified_qs(f)
        and not any(p.name.lower() in archive_dirs for p in f.parents)
        and not any(p.name.lower() in VENDOR_DIRS_QS for p in f.parents)
        and not any(fd in f.parents for fd in _qs_frontend_dirs)
        and not ('ado' in f.parts and any(p in _stata_lib_dirs for p in f.parts))
    ]

    # try to find execution order from README run block
    readme_order = []
    for rf in all_files:
        if rf.name.lower() in {'readme.md', 'readme.txt', 'readme.rst'}:
            try:
                rsrc = rf.read_text(encoding='utf-8', errors='ignore')
                # Find python/Rscript commands in code blocks
                for m in re.finditer(
                    r'(?:python|Rscript|julia)\s+([\w/.-]+\.(?:py|r|jl|m|sh))\b',
                    rsrc, re.IGNORECASE):
                    fname = m.group(1).split('/')[-1]
                    match = next((f for f in code_files if f.name == fname), None)
                    if match and match not in readme_order:
                        readme_order.append(match)
            except Exception:
                pass
    # try to find numbered scripts — support integer (01_, 1_), decimal (1.2_),
    # period/period-space (1. name, 1.name), and compound (3-1. name) prefixes;
    # sort by (major, minor) tuple for correct order
    numbered = []
    for f in code_files:
        # Separator: underscore, hyphen, or period-not-followed-by-digit
        m = re.match(r'^(\d+)(?:[.\-](\d+))?(?:[_\-]|\.(?!\d))', f.name)
        if m:
            major = int(m.group(1))
            minor = int(m.group(2)) if m.group(2) else 0
            numbered.append(((major, minor), f))
    numbered.sort(key=lambda x: x[0])

    # _PartN infix pattern (e.g. Master_Part1_Data.m, Script_Part2.R)
    # Only used when leading-prefix detection found nothing
    if not numbered:
        _part_candidates = []
        for f in code_files:
            mp = re.search(r'[_\-][Pp]art(\d+)', f.stem)
            if mp:
                _part_candidates.append(((int(mp.group(1)), 0), f))
        # Require ≥2 distinct part numbers to treat as an ordered sequence
        if len({key[0] for key, _ in _part_candidates}) >= 2:
            numbered = sorted(_part_candidates, key=lambda x: x[0])

    # prefer README order over alphabetical — track source for confidence level
    _numbered_from_filenames = bool(numbered)
    if readme_order and not numbered:
        numbered = [((i + 1, 0), f) for i, f in enumerate(readme_order)]

    # Master run-script — if a run_all / run.sh exists at any depth, use it as
    # the single entry point rather than listing every numbered file individually
    import re as _rerun
    _MAIN_ENTRY_NAMES = {'main.m', 'main.py', 'main.ipynb', 'index.ipynb'}
    _run_candidates = [
        f for f in all_files
        if _rerun.match(r'^run[_\-]?all\b.*\.(sh|bash|py|do)$', f.name.lower())
        or f.name.lower() in {'run.sh', 'run.bash', 'master.sh', 'master.do',
                               'run_analysis.sh', 'run_replication.sh'}
        or f.name.lower() in _MAIN_ENTRY_NAMES
    ]
    # pick shallowest (root-level wins over subfolder), same logic as README picker
    _run_script = min(
        _run_candidates,
        key=lambda x: len(x.relative_to(repo_dir).parts),
        default=None
    )
    def _entry_cmd(f):
        """Return the shell command to run a single entry-point file."""
        rel = f.relative_to(repo_dir)
        ext = f.suffix.lower()
        if ext in {'.sh', '.bash'}:
            return str(rel), f'bash {rel}'
        elif ext == '.py':
            return str(rel), f'python {rel}'
        elif ext == '.do':
            return str(rel), f'stata -b do {rel}'
        elif ext == '.m':
            return str(rel), f'matlab -batch "run(\'{rel}\')"'
        elif ext == '.ipynb':
            return str(rel), f'jupyter nbconvert --to notebook --execute {rel}'
        elif ext in {'.js', '.mjs', '.cjs'}:
            return str(rel), f'node {rel}'
        elif ext == '.html':
            return str(rel), f'# Open {rel} in a browser'
        elif ext == '.txt' and _is_code_txt(f):
            _ctxt_src = f.read_text(encoding='utf-8', errors='ignore')
            if re.search(r'library\s*\(|require\s*\(', _ctxt_src, re.IGNORECASE):
                return str(rel), f'Rscript {rel}  # rename to .R first'
            elif re.search(r'^\s*(?:use|cd|ssc\s+install|insheet|infile)\s', _ctxt_src, re.MULTILINE):
                return str(rel), f'stata -b do {rel}  # rename to .do first'
            elif re.search(r'^(?:import|from)\s+\w', _ctxt_src, re.MULTILINE):
                return str(rel), f'python {rel}  # rename to .py first'
            else:
                return str(rel), f'# {rel}  # code stored as .txt — rename with correct extension before running'
        else:
            return str(rel), f'./{rel}'

    if _run_script and len(code_files) > 3:
        _run_rel_str, _run_cmd = _entry_cmd(_run_script)

        # Any other main.* files that weren't chosen as the primary entry point
        _secondary_mains = [
            f for f in _run_candidates
            if f != _run_script and f.name.lower() in _MAIN_ENTRY_NAMES
        ]
        _secondary_block = []
        for _sf in _secondary_mains:
            _sf_rel_str, _sf_cmd = _entry_cmd(_sf)
            _secondary_block += [
                '',
                f'### Also: `{_sf_rel_str}`',
                '',
                '> ⚠️ A second entry point was detected alongside the primary script.',
                '> It may cover a separate part of the analysis — run it independently if needed.',
                '',
                '```bash',
                _sf_cmd,
                '```',
            ]

        _run_lines = [
            '# ValiChord Repository Readiness Check — Quick Start',
            '',
            '> ✅ **Master run script detected.**',
            '> **Confidence level: HIGH** — a single orchestrating script was found.',
            '> Run the script below to execute the full pipeline.',
            '',
            '---',
            '',
            '## Execution',
            '',
            f'```bash',
            _run_cmd,
            '```',
            '',
            f'(`{_run_rel_str}` orchestrates the full analysis pipeline.)',
            *_secondary_block,
            '',
            '---',
            '',
            '## Before Running',
            '',
            *_renumber_steps([
                *([] if any(
                    f.name.lower() in README_NAMES and
                    len(f.read_text(encoding='utf-8', errors='ignore').strip()) > 500
                    for f in all_files
                ) else ['1. Complete `README_DRAFT.md` and rename to `README.md`']),
                *(_quickstart_step2(all_files, code_files)),
                *_install_instructions(code_files, all_files),
                'N. Test on a **clean machine** before publishing',
            ]),
            '',
            '---',
            '',
            f'*Generated by ValiChord Repository Readiness Check v15 — {now}*',
        ]
        out = output_dir / 'QUICKSTART_DRAFT.md'
        out.write_text('\n'.join(_run_lines), encoding='utf-8-sig')
        print(f"  → QUICKSTART_DRAFT.md (run_all entry point)")
        return

    # Shiny app — generate dedicated interactive-app QUICKSTART
    import re as _reshiny
    _shiny_names = {'server.r', 'ui.r', 'app.r'}
    _all_names_lower = {f.name.lower() for f in all_files}
    # Monorepo — detect independent sub-projects and generate per-project sections
    import re as _remono
    _dep_files_mono = {'requirements.txt', 'environment.yml', 'renv.lock',
                       'pyproject.toml', 'pipfile', 'setup.py'}
    _subdirs_mono = {}
    for _f in all_files:
        try:
            _rel = _f.relative_to(repo_dir)
            if len(_rel.parts) >= 2:
                _subdirs_mono.setdefault(_rel.parts[0], []).append(_f)
        except Exception:
            pass
    # Peel single common top-level wrapper (e.g. zip extracts as monorepo/paper1/...)
    if len(_subdirs_mono) == 1:
        _wrapper_files = list(_subdirs_mono.values())[0]
        _subdirs_mono = {}
        for _f in _wrapper_files:
            try:
                _rel = _f.relative_to(repo_dir)
                if len(_rel.parts) >= 3:
                    _subdirs_mono.setdefault(_rel.parts[1], []).append(_f)
            except Exception:
                pass
    _subprojects_mono = []
    for _sd, _sfiles in _subdirs_mono.items():
        _sfnames = {_f.name.lower() for _f in _sfiles}
        _ssuffixes = {_f.suffix.lower() for _f in _sfiles}
        if (_ssuffixes & {'.py', '.r', '.rmd', '.jl', '.m', '.do'}) and \
           (_sfnames & _dep_files_mono or _sfnames & {'readme.md', 'readme.txt'}):
            _subprojects_mono.append((_sd, _sfiles, _ssuffixes, _sfnames))
    _is_monorepo = len(_subprojects_mono) >= 2
    if _is_monorepo:
        mono_lines = [
            '# ValiChord Repository Readiness Check — Quick Start',
            '',
            '> ⚠️ **MONOREPO DETECTED** — This repository contains multiple independent',
            '> sub-projects. Run each sub-project independently — they are NOT sequential.',
            '',
            '---',
            '',
        ]
        for _sd, _sfiles, _ssuffixes, _sfnames in _subprojects_mono:
            _has_renv = 'renv.lock' in _sfnames
            _has_req = 'requirements.txt' in _sfnames
            _has_env = 'environment.yml' in _sfnames or 'environment.yaml' in _sfnames
            _is_r = bool(_ssuffixes & {'.r', '.rmd'})
            _is_py = '.py' in _ssuffixes
            # Find entry point
            _has_index_html = any(_f.name.lower() == 'index.html' for _f in _sfiles)
            _has_js = any(_f.suffix.lower() == '.js' for _f in _sfiles)
            _has_analysis_code = any(
                _f.suffix.lower() in {'.py', '.r', '.rmd', '.jl', '.m', '.do'}
                for _f in _sfiles
            )
            _entry = next(
                (_f.name for _f in _sfiles
                 if _f.suffix.lower() in {'.py', '.r', '.rmd', '.jl', '.m', '.do'}
                 and _remono.match(r'^(main|run|analyse|analyze|model|pipeline|app)',
                                   _f.name.lower())),
                next((_f.name for _f in _sfiles
                      if _f.suffix.lower() in {'.py', '.r', '.rmd', '.jl', '.m', '.do'}),
                     None)
            )
            if _has_index_html and _has_js and not _has_analysis_code:
                _entry = 'index.html'
                _lang = 'web'
            _lang = 'Python' if _is_py else ('R' if _is_r else 'unknown')
            mono_lines += [
                f'## Sub-project: {_sd}/ ({_lang})',
                '',
                f'1. `cd {_sd}/`',
            ]
            step = 2
            if _has_env:
                mono_lines.append(f'{step}. `conda env create -f environment.yml && conda activate ...`')
                step += 1
            elif _has_renv:
                mono_lines.append(f'{step}. `Rscript -e "renv::restore()"`')
                step += 1
            elif _has_req:
                mono_lines.append(f'{step}. `pip install -r requirements.txt`')
                step += 1
            if _entry:
                if _is_py:
                    mono_lines.append(f'{step}. `python {_entry}`')
                elif _is_r:
                    mono_lines.append(f'{step}. `Rscript {_entry}`')
                else:
                    mono_lines.append(f'{step}. Run `{_entry}`')
            mono_lines.append('')
        mono_content = '\n'.join(mono_lines) + '\n'
        output_file = output_dir / 'QUICKSTART_DRAFT.md'
        output_file.write_text(mono_content, encoding='utf-8')
        return output_file

    _is_shiny_repo = (
        any(n in _all_names_lower for n in _shiny_names) or
        any(
            f.suffix.lower() in {'.r', '.rmd'} and
            _reshiny.search(
                r'library\s*\(\s*shiny\s*\)|shiny::runApp|shinyApp\s*\(',
                f.read_text(encoding='utf-8', errors='ignore')
            )
            for f in all_files
        )
    )
    if _is_shiny_repo:
        _all_names = {f.name.lower() for f in all_files}
        _has_renv = 'renv.lock' in _all_names
        _app_parents = [
            f.parent for f in all_files
            if f.name.lower() in {'server.r', 'ui.r'}
            and f.parent != repo_dir
        ]
        _app_dir = (
            "'" + str(_app_parents[0].relative_to(repo_dir)).replace('\\', '/') + "'"
            if _app_parents else '.'
        )
        shiny_lines = [
            '# ValiChord Repository Readiness Check — Quick Start',
            '',
            '> ⚠️ **This repository contains a Shiny web application.**',
            '> **Do NOT run `server.R` or `ui.R` directly.**',
            '> Reproduction requires launching the app and interacting with the UI.',
            '',
            '---',
            '',
            '## Launching the Shiny App',
            '',
        ]
        step = 1
        _readme_exists = any(
            f.name.lower() in {'readme.md', 'readme.txt'} and
            len(f.read_text(encoding='utf-8', errors='ignore').strip()) > 500
            for f in all_files
        )
        if not _readme_exists:
            shiny_lines.append(f'{step}. Complete `README_DRAFT.md` and rename to `README.md`')
            step += 1
        if _has_renv:
            shiny_lines.append(f'{step}. Restore R environment: `Rscript -e "renv::restore()"`')
            step += 1
        else:
            shiny_lines.append(f'{step}. Install R dependencies: `Rscript -e "install.packages(c(\'shiny\', ...))"` (see README_DRAFT)')
            step += 1
        shiny_lines += [
            f'{step}. Launch the app: `Rscript -e "shiny::runApp(' + _app_dir + ')"` ',
            f'{step+1}. Open browser at `http://127.0.0.1:PORT` (port shown in console output)',
            f'{step+2}. See **[DB] finding** for required interaction instructions and expected outputs',
            '',
            '---',
            '',
            '> ⚠️ **IMPORTANT**: No output files are generated automatically.',
            '> Reproduction requires manual interaction with the UI and visual verification',
            '> of charts and tables against published figures.',
        ]
        shiny_content = '\n'.join(shiny_lines) + '\n'
        output_file = output_dir / 'QUICKSTART_DRAFT.md'
        output_file.write_text(shiny_content, encoding='utf-8')
        return output_file

    # ── Figure-organised repository ──────────────────────────────────────────
    # Pattern: sibling folders named "Figure N" / "FigN" / "Panel N", each
    # containing one or more scripts that reproduce that figure independently.
    _fig_dir_pat = re.compile(r'^(?:fig(?:ure)?|panel)[\s_\-]?\d+', re.IGNORECASE)
    _fig_code_files = [
        f for f in code_files
        if f.parent != repo_dir
        and _fig_dir_pat.match(f.parent.name)
    ]
    _is_figure_repo = (
        len(_fig_code_files) >= 2
        and len(_fig_code_files) >= len(code_files) * 0.5
    )
    if _is_figure_repo:
        def _fig_num(name):
            m = re.search(r'\d+', name)
            return int(m.group()) if m else 0

        _fig_by_dir: dict = {}
        for _ff in _fig_code_files:
            _fig_by_dir.setdefault(_ff.parent.name, []).append(_ff)

        _readme_long = any(
            f.name.lower() in README_NAMES
            and len(f.read_text(encoding='utf-8', errors='ignore').strip()) > 500
            for f in all_files
        )
        fig_lines = [
            '# ValiChord Repository Readiness Check — Quick Start',
            '',
            '> ✅ **Figure-organised repository detected.**',
            '> Scripts are organised by figure — each folder reproduces one figure',
            '> independently. Scripts are **not** sequential; run them in any order.',
            '> **Confidence level: HIGH**',
            '',
            '---',
            '',
            '## Before Running',
            '',
            *_renumber_steps([
                *([] if _readme_long else
                  ['1. Complete `README_DRAFT.md` and rename to `README.md`']),
                *(_quickstart_step2(all_files, code_files)),
                *_install_instructions(code_files, all_files),
                'N. Test on a **clean machine** before publishing',
            ]),
            '',
            '---',
            '',
            '## Figure Scripts (run each independently)',
            '',
            '> Each block below is self-contained.',
            '> Running one does not require first running any other.',
            '',
        ]
        for _dir_name in sorted(_fig_by_dir, key=_fig_num):
            fig_lines.append(f'### {_dir_name}')
            fig_lines.append('')
            for _ff in sorted(_fig_by_dir[_dir_name], key=lambda x: x.name):
                _, _ff_cmd = _entry_cmd(_ff)
                fig_lines += ['```bash', _ff_cmd, '```', '']
        fig_lines += [
            '---',
            '',
            f'*Generated by ValiChord Repository Readiness Check v15 — {now}*',
        ]
        output_file = output_dir / 'QUICKSTART_DRAFT.md'
        output_file.write_text('\n'.join(fig_lines), encoding='utf-8-sig')
        print('  → QUICKSTART_DRAFT.md (figure-organised)')
        return output_file

    lines = [
        '# ValiChord Repository Readiness Check — Quick Start',
        '',
        *(['> ✅ **Execution order inferred from numbered script filenames.**',
           '> **Confidence level: HIGH** — numeric prefixes make order explicit.',
           '> Verify this matches your intended pipeline before publishing.']
          if _numbered_from_filenames else
          ['> ⚠️ **IMPORTANT — THIS EXECUTION ORDER IS INFERRED**',
           '> **AND HAS NOT BEEN VALIDATED.**',
           '> ',
           '> The script order below was generated by automated',
           '> analysis and may be incorrect. Do not rely on it',
           '> without manual verification against your own',
           '> knowledge of the pipeline.',
           '> ',
           '> **Confidence level: LOW**']),
        '',
        '---',
        '',
    ]

    if numbered:
        lines += [
            '## Inferred Execution Order',
            '(from numbered script filenames)' if _numbered_from_filenames else '(from README run commands)',
            '',
        ]
        for i, (_, f) in enumerate(numbered, 1):
            rel = f.relative_to(repo_dir)
            lines.append(f'{i}. `{rel}`')
        lines.append('')
    else:
        lines += [
            '## Script Files Found',
            '',
            'No numbered scripts detected. '
            'The following scripts were found — ',
            'you must specify the correct execution order:',
            '',
        ]
        notebook_extensions = NOTEBOOK_EXTENSIONS

        # Detect JS/web-only repos and show entry point instead of listing all JS files
        # Use all_files (not code_files) because JS files are excluded from code_files
        # by the frontend-dir filter, making code_files empty for pure-JS deposits.
        _qs_web_suffixes = {'.js', '.html', '.css', '.ts'}
        _qs_analysis_suffixes = {'.py', '.r', '.rmd', '.jl', '.do', '.m'}
        _qs_vendor_dirs = {'vendor', 'lib', 'dist', 'node_modules', 'target', 'bower_components'}
        _qs_is_web = (
            any(f.suffix.lower() in _qs_web_suffixes
                and not any(p.lower() in _qs_vendor_dirs for p in f.parts)
                for f in all_files) and
            not any(f.suffix.lower() in _qs_analysis_suffixes for f in all_files)
        )
        # Find HTML entry point — prefer index.html at root, fall back to any .html
        _qs_index = next(
            (f for f in all_files if f.name.lower() == 'index.html'
             and len(f.relative_to(repo_dir).parts) == 1),
            next((f for f in all_files if f.name.lower() == 'index.html'),
                 next((f for f in sorted(all_files, key=lambda x: len(x.relative_to(repo_dir).parts))
                       if f.suffix.lower() == '.html'), None))
        )
        if _qs_is_web and _qs_index:
            lines += [
                '> ℹ️ **This is a web application.**',
                '> JavaScript files are loaded by the browser — they are not executed sequentially.',
                '',
                '## Entry Point',
                '',
                f'Open `{_qs_index.relative_to(repo_dir)}` in a WebXR-capable browser.',
                '',
                '> If this is a VR/WebXR application, a compatible headset (e.g. Meta Quest)',
                '> or browser with WebXR support is required.',
                '',
            ]
            # Skip the rest of the file listing for web repos
            lines += [
                '---',
                '',
                '*Generated by ValiChord Repository Readiness Check v15*',
            ]
            output_file = output_dir / 'QUICKSTART_DRAFT.md'
            output_file.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            return output_file

        for f in sorted(code_files, key=lambda x: x.name):
            if f.suffix.lower() in notebook_extensions:
                continue  # notebooks listed separately below
            rel = f.relative_to(repo_dir)
            if f.suffix.lower() == '.txt' and _is_code_txt(f):
                lines.append(f'- `{rel}` _(code stored as plain text — consider renaming to .R, .py, .do etc.)_')
            else:
                lines.append(f'- `{rel}`')
        # also list notebooks
        notebook_files = [f for f in all_files if f.suffix.lower() in NOTEBOOK_EXTENSIONS]
        # build sets of notebook filenames by [J] sub-case
        _j_nonlinear = set()
        _j_counts_cleared = set()  # null counts but outputs present
        _j_never_run = set()       # null counts and no outputs
        for fi in findings:
            if not isinstance(fi, dict) or fi.get('mode') != 'J':
                continue
            _nb_name = fi['title'].rsplit(': ', 1)[-1]
            if fi['title'].startswith('Notebook cells executed out of order'):
                _j_nonlinear.add(_nb_name)
            elif fi['title'].startswith('Execution counts cleared'):
                _j_counts_cleared.add(_nb_name)
            else:
                _j_never_run.add(_nb_name)
        for f in sorted(notebook_files, key=lambda x: x.name):
            rel = f.relative_to(repo_dir)
            if f.name in _j_nonlinear:
                lines.append(f'- `{rel}` ⚠️ WARNING: non-linear execution order detected — '
                             f'do NOT run top-to-bottom until execution order is resolved '
                             f'and documented (see [J] finding).')
            elif f.name in _j_counts_cleared:
                lines.append(f'- `{rel}` ⚠️ WARNING: execution counts cleared before sharing — '
                             f're-run top-to-bottom (Kernel > Restart & Run All) to verify '
                             f'outputs are reproducible (see [J] finding).')
            elif f.name in _j_never_run:
                lines.append(f'- `{rel}` ⚠️ WARNING: notebook has never been run — '
                             f'outputs are not saved. Run from scratch and verify results '
                             f'before sharing (see [J] finding).')
            else:
                if f.suffix.lower() in {'.rmd', '.qmd'}:
                    lines.append(f'- `{rel}` (open in RStudio and knit, or run via: Rscript -e \'rmarkdown::render("{rel}")\')')
                else:
                    lines.append(f'- `{rel}` (open in Jupyter and run all cells top to bottom)')
        lines.append('')

    lines += [
        '---',
        '',
        '## Before Running',
        '',
        *_renumber_steps([
            *([] if any(
                f.name.lower() in README_NAMES and
                len(f.read_text(encoding='utf-8', errors='ignore').strip()) > 500 and
                sum(1 for s in ['usage', 'requirement', 'installation', 'data', 'reproduc', 'run']
                    if s in f.read_text(encoding='utf-8', errors='ignore').lower()) >= 3
                for f in all_files
            ) else ['1. Complete `README_DRAFT.md` and rename to `README.md`']),
            *(_quickstart_step2(all_files, code_files)),
            *_install_instructions(code_files, all_files),
            'N. Test on a **clean machine** — not just a new folder '
            'on your development machine',
            *(['WARNING: Internet access required at runtime -- '
               'code fetches live data. Document snapshot date and source version in README.']
              if any(isinstance(f, dict) and f.get('mode') in {'AS', 'CI', 'AQ'}
                     for f in findings)
              else []),
            *(['WARNING: GPU required — code uses torch.device("cuda") with no CPU fallback. '
               'A CUDA-capable GPU is required to run this code. '
               'See [CV] finding for fix instructions.']
              if any(isinstance(f, dict) and f.get('mode') == 'CV'
                     for f in findings)
              else []),
            *(['WARNING: System libraries required before pip install — see [CX] finding for install instructions.']
              if any(isinstance(f, dict) and f.get('mode') == 'CX'
                     for f in findings)
              else []),
            *(['WARNING: Authenticated cloud API required — '
               'credentials must be configured before running. '
               'See [CI] finding for account and authentication requirements.']
              if any(isinstance(f, dict) and f.get('mode') == 'CI'
                     and 'Authenticated' in f.get('title', '')
                     for f in findings)
              else [])
        ]),
        '',
        '---',
        '',
        f'*Generated by ValiChord Repository Readiness Check v15 — {now}*',
    ]

    out = output_dir / 'QUICKSTART_DRAFT.md'
    out.write_text('\n'.join(lines), encoding='utf-8-sig')
    print(f"  → QUICKSTART_DRAFT.md")


# ── LICENCE_DRAFT.txt ────────────────────────────────────────────────────────

def _generate_licence_draft(output_dir, all_files=None, is_cad=False):
    """Generate LICENCE_DRAFT.txt."""

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    year = datetime.now().year

    if is_cad:
        content = f"""LICENCE_DRAFT.txt — generated by ValiChord Repository Readiness Check v15
Generated: {now}

YOU MUST COMPLETE THIS FILE before sharing your repository.

Choose a licence and replace this entire file with your chosen
licence text.

============================================================
RECOMMENDED FOR CAD/DESIGN FILES: Creative Commons CC-BY 4.0
============================================================

Design files, geometry, and technical drawings are best licensed under
Creative Commons Attribution 4.0 International (CC-BY 4.0).

See: https://creativecommons.org/licenses/by/4.0/

============================================================
IMPORTANT QUESTIONS TO ANSWER BEFORE CHOOSING:
============================================================

1. Does this design derive from or modify a third-party model?
   If yes: check the licence of the original — your licence must comply.

2. Does your institution have a default IP policy covering design files?
   If yes: check whether you need institutional approval before sharing.

3. Does your funder require a specific open licence?
   If yes: use that licence.

4. Is this design subject to any export control restrictions?
   If yes: seek legal advice before depositing openly.

============================================================
Rename this file to LICENCE (no extension) or LICENCE.md
after completing it.
============================================================
"""
    else:
        content = f"""LICENCE_DRAFT.txt — generated by ValiChord Repository Readiness Check v15
Generated: {now}

YOU MUST COMPLETE THIS FILE before sharing your repository.

Choose one of the following options and replace this entire
file with your chosen licence text.

============================================================
RECOMMENDED FOR CODE: MIT Licence
============================================================

MIT License

Copyright (c) {year} [YOUR NAME]

Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation
files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or
sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following
conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

============================================================
RECOMMENDED FOR DATA: Creative Commons CC-BY 4.0
============================================================

If your repository includes data, consider licensing it under
Creative Commons Attribution 4.0 International (CC-BY 4.0).

See: https://creativecommons.org/licenses/by/4.0/

============================================================
IMPORTANT QUESTIONS TO ANSWER BEFORE CHOOSING:
============================================================

1. Does your data include human subjects data?
   If yes: do you have authorisation to share it?

2. Does your code use any GPL-licensed libraries?
   If yes: your code may need to be GPL-licensed too.

3. Does your institution have a default IP policy?
   If yes: check whether you need institutional approval.

4. Does your funder require a specific open licence?
   If yes: use that licence.

============================================================
Rename this file to LICENCE (no extension) or LICENCE.md
after completing it.
============================================================
"""

    out = output_dir / 'LICENCE_DRAFT.txt'
    out.write_text(content, encoding='utf-8-sig')
    print(f"  → LICENCE_DRAFT.txt")


# ── README placeholder ───────────────────────────────────────────────────────


def generate_proposed_corrections(repo_dir, all_files, findings, output_dir):
    """Generate corrected file copies in /proposed_corrections/."""

    corrections_dir = output_dir / 'proposed_corrections'
    corrections_dir.mkdir(exist_ok=True)

    # get all [C] absolute path findings
    path_findings = [f for f in findings if f['mode'] == 'C']

    if not path_findings:
        return

    # write a README for the corrections folder
    readme_lines = [
        '# proposed_corrections/',
        '',
        '> ⚠️ **THESE FILES CONTAIN A DELIBERATE RUNTIME ERROR.**',
        '> They will not execute until you remove the error block',
        '> at the top of each file.',
        '>',
        '> This is intentional. You must review each correction',
        '> before using it. The tool cannot guarantee that the',
        '> relative path replacements are correct for your setup.',
        '',
        '## How to use these files',
        '',
        '1. Open each file and read the correction at the top',
        '2. Verify the relative path is correct for your directory structure',
        '3. Remove the `raise RuntimeError` block at the top',
        '4. Replace the corresponding file in your repository',
        '5. Test that your code still runs correctly',
        '',
        '## Files corrected',
        '',
    ]

    corrected_files = []

    # [C] findings are now grouped (one finding covering all affected files).
    # Parse all filenames from evidence[0] which has format 'Files: a.R, b.py'.
    target_files = []
    for path_finding in path_findings:
        evidence = path_finding.get('evidence', [])
        if not evidence:
            continue
        ev0 = evidence[0]
        if ev0.startswith('Files: '):
            names_part = re.sub(r'\s*\(and \d+ more files?\)', '', ev0[len('Files: '):])
            file_names = {n.strip() for n in names_part.split(',')}
            target_files += [f for f in all_files if f.name in file_names]
        else:
            # Legacy single-file format: 'Evidence: filename line N: ...'
            target_files += [f for f in all_files if ev0.startswith(f'Evidence: {f.name}')]

    # find and replace absolute paths
    abs_pattern = re.compile(
        r'(/Users/[a-zA-Z][a-zA-Z0-9_\-]{1,}/[^\s\'")\]]*)'
        r'|(/home/[a-zA-Z][a-zA-Z0-9_\-]{1,}/[^\s\'")\]]*)'
        r'|(/root/[a-zA-Z][^\s\'")\]]*)'
        r'|([A-Z]:\\\\[A-Za-z][^\s\'")\]]*)'
        r'|([A-Z]:/[A-Za-z][^\s\'")\]]*)'
    )

    for src_file in target_files:
        try:
            content = src_file.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue

        # Replace paths line-by-line, skipping ~/  and export PATH= lines
        # (mirrors the detection exclusions in detect_C_absolute_paths)
        _is_shiny_file = src_file.name.lower() in {'app.r', 'server.r', 'ui.r'}
        corrected_lines = []
        replacements = []
        for _ln in content.splitlines(keepends=True):
            _s = _ln.strip()
            if '~/' in _s or re.match(r'export\s+\w*PATH\s*=', _s):
                corrected_lines.append(_ln)
                continue
            # Shiny: setwd() must be removed entirely, not path-fixed.
            # Shiny automatically sets the working directory to the app folder,
            # so file reads relative to app.R work without any setwd() call.
            if _is_shiny_file and re.match(r'\s*setwd\s*\(', _ln):
                eol = '\r\n' if _ln.endswith('\r\n') else '\n'
                corrected_lines.append(
                    '# REMOVED: setwd() — Shiny sets the working directory to the'
                    ' app folder automatically.' + eol
                    + '# If dataset.csv is in the same folder as app.R,'
                    ' read.table("dataset.csv", ...) already works without setwd().' + eol
                )
                replacements.append((_ln.strip(), '# REMOVED: setwd()'))
                continue
            _line_matches = abs_pattern.findall(_ln)
            _line_flat = [m for grp in _line_matches for m in grp if m]
            for _m in _line_flat:
                _parts = _m.replace('\\', '/').rstrip('/').split('/')
                _suggested = './data/' + _parts[-1] if _parts else './data/file'
                _ln = _ln.replace(_m, _suggested, 1)
                replacements.append((_m, _suggested))
            corrected_lines.append(_ln)

        if not replacements:
            continue

        corrected = ''.join(corrected_lines)

        # build the warning block
        warning_lines = [
            '# ============================================================',
            '# VALICHORD PROPOSED CORRECTION — DO NOT RUN WITHOUT REVIEWING',
            '# ============================================================',
            '# This file was generated by ValiChord Repository Readiness Check.',
            '# The following absolute paths were detected and replaced',
            '# with suggested relative paths:',
            '#',
        ]
        for orig, sugg in replacements:
            warning_lines.append(f'#   ORIGINAL:  {orig}')
            warning_lines.append(f'#   SUGGESTED: {sugg}')
            warning_lines.append('#')
        warning_lines += [
            '# VERIFY each replacement before using this file.',
            '# The suggested paths may not match your directory structure.',
            '# ============================================================',
            '',
            _make_guard(src_file).rstrip('\n'),
            '',
            '# ============================================================',
            '',
        ]

        warning_block = '\n'.join(warning_lines) + '\n'
        final_content = warning_block + corrected

        out_file = corrections_dir / src_file.name
        out_file.write_text(final_content, encoding='utf-8-sig')
        corrected_files.append(src_file.name)

    # If no files were actually corrected (e.g. pattern mismatch between
    # detector and generator), skip writing the README entirely
    if not corrected_files:
        return

    # write the corrections README — consolidate duplicate filenames
    from collections import Counter
    file_counts = Counter(corrected_files)
    for fname, count in sorted(file_counts.items()):
        if count > 1:
            readme_lines.append(f'- `{fname}` ({count} corrections)')
        else:
            readme_lines.append(f'- `{fname}`')

    readme_lines += [
        '',
        '---',
        '',
        f'*Generated by ValiChord Repository Readiness Check v15*',
    ]

    readme_out = corrections_dir / 'README.md'
    readme_out.write_text('\n'.join(readme_lines), encoding='utf-8-sig')

    print(f"  → proposed_corrections/ ({len(corrected_files)} files)")
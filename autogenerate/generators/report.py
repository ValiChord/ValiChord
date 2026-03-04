"""
ValiChord Auto-Generate
Cleaning Report Generator
Produces CLEANING_REPORT.md and ASSESSMENT.md
"""

import re
from pathlib import Path
from datetime import datetime


_CODE_TXT_STEM_KW = frozenset({
    'code', 'script', 'analysis', 'replication', 'pipeline', 'main', 'run'
})
_CODE_TXT_PAT = re.compile(
    r'library\s*\(|import\s+\w|^\s*def\s+\w|\bfunction\s*\(|\bcd\s+|\buse\s+',
    re.MULTILINE
)


def _is_code_txt(f):
    """Return True if a .txt file's stem and content suggest it is actually code."""
    if f.suffix.lower() != '.txt':
        return False
    if not any(kw in f.stem.lower() for kw in _CODE_TXT_STEM_KW):
        return False
    try:
        with f.open('rb') as fh:
            raw = fh.read(2 * 1024 * 1024)  # 2 MB cap
        return bool(_CODE_TXT_PAT.search(raw.decode('utf-8', errors='ignore')))
    except Exception:
        return False


def _assessment_verification_questions(all_files):
    """Return verification questions appropriate to repo type."""
    _cad_exts      = {'.step', '.stp', '.stl', '.igs', '.iges', '.f3d', '.obj'}
    _code_exts     = {'.py', '.r', '.jl', '.do', '.m', '.rmd', '.ipynb', '.smk', '.nf', '.groovy'}
    _tabular_exts  = {'.csv', '.tsv', '.xlsx', '.xls', '.dta', '.sav',
                      '.parquet', '.feather', '.arrow', '.dif'}
    _software_exts = {'.jar', '.exe', '.dll', '.so', '.dylib', '.class', '.app'}
    has_cad      = any(f.suffix.lower() in _cad_exts for f in all_files)
    has_code     = any(f.suffix.lower() in _code_exts or f.name in {'Snakefile', 'main.nf'} or _is_code_txt(f) for f in all_files)
    has_tabular  = any(f.suffix.lower() in _tabular_exts for f in all_files)
    has_software = any(f.suffix.lower() in _software_exts for f in all_files) and not has_code

    if has_cad and not has_code and not has_tabular:
        return [
            '1. **File integrity:** Do all STEP and STL files open without errors in your CAD software?',
            '',
            '2. **Drawing consistency:** Do the engineering drawings (PDF) match the 3D geometry in revision number and dimensions?',
            '',
            '3. **Design provenance:** Is the origin of this design documented? If it derives from or modifies a prior design, is that prior work cited?',
            '',
            '4. **Intended use:** Have you documented what these files are intended for (e.g. CFD meshing, manufacture, 3D printing, validation)?',
            '',
            '5. **Licence:** Is the licence appropriate for design files? If the geometry derives from a third-party licensed model, does your chosen licence comply?',
        ]

    if has_software:
        return [
            '1. **Runtime requirements:** What Java/runtime version is required? '
            'Have you tested on Windows, macOS, and Linux? Document any OS-specific behaviour.',
            '',
            '2. **Execution:** What is the exact command to run the tool? '
            'Is there an example input file validators can use to confirm correct output?',
            '',
            '3. **Expected output:** What should a validator see when the tool runs correctly? '
            'Describe expected output files, console messages, or return codes.',
            '',
            '4. **Input format:** What input format(s) does the tool accept? '
            'Provide a minimal working example input file.',
            '',
            '5. **Licence:** Is the software licence clearly stated? '
            'If the tool bundles third-party libraries (e.g. in a fat JAR), '
            'are their licences compatible with yours?',
        ]

    if not has_code:
        return [
            '1. **Data completeness:** Are all variables and cases '
            'described in the codebook present in the data files?',
            '',
            '2. **Data provenance:** Where did each data file come from? '
            'If any data is anonymised or synthetic, document the transformation.',
            '',
            '3. **Access conditions:** Can the data be shared openly? '
            'If not, document the access restrictions and who to contact.',
            '',
            '4. **File integrity:** Have you verified checksums for all data files?',
            '',
            '5. **Licence:** Is the data licence clearly stated and appropriate '
            'for the sensitivity of the data?',
        ]
    return [
        '1. **Definition of successful reproduction:** What exactly '
        'should a validator see when they have successfully reproduced '
        'your results? Include numerical values and tolerance bands '
        'where relevant.',
        '',
        '2. **Data provenance:** Where did each data file come from? '
        'If any data is anonymised or synthetic, document the '
        'transformation.',
        '',
        '3. **Platform sensitivity:** Did you run this on a specific '
        'OS, GPU, or hardware configuration? Do results differ '
        'across platforms?',
        '',
        '4. **Stochasticity:** Are any results expected to vary '
        'between runs? If so, by how much?',
        '',
        '5. **Figure mapping:** Which script produces which figure '
        'in your paper? Please complete this mapping:',
        '',
        '   | Paper Figure | Generated File | Script |',
        '   |---|---|---|',
        '   | Figure 1 | | |',
        '   | Figure 2 | | |',
        '   | Figure 3 | | |',
        '',
        '6. **Manual steps:** Are there any steps in your analysis '
        'that cannot be automated — e.g., manual data entry, '
        'GUI-based steps, or proprietary software exports?',
    ]

def generate_cleaning_report(repo_name, repo_dir, all_files,
                              findings, output_dir):
    """Generate CLEANING_REPORT.md and ASSESSMENT.md."""

    _write_cleaning_report(repo_name, repo_dir, all_files,
                           findings, output_dir)
    _write_assessment(repo_name, all_files, findings, output_dir)


def _severity_emoji(severity):
    return {
        'CRITICAL': '🔴',
        'SIGNIFICANT': '🟡',
        'LOW CONFIDENCE': '🔵',
    }.get(severity, '⚪')


def _write_cleaning_report(repo_name, repo_dir, all_files,
                            findings, output_dir):

    critical   = [f for f in findings if f['severity'] == 'CRITICAL']
    significant = [f for f in findings if f['severity'] == 'SIGNIFICANT']
    low        = [f for f in findings if f['severity'] == 'LOW CONFIDENCE']
    info       = [f for f in findings if f['severity'] == 'INFO']

    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    lines = []

    # ── header ───────────────────────────────────────────────────────
    lines += [
        '# ValiChord Repository Readiness Check — Cleaning Report',
        '',
        '> ⚠️ **ANTI-AUTHORITY NOTICE**',
        '> ',
        '> This report was generated by automated analysis. '
        'None of the proposed',
        '> improvements have been validated by running the code. '
        'The researcher',
        '> is responsible for all decisions about the final state '
        'of this repository.',
        '> All generated files have `_DRAFT` in their names and '
        'must be verified',
        '> before use.',
        '',
        f'**Repository:** {repo_name}',
        f'**Processed:** {now}',
        f'**ValiChord Spec:** v15',
        f'**Files analysed:** {len(all_files)}',
        '',
        '> **This report assesses validatability, not truth. A clean report does not '
        'imply that results are correct — only that an independent validator has a '
        'reasonable chance of attempting reproduction.**',
        '',
    ]

    # ── researcher warning (Form A) ──────────────────────────────────
    lines += [
        '---',
        '',
        '## ⚠️ Important — Read Before Proceeding',
        '',
        'This tool has organised your repository and filled in missing '
        'documentation, preparing it for independent validation.',
        '',
        'Because the tool only reads your files and does not run your '
        'code, it cannot assess whether your analysis is correct, '
        'statistically sound, or free from error. '
        '**It only ensures your files are organised and documented.**',
        '',
        '**If anything this tool has generated contradicts your '
        'knowledge of your own research, the tool is wrong.** '
        'Any conflict must be resolved in your favour.',
        '',
        '**If your cleaned repository runs end-to-end but produces '
        'results that differ from your published paper, this is not '
        'a ValiChord Repository Readiness Check error.** First check whether you adopted any proposed corrections — a correction may have introduced a change. If no corrections were adopted and results still differ, this is a scientific discrepancy only '
        'you can resolve.',
        '',
        '**This report does not constitute certification that this '
        'repository is reproducible.** It identifies packaging '
        'problems and generates draft improvements. Running your '
        'pipeline on a genuinely clean machine is the only reliable '
        'test.',
        '',
    ]

    # ── summary table ────────────────────────────────────────────────
    lines += [
        '---',
        '',
        '## Summary',
        '',
        '| Severity | Count |',
        '|---|---|',
        f'| 🔴 CRITICAL | {len(critical)} |',
        f'| 🟡 SIGNIFICANT | {len(significant)} |',
        f'| 🔵 LOW CONFIDENCE | {len(low)} |',
        f'| **Total findings** | **{len(critical) + len(significant) + len(low)}** |',
        '',
    ]

    # minimal findings note
    if len(critical) == 0 and len(significant) == 0:
        lines += [
            '> ✅ **No CRITICAL or SIGNIFICANT findings detected.**',
            '> This means common packaging problems were not found — '
            'it does not mean',
            '> the repository is verified as reproducible. Running '
            'the complete pipeline',
            '> on a clean machine remains the only reliable test.',
            '',
        ]

    # ── positive observations (INFO) ─────────────────────────────────
    if info:
        lines += ['---', '', '## ✅ Positive Observations', '']
        for f in info:
            lines.append(f'- **[{f["mode"]}]** {f["title"]}')
            for e in f.get('evidence', []):
                lines.append(f'  - `{e}`')
        lines.append('')

    # ── findings by severity ─────────────────────────────────────────
    for severity, group in [
        ('CRITICAL', critical),
        ('SIGNIFICANT', significant),
        ('LOW CONFIDENCE', low),
    ]:
        if not group:
            continue

        emoji = _severity_emoji(severity)
        lines += [
            '---',
            '',
            f'## {emoji} {severity} Findings',
            '',
        ]

        for f in group:
            lines += [
                f'### [{f["mode"]}] {f["title"]}',
                '',
                f['detail'],
                '',
            ]
            if f.get('evidence'):
                for e in f['evidence']:
                    lines.append(f'- `{e}`')
                lines.append('')

    # ── generated files list ─────────────────────────────────────────
    lines += [
        '---',
        '',
        '## Generated Files',
        '',
        'The following `_DRAFT` files have been generated. '
        'Each must be verified and renamed (remove `_DRAFT`) '
        'before use.',
        '',
        '| File | Purpose |',
        '|---|---|',
        '| `README_DRAFT.md` | Repository documentation template |',
        *(['| `requirements_DRAFT.txt` | Dependency information — see file for details |',
           '| `QUICKSTART_DRAFT.md` | Inferred execution order |']
          if any(f.suffix.lower() in {'.py', '.r', '.jl', '.do', '.m', '.rmd'} for f in all_files)
          else []),
        *(['| `LICENCE_DRAFT.txt` | Licence template |']
          if not any(f.name.lower() in {'licence', 'license', 'licence.md', 'license.md',
                                         'licence.txt', 'license.txt', 'copying', 'copying.md'}
                     for f in all_files) else []),
        '| `INVENTORY_DRAFT.md` | File inventory |',
        '| `ASSESSMENT.md` | Detailed assessment questions |',
        '',
        '> All files in `/proposed_corrections/` contain a runtime '
        'error by design.',
        '> They will not execute until you actively remove that error.',
        '',
        '---',
        '',
        f'*ValiChord Repository Readiness Check — Assessment — '
        f'Specification v15 — {now}*',
        '*© 2026 Ceri John. All Rights Reserved.*',
    ]

    out = output_dir / 'CLEANING_REPORT.md'
    out.write_text('\n'.join(lines), encoding='utf-8-sig')
    print(f"  → CLEANING_REPORT.md")


def _write_assessment(repo_name, all_files, findings, output_dir):
    """Generate ASSESSMENT.md with questions for the researcher."""

    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    lines = [
        '# ValiChord Repository Readiness Check — Assessment',
        '',
        f'**Repository:** {repo_name}',
        f'**Generated:** {now}',
        '',
        'This file contains questions and action items for the '
        'researcher to complete. These cannot be answered by '
        'automated analysis — only you know the answers.',
        '',
        '---',
        '',
        '## Action Items',
        '',
    ]

    # generate action items from findings
    action_map = {
        'A':  'Complete all placeholder sections in README_DRAFT.md, '
              'especially the study overview and definition of '
              'successful reproduction.',
        'B':  'Add exact version numbers to all packages marked '
              'UNKNOWN in requirements_DRAFT.txt. '
              'For Python: run `pip freeze` in your original environment. '
              'For R: run `installed.packages()` or `sessionInfo()` in R. '
              'For Julia: run `Pkg.status()` in your original environment, '
              'or commit your Manifest.toml.',
        'C':  'Review corrected path files in /proposed_corrections/ '
              'and verify each relative path is correct before '
              'applying.',
        'D':  'Verify the execution order in QUICKSTART_DRAFT.md '
              'matches your actual pipeline.',
        'N':  'Choose a licence for your code and data and complete '
              'LICENCE_DRAFT.txt.',  # may be overridden below for CAD deposits
        'Z':  'Add the commit hash or version tag for this exact '
              'deposit to your README.',
        'W':  'Run `git lfs pull` before creating your deposit ZIP '
              'to include actual data files.',
        'BJ': 'Provide decryption keys separately to validators, '
              'or replace encrypted files with the actual data if '
              'sharing is permitted.',
        'J':  'Fix the non-linear notebook execution order before deposit. Re-run the notebook from scratch (Kernel > Restart & Run All) and confirm all cell numbers are sequential. If the correct order differs from top-to-bottom, document it explicitly in README.',
        'BM': 'Complete the missing required field(s) in CITATION.cff (e.g. date-released). See https://citation-file-format.github.io/ for the full spec.',
        'BK': 'Replace clock-based filenames with fixed names, '
              'and replace clock-based seeds with fixed integers.',
        'BL': 'Pin your version number explicitly. Replace '
              'setuptools_scm / versioneer with '
              '`__version__ = "1.0.0"` in your package.',
        'BW': 'Replace empty stub code files with the actual code, or remove '
              'them and document the omission in your README. '
              'A 1–5 byte file cannot contribute to reproducing your results.',
        'AK': '',  # handled below — severity determines the action text
        'ND': 'Deposit the underlying data and/or analysis scripts used to '
              'produce your results. Manuscript files, supplementary documents, '
              'and figures alone are not a reproducible deposit — validators '
              'need the raw or processed data (e.g. .csv, .xlsx, .dta) and, '
              'where possible, the code that analyses it.',
    }

    _cad_exts     = {'.step', '.stp', '.stl', '.igs', '.iges', '.f3d', '.obj'}
    _tabular_exts = {'.csv', '.tsv', '.xlsx', '.xls', '.dta', '.sav',
                     '.parquet', '.feather', '.arrow', '.dif'}
    _code_exts    = {'.py', '.r', '.jl', '.do', '.m', '.rmd', '.ipynb', '.smk', '.nf', '.groovy'}
    _is_cad = (
        any(f.suffix.lower() in _cad_exts for f in all_files)
        and not any(f.suffix.lower() in _code_exts or f.name in {'Snakefile', 'main.nf'} for f in all_files)
        and not any(f.suffix.lower() in _tabular_exts for f in all_files)
    )
    if _is_cad:
        action_map['N'] = 'Choose a licence for your design files and complete LICENCE_DRAFT.txt.'

    modes_found = {f['mode'] for f in findings}
    # BM has two sub-types: LOW CONFIDENCE (no cff) and SIGNIFICANT (missing fields)
    # Only show the action item when a cff exists but has missing fields
    bm_action_applies = any(
        f['mode'] == 'BM' and f.get('severity') == 'SIGNIFICANT'
        for f in findings
    )
    added = False

    for mode, action in action_map.items():
        if mode == 'B':
            if 'B' in modes_found:
                _b = next((f for f in findings if f.get('mode') == 'B'), None)
                _b_title = _b.get('title', '') if _b else ''
                if 'MATLAB' in _b_title:
                    lines += ['- **[B]** List the MATLAB version and required toolboxes '
                              'in your README. Run `ver` in MATLAB to see the version, '
                              'and list any toolboxes used (e.g. Statistics and Machine '
                              'Learning Toolbox).', '']
                elif 'Stata' in _b_title:
                    lines += ['- **[B]** List the Stata version and any packages installed '
                              'via `ssc install` in your README. Run `version` and '
                              '`ado describe` in Stata to identify them.', '']
                elif 'SAS' in _b_title:
                    lines += ['- **[B]** List the SAS version, required SAS products/modules, '
                              'and any SASLIB paths in your README. Run `proc product_status;` '
                              'to identify installed components.', '']
                else:
                    lines += [f'- **[B]** {action}', '']
                added = True
            continue
        if mode == 'AK':
            if any(f['mode'] == 'AK' and f.get('severity') == 'SIGNIFICANT' for f in findings):
                lines += ['- **[AK]** Download your Colab notebooks and commit them to '
                          'the repository (File > Download > Download .ipynb in Colab). '
                          'An externally hosted notebook that goes offline makes your '
                          'analysis irreproducible by definition.', '']
                added = True
            elif 'AK' in modes_found:
                lines += ['- **[AK]** Archive any external URLs using the Wayback Machine '
                          '(web.archive.org) and replace direct links with archived or '
                          'DOI-resolved URLs where possible.', '']
                added = True
            continue
        if mode == 'BM':
            if any(f['mode'] == 'BM' and f.get('severity') == 'SIGNIFICANT' for f in findings):
                lines += ['- **[BM]** Complete the missing required field(s) in '
                          'CITATION.cff (e.g. date-released). '
                          'See https://citation-file-format.github.io/ for the full spec.', '']
                added = True
            elif 'BM' in modes_found:
                lines += ['- **[BM]** Add a CITATION.cff file to make your repository '
                          'citable. See https://citation-file-format.github.io/ '
                          'for the required fields and format.', '']
                added = True
            continue
        if mode in modes_found:
            lines += [f'- **[{mode}]** {action}', '']
            added = True

    if not added:
        lines += [
            '✅ No specific action items generated from current '
            'findings.',
            '',
        ]

    # Standard verification questions — suppressed when [ND] fires because
    # data-completeness / provenance questions are meaningless for a deposit
    # that contains no data.
    lines += ['---', '', '## Standard Verification Questions', '']
    if 'ND' in modes_found:
        lines += [
            '> **This deposit does not appear to contain any data or code files.**',
            '> The questions below are not applicable until the underlying research',
            '> materials have been deposited.',
            '',
            '1. **Deposit research materials:** Please provide the data files and/or '
            'analysis scripts used to produce your results. A deposit consisting '
            'only of manuscript and figure files cannot be validated.',
        ]
    else:
        lines += [
            'Please answer these regardless of the findings above:',
            '',
            *(_assessment_verification_questions(all_files)),
        ]
    lines += [
        '',
        '---',
        '',
        f'*Generated by ValiChord Repository Readiness Check — '
        f'Specification v15 — {now}*',
    ]

    out = output_dir / 'ASSESSMENT.md'
    out.write_text('\n'.join(lines), encoding='utf-8-sig')
    print(f"  → ASSESSMENT.md")
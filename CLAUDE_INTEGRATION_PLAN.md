# Claude API Integration Plan — ValiChord Autogenerate

**Author:** Ceri John + Claude Code
**Date:** March 2026
**Status:** Ready to implement — pending API credit allocation

---

## Context

This document is the implementation plan for integrating the Claude API into ValiChord's automated deposit analyser (`autogenerate/valichord.py` and `backend/app.py`). It was written at the point of submitting the Anthropic AI for Science Program application.

The plan is grounded in three source documents:
- **ValiChord Repository Cleaning Specification v15** (`ValiChord_Repository_Cleaning_Specification_15.md` on GitHub) — the original authoritative spec, written explicitly as instructions for a "cleaning LLM"
- **ValiChord at Home** (`docs/9_Valichord_at_Home.md`) — the researcher-facing tool that this pipeline feeds
- **UX Design** (`docs/18_The_UX/README.md`) — specifically the Validator Active Workspace, which displays the autogenerate output as a pre-screening report

The spec v15 was written to instruct an LLM directly. The current `autogenerate/` Python system is a rule-based partial implementation of that spec — covering the structurally-detectable failure modes. Claude's role is to cover the semantically-detectable ones: those that require actually reading and understanding code, cross-referencing files, and reasoning about methodology.

---

## What Exists Today

### Pipeline

```
ZIP → extract → run_simple_detectors() → generate_all_drafts()
                                        → generate_cleaning_report()
                                        → output ZIP
```

### What the rule-based system can detect

Pattern-matching against file structure and content:
- Presence/absence of README, licence, dependency files
- Absolute paths and hardcoded machine-specific paths
- Unpinned dependencies (missing version numbers)
- Missing checksums
- File naming inconsistencies
- Potential human subjects data (column header scanning)
- Broken source chains (file references that don't resolve)
- ~25 failure modes total from spec v15's ~60

### What it cannot detect

Anything requiring reading and understanding code logic:
- Whether the code actually does what the README/methods section claims
- Whether variables in the README match column names in data files
- Whether random seeds are set correctly for all RNG libraries used
- Whether intermediate outputs are written to paths that exist in the deposit
- Whether a statistical method is appropriate for the data described
- Whether analysis steps referenced in a paper are present in the code
- Whether a dependency is used but not declared (requires following imports)
- Whether the reported software environment is plausible given the actual imports

These are Failure Modes from spec v15 that the current system cannot reach.

---

## The New Pipeline

```
ZIP → extract → run_simple_detectors()
              → run_claude_analysis()        ← NEW
              → merge_findings()             ← NEW (trivial)
              → generate_all_drafts()
              → generate_cleaning_report()   ← enhanced with Claude detail
              → output ZIP
```

---

## New File: `autogenerate/detectors/claude_semantic.py`

This is the primary implementation target. It performs all three Claude tasks in a **single API call per deposit**.

### Function signature

```python
def run_claude_analysis(
    repo_dir: Path,
    all_files: list[Path],
    existing_findings: list[dict],
) -> tuple[list[dict], dict[str, str]]:
    """
    Run Claude semantic analysis on a research deposit.

    Returns:
        (additional_findings, enhanced_details)

        additional_findings: list of finding dicts in same schema as
            run_simple_detectors() output — {mode, severity, detail, ...}

        enhanced_details: dict mapping finding mode codes to deposit-specific
            explanatory text, replacing generic template text in the report.

    If ANTHROPIC_API_KEY is not set, returns ([], {}) immediately —
    the pipeline runs exactly as before (graceful degradation).
    """
```

### What gets sent to Claude

Built by `_build_context()`:

1. **System prompt** — The core rules from spec v15:
   - Anti-Hallucination Rule: never infer what is not stated; never map figures to files
   - Non-Destructive Rule: never propose deletion; `_DRAFT` suffix on all generated files
   - Anti-Authority Principle: the tool suggests; the researcher decides; researcher's expertise always takes precedence
   - "Results differ from paper ≠ ValiChord error"
   - Severity definitions: CRITICAL / SIGNIFICANT / LOW CONFIDENCE

2. **README content** — full text (capped at 8,000 chars)

3. **Code files** — all R, Python, MATLAB, Stata, Julia, .do files ≤ 50KB each, prefixed with `--- FILE: relative/path ---`

4. **Data column headers** — for each CSV/TSV/XLSX, the first row only

5. **Existing findings summary** — the mode codes and severities already found by rule-based detection, so Claude does not duplicate them

6. **Task instructions** — the three specific tasks (see below)

### Task 1: Cross-file consistency analysis

Claude is asked to check:
- Does the code implement the statistical method described in the README/methods? (e.g. "logistic regression" in README → is `glm(family=binomial)` or equivalent present in R? `sklearn.linear_model.LogisticRegression` or `statsmodels.Logit` in Python? `logit` in Stata?)
- Do variable names referenced in the README prose match column headers found in the data files?
- Is the software environment described in the README (Python version, key packages) consistent with the actual imports in the code?
- Are analysis steps described in the paper abstract or README present in the submitted scripts?

Output: list of findings, each with:
```json
{
  "mode": "SEMANTIC_CONSISTENCY",
  "severity": "SIGNIFICANT",
  "detail": "README describes ordinal logistic regression but analysis.R contains only lm() calls. No polr(), clm(), or equivalent found.",
  "files": ["analysis.R", "README.md"]
}
```

### Task 2: Code-level reproducibility assessment

Claude is asked to check each script for:
- **Random seeds:** Are seeds set for all RNG libraries imported? (`numpy`, `random`, `torch`, `tensorflow`, `jax` — each requires its own seed). JAX requires explicit key management via `jax.random.PRNGKey()`.
- **Undeclared dependencies:** Packages imported that are not in any dependency file found by rule-based detection.
- **Intermediate output paths:** Files written to paths (e.g. `/tmp/`, hardcoded subdirectories) that do not exist in the deposit.
- **Analysis steps in README not present in code:** Referenced procedures with no corresponding code.
- **System clock usage in filenames or seeds:** `datetime.now()`, `time.time()` in output filename generation or seed initialisation (Failure Mode BK from spec v15).
- **Git history dependency:** `subprocess(["git", ...])`, `setuptools_scm`, `versioneer` calls that will fail on a ZIP download (Failure Mode BL from spec v15).

Output: same finding schema as above, with mode codes referencing spec v15 where applicable (e.g. `"mode": "BK_SYSTEM_CLOCK"`).

### Task 3: Contextualised report detail

For each finding already identified by `run_simple_detectors()`, Claude writes a deposit-specific explanation that replaces the generic template text in `CLEANING_REPORT.md`.

The explanation:
- References the specific file(s) and line pattern where the issue was found
- Explains why this matters for *this type* of research (a missing seed matters differently in a Monte Carlo simulation vs a descriptive survey)
- Suggests a concrete remediation step calibrated to the language and framework in use
- Respects the Anti-Authority Principle: frames everything as a suggestion, not a verdict

Output: dict mapping mode codes to enhanced detail strings:
```json
{
  "B": "No requirements.txt or environment.yml found. The deposit imports numpy, pandas, and scikit-learn (found in analysis.py lines 1-3) but no version constraints are recorded. On Python 3.12, scikit-learn ≥ 1.3 changed the default solver for LogisticRegression — a version mismatch here could produce different convergence behaviour. Suggested fix: run `pip freeze > requirements.txt` in your analysis environment.",
  "F": "random.seed(42) is set at analysis.py:15 but torch.manual_seed() is not called. The model uses torch.nn.Dropout layers (analysis.py:89, 134) whose behaviour during training is controlled by PyTorch's RNG, not Python's random module. Add torch.manual_seed(42) after the existing seed call."
}
```

### Claude API call structure

```python
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    system=SYSTEM_PROMPT,  # spec v15 rules + output format instructions
    messages=[{
        "role": "user",
        "content": context_string  # assembled by _build_context()
    }]
)
```

Response is requested as structured JSON (via system prompt instruction). Parsed with `json.loads()`. If parsing fails, `run_claude_analysis()` logs a warning and returns `([], {})` — degrading gracefully.

### Context window budget

| Component | Typical tokens |
|---|---|
| System prompt (spec rules + format) | ~1,200 |
| README | ~600 |
| 3 code files @ 5KB each | ~3,750 |
| CSV column headers | ~300 |
| Existing findings summary | ~400 |
| Task instructions | ~500 |
| **Total input** | **~6,750** |
| Claude output (JSON findings + enhanced details) | ~2,000 |
| **Total per deposit** | **~8,750** |

1,000 deposits ≈ 8.75M tokens. Consistent with application estimate.

For large deposits (many code files), `_build_context()` applies a priority filter:
1. Always include README
2. Include code files in order of size (smallest first, most likely to be analysis scripts)
3. Cap total code content at ~30,000 chars
4. Always include existing findings summary

---

## Changes to `autogenerate/valichord.py`

Three additions only:

```python
# 1. Import
from detectors.claude_semantic import run_claude_analysis

# 2. After run_simple_detectors(), before generate_all_drafts():
print("Running semantic analysis...")
claude_findings, enhanced_details = run_claude_analysis(
    repo_dir, all_files, findings
)
if claude_findings:
    findings = findings + claude_findings
    print(f"  Claude findings: {len(claude_findings)}")
else:
    print("  (no API key — semantic analysis skipped)")

# 3. Pass enhanced_details to report generator:
generate_cleaning_report(
    zip_path.name, repo_dir, all_files, findings, output_dir,
    enhanced_details=enhanced_details   # ← new kwarg
)
```

---

## Changes to `autogenerate/generators/report.py`

One change in the finding render loop. Currently:

```python
detail_text = finding['detail']
```

Becomes:

```python
detail_text = enhanced_details.get(finding['mode'], finding['detail'])
```

`generate_cleaning_report()` gains `enhanced_details: dict = None` as a kwarg, defaulting to `{}`. Fully backwards compatible — existing tests unchanged.

---

## Changes to `backend/app.py`

Mirror the same three changes from `valichord.py`. Per the two-entry-point rule in project memory: both entry points must receive every change.

---

## ValiChord at Home connection

The UX design document (`docs/18_The_UX/README.md`) describes the Validator's Active Workspace (Screen 2):

> *"ValiChord analysis report — the automated pre-screening output from ValiChord at Home, showing known reproducibility issues in the deposit"*

The output of this pipeline **is** that pre-screening report. When ValiChord at Home is built as a standalone researcher tool, it will import `detectors/claude_semantic.py` directly. No architectural changes needed — the module is already designed as a drop-in.

The key difference in at Home context: the `enhanced_details` output becomes the primary researcher-facing content (contextualised, actionable, mentor-not-gatekeeper tone), while the raw findings power the severity badges and PRS score.

---

## Spec v15 failure modes: rule-based vs Claude

The following maps which of spec v15's ~60 failure modes are covered by the current rule-based system vs. which Claude adds:

### Currently covered (rule-based)
A (no README), B (unpinned deps), C (absolute paths), D (no licence), E (undocumented data), F (partial — detects missing seed files, not logic), G (derived objects), H (inline version comments), I (README variable listings), K (dependency files), L (publication materials misclassified), M (duplicate format pairs), N (casing inconsistency), O (imaging/mesh deposits), Q (checksum scope), R (OSF DOI), S (human subjects), T (filename chars), U (psychometric terms), V (Windows-illegal chars), Y (data without docs), Z (version tags), BA (missing checksums), BD (non-researcher R files), CA (broken source chain)

### Added by Claude semantic analysis
- **Cross-file consistency** (README method vs code implementation)
- **Variable name matching** (README variables vs data column headers)
- **Complete seed coverage** (all RNG libraries, including JAX key management)
- **Undeclared dependency detection** (imports not in dependency files)
- **Intermediate output paths** (written to non-existent locations)
- **BK** (system clock dependency in filenames/seeds)
- **BL** (git history dependency — setuptools_scm, git describe)
- **BE** (compiler flags — `-march=native` — semantic check)
- **BF** (runtime env shadowing — cross-file check)
- **Contextualised detail** for all existing findings

---

## Build order

1. **`detectors/claude_semantic.py`** — the Claude call, JSON parsing, finding schema mapping, graceful degradation
2. **`autogenerate/valichord.py`** — wire in the call, pass `enhanced_details` downstream
3. **`autogenerate/generators/report.py`** — consume `enhanced_details` in render loop
4. **`backend/app.py`** — mirror steps 2 and 3
5. **Test** on existing sample deposits in `autogenerate/output/` and `output/`
6. **Calibrate** system prompt against known-good deposits — adjust severity thresholds if Claude over- or under-fires

---

## Key constraints from spec v15 to honour in the system prompt

These are non-negotiable rules from the spec. The Claude system prompt must include all of them:

**Anti-Hallucination Rule:** Never infer what is not in the files. Never map figures to files. Never guess what a variable-based path resolves to by following cross-file references. If something is not stated explicitly, report it as absent, not as present.

**Non-Destructive Rule:** Never propose deletion of any file. Every generated file has a `_DRAFT` suffix. Corrected copies go in `/proposed_corrections/` only.

**Anti-Authority Principle:** The tool suggests; the researcher verifies and decides. The researcher's domain knowledge always takes precedence over the tool's assessment. Every finding is framed as "check this" not "this is wrong."

**"Results differ ≠ ValiChord error":** Explicitly include this disclaimer in the output. A validator getting different numbers does not mean ValiChord made a mistake — it means reproduction failed, which is the point.

**Evidence citation:** Every finding must cite `file:line` or `file:section` where the evidence was found. No finding without evidence.

---

## Environment variable

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

If absent: pipeline runs as today (rule-based only). No error raised. Status line in output: `"Semantic analysis: skipped (no API key)"`.

---

## Notes for resuming this work

- The `autogenerate/output/` directory contains several real processed deposits that can be used to test the integration. Unzip any of them and use the original repository inside as test input.
- The `output/` directory at root also has deposits including Dryad downloads.
- Start with `detectors/claude_semantic.py` — get the API call working and returning parseable JSON before touching the pipeline wiring.
- The system prompt is the hardest part. The spec v15 rules need to be expressed precisely enough that Claude applies them consistently, but not so rigidly that valid deposits get over-flagged.
- Check memory file (`/home/codespace/.claude/projects/-workspaces-ValiChord/memory/MEMORY.md`) for recurring bug patterns in the existing detectors — some of these will be relevant when writing the Claude prompt (e.g. Pattern A on root-vs-subfolder selection, Pattern K on R package library files).

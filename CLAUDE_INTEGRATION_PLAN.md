# Claude API Integration Plan — ValiChord Autogenerate

**Author:** Ceri John + Claude Code
**Date:** March 2026
**Status:** Rule-based detectors implemented. Claude semantic layer pending API credit allocation.

---

## Context

This document is the implementation plan for integrating the Claude API into ValiChord's automated deposit analyser (`valichord_at_home/valichord.py` and `backend/app.py`). It was written at the point of submitting the Anthropic AI for Science Program application and has been updated to reflect the current state of the codebase.

The plan is grounded in three source documents:
- **ValiChord Repository Cleaning Specification v15** (`ValiChord_Repository_Cleaning_Specification_15.md` on GitHub) — the original authoritative spec, written explicitly as instructions for a "cleaning LLM"
- **ValiChord at Home** (`docs/9_Valichord_at_Home.md`) — the researcher-facing tool that this pipeline feeds
- **UX Design** (`docs/18_The_UX/README.md`) — specifically the Validator Active Workspace, which displays the autogenerate output as a pre-screening report

The spec v15 was written to instruct an LLM directly. The current `valichord_at_home/` Python system is a rule-based implementation of that spec — covering structurally and syntactically detectable failure modes. Claude's role is to cover the semantically-detectable ones: those that require actually reading and understanding code, cross-referencing files, and reasoning about methodology.

---

## What Exists Today

### Pipeline

```
ZIP → extract → run_simple_detectors() → generate_all_drafts()
                                        → generate_cleaning_report()
                                        → output ZIP
```

### What the rule-based system can detect

Pattern-matching against file structure and content — **128 detector functions** covering:
- Presence/absence of README, licence, dependency files
- Absolute paths and hardcoded machine-specific paths
- Unpinned and missing dependencies (including cross-referencing actual imports against declared packages — **[DH]**, implemented March 2026)
- Missing checksums, seeds, container definitions
- Random seed coverage across all major RNG libraries: numpy, torch, tensorflow, sklearn, lightgbm, xgboost, JAX — **[F]**
- System clock dependency — **[BK]**; git history dependency — **[BL]**
- File naming inconsistencies, duplicate format pairs, encoding issues
- Potential human subjects data (column header scanning)
- Broken source chains, missing script references
- README variable names vs data column headers — **[DI]**, implemented March 2026
- Language-specific issues: R renv/packrat, Python conda/pip, Julia manifests, MATLAB toolboxes
- Workflow managers, Docker, Snakemake, Nextflow

### What it cannot detect

The following require semantic understanding that rule-based pattern matching cannot provide:

| Gap | Why rule-based is insufficient |
|---|---|
| Code does what README/methods claims | Requires understanding statistical method names and their code equivalents across all languages and frameworks |
| Analysis steps in README present in code | Keyword matching covers ~70%; the remaining 30% (wrong model family, mis-specified formula) requires code comprehension |
| Intermediate output paths exist in deposit | Only catchable for literal string paths; f-strings and variable-based paths require code execution tracing |
| Reported software environment plausible for actual imports | Import detection is rule-based; version plausibility (e.g. uses a PyTorch 2.0 API but declares torch==1.8) requires API history knowledge |
| Contextualised, deposit-specific report detail | Generic template text; Claude can tailor findings to the specific language, framework, and research type |

**Removed from Claude scope (now covered rule-based):**
- Random seed coverage — implemented in [F]
- Undeclared dependency detection — implemented in [DH]
- Variable name mismatch — implemented in [DI]
- BK (system clock) and BL (git history dependency) — already implemented

**Deliberately out of scope (too high false-positive risk):**
- Statistical method appropriateness — requires deep domain expertise; Claude over-fires and would violate the Anti-Authority Principle

---

## The New Pipeline (when API key is available)

```
ZIP → extract → run_simple_detectors()    ← runs always (128 detectors)
              → run_claude_analysis()      ← NEW: silent if no ANTHROPIC_API_KEY
              → merge_findings()           ← NEW (trivial)
              → generate_all_drafts()
              → generate_cleaning_report() ← enhanced with Claude detail if key present
              → output ZIP
```

**Graceful degradation:** if `ANTHROPIC_API_KEY` is not set, `run_claude_analysis()` returns `([], {})` immediately. The pipeline runs exactly as today. No error is raised. The 128 rule-based detectors always run.

---

## New File: `valichord_at_home/detectors/claude_semantic.py`

This is the primary remaining implementation target. It performs all Claude tasks in a **single API call per deposit**.

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
            run_simple_detectors() output — {mode, severity, title, detail, evidence}

        enhanced_details: dict mapping finding mode codes to deposit-specific
            explanatory text, replacing generic template text in the report.

    If ANTHROPIC_API_KEY is not set, returns ([], {}) immediately.
    """
```

### What gets sent to Claude

Built by `_build_context()`:

1. **System prompt** — The core rules from spec v15 (see Key Constraints below)
2. **README content** — full text (capped at 8,000 chars)
3. **Code files** — all R, Python, MATLAB, Stata, Julia, .do files ≤ 50KB each, prefixed with `--- FILE: relative/path ---`
4. **Data column headers** — for each CSV/TSV/XLSX, the first row only
5. **Existing findings summary** — mode codes and severities already found, so Claude does not duplicate them
6. **Task instructions** — the two specific tasks (see below)

### Task 1: Cross-file consistency analysis

Claude is asked to check:
- Does the code implement the statistical method described in the README/methods? (e.g. "logistic regression" in README → is `glm(family=binomial)` or equivalent present in R? `sklearn.linear_model.LogisticRegression` or `statsmodels.Logit` in Python? `logit` in Stata?)
- Is the software environment described in the README (Python version, key packages) consistent with the actual imports in the code?
- Are analysis steps described in the paper abstract or README present in the submitted scripts?

Output: list of findings, each with:
```json
{
  "mode": "SEMANTIC_CONSISTENCY",
  "severity": "SIGNIFICANT",
  "title": "README describes ordinal logistic regression but no equivalent found in code",
  "detail": "README describes ordinal logistic regression but analysis.R contains only lm() calls. No polr(), clm(), or equivalent found.",
  "files": ["analysis.R", "README.md"]
}
```

### Task 2: Contextualised report detail

For each finding already identified by `run_simple_detectors()`, Claude writes a deposit-specific explanation that replaces the generic template text in `CLEANING_REPORT.md`.

The explanation:
- References the specific file(s) and line pattern where the issue was found
- Explains why this matters for *this type* of research
- Suggests a concrete remediation step calibrated to the language and framework in use
- Respects the Anti-Authority Principle: frames everything as a suggestion, not a verdict

Output: dict mapping mode codes to enhanced detail strings:
```json
{
  "B": "No requirements.txt or environment.yml found. The deposit imports numpy, pandas, and scikit-learn (found in analysis.py lines 1-3) but no version constraints are recorded. Suggested fix: run `pip freeze > requirements.txt` in your analysis environment.",
  "F": "random.seed(42) is set at analysis.py:15 but torch.manual_seed() is not called. The model uses torch.nn.Dropout layers whose behaviour during training is controlled by PyTorch's RNG. Add torch.manual_seed(42) after the existing seed call."
}
```

### Claude API call structure

```python
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    system=SYSTEM_PROMPT,
    messages=[{
        "role": "user",
        "content": context_string  # assembled by _build_context()
    }]
)
```

Response is requested as structured JSON (via system prompt instruction). Parsed with `json.loads()`. If parsing fails, `run_claude_analysis()` logs a warning and returns `([], {})`.

**Note on structured output:** Claude occasionally produces valid content with prose before/after the JSON block. The parser should use a regex to extract the JSON block before calling `json.loads()` rather than parsing the raw response string directly.

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

For large deposits, `_build_context()` applies a priority filter:
1. Always include README
2. Include code files in order of size (smallest first — most likely to be analysis scripts)
3. Cap total code content at ~30,000 chars
4. Always include existing findings summary

---

## Changes to `valichord_at_home/valichord.py`

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

## Changes to `valichord_at_home/generators/report.py`

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

Mirror the same three changes from `valichord.py`. Per the two-entry-point rule: both entry points must receive every change.

---

## ValiChord at Home connection

The UX design document (`docs/18_The_UX/README.md`) describes the Validator's Active Workspace (Screen 2):

> *"ValiChord analysis report — the automated pre-screening output from ValiChord at Home, showing known reproducibility issues in the deposit"*

The output of this pipeline **is** that pre-screening report. When ValiChord at Home is built as a standalone researcher tool, it will import `detectors/claude_semantic.py` directly. No architectural changes needed — the module is already designed as a drop-in.

The `enhanced_details` output becomes the primary researcher-facing content in the at Home context (contextualised, actionable, mentor-not-gatekeeper tone), while the raw findings power the severity badges and PRS score.

---

## Spec v15 failure modes: rule-based vs Claude

### Currently covered (rule-based) — 128 detectors

All detector functions in `failure_modes_simple.py` — spanning failure modes A through HS plus custom codes. Key additions since original plan:

- **[DH]** Undeclared imports: Python imports vs requirements.txt/environment.yml; R library() calls vs renv.lock/DESCRIPTION
- **[DI]** Variable name mismatch: README variable documentation sections vs tabular data column headers

### Added by Claude semantic analysis

- **Cross-file consistency** (README method description vs code implementation)
- **Analysis steps coverage** (steps mentioned in README present in submitted scripts)
- **Intermediate output paths** (written to paths constructed dynamically — not detectable by static analysis)
- **Software environment plausibility** (version claims vs actual API usage)
- **Contextualised detail** for all existing findings

### Deliberately out of scope

- **Statistical method appropriateness** — requires domain expertise that varies by field; Claude over-fires on legitimate methodological choices and violates the Anti-Authority Principle

---

## Build order (remaining work)

1. **`detectors/claude_semantic.py`** — the Claude call, JSON parsing, finding schema mapping, graceful degradation
2. **`valichord_at_home/valichord.py`** — wire in the call, pass `enhanced_details` downstream
3. **`valichord_at_home/generators/report.py`** — consume `enhanced_details` in render loop
4. **`backend/app.py`** — mirror steps 2 and 3
5. **Test** on deposits in `valichord_at_home/output/` and `output/`
6. **Calibrate** system prompt — adjust severity thresholds if Claude over- or under-fires

---

## Key constraints from spec v15 to honour in the system prompt

**Anti-Hallucination Rule:** Never infer what is not in the files. Never map figures to files. Never guess what a variable-based path resolves to. If something is not stated explicitly, report it as absent, not as present.

**Non-Destructive Rule:** Never propose deletion of any file. Every generated file has a `_DRAFT` suffix. Corrected copies go in `/proposed_corrections/` only.

**Anti-Authority Principle:** The tool suggests; the researcher verifies and decides. The researcher's domain knowledge always takes precedence over the tool's assessment. Every finding is framed as "check this" not "this is wrong."

**"Results differ ≠ ValiChord error":** Explicitly include this disclaimer. A validator getting different numbers does not mean ValiChord made a mistake — it means reproduction failed, which is the point.

**Evidence citation:** Every finding must cite `file:line` or `file:section` where the evidence was found. No finding without evidence.

---

## Environment variable

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

If absent: pipeline runs as today (rule-based only, 128 detectors). No error raised. Status line in output: `"Semantic analysis: skipped (no API key)"`.

---

## Notes for resuming this work

- The `valichord_at_home/output/` directory contains real processed deposits for testing. Unzip any and use the original repository inside as test input.
- The `output/` directory at root also has deposits including Dryad downloads.
- Start with `detectors/claude_semantic.py` — get the API call working and returning parseable JSON before touching the pipeline wiring.
- The system prompt is the hardest part. The spec v15 rules need to be expressed precisely enough that Claude applies them consistently, but not so rigidly that valid deposits get over-flagged.
- Use a regex to extract the JSON block from the response before `json.loads()` — Claude occasionally adds prose before/after the JSON.
- Check memory file for recurring bug patterns in existing detectors — some are relevant when writing the Claude prompt (Pattern A on root-vs-subfolder selection, Pattern K on R package library files).
- The [DH] and [DI] detectors (now implemented) provide useful context to include in the existing findings summary sent to Claude, since they represent the boundary between what rule-based has already found and what Claude is being asked to add.

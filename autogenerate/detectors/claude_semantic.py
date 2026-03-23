"""
ValiChord Auto-Generate
Claude API semantic analysis — optional layer on top of rule-based detectors.

Requires ANTHROPIC_API_KEY to be set in the environment.
If the key is absent this module returns ([], {}) immediately and the
pipeline runs exactly as without it — no error is raised, no findings
are affected.

Usage (called from valichord.py and backend/app.py):

    from detectors.claude_semantic import run_claude_analysis

    claude_findings, enhanced_details = run_claude_analysis(
        repo_dir, all_files, existing_findings
    )
    if claude_findings:
        findings += claude_findings
"""

import os
import json
import re
from pathlib import Path

# ── constants ──────────────────────────────────────────────────────────────────

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096

# Total characters of code content to include in the context (≈ 30k tokens).
_MAX_CODE_CHARS = 120_000

# Maximum README characters to include.
_MAX_README_CHARS = 8_000

# Code file extensions to send to Claude.
_SEMANTIC_CODE_EXTS = {'.py', '.r', '.rmd', '.qmd', '.jl', '.m', '.do', '.sas', '.ado'}

# ── system prompt ──────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a research reproducibility assistant analysing a scientific code deposit.
Your role is to identify reproducibility issues that require reading and understanding
code logic — issues that cannot be found by pattern matching alone.

## Non-negotiable rules

**Anti-Hallucination Rule:** Never infer what is not explicitly present in the files
provided. Never map figures to files. Never guess what a variable-based path resolves
to. If something is not stated explicitly, report it as absent — not as present.

**Anti-Authority Principle:** The tool suggests; the researcher verifies and decides.
The researcher's domain knowledge always takes precedence. Every finding must be
framed as "check this" not "this is wrong". Use hedged language: "appears to",
"may indicate", "could not find".

**Non-Destructive Rule:** Never propose deletion of any file. All generated files
must carry a _DRAFT suffix. Corrections go in proposed_corrections/ only.

**Evidence citation:** Every finding must cite the specific file and either a line
reference or a quoted phrase where the evidence was found. No finding without evidence.

**Results differ ≠ error:** A validator obtaining different numerical results does
not mean ValiChord made a mistake — it means reproduction failed, which is the point.

## Severity definitions

- SIGNIFICANT: would likely cause reproduction to fail or produce different results
- LOW CONFIDENCE: worth checking but may be intentional or benign

## Output format

Respond with a single JSON object. Do not include any prose before or after the JSON.

{
  "additional_findings": [
    {
      "mode": "SEMANTIC_CONSISTENCY",
      "severity": "SIGNIFICANT",
      "title": "Short title (max 80 chars)",
      "detail": "Explanation respecting Anti-Authority Principle.",
      "evidence": ["file.py: quoted phrase or line ref"]
    }
  ],
  "enhanced_details": {
    "MODE_CODE": "Deposit-specific replacement for the generic finding detail. Reference specific files, line patterns, and why this matters for this type of research. Suggest a concrete fix calibrated to the language and framework in use."
  }
}

If you find nothing to add and nothing to enhance, return:
{"additional_findings": [], "enhanced_details": {}}
"""

# ── context builder ────────────────────────────────────────────────────────────

def _build_context(repo_dir: Path, all_files: list, existing_findings: list) -> str:
    """Assemble the user message to send to Claude."""
    parts = []

    # 1. README
    readme_candidates = sorted(
        [f for f in all_files
         if f.name.lower() in {'readme.md', 'readme.txt', 'readme.rst', 'readme'}],
        key=lambda x: len(x.parts)
    )
    if readme_candidates:
        try:
            readme_text = readme_candidates[0].read_text(encoding='utf-8', errors='ignore')
            parts.append(f"--- README: {readme_candidates[0].name} ---\n"
                         + readme_text[:_MAX_README_CHARS])
        except Exception:
            pass

    # 2. Code files (smallest first — most likely to be analysis scripts)
    code_files = sorted(
        [f for f in all_files
         if f.suffix.lower() in _SEMANTIC_CODE_EXTS
         and f.stat().st_size <= 50 * 1024],  # skip files > 50 KB
        key=lambda f: f.stat().st_size
    )
    total_chars = 0
    for f in code_files:
        if total_chars >= _MAX_CODE_CHARS:
            break
        try:
            text = f.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        rel = f.relative_to(repo_dir)
        parts.append(f"--- FILE: {rel} ---\n{text}")
        total_chars += len(text)

    # 3. Column headers from tabular data files
    header_lines = []
    for f in all_files:
        if f.suffix.lower() not in {'.csv', '.tsv', '.tab'}:
            continue
        try:
            with f.open(encoding='utf-8', errors='ignore') as fh:
                first = fh.readline()
            rel = f.relative_to(repo_dir)
            header_lines.append(f"  {rel}: {first.strip()[:200]}")
        except Exception:
            continue
    if header_lines:
        parts.append("--- DATA COLUMN HEADERS ---\n" + "\n".join(header_lines[:20]))

    # 4. Existing findings summary (so Claude doesn't duplicate them)
    if existing_findings:
        summary_lines = [
            f"  [{f['mode']}] {f['severity']}: {f['title']}"
            for f in existing_findings
            if f.get('severity') != 'INFO'
        ]
        parts.append(
            "--- EXISTING FINDINGS (do not duplicate) ---\n"
            + "\n".join(summary_lines)
        )

    # 5. Task instructions
    parts.append("""\
--- TASKS ---

Task 1 — Cross-file consistency:
Check whether the code implements the statistical method described in the README.
Check whether analysis steps described in the README are present in the submitted scripts.
Check whether the reported software environment is plausible given the actual imports.
Report only concrete mismatches with specific evidence.

Task 2 — Contextualised detail:
For each existing finding listed above, write a deposit-specific explanation that replaces
the generic template text. Reference the specific files and patterns involved. Explain why
this matters for this type of research. Suggest a concrete fix for the language/framework
in use. Respect the Anti-Authority Principle throughout.
Add an entry to enhanced_details only if you can genuinely improve on the generic text.
""")

    return "\n\n".join(parts)


# ── response parser ────────────────────────────────────────────────────────────

def _parse_response(text: str) -> tuple[list, dict]:
    """Extract JSON from Claude's response. Returns (findings, enhanced_details)."""
    # Claude occasionally wraps JSON in a markdown code block — strip it.
    match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', text, re.DOTALL)
    if match:
        text = match.group(1)
    else:
        # Find the outermost {...} block
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            text = text[start:end + 1]

    try:
        data = json.loads(text)
    except Exception:
        return [], {}

    findings = data.get('additional_findings', [])
    enhanced = data.get('enhanced_details', {})

    # Basic schema validation — drop malformed entries silently
    valid_findings = []
    for f in findings:
        if all(k in f for k in ('mode', 'severity', 'title', 'detail')):
            valid_findings.append({
                'mode':     f['mode'],
                'severity': f['severity'],
                'title':    f['title'],
                'detail':   f['detail'],
                'evidence': f.get('evidence', []),
            })

    return valid_findings, (enhanced if isinstance(enhanced, dict) else {})


# ── public entry point ─────────────────────────────────────────────────────────

def run_claude_analysis(
    repo_dir: Path,
    all_files: list,
    existing_findings: list,
) -> tuple[list, dict]:
    """Run Claude semantic analysis on a research deposit.

    Returns:
        (additional_findings, enhanced_details)

        additional_findings — list of finding dicts in the same schema as
            run_simple_detectors() output: {mode, severity, title, detail, evidence}

        enhanced_details — dict mapping finding mode codes to deposit-specific
            explanatory text, replacing generic template text in the report.

    If ANTHROPIC_API_KEY is not set, returns ([], {}) immediately and the
    pipeline continues unchanged.
    """
    if not os.environ.get('ANTHROPIC_API_KEY'):
        return [], {}

    try:
        import anthropic
    except ImportError:
        print("  [Claude] anthropic package not installed — semantic analysis skipped.")
        print("  [Claude] Install with: pip install anthropic")
        return [], {}

    context = _build_context(repo_dir, all_files, existing_findings)

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context}],
        )
        raw = response.content[0].text
    except Exception as e:
        print(f"  [Claude] API call failed: {e}")
        return [], {}

    findings, enhanced = _parse_response(raw)

    if findings or enhanced:
        print(f"  [Claude] {len(findings)} additional finding(s), "
              f"{len(enhanced)} enhanced detail(s)")
    else:
        print("  [Claude] No additional findings.")

    return findings, enhanced

# ValiChord — Repository Cleaning Specification
## What Makes a Research Repository Reproducible, What Makes One Broken, and How to Fix It

**Author:** Ceri John
**Date:** February 2026
**Version:** 15 — revised following multi-LLM critical review of v14 (Gemini final review)
**Status:** Working draft — submitted for further review

**© 2026 Ceri John. All Rights Reserved.**

**Contact:** topeuph@gmail.com

---

## Version History

| Version | Date | Changes |
|---|---|---|
| 1 | February 2026 | Initial draft |
| 2 | February 2026 | Failure modes B–T; confidence labeling; non-linear scope note |
| 3 | February 2026 | Failure modes U–Z; Reorganisation Protocol; Path Correction Protocol; dependency cross-referencing |
| 4 | February 2026 | Failure modes AA–AK; Anti-Hallucination Rule; Non-Destructive Rule; run_all.sh; Bioconductor; GIS formats |
| 5 | February 2026 | Failure modes AL–AO; evidence citation (file:line); unified diff; MATLAB .mlx; Nix/Guix/Spack |
| 6 | February 2026 | Failure modes AP–AR; CITATION.cff; DVC/MLflow; dependency opt-in; container split; Quarto; "definition of successful reproduction" |
| 7 | February 2026 | Failure modes AS–AV; run_all.sh constraints; CITATION.cff structured evidence; corrected-copy files; PPM date-based; evidence hierarchy |
| 8 | February 2026 | Failure mode AW; F/K/S/AT expanded; canonical dependency identification; credential vs configuration; Rust/Go/Java/JS |
| 9 | February 2026 | Failure mode AX; submodules; editable installs; GPU wheel variants; Simulink; RAM; Anti-Authority Principle; _DRAFT system |
| 10 | February 2026 | Failure modes AY, AZ, BA; semantic-structural filenames; AX column rename demotion; GPU control vars; shapefile/checksum |
| 11 | February 2026 | Failure modes BB, BC; AL/K/F/AD expanded; AZ namespace packages; /proposed_corrections/; Airflow/Dagster; researcher warning |
| 12 | February 2026 | Failure modes BD, BE; semantic labels removed; _DRAFT naming; runtime errors in corrected-copy files; CITATION.cff tightened; ML leakage callout; conda channel priority; Python version-specific syntax; test file contamination; conda/pip split; Julia Pluto; distributed training; E-Prime/PsychoPy; monorepo shared library warning |
| 13 | February 2026 | Failure modes BF (runtime env shadowing), BG (timestamp ordering); dynamic imports in AZ; AM expanded (mixed precision, JAX XLA/TPU); BD expanded; AQ expanded (implicit network access); README-derived run_all demoted to QUICKSTART LOW CONFIDENCE; all-file import scanning; .env.example URL/hostname/port guard; renv.lock GitHub remotes expanded; MATLAB .mat version differences; Julia Pluto hidden cells; "results differ ≠ ValiChord error"; figure-to-file mapping prohibition |
| 14 | February 2026 | Failure modes BH (hidden startup scripts), BI (hardcoded thread counts), BJ (encrypted files); F expanded (JAX PRNG explicit keys); file purpose: # Purpose:/#Summary: comment extraction at LOW CONFIDENCE; CITATION_DRAFT.cff: CITATION/CITATION.txt BibTeX; R Depends/Imports wording tightened; NetLogo JRE; PsychoPy monitor calibration; clean machine: cache flags |
| 15 | February 2026 | Failure modes BK (system clock dependency), BL (shallow clone/missing git history); Pluto embedded Project.toml block check; file header comment semantic label: always-appended caveat added; CITATION_DRAFT.cff: CrossRef API DOI resolution added at MEDIUM CONFIDENCE (source: CrossRef API); variable-based path resolution guard added to Anti-Hallucination Rule; HPC clean machine warning added to Form A |

---

## Purpose of This Document

This document defines the specification for ValiChord's Auto-Generate feature — a tool that accepts a messy research repository, analyses its contents, and returns an improved version for researcher verification.

It serves three purposes:

1. **Engineering specification.** It tells the cleaning LLM exactly what to assess, what to generate, what to reorganise, and what to leave strictly alone.
2. **Quality benchmark.** It defines what a reproducible repository looks like, so the output can be evaluated against a clear standard.
3. **Researcher communication.** It provides the foundation for explaining to researchers what the tool does, what it cannot do, and why their verification is not optional.

This document does not contain code. It contains the thinking that must precede code.

---

## A Note on Scope

This specification is written primarily for **single linear pipelines** — code that moves from raw data through analysis to published outputs in a defined sequence. This covers the majority of computational research in social sciences, ecology, economics, psychology, and many areas of biology.

Modern research in machine learning, genomics, climate modelling, and physics simulation often involves parameter sweeps, stochastic outputs, and multiple experimental runs where approximate reproduction is the realistic standard. These workflows are significantly more complex. The model of a "perfect repository" here is a target for linear pipelines. Extensions for non-linear workflows are noted where relevant but not fully specified in this version.

**Multi-project repositories:** A submitted archive containing several independent papers or code trees is outside the primary scope (see Failure Mode AO). The tool detects shared library directories and warns before any reorganisation proposal — see Monorepo Shared Library Warning in Section 4.

**Pure data deposits:** If no code files are detected, the assessment pivots to data documentation only — README adequacy, data dictionary, licence, and provenance documentation.

**Previously processed repositories:** If a `CLEANING_REPORT.md` with ValiChord headers is detected, the tool flags this and warns before proceeding.

---

## Section 1: What a Research Repository Is

### For Researchers Who May Not Know the Term

When you publish a scientific paper that uses computational methods — analysing data, running simulations, building statistical models — you produce two things: the paper, and the work behind the paper.

The work behind the paper is a collection of files: the data you analysed, the code you wrote to analyse it, and instructions explaining how everything fits together. Together, these files form your **research repository** — sometimes called a **data package**, **replication package**, or **code and data deposit**.

The repository is the reproducibility package. It is what another researcher would need to sit down with, on their own computer, and attempt to get the same results you reported. When it is well constructed, that is possible. When it is poorly constructed, it is not — and most repositories, in practice, are poorly constructed, not because researchers are careless, but because nobody taught them what a good one looks like, and there was no time, credit, or support for making it right.

ValiChord's Auto-Generate feature exists to help fix that. It takes what you have, works out what is missing, and returns an improved draft for you to check. It does not verify your results. Only you can do that.

### What a Repository Is Not

A repository is not the published paper itself; a backup of your working directory; a live database or web application; a record of every dead end you explored; or a guarantee that results are correct. It is specifically the **minimum set of files needed for an independent researcher to reproduce your published computational results**.

### Where Repositories Live

Repositories are typically deposited in Zenodo, Figshare, OSF, GitHub/GitLab, Dryad, institutional repositories, or domain-specific archives (ICPSR, GEO, OpenNeuro, PANGAEA). For Auto-Generate, repositories are submitted as a compressed ZIP archive.

---

## Section 2: The Anatomy of a Perfect Repository

A perfect research repository has five components, all present and all functional.

### Component 1: A README File

**A perfect README contains:**

**1. Study identification**
- Full title of the associated paper
- Authors and affiliations
- DOI or URL of the published paper (or preprint)
- Date of deposit
- **Commit hash or version tag** corresponding to this deposit (see Failure Mode Z)

**2. Study overview** (2–5 sentences, written by the researcher). The cleaning tool leaves this as a placeholder if no abstract, paper draft, or explicit plain-language description exists in the repository.

**3. Repository structure** — a description of every folder and key file

**4. System requirements**
- Operating system with version if platform-specific
- Programming language and exact version
- Hardware requirements including GPU model, minimum CPU architecture (see Failure Mode AT), and minimum RAM
- Estimated runtime on standard hardware
- Whether HPC, cluster, or cloud platform access is required; if so, the number of nodes and cores used
- Any required proprietary software or vendor SDKs (see Failure Mode AS)

**5. Installation instructions** — step-by-step environment setup; `.env.example` referenced if environment variables required; workflow manager installation (see Failure Mode AR); PPM snapshot date if used for CRAN packages

**6. Execution instructions** — numbered steps, which script produces which result; `run_all.sh` or Makefile referenced as primary entry point if generated

**7. Data access instructions** — location, format, download URL; exact version of any versioned external dataset (see Failure Mode AW); if data is anonymised or synthetic, state explicitly; MD5 or SHA-256 checksums for any large externally-hosted files

**8. Expected outputs** — what a validator should see; key numerical results; **explicit figure-to-file mapping provided by the researcher** (the tool cannot infer this — see Anti-Hallucination Rule); whether exact visual appearance is required or only numerical data

**9. Definition of successful reproduction** — explicit researcher-written statement. Required; procedural placeholder only:

> *[You must complete this section. State what constitutes successful reproduction of your results. This is a required section — do not leave this placeholder in place.]*

**10. Known issues, limitations, and platform dependencies** — stochasticity, external services, manual steps, platform-sensitive numerics, proprietary SDK requirements

**11. Licence** — code licence, data licence, redistribution restrictions; confirmation of authorisation to share any human subjects data

**12. Contact** — who to contact if reproduction fails

---

### Component 2: Data Files

A perfect data component is organised in clearly named folders; includes a data dictionary; distinguishes raw from processed data; uses open formats; documents provenance including exact version of any external versioned data source and checksums for large externally-hosted files; contains no undisclosed sensitive data; avoids symlinks; and — if anonymised or synthetic — documents the transformation.

Geospatial Shapefile format requires the complete bundle: `.shp`, `.shx`, `.dbf`, `.prj`, optionally `.cpg`.

On derived objects: the repository must contain the code that produces each from upstream data (see Failure Mode G).

---

### Component 3: A Dependency Specification

**The single most important rule: pin exact version numbers.**

**Python:**
- `requirements.txt` with exact versions, generated via `pip freeze` in a **plain virtualenv only**
- **conda environments:** `pip freeze` inside conda omits conda-managed packages. Use `conda env export` for conda packages; `pip list --format=freeze` for pip-only additions.
- OR `poetry.lock`, `Pipfile.lock`, `conda-lock.yml`
- OR `environment.yml` with pinned versions (`--no-builds` for portability)
- **conda channel priority:** Document the channel order used, or use `conda-lock`.
- **micromamba / mamba:** Document the tool used alongside any lock file.
- Python version specified in README and environment file
- **Editable installs:** Document with source path or git URL and commit hash.
- **GPU-specific wheel variants:** Document exact variant string and system-level CUDA toolkit requirement.
- **GPU control environment variables:** `CUDA_VISIBLE_DEVICES`, `CUDA_DEVICE_ORDER`, `TF_CPP_MIN_LOG_LEVEL` — include in `.env.example`.
- **JAX note:** JAX requires functional purity for reproducible JIT compilation. **JAX uses a completely separate PRNG system from numpy — `np.random.seed()` does not affect JAX random number generation.** JAX requires explicit key management via `jax.random.PRNGKey()` or `jax.random.key()`, with keys passed explicitly through every random call. If `jax` is imported and no key generation calls are found, JAX's stochastic operations are uncontrolled. Additionally, JAX uses XLA as its compilation backend — XLA produces different results across hardware backends (CPU, GPU, TPU); on TPUs, XLA may default to bfloat16 for float32 computations.
- **Python version-specific syntax:** `match` (3.10+), walrus `:=` (3.8+), type parameter syntax `type X = ...` (3.12+), generic functions with type parameters (3.12+), positional-only `/` (3.8+).
- **Shebang line version pins:** Flag if shebang version differs from README-documented version.
- **setuptools_scm / versioneer / git describe:** If version is determined from git history, ZIP download will fail. See Failure Mode BL.
- **Dynamic imports:** `importlib.import_module(var)`, `__import__(name)` prevent static dependency extraction. See AZ.

**R:**
- `renv.lock` — current best practice; GitHub remotes: commits can be deleted; repositories removed. Flag as SIGNIFICANT.
- `packrat.lock` — strongly deprecated.
- R version specified in README.
- **Bioconductor:** Both R version and Bioconductor release version; `renv.lock` preferred.
- **`Depends` vs `Imports` (check, not verdict):** Bare function calls from `Imports`-only packages without `library()` or `::` — a check to perform, not an automatic failure.

**MATLAB:**
- Toolboxes with exact versions; MATLAB version specified.
- `.mat` version differences: v7.3 (HDF5) vs older proprietary formats — document.
- **`parfor` and random number streams:** See Failure Mode F.
- Simulink: toolboxes, solver, S-Function compiler requirements.
- MATLAB Compiler Runtime executables: CRITICAL.

**Julia:**
- `Project.toml` + `Manifest.toml` — both required.
- **Versioned Manifest naming:** Julia 1.10+ creates `Manifest-v1.10.toml`.
- **Pluto notebooks:** Reactive, browser-based; cannot run headlessly without PlutoSliderServer. May contain hidden cells. **Since Pluto ≥ 0.15, notebooks embed their own `[deps]` environment block directly in the notebook file.** Check for this embedded block (recognisable as a `# ╔═╡ 00000000-0000-0000-0000-000000000001` cell containing TOML). If present: note as a positive indicator — the notebook is self-contained. If absent and no external `Project.toml` links to the notebook: flag as SIGNIFICANT.

**Stata:** `version` command is a positive reproducibility signal. Flag if undocumented in README.

**SAS:** Version and required modules; custom macros included.

**Shell/Bash:** Shell version for non-POSIX features; GNU vs BSD utility variants; Unix LF line endings.

**C/C++/Fortran:** Compiler, build system, all dependencies; `-march=native` and optimisation flags (see BE).

**Rust:** `Cargo.lock` required; platform-specific crates at LOW CONFIDENCE.

**Go:** `go.mod` + `go.sum`; Go version specified.

**Java:** `pom.xml` or `build.gradle` + `gradle.properties`; JDK version specified.

**JavaScript / TypeScript:** `package-lock.json` or `yarn.lock`; no mixing; `.npmrc`/`.yarnrc` flagged.

**Multi-language / glue layers:** All language dependencies fully specified (see Failure Mode AI).

**Workflow managers:** Name, exact version, installation instructions. Snakemake, Nextflow, CWL, WDL, Prefect, Apache Airflow, Dagster. Airflow/Dagster detection is heuristic — LOW CONFIDENCE.

**Containerisation:** Base images pinned to digest; all `RUN` package installations pinned (see AD). Nix/Guix/Spack/DVC/MLflow/W&B/Renku/Whole Tale/Code Ocean noted as positive indicators.

---

### Component 4: Analysis Code

Scripts named for execution order or coordinated by a master `run_all.sh` / Makefile. Comments explaining what and why. Relative paths only. No home directory paths. File names matching casing in code. No symlinks. Environment variables documented. **Random seeds set for all RNG libraries, including explicit JAX key management** (see Failure Mode F). Outputs written to a designated folder. Production configuration distinguished from test/debug. Figure output files named to match paper figure numbering.

**Warning on self-modifying code:** `exec()`, `eval()`, file writes to code files, knitr with cache/dependson chains. Flag and exclude from all reorganisation proposals.

---

### Component 5: A Licence File

MIT for code, CC-BY for data is a reasonable default.

---

## Section 3: What a Messy Repository Looks Like

Failure modes are documented from reproducibility literature and from the experience of validators. Each is assigned a letter for reference in CLEANING_REPORT.md and ASSESSMENT.md.

---

### Failure Mode A: No README, or an Inadequate One

**What it looks like:** README absent, or containing only a paper title.

**What the cleaning tool does:** Generate `README_DRAFT.md` with all standard sections. Study overview as placeholder. `README.md` placeholder at root directing to draft.

**Consequence:** No starting point for a validator.

---

### Failure Mode B: Unpinned or Missing Dependencies

**What it looks like:** No dependency file. Package names without versions. Multiple inconsistent files.

**What the cleaning tool does:** Extract package names from import statements — scanning **all code files** including imports inside functions and conditional blocks — after local module filtering, namespace package detection, and dynamic import flagging (see AZ). Generate `requirements_DRAFT.txt` with DEPENDENCY EXTRACTION NOTICE; UNKNOWN for all versions. Flag as CRITICAL.

**Consequence:** Version mismatches silently break code or change results.

---

### Failure Mode C: Broken or Absolute Paths

**What it looks like:** `pd.read_csv("C:/Users/JohnSmith/Desktop/data.csv")`.

**What the cleaning tool does:** Scan for absolute path patterns. Generate unified diff AND corrected-copy file in `/proposed_corrections/`. Never auto-apply.

**Consequence:** Code fails before any analysis runs.

---

### Failure Mode D: No Execution Order or Entry Point

**What it looks like:** Multiple scripts with ambiguous names, no documentation.

**What the cleaning tool does:** Generate `run_all_DRAFT.sh` at HIGH CONFIDENCE only (consistently numbered scripts, no parallel branches). Otherwise generate `QUICKSTART_DRAFT.md` with ⚠️ banner — including when execution order is derived from README only (LOW CONFIDENCE).

**Consequence:** Validator cannot determine where to start.

---

### Failure Mode E: Missing or Inaccessible Data

**What it looks like:** No data, no download instructions, broken links, missing checksums.

**What the cleaning tool does:** If no data and no instructions, flag as CRITICAL. Generate data access placeholder with checksum fields.

**Consequence:** Reproduction impossible from the start.

---

### Failure Mode F: Undocumented Stochasticity

**What it looks like:** Analysis using randomness with no documentation of how variation is handled.

**Multi-library seed inconsistency:** `np.random.seed()` set but `torch`, `sklearn`, `tensorflow`, `lightgbm` each maintain independent states. Flag incomplete coverage as SIGNIFICANT.

**JAX PRNG:** `np.random.seed()` does nothing for JAX. JAX uses explicit functional PRNG — every stochastic operation requires a `jax.random.PRNGKey()` or `jax.random.key()` call, with keys passed explicitly through the call stack. Detect `jax` imports; scan for `jax.random.PRNGKey` or `jax.random.key()` calls. If `jax` is imported and no key generation calls are found, flag as SIGNIFICANT: *"JAX is imported but no JAX PRNG key generation (`jax.random.PRNGKey` or `jax.random.key`) was detected. `np.random.seed()` does not control JAX's random number generation. JAX stochastic operations in this code may be uncontrolled."*

**MATLAB `parfor` and random number streams:** Detect `parfor` with RNG functions inside the loop and no `RandStream` management. Flag as SIGNIFICANT.

**Locale/timezone-dependent seed behaviour:** Code combining timestamps with seed initialisation. Flag as a note.

**What the cleaning tool does:** Detect all RNG library imports; check for seed calls for each; flag incomplete coverage. Detect JAX without key management. Detect `parfor` + RNG without stream management. Never insert seeds.

**Consequence:** Validator cannot distinguish genuine failure from expected variation.

---

### Failure Mode G: Data–Code Version Mismatch, Stale Derived Objects, or Missing Upstream Scripts

**What it looks like:** Precomputed derived objects with no generating script. `.mat` workspace saves loaded but not produced by any script.

**`.mat` version note:** Document MATLAB version used to save `.mat` files and whether v7.3 (HDF5) format was used.

**What the cleaning tool does:** For each derived object, check whether any script produces it. If none found, flag as CRITICAL.

**Consequence:** Pipeline incomplete — cannot be run from raw data.

---

### Failure Mode H: Chaotic File Structure

**What it looks like:** All files in root. Ambiguously named folders. Multiple file versions.

**What the cleaning tool does:** Propose reorganisation per Reorganisation Protocol and Monorepo Shared Library Warning.

**Consequence:** Validators cannot identify relevant files.

---

### Failure Mode I: Undocumented Preprocessing

**What it looks like:** Analysis begins with already-cleaned data. No code produces it from raw.

**What the cleaning tool does:** Flag as SIGNIFICANT. Generate preprocessing placeholder.

**Consequence:** Pipeline incomplete.

---

### Failure Mode J: External Services, APIs, and Credentials

**What it looks like:** API calls or database queries. Credentials not documented.

**What the cleaning tool does:** Detect API call patterns. Generate `.env.example`. Log external dependencies.

**Consequence:** Reproduction may be impossible without credentials.

---

### Failure Mode K: Notebook, Live Script, and Caching State Dependency

**What it looks like:** Jupyter notebooks with non-sequential execution counts. MATLAB `.mlx` live scripts. Quarto `.qmd`. R Markdown with knitr caching. Stata do-files assuming interactive state.

**Jupyter kernel widget state:** `ipywidgets`/`ipympl`/`plotly` imports + widget output cells → SIGNIFICANT.

**General caching artifacts:** `joblib.Memory`, `torch.compile()` caches, DVC cache, Streamlit caching without clear-cache instructions → SIGNIFICANT.

**Julia Pluto notebooks:** Reactive, browser-based. May contain **hidden cells** — collapsed in the UI but executing as part of the notebook. Hidden cells may set seeds, configure environments, or load data invisibly. Additionally, check for the embedded `[deps]` environment block (Pluto ≥ 0.15 feature, identifiable by a `# ╔═╡ 00000000-0000-0000-0000-000000000001` cell containing TOML) — if present, note as positive indicator; if absent, flag as SIGNIFICANT.

**Consequence:** Validator cannot reliably reproduce state-dependent analyses.

---

### Failure Mode L: Build and Compilation Requirements

**What it looks like:** C/C++/Fortran compilation, CUDA toolchain unspecified. Build files present.

**What the cleaning tool does:** Detect build files and CUDA imports. Flag as SIGNIFICANT.

**Consequence:** Validators without the required build environment cannot reproduce the work.

---

### Failure Mode M: Encoding, Locale, and Line Ending Issues

**What it looks like:** Non-UTF-8 encoding undeclared. Shell scripts with Windows CRLF line endings.

**What the cleaning tool does:** Detect CRLF in shell scripts → SIGNIFICANT. Detect datetime/timezone patterns without explicit handling → note.

**Consequence:** Silent errors or cryptic failures.

---

### Failure Mode N: Licensing Conflicts and Redistribution Restrictions

**What it looks like:** No licence file. Code licensed but not data.

**What the cleaning tool does:** Generate `LICENCE_DRAFT.txt` if absent. Flag data files without licence statement.

**Consequence:** Validators have no legal clarity.

---

### Failure Mode O: Intermediate Artifacts and Large Computational Outputs

**What it looks like:** Pipelines assuming precomputed outputs not in the repository.

**What the cleaning tool does:** Detect references to large binary formats not present. Flag as SIGNIFICANT.

**Consequence:** Reproduction requires resources the validator does not have.

---

### Failure Mode P: Multiple Experiments With No Clear Paper Mapping

**What it looks like:** Many experimental runs with no documentation.

**What the cleaning tool does:** Detect multiple results directories. Generate paper-mapping template.

**Consequence:** Validator cannot determine which configuration to reproduce.

---

### Failure Mode Q: Security Risks in Repository Code

**What it looks like:** `rm -rf`, code downloading and executing external scripts, hardcoded credentials.

**What the cleaning tool does:** Flag as CRITICAL in Step 1. Never execute submitted code.

**Consequence:** Validators risk data loss or security compromise.

---

### Failure Mode R: Hardcoded Parameters and Magic Numbers

**What it looks like:** `threshold = 0.73` with no comment.

**What the cleaning tool does:** Flag as a note. Generate parameter documentation placeholder.

**Consequence:** Validator cannot verify the analysis matches the paper's methods.

---

### Failure Mode S: Figures Not Generated by Code, or Figures Without Paper Mapping

**What it looks like:** Published figures not produced by code. Code generates figures without paper numbering.

**What the cleaning tool does:** Inventory image files. Match against file-write operations. Flag unmatched as SIGNIFICANT. Generate figure-to-paper mapping template for researcher completion — **never infer mapping from filenames** (see Anti-Hallucination Rule).

**Consequence:** Computational and published outputs cannot be reliably matched.

---

### Failure Mode T: Hidden Manual Steps

**What it looks like:** Pipeline expects a file requiring manual export from proprietary software.

**What the cleaning tool does:** Flag missing upstream scripts with no documented source.

**Consequence:** Computational chain broken before the first line of code runs.

---

### Failure Mode U: Environment Variable and Secret Leaks

**What it looks like:** `os.getenv("API_KEY")` with no `.env.example`. Credentials hardcoded.

**What the cleaning tool does:** Detect environment variable patterns. Apply credential vs. configuration distinction. See BF for runtime shadowing. Flag credentials as CRITICAL.

**Consequence:** Code unrunnable without undocumented credentials, or credentials exposed.

---

### Failure Mode V: Case-Sensitivity, Windows Path Separators, and Filesystem Limits

**What it looks like:** Case mismatches. Backslash paths. Deep nesting approaching Windows MAX_PATH limit.

**What the cleaning tool does:** Flag case mismatches as SIGNIFICANT. Detect backslash paths → SIGNIFICANT. Flag deep/long paths as a note. Generate corrected-copy files. Never auto-apply.

**Consequence:** Code works on researcher's machine; fails on validator's.

---

### Failure Mode W: Git LFS Pointer Files and Missing Git Submodules

**What it looks like:** Git LFS pointer files. `.gitmodules` present but submodule directories empty.

**What the cleaning tool does:** Scan for LFS pointer signatures → CRITICAL. Detect `.gitmodules` → SIGNIFICANT.

**Consequence:** Repository appears complete but is missing data or dependency code.

---

### Failure Mode X: HPC and Cluster-Only Pipelines

**What it looks like:** SLURM (`#SBATCH`), PBS (`#PBS`), LSF (`#BSUB`) scripts. Cluster-specific paths.

**What the cleaning tool does:** Detect scheduler directives and cluster paths. Flag as SIGNIFICANT.

**Consequence:** Validators without HPC access cannot reproduce the work.

---

### Failure Mode Y: Stale Outputs

**What it looks like:** Output files whose timestamps appear older than the analysis code.

**What the cleaning tool does:** Compare timestamps. Flag as LOW CONFIDENCE with caveat — ZIP timestamps are unreliable. Signal, not verdict.

**Consequence:** Reproduced results may differ from published figures.

---

### Failure Mode Z: Branch / Tag Mismatch and "Zipped HEAD" Drift

**What it looks like:** No commit hash in README.

**What the cleaning tool does:** Check for commit hash or version tag. If absent, flag as SIGNIFICANT.

**Consequence:** Repository may not match the published results.

---

### Failure Mode AA: Cloud / Notebook Platform Dependence

**What it looks like:** Colab paths, Kaggle imports, Databricks paths, Azure ML, SageMaker Studio.

**What the cleaning tool does:** Detect platform-specific patterns. Flag as SIGNIFICANT.

**Consequence:** Reproduction fails off-platform.

---

### Failure Mode AB: Database / Schema Drift

**What it looks like:** SQL scripts assuming a schema version that has since changed.

**What the cleaning tool does:** Detect `.sql` and database connection patterns. Flag as SIGNIFICANT.

**Consequence:** Queries run but return different data.

---

### Failure Mode AC: Anonymised / Synthetic Data Mismatch

**What it looks like:** Shared data anonymised; paper used original; transformation undocumented.

**What the cleaning tool does:** Undetectable automatically. ASSESSMENT.md prompts researcher to document.

**Consequence:** Validators can run the pipeline but cannot reproduce published numbers.

---

### Failure Mode AD: Container Drift — Unpinned Base Images and Container-Internal Package Drift

**What it looks like:** Floating tags in Dockerfile. Unversioned package installation inside `RUN` instructions.

**What the cleaning tool does:** Detect floating tags → SIGNIFICANT. Scan `RUN` instructions → SIGNIFICANT.

**Consequence:** Container provides apparent reproducibility guarantee that it does not deliver.

---

### Failure Mode AE: Container Image Inaccessible

**What it looks like:** Dockerfile present but built image never published to a public registry.

**What the cleaning tool does:** Flag as a note.

**Consequence:** Validators must build from source, reintroducing drift risk.

---

### Failure Mode AF: Symlinks

**What it looks like:** Symlinks that break when zipped or on Windows.

**What the cleaning tool does:** Detect symlinks in archive metadata. Flag as SIGNIFICANT.

**Consequence:** Files that appear present are not actually accessible.

---

### Failure Mode AG: Non-Scriptable GUI Analysis Steps

**What it looks like:** Key analysis performed through GUIs with no scriptable equivalent.

**What the cleaning tool does:** Flag known GUI-dependent patterns. README must describe every GUI step.

**Consequence:** Even with full documentation, the analysis cannot be automated.

---

### Failure Mode AH: Test / Dev Configuration Leakage

**What it looks like:** Config files defaulting to toy datasets or debug parameters.

**What the cleaning tool does:** Inspect config files for suspicious values. Flag as SIGNIFICANT.

**Consequence:** Validators produce plausible-looking but incorrect results.

---

### Failure Mode AI: Mixed-Language Glue Layer Dependency Gap

**What it looks like:** R calling Python via `reticulate`. Only one language documented.

**What the cleaning tool does:** Detect cross-language call patterns. Flag as CRITICAL when only one language documented.

**Consequence:** Environment reconstruction fails at the language boundary.

---

### Failure Mode AJ: Time-Dependent External Resources

**What it looks like:** Web scraping of changing pages, dynamic URLs.

**What the cleaning tool does:** Detect scraping libraries and dynamic URL patterns. Flag as SIGNIFICANT.

**Consequence:** Re-running yields different data.

---

### Failure Mode AK: Nested Archives and Opaque Bundles

**What it looks like:** ZIP containing inner archives.

**What the cleaning tool does:** Detect nested archives. Flag as SIGNIFICANT.

**Consequence:** Validators may miss critical content.

---

### Failure Mode AL: Data Leakage Patterns (Supervised ML Pipelines)

**What it looks like:** Preprocessing applied before the train/test split.

**Target-aware preprocessing sub-patterns (LOW CONFIDENCE — signals, not verdicts):**
(Kapoor & Narayanan 2023, updated 2025)
- `LabelEncoder`, `StandardScaler`, `SimpleImputer` fitted on full dataset before split
- SMOTE, ADASYN applied before the split
- Feature selection using target variable before the split

Every flag must state: *"This pattern may indicate data leakage. The tool is not asserting leakage is present."*

**Consequence:** Published performance metrics may be over-optimistic.

---

### Failure Mode AM: Numerical Platform Sensitivity

**What it looks like:** Results deterministic on one machine but differing across platforms.

**Mixed-precision and hardware-specific numerics:**
- **PyTorch AMP** (`torch.cuda.amp`) — float16/bfloat16 on GPU
- **TensorFlow mixed precision** (`tf.keras.mixed_precision`)
- **JAX on TPU via XLA** — may default to bfloat16 for float32
- **GPU vs CPU floating-point paths**

**What the README must document:** Hardware; BLAS implementation; CUDA/cuDNN/framework versions; precision mode; deterministic mode; thread count; **tolerance bands for key outputs**.

**What the cleaning tool does:** Detect BLAS, CUDA, `torch.cuda.amp`, `tf.keras.mixed_precision`, JAX imports, OpenMP, multi-threaded reductions. Flag as SIGNIFICANT where configuration absent from README.

**Consequence:** Validators obtain results that differ within a range they cannot evaluate.

---

### Failure Mode AN: Deprecated / Rotting External Resource References

**What it looks like:** Static URLs that once worked and now do not.

**What the cleaning tool does:** Extract all URLs. Log in ASSESSMENT.md. Does not check liveness.

**Consequence:** Links dead or pointing to different versions.

---

### Failure Mode AO: Multi-Project Monorepo

**What it looks like:** A single ZIP containing several independent papers or code trees.

**What the cleaning tool does:** Detect multiple README files or pipeline roots. Flag as SIGNIFICANT. Apply Monorepo Shared Library Warning.

**Consequence:** The tool mis-infers pipeline structure.

---

### Failure Mode AP: Stale or Inconsistent Lock Files

**What it looks like:** Lock file not regenerated after final code version. `poetry.lock` and `requirements.txt` both present — `requirements.txt` may be stale.

**What the cleaning tool does:** Cross-reference imports against dependency files. If both `poetry.lock` and `requirements.txt` present, note: *"poetry.lock is authoritative. requirements.txt may be a stale export."*

**Consequence:** Declared environment does not match what the code requires.

---

### Failure Mode AQ: Implicit Runtime Dependencies and Network Access

**What it looks like:** Code that silently reaches out to the network at runtime.

**Model weight downloads:** `AutoModel.from_pretrained("...")` without `local_files_only=True`, `nltk.download()`, `spacy.load()`, `torch.hub.load()`.

**Implicit network access beyond model weights:** `pandas.read_html(url)`, R `download.file()` inside helper functions, MATLAB `webread()`, scraping embedded in utility functions.

**What the cleaning tool does:** Detect all known runtime network access patterns. Flag as SIGNIFICANT. For `from_pretrained` without `local_files_only=True`: note pin instructions. Generate ASSESSMENT.md entry for each detected implicit network call.

**Consequence:** Hidden dependency on network availability and resource version.

---

### Failure Mode AR: Undocumented Workflow Manager Requirements

**What it looks like:** Snakefile, `*.nf`, `*.cwl`, `*.wdl`, Airflow/Dagster/Prefect files without documentation.

**What the cleaning tool does:** Detect workflow manager files (Airflow/Dagster at LOW CONFIDENCE heuristic). Flag as SIGNIFICANT.

**Consequence:** Validators cannot execute the pipeline.

---

### Failure Mode AS: Proprietary Binary Format System-Level Dependencies

**What it looks like:** Instrument format wrapper libraries — pip install succeeds but runtime fails due to missing vendor SDK.

**What the cleaning tool does:** Detect known wrapper library imports. Flag as SIGNIFICANT.

**Consequence:** Validator installs all dependencies; code still fails.

---

### Failure Mode AT: Implicit Hardware Dependencies (Beyond GPUs)

**What it looks like:** `-march=native` causing `SIGILL`. ARM64 vs x86_64 incompatibility.

**What the cleaning tool does:** Scan for `-march=native`. Detect architecture-specific packages. Flag at LOW CONFIDENCE.

**Consequence:** Code works on researcher's machine; fails on validator's.

---

### Failure Mode AU: Undocumented Critical Environment Variables

**What it looks like:** Environment variables with no code-level default affecting computation.

**What the cleaning tool does:** Distinguish variables with defaults (SIGNIFICANT), infrastructure-only (SIGNIFICANT), no-default computation (CRITICAL).

**Consequence:** Validators set plausible values and cannot reproduce results.

---

### Failure Mode AV: Visualisation Library Drift

**What it looks like:** Results numerically correct but figures differ due to minor version updates.

**What the cleaning tool does:** Detect unpinned visualisation libraries. Flag as SIGNIFICANT.

**Consequence:** Correct results; figures look different; validators cannot assess success.

---

### Failure Mode AW: Data Versioning Without Version Capture

**What it looks like:** Research using versioned external source (Ensembl, UniProt, NCBI) without recording which version.

**What the cleaning tool does:** Detect references to known versioned databases. Flag as SIGNIFICANT.

**Consequence:** Validator using a different version obtains different results.

---

### Failure Mode AX: Silent Code-Data Schema Mismatch

**What it looks like:** Column name mismatches or missing join keys producing silent failures.

**What the cleaning tool does:** Extract column name expectations from code. Compare against data file headers. Detect renaming → demote to LOW CONFIDENCE. Confirmed mismatches → SIGNIFICANT.

**Consequence:** Code runs, producing silently incorrect results.

---

### Failure Mode AY: Home Directory Configuration Leaks

**What it looks like:** `os.path.expanduser("~/.research_config")`, `Path.home()`, `$HOME`, hardcoded `/Users/username/`.

**What the cleaning tool does:** Scan for home directory path patterns. Flag as SIGNIFICANT. Not included in path correction proposals.

**Consequence:** Code fails immediately at runtime for any validator.

---

### Failure Mode AZ: Import Inconsistency — Local Modules, Namespace Packages, Dynamic Imports, and Unresolvable Imports

**What it looks like:**
1. **Local module misidentified:** `import utils` where `utils.py` exists in the repository
2. **Defunct or internal library**
3. **Namespace packages:** `google.cloud`, `azure.storage` — do not uniquely identify installable package
4. **Dynamic imports:** `importlib.import_module(var)`, `__import__(name)`, R `get(paste0(...))`, Julia `@eval using $(Symbol(pkg))` — DEPENDENCY EXTRACTION NOTICE must state: *"Dynamic import patterns detected in [file:line]. The dependency skeleton may be significantly incomplete."*

**Consequence:** Dependency skeleton contains unresolvable entries or is silently incomplete.

---

### Failure Mode BA: Framework-Specific Floating-Point Divergence (Apple Accelerate)

**What it looks like:** Apple's Accelerate framework (default BLAS on Apple Silicon via conda-forge from 2025) produces results diverging from Intel MKL or OpenBLAS.

**What the cleaning tool does:** Detect numpy/scipy/pytorch + Apple Silicon indicators. Flag as SIGNIFICANT.

**Consequence:** Results differ between Apple Silicon and Intel hardware.

---

### Failure Mode BB: Silent Library Fallbacks Producing Degraded Results

**What it looks like:** `matplotlib` → Agg; TensorFlow → CPU; GDAL without drivers; R's `sf` without GEOS/PROJ.

**What the cleaning tool does:** Detect imports of libraries with known silent fallbacks. Flag as SIGNIFICANT where README does not document required system dependencies.

**Consequence:** Pipeline runs; output looks valid but is incorrect or degraded.

---

### Failure Mode BC: Implicit Parallel Execution Without Documentation

**What it looks like:** NumPy/SciPy with multithreaded BLAS; `data.table` in R; Stan/RStan; joblib without explicit `n_jobs`; distributed training: `torch.distributed`, Horovod, DeepSpeed.

**What the cleaning tool does:** Detect parallel-by-default libraries and distributed training patterns. Flag as SIGNIFICANT where README does not document execution environment including node and core count.

**Consequence:** Results vary across machines; OOM failures; unexplained numerical differences.

---

### Failure Mode BD: Non-Determinism from Unordered Data Structures (Python)

**What it looks like:** Code relying on iteration order of sets, dicts. Also: `pandas.groupby()` order varying across versions or with ties; `json.dumps()` with unordered keys in order-sensitive contexts.

**What the cleaning tool does:** At LOW CONFIDENCE, detect sets/dicts/groupby in order-sensitive contexts. Flag at LOW CONFIDENCE with caveat.

**Consequence:** Non-deterministic results not explained by any RNG seed.

---

### Failure Mode BE: Compiler Optimisation Flag Divergence

**What it looks like:** `-Ofast`, `-ffast-math`, `-funsafe-math-optimizations` in build configuration. Violate IEEE 754, change numerical results.

**What the cleaning tool does:** Scan `Makefile`, `CMakeLists.txt`, `meson.build`. Flag as SIGNIFICANT.

**Consequence:** Numerical results differ between researcher's and validator's compiled binary.

---

### Failure Mode BF: Runtime Environment Variable Shadowing

**What it looks like:** `os.environ["VAR"] = "value"` at runtime overrides externally-set variable. Distinct from U and AU — those are about a variable not being set. This is about a correctly-set variable being silently overridden.

**What the cleaning tool does:** Scan for `os.environ[key] = value`, `os.putenv(key, value)`, `os.environ.update({...})`. Flag as SIGNIFICANT. Cross-reference against `.env.example` — if the shadowed variable appears there, flag the conflict explicitly.

**Consequence:** Reproduction silently diverges even when the validator has correctly set all documented environment variables.

---

### Failure Mode BG: Timestamp-Dependent File Ordering

**What it looks like:** `os.listdir()` without sorting, `glob.glob()` without sorting, or `os.path.getmtime()` used to infer processing order.

**What the cleaning tool does:** Scan for these patterns without immediately adjacent sorting. Flag at LOW CONFIDENCE.

**Consequence:** Pipeline processes files in a different order on the validator's machine.

---

### Failure Mode BH: Hidden Startup Script Dependencies (.Rprofile, .pythonrc.py)

**What it looks like:** Code using library functions without declaring them in that file, relying on `.Rprofile`, `.pythonrc.py`, or IPython startup files not included in the repository. Code that works perfectly on the researcher's machine fails on a validator's clean machine with errors that look like missing packages rather than missing imports.

**What the cleaning tool does:** For each code file, scan for calls to functions from common libraries without a corresponding `library()` or `import` statement in **that specific file**. Cross-reference against the full repository call chain. If function calls cannot be traced to an import anywhere in the expected call chain, flag as SIGNIFICANT: *"This file uses functions from [library] without an explicit import statement. Confirm whether this file relies on a local startup script not included in this repository."*

**Consequence:** Code fails immediately on a validator's clean machine.

---

### Failure Mode BI: Hardcoded Excessive Thread / Worker Counts

**What it looks like:** `n_jobs=64`, `workers=32`, `num_threads=48`, `nthread=32`, `setDTthreads(64)`, `mpirun -np 128` — tuned to the researcher's high-core-count workstation.

**Distinct from BC:** BC flags undocumented parallel execution. BI flags documented but inappropriately large fixed values.

**What the cleaning tool does:**
- Hardcoded parallelism integers ≥ 16 in `n_jobs`, `n_workers`, `num_threads`, `nthread`, `workers`, `processes` and equivalents → SIGNIFICANT: *"Hardcoded thread/worker count of [N] requires a machine with at least [N] cores. Consider using `os.cpu_count()` or documenting minimum core count in README system requirements."*
- Hardcoded integers ≥ 4 and < 16 → LOW CONFIDENCE.

**Consequence:** Pipeline appears to hang or crash on validator hardware.

---

### Failure Mode BJ: Encrypted or High-Entropy Data Files

**What it looks like:** Files with encryption extensions (`.gpg`, `.enc`, `.secret`, `.age`, `.asc`) or binary content characteristic of encryption (git-crypt magic bytes, abnormally high entropy) with data-like names or extensions.

**What the cleaning tool does:**
- Files with encryption extensions → CRITICAL.
- Binary files with data extensions + git-crypt magic bytes or high entropy → SIGNIFICANT.
- In INVENTORY_DRAFT.md: mark as `[POSSIBLY ENCRYPTED — may be unusable without key]`.

**Consequence:** Repository appears to contain the required data, but files are unusable.

---

### Failure Mode BK: System Clock Dependency

**What it looks like:** Code using the system clock in ways that make exact reproduction impossible across different runs or machines:

1. **Clock-based output filenames:** `datetime.now()` or `time.time()` used to generate output filenames or log file names. The validator's output files will have different names from the researcher's, making comparison impossible. Multiple runs in the same second may produce colliding filenames.
2. **Clock-based seed initialisation:** `datetime.now().timestamp()` or `int(time.time())` used as a random seed. Results differ depending on exactly when the code runs.
3. **Timezone-sensitive datetime operations:** Code that produces different results depending on the system timezone (e.g., `datetime.now()` vs `datetime.utcnow()`, or date arithmetic that straddles daylight saving time boundaries).

**What the cleaning tool does:** Scan for `datetime.now()`, `datetime.today()`, `time.time()`, and equivalent patterns in the following contexts:
- Used as an argument to filename string formatting → SIGNIFICANT: *"Output filenames derived from the system clock will differ between runs. Use a fixed identifier or include the timestamp in README expected outputs."*
- Used in seed initialisation → SIGNIFICANT: *"Random seed derived from system clock produces different results each run. Use a fixed integer seed."*
- Used in date arithmetic without explicit timezone handling → flag as a note.

**Consequence:** Validator cannot reproduce the researcher's exact output filenames; clock-based seeds produce different results with no obvious cause.

---

### Failure Mode BL: Shallow Clone or Missing Git History Dependency

**What it looks like:** Code or packaging configuration that relies on git history to determine version numbers — a dependency that fails silently when the repository is downloaded as a ZIP archive, because ZIP downloads from Zenodo, GitHub, or similar platforms strip the `.git` directory entirely.

**Affected patterns:**
- **`setuptools_scm`** in `setup.py`, `pyproject.toml`, or `setup.cfg` — determines package version from git tags and commits. Fails with `LookupError: setuptools-scm was unable to detect version` when `.git` is absent.
- **`versioneer`** — similar git-history-based versioning tool; same failure mode.
- **`git describe` in shell scripts or Makefile** — outputs the most recent tag plus commit count; fails with `fatal: not a git repository` when `.git` is absent.
- **`subprocess.run(["git", ...])` or `os.system("git ...")` calls** for version or metadata purposes — crash immediately without `.git`.

**Why this matters specifically for research repositories:** Research code is almost always distributed as a ZIP deposit (Zenodo, Figshare, OSF, institutional repositories). The `.git` directory is either stripped by the depositing platform or never included. Code that works perfectly when cloned from GitHub will crash on the first import when downloaded from a repository deposit.

**What the cleaning tool does:** Scan `setup.py`, `pyproject.toml`, `setup.cfg` for `setuptools_scm`, `versioneer`. Scan shell scripts and Makefiles for `git describe` and `git log` calls. Scan Python files for `subprocess` calls containing `["git", ...]` or `os.system("git ...")`. Flag all instances as SIGNIFICANT: *"This code uses git history to determine version numbers or metadata. When downloaded as a ZIP archive (e.g., from Zenodo or GitHub's download button), the `.git` directory is absent and this will fail immediately. Pin the version number explicitly in `__version__ = '1.0.0'` or use `importlib.metadata.version()` with a static version in `pyproject.toml`."*

**Consequence:** Code that runs correctly when cloned from version control fails immediately when downloaded as a ZIP deposit — which is how validators will obtain it from Zenodo, Figshare, OSF, or institutional repositories.

---

## Section 4: The Cleaning Logic

### The Foundational Principle: Packaging vs. Content

ValiChord Auto-Generate cleans the **packaging** of research. It does not touch the **content**.

Two operations are explicitly prohibited:
- **Random seed insertion** — detect and flag only; never insert.
- **Dependency version inference** — extract only explicitly stated versions; all others UNKNOWN.

---

### The Non-Destructive Transformations Rule

All cleaning operations must be non-destructive and reversible. The original submitted archive is always preserved unchanged.

---

### Principle 1: Generate What Can Be Safely Inferred From Packaging

**Safe to generate:**
- `README_DRAFT.md` — confidence-labeled; study overview placeholder; `README.md` placeholder at root
- **File and folder descriptions — structural I/O plus optional comment-based semantic label:**

  The primary description is purely structural: which files are read, which are written, from code evidence at the appropriate confidence level. Example: *"Script `01_clean.py`: reads `data/raw/responses.csv`, writes `data/clean/responses_clean.csv` [HIGH CONFIDENCE — code evidence, lines 12, 47]."*

  **Variable-based paths must not be resolved across files.** If the path argument to a file read/write is a variable rather than a string literal, and the variable is not defined in the same file at the point of the call, record the variable name only: *"reads from `config['path']` — path not resolvable from this file [UNCLASSIFIED]."* The tool must never follow variable references to other files to infer a path.

  **Optional semantic label from structured file header comment (LOW CONFIDENCE, with mandatory caveat):** If the file contains a structured header comment explicitly stating purpose — `# Purpose: ...`, `# Summary: ...`, `# Description: ...`, or a module docstring beginning with an explicit purpose statement — extract that text verbatim at LOW CONFIDENCE with source type `(comment — file header)` and the mandatory appended caveat: *(Note: extracted from a code comment — may refer to a previous version of this analysis.)*

  If no header comment and no I/O evidence: *"Script `01_clean.py`: no I/O evidence found [UNCLASSIFIED]."*

- Dependency package names — scanning **all code files** including imports inside functions and conditional blocks — DEPENDENCY EXTRACTION NOTICE on all generated files
- Execution order documentation
- **`run_all_DRAFT.sh` — HIGH CONFIDENCE only** (numbered scripts, no parallel branches, no conflicts)
- **README-documented execution order → `QUICKSTART_DRAFT.md` at LOW CONFIDENCE only**
- LICENCE file (as `LICENCE_DRAFT.txt`)
- `.gitignore` (standard research template)
- `.env.example` — configuration from `os.getenv("VAR", default)` only; **never infer URLs, hostnames, usernames, or port numbers**; credentials always generic; `# INFERRED FROM CODE — VERIFY VALUE` above each variable
- **`CITATION_DRAFT.cff` — from structured evidence only:**
  - `.bib` file with DOI
  - `codemeta.json`
  - Existing `CITATION.cff`
  - `CITATION` (no extension) or `CITATION.txt` containing a BibTeX block — parse and populate matching fields at MEDIUM CONFIDENCE
  - A clearly labelled `## Citation` section in README with explicit field labels (`DOI:`, `Authors:`, `Title:` under the heading) — populate matching fields at MEDIUM CONFIDENCE
  - **CrossRef API DOI resolution (new):** If a DOI is found anywhere in the README — even in prose (e.g., "Cite this work as: https://doi.org/10.xxxx/xxxxx" or "DOI: 10.xxxx/xxxxx") — the tool may perform a read-only CrossRef API lookup (`https://api.crossref.org/works/{DOI}`) and populate `CITATION_DRAFT.cff` fields from the returned canonical record at MEDIUM CONFIDENCE. Source type: `(CrossRef API — DOI resolution)`. Note in CLEANING_REPORT.md: *"CITATION fields populated from CrossRef API lookup of DOI [DOI] — verify against actual publication."* If the API lookup fails (network unavailable, DOI not found): generate empty template, note the attempted DOI in ASSESSMENT.md.
  - All populated fields at MEDIUM CONFIDENCE; unpopulated fields as placeholders.
  - Prose sentences containing a DOI without a CrossRef lookup remain insufficient on their own — the CrossRef resolution is what elevates them.
- `CLEANING_REPORT.md`, `ASSESSMENT.md`, `INVENTORY_DRAFT.md`
- Data dictionary template — see Data Dictionary Constraint

**Never generated:**
- Dependency versions not explicitly stated
- Values, parameters, or thresholds in code
- Preprocessing steps not in the repository
- Scientific descriptions of variables, methods, or findings
- Scientific claims
- **File purpose semantic labels from filenames** — structural I/O and explicit header comments only
- **Data provenance from filename**
- **Expected numerical results** — never reproduced from any in-repository source
- **Workflow manager semantics** — structural only
- **Figure-to-paper mapping from filenames** — template for researcher completion only
- Study overview from filenames, variable names, or directory structure
- DOIs, publication years, or author details not in structured repository files or CrossRef API response

---

### The Dependency Skeleton Caveat

Every generated dependency skeleton carries:

```
# ============================================================
# DEPENDENCY EXTRACTION NOTICE — generated by ValiChord Auto-Generate
# These package names were inferred from import statements by
# static analysis of ALL code files (including imports inside
# functions and conditional blocks). This list is NOT authoritative.
# - Local module names (files in this repository) have been
#   excluded and are listed separately below.
# - Namespace packages (google.*, azure.*, aws.*) are marked
#   AMBIGUOUS — confirm the exact installable package name.
# - Dynamic import patterns detected: [YES/NO]
#   If YES, this list may be significantly incomplete — see [files].
# - It may include optional, conditional, or unused packages.
# - ALL VERSION NUMBERS ARE UNKNOWN and must be supplied by the
#   researcher before this file can be used for reproduction.
# ============================================================
```

---

### The run_all.sh Constraints

`run_all_DRAFT.sh` is generated **only** at HIGH CONFIDENCE — all three conditions simultaneously met:
1. Scripts consistently and unambiguously numbered (01_, 02_, 03_...) with no gaps
2. No parallel branches; alphabetical suffixes (`03a_`, `03b_`) explicitly disqualify
3. No conflicting orderings exist

When generated: generic invocation; no shebang; no logical additions; confidence comment on line 1.

**README-documented order:** Generates `QUICKSTART_DRAFT.md` at LOW CONFIDENCE only — not `run_all_DRAFT.sh`.

---

### QUICKSTART_DRAFT.md Requirements

First content block:

```
> ⚠️ IMPORTANT — THIS EXECUTION ORDER IS INFERRED AND HAS NOT BEEN VALIDATED
> The script order below was generated by automated analysis and may be incorrect.
> [If from README: "Derived from README documentation, not from code structure."]
> Do not rely on it without manual verification.
> Confidence level: [LOW]
```

---

### The Corrected-Copy File Safety Rule

All corrected-copy files in `/proposed_corrections/` carry:

1. **UNVALIDATED PROPOSAL header** as lines 1–7 (comment block)
2. **Language-appropriate runtime error immediately following:**
   - Python: `raise RuntimeError("This file contains unverified changes from ValiChord. Do not run directly. See CLEANING_REPORT.md.")`
   - R: `stop("Unverified changes from ValiChord. Do not run directly. See CLEANING_REPORT.md.")`
   - Julia: `error("Unverified changes from ValiChord. Do not run directly. See CLEANING_REPORT.md.")`
   - Shell: `echo "UNVALIDATED PROPOSAL: Do not execute. See CLEANING_REPORT.md." && exit 1`
   - MATLAB: `error('Unverified changes from ValiChord. Do not run directly. See CLEANING_REPORT.md.')`

---

### The Generated File Naming Convention

All generated shareable files use `_DRAFT` in the filename: `README_DRAFT.md`, `INVENTORY_DRAFT.md`, `requirements_DRAFT.txt`, `CITATION_DRAFT.cff`, `QUICKSTART_DRAFT.md`, `run_all_DRAFT.sh`, `data_dictionary_DRAFT.md`, `LICENCE_DRAFT.txt`. Internal files: `CLEANING_REPORT.md`, `ASSESSMENT.md`, `dependency_sync_proposals.txt`.

---

### The Credential vs. Configuration Distinction

**Configuration variables:** Extracted only from explicit `os.getenv("VAR", default)` patterns. **Never infer URLs, hostnames, usernames, or port numbers.** Each entry: `# INFERRED FROM CODE — VERIFY VALUE`. If no default in the call: treat as credential.

---

### The Data Dictionary Constraint

**Base rule (absolute):** Description column empty for all rows.

**Exception 1:** `# variable_name: description` adjacent to variable definition. LOW CONFIDENCE; `(comment — inline)`.

**Exception 2:** Contiguous `# key: value` block where keys match column names in identified data files. LOW CONFIDENCE; `(comment — data dictionary format)`.

**All other descriptions remain empty.**

---

### Principle 2: Flag What Cannot Be Safely Inferred

Must flag, not generate: authoritative script versions; parameter correctness; preprocessing completeness; unspecified dependency versions (UNKNOWN); credentials (CRITICAL); critical no-default computation variables (CRITICAL); commit hash absence; derived objects without upstream scripts; leakage patterns (LOW CONFIDENCE with caveat); all external URLs; runtime model downloads; implicit network access; figure-to-paper correspondence; schema mismatches; home directory paths; import ambiguity; namespace packages; silent fallbacks; implicit parallelism; container-internal drift; hash randomisation; compiler flags; conda channel priority; runtime env shadowing; timestamp ordering; hidden startup scripts; excessive thread counts; encrypted files; system clock dependencies; git history dependencies.

---

### Principle 3: Confidence Labeling, Evidence Citation, and Evidence Hierarchy

| Label | Meaning |
|---|---|
| HIGH CONFIDENCE | From explicit, unambiguous code evidence |
| MEDIUM CONFIDENCE | From reasonable inference; from structured metadata; from CrossRef API DOI resolution |
| LOW CONFIDENCE | From weak evidence, comments, file header comments, type inference, README order, or demoted checks |
| UNKNOWN | Cannot be determined; researcher must supply |
| AMBIGUOUS | Requires researcher confirmation before any action |

**Evidence Hierarchy:**
1. **Code** — function calls, file I/O, explicit assignments (strongest)
2. **Structured comments** — `# Purpose:`, `# Summary:`, `# variable_name: description` — always LOW CONFIDENCE
3. **CrossRef API** — canonical public registry; MEDIUM CONFIDENCE
4. **File and directory names** — for identifying files only; no semantic labels from names alone
5. **Unstructured comments and narrative text** — weakest; always LOW CONFIDENCE

Evidence citation format: `Evidence: [filename] line [N] ([source type]): [evidence]`

Source types: `(code)`, `(comment — file header)`, `(comment — inline)`, `(comment — data dictionary format)`, `(filename)`, `(directory structure)`, `(README structured metadata)`, `(BibTeX — CITATION file)`, `(CrossRef API — DOI resolution)`

**Every non-placeholder sentence** in any generated file must be supported in CLEANING_REPORT.md by a citation.

---

### Principles 4–8 (stable from v14)

**Principle 4:** Record every action in CLEANING_REPORT.md.

**Principle 5:** The original is never modified.

**Principle 6:** Never execute submitted code. All submitted code treated as potentially malicious. CrossRef API lookup is a read-only external registry call and is not subject to this prohibition.

**Principle 7:** Cleaning must be deterministic.

**Principle 8 (Anti-Authority Principle):** All shareable files use `_DRAFT` naming. All corrected-copy files in `/proposed_corrections/` with UNVALIDATED PROPOSAL header and runtime error. All dependency skeletons carry DEPENDENCY EXTRACTION NOTICE. CLEANING_REPORT.md carries Anti-Authority header.

---

### The Anti-Hallucination Rule

**The cleaning tool must never invent scientific claims, parameter values, data descriptions, method descriptions, or any other content not directly grounded in the submitted repository or returned by a canonical public API.**

Specific prohibitions:
- **README study overview** — placeholder only
- **File purpose semantic labels from filenames** — structural I/O and explicit header comments only; header comment labels always carry mandatory caveat
- **Variable-based path resolution across files** — if a path is a variable not defined in the same file, record variable name only as UNCLASSIFIED; never follow variable references to other files to infer a path
- **Data provenance from filename**
- **Expected numerical results** — never reproduced from any in-repository source
- **Workflow manager semantics** — structural only
- **Figure-to-paper mapping from filenames** — template for researcher completion only
- Dependency versions — UNKNOWN unless explicitly stated
- **Data dictionary descriptions** — empty; two narrow comment exceptions only
- `.env.example` — no URLs, hostnames, usernames, port numbers inferred
- **CITATION_DRAFT.cff** — structured evidence + CrossRef API resolution only; prose DOIs without CrossRef lookup do not qualify on their own
- **Positive indicators** — "structures commonly associated with reproducibility practice," not guarantees
- **Leakage flags** — always include caveat

---

### The Reorganisation Protocol

When reorganisation proposed: CLEANING_REPORT.md lists every move with path-breakage warnings and affected code references. Two correction forms: unified diff and corrected-copy in `/proposed_corrections/`. Self-modifying code excluded.

---

### The Path Correction Protocol

Absolute paths → corrected-copy and unified diff. Backslash separators → SIGNIFICANT. Case mismatches → FLAGGED. Home directory paths (AY) → SIGNIFICANT only; not path-corrected.

---

### Monorepo Shared Library Warning

Before generating any reorganisation proposal, scan for directories shared by multiple independent project trees. If detected: flag as SIGNIFICANT and defer reorganisation proposals for paths including the shared directory.

---

## Section 5: The Cleaning Process — Step by Step

### Step 1: Safety Check

Scan for: deletion operations; external code execution; credentials; Git LFS pointer files; HPC scheduler directives; nested archives; symlinks; cloud platform-specific paths; self-modifying scripts; home directory paths (AY); proprietary binary only; runtime env shadowing (BF); implicit network access (AQ); timestamp-dependent ordering (BG); encrypted/high-entropy data files (BJ); hidden startup script dependencies (BH); **system clock dependency (BK)**; **git history dependency (BL)**.

**Edge cases:** Previously processed repository → warn. Empty/link-only → CRITICAL. `.git` directory → SIGNIFICANT. Git submodules → SIGNIFICANT. Pure data deposit → pivot. Notebook-only → SIGNIFICANT. Monorepo → warn; defer reorganisation.

### Step 2: Inventory

Read and list every file: name, path, type, size, structural I/O description (code evidence or UNCLASSIFIED); variable-based paths recorded as UNCLASSIFIED without cross-file resolution; optional LOW CONFIDENCE semantic label from `# Purpose:` / `# Summary:` header comment with mandatory caveat; suspected encrypted files marked `[POSSIBLY ENCRYPTED]`. No semantic labels from filenames. No figure-to-paper mapping inferences.

Output: `INVENTORY_DRAFT.md`

### Step 3: Assessment

Evaluate against all failure modes A–BL.

**Additions from v15:**
- **System clock dependency (BK):** `datetime.now()`, `time.time()` in filename generation → SIGNIFICANT; in seed initialisation → SIGNIFICANT; in date arithmetic without timezone → note
- **Git history dependency (BL):** `setuptools_scm`, `versioneer` in setup files; `git describe` or `git log` in scripts/Makefiles; `subprocess(["git", ...])` for version purposes → SIGNIFICANT
- **Pluto embedded `[deps]` block (K):** Check for `# ╔═╡ 00000000-0000-0000-0000-000000000001` TOML cell; if present → positive indicator; if absent → SIGNIFICANT
- **CrossRef DOI lookup:** Scan README for DOIs in prose; attempt CrossRef API lookup; record result in ASSESSMENT.md
- **Variable-based paths (AX, B, INVENTORY):** Record variable name as UNCLASSIFIED; do not follow cross-file references

All v14 checks apply unchanged.

**Minimal findings note:** Zero CRITICAL and zero SIGNIFICANT → *"No CRITICAL or SIGNIFICANT findings detected. This does not mean the repository is verified as reproducible. Running the complete pipeline on a clean machine remains the only reliable test."*

Output: `ASSESSMENT.md`

### Step 4: Structure Proposal

Reorganisation per Reorganisation Protocol. Monorepo Shared Library Warning first.

### Step 5: Generation

1. `README_DRAFT.md` + placeholder `README.md`
2. Dependency skeleton — all-file scan; DEPENDENCY EXTRACTION NOTICE; UNKNOWN versions
3. `dependency_sync_proposals.txt` — only after canonical file identified
4. `.env.example` — os.getenv only; no URL/hostname/port; `# INFERRED FROM CODE — VERIFY VALUE`
5. `LICENCE_DRAFT.txt`
6. `CITATION_DRAFT.cff` — BibTeX (CITATION/CITATION.txt), structured `## Citation` section, `.bib`, `codemeta.json`, and CrossRef API DOI resolution — all at MEDIUM CONFIDENCE; empty template otherwise
7. `run_all_DRAFT.sh` — HIGH CONFIDENCE only; otherwise `QUICKSTART_DRAFT.md`
8. `QUICKSTART_DRAFT.md` — ⚠️ banner; confidence level; source note
9. `data_dictionary_DRAFT.md` — empty descriptions; two narrow comment exceptions
10. `.gitignore`

### Step 6: Path, Case, and Backslash Identification

Corrected-copy files → `/proposed_corrections/` with runtime error. Home directory paths → SIGNIFICANT only. Runtime env shadowing (BF) → cross-referenced against `.env.example`. Encrypted files → noted in INVENTORY. None auto-applied.

### Step 7: Cleaning Report

Generate `CLEANING_REPORT.md` with:
- Anti-Authority Principle header
- Form A researcher warning (Section 6)
- "Results differ from paper ≠ ValiChord error" statement
- ML leakage standalone callout if ML libraries detected
- Minimal findings note if zero CRITICAL/SIGNIFICANT
- All findings A–BL with context-specific flags
- CrossRef API lookup results and any DOI resolution notes

### Step 8: Package

Return a ZIP: original files; `_DRAFT` files; placeholder files; `ASSESSMENT.md`, `CLEANING_REPORT.md`, `INVENTORY_DRAFT.md`; unified diff files; `/proposed_corrections/` subfolder.

---

## Section 6: The Mandatory Researcher Warning

The warning appears in two forms: **Form A** (before submission and at top of CLEANING_REPORT.md) and **Form B** (adjacent to each relevant finding).

---

> ### Preparing Your Repository for Independent Validation
>
> This tool has organised your repository and filled in missing documentation, preparing it for independent validation.
>
> Because the tool only reads your files and does not run your code, it cannot assess whether your analysis is correct, statistically sound, or free from error. **It only ensures your files are organised and documented.** Your expertise is the final and most important step.
>
> **All generated files have `_DRAFT` in their names.** Placeholder files at expected locations explain where each draft is. Remove `_DRAFT` — and the placeholder — only after you have verified the content.
>
> **If anything the tool has generated contradicts your knowledge of your own research, the tool is wrong.** Any conflict must be resolved in your favour.
>
> **If your cleaned repository runs end-to-end but produces results that differ from your published paper, this is not a ValiChord error.** It is a scientific discrepancy only you can resolve. ValiChord handles packaging; it cannot handle scientific content.
>
> ---
>
> #### If your work uses supervised machine learning — read this first
>
> **Data leakage** — test-set information influencing training — produces performance metrics that cannot be reproduced independently. Before sharing, verify:
> - Scaling, imputation, and encoding fitted **on training data only**
> - Oversampling (SMOTE, ADASYN) applied **after** the train/test split
> - Feature selection used **only training labels**
>
> Potential leakage patterns are flagged at LOW CONFIDENCE — signals only.
>
> ---
>
> **Before sharing, please:**
>
> - **Test on a clean machine.** The easiest way is to create a free **GitHub Codespace** and run your code there. Alternatively: fresh Docker container, secondary laptop, or new virtual machine. A new folder on your development machine is not enough.
>
>   When testing, ensure pip and conda are not pulling from a local package cache — use `pip install --no-cache-dir` and run `conda clean --all` before testing. This ensures every dependency is actually reachable from scratch.
>
>   **If your code uses SLURM, PBS, MPI, or other HPC scheduler directives, your clean machine test must simulate the same number of nodes and cores used in the original analysis** to detect hardcoded hardware dependencies (see Failure Mode BI). A single-node laptop test is insufficient for validating HPC-only pipelines.
>
>   *If the test fails, use the errors: missing package → add to dependency file; file not found → check relative paths; `NameError` or function not found → you may rely on a local startup script (`.Rprofile`, `.pythonrc.py`) not included in the repository; `setuptools-scm unable to detect version` → see Failure Mode BL; numerical mismatch → document tolerance bands.*
>
> - Rename and verify every `_DRAFT` file — a fluent-looking draft is not a verified one
> - **Complete the "Definition of Successful Reproduction" section** — include tolerance bands for platform-sensitive numerics
> - Add exact version numbers to all UNKNOWN dependencies
> - Apply corrections from `/proposed_corrections/` only after reviewing each change; files there contain runtime errors by design
> - Check any runtime environment variable shadowing flagged in this report
> - Check any file ordering relying on `os.listdir()` or `glob.glob()` without sorting
> - Check for any encrypted files flagged in this report
> - **Check for any output filenames generated from `datetime.now()` or `time.time()` — these will differ from the validator's filenames** (see Failure Mode BK)
> - **Check for any code using `setuptools_scm`, `versioneer`, or `git describe` — these will fail when the repository is downloaded as a ZIP archive** (see Failure Mode BL)
> - If JAX is imported: verify that `jax.random.PRNGKey` or `jax.random.key()` calls are present — `np.random.seed()` does not control JAX stochasticity
> - Provide checksums for any large externally-hosted files
> - Confirm your licence covers all included data; legal responsibility for data sharing remains with you
> - Address all CRITICAL and SIGNIFICANT findings in this report
>
> **This tool does not check for scientific errors, data fabrication, statistical mistakes, or p-hacking.** Running your pipeline on a clean machine is the only reliable check that your repository faithfully represents your published work.

---

## Section 7: What Auto-Generate Cannot Do

**Cannot:** Run code; verify results; determine dependency versions not stated; insert random seeds; reconstruct missing preprocessing; assess methodological correctness; detect data fabrication; verify redistribution rights; generate Docker image digests; preserve git history; auto-apply corrections; analyse nested archive contents; verify URL liveness; confirm leakage; determine tolerance bands; detect race conditions; verify checksum correctness; infer scientific meaning from filenames; infer figure-to-paper mapping from filenames; generate semantic labels from filenames; resolve variable-based paths by following cross-file references; decrypt encrypted files; determine which startup scripts a researcher depends on.

**Can:** Identify all failure modes A–BL; scan all code files for imports including nested/conditional; detect hidden startup dependencies (BH); detect hardcoded excessive thread counts (BI); detect encrypted/high-entropy data files (BJ); detect system clock dependency (BK); detect git history dependency (BL); detect runtime env shadowing (BF) and cross-reference against .env.example; detect timestamp-dependent ordering (BG); detect JAX without PRNG key management (F); detect Pluto embedded `[deps]` block; attempt CrossRef API DOI lookup and populate CITATION_DRAFT.cff at MEDIUM CONFIDENCE; extract file header comment semantic labels at LOW CONFIDENCE with mandatory caveat; record variable-based paths as UNCLASSIFIED without cross-file resolution; generate minimal findings note; identify all other failure modes A–BJ.

---

## Section 8: Size Limits and Scope

**Repository size limit:** 50MB compressed. Above 50MB: process code and documentation; generate data inventory template with checksum fields.

### File types processed (read in detail)

**Code:** .py, .R, .Rmd, .qmd, .jl, .m, .mlx, .sh, .bash, .ipynb, .do, .sas, .ado, .c, .cpp, .f, .f90, .sql, .rs, .go, .java, .js, .ts

**Workflow definitions:** Snakefile, *.smk, *.nf, *.cwl, *.wdl, Airflow DAG Python files (LOW CONFIDENCE heuristic), Dagster pipeline files (LOW CONFIDENCE heuristic), Prefect flow files

**Documentation:** .md, .txt, .rst, .html (static), .tex, .docx (text extracted). **CITATION and CITATION.txt specifically scanned for BibTeX blocks. README scanned for DOIs for CrossRef API lookup.**

**Configuration:** requirements.txt, environment.yml, DESCRIPTION, renv.lock, packrat.lock, poetry.lock, Pipfile.lock, conda-lock.yml, Dockerfile, docker-compose.yml, Makefile, CMakeLists.txt, meson.build, .yaml, .toml, .json (under 1MB), .ini, .cfg, .env, .env.example, config.py, settings.py, params.yaml, setup.py, **pyproject.toml (scanned for setuptools_scm and versioneer — see BL)**, CITATION.cff, CITATION, CITATION.txt, codemeta.json, MLproject, dvc.yaml, .dvc, default.nix, guix.scm, spack.yaml, Cargo.toml, Cargo.lock, go.mod, go.sum, pom.xml, build.gradle, package.json, package-lock.json, yarn.lock, .npmrc, .yarnrc, .gitmodules

**Reproducibility platform manifests:** `.renku/`, `wholeTaleManifest.json`, Code Ocean capsule metadata

**CI / Test artefacts (read for context only):** .github/workflows/*.yml, .travis.yml, Jenkinsfile, pytest.ini

**Simulink (identified for documentation check):** .slx

### File types identified but not read in detail

**Data:** .csv, .tsv, .xlsx, .json (large), .parquet, .feather, .rds, .RData, .dta, .sav, .sas7bdat, .mat, .pkl, .npy, .npz, .hdf5, .h5, .nc, .nii, .nii.gz, .bam, .fastq, .vcf, .edf

**Possibly encrypted:** .gpg, .enc, .secret, .age, .asc → CRITICAL. Binary files with data extensions + high entropy or git-crypt magic bytes → SIGNIFICANT.

**Single-cell / spatial omics:** .h5ad (AnnData), .zarr (directory), .mtx (bundle check)

**Geospatial:** .shp (bundle check: requires .shx + .dbf), .dbf, .shx, .prj, .cpg, .geojson, .gpkg, .tif/.tiff

**Neuroimaging:** .nii, .nii.gz — BIDS structure noted as positive indicator

**Neurophysiology signal formats:** .edf, .bdf, .set and .fdt (EEGLAB sidecar pair), .vhdr and .vmrk (BrainVision sidecar pair) — sidecar completeness checks

**Audio / signal processing:** .wav, .flac, .mp3 — flag if no format documentation

**Behavioural experiment files:** .edat2, .ebs2 (E-Prime), .psyexp (PsychoPy) — completeness check: data without experiment definition → SIGNIFICANT; for PsychoPy: check for `monitors/` directory or calibration `.json` files — if absent → SIGNIFICANT

**Simulation framework files:**
- .mph (COMSOL), .wbpj/.cas (ANSYS), OpenFOAM case directories, .inp (Abaqus) → SIGNIFICANT
- .root (ROOT framework, CERN) → SIGNIFICANT
- .stp/.step/.iges (CAD/engineering) → note

**Agent-based modelling:** .nlogo (NetLogo) — flag NetLogo version AND JRE version documentation as SIGNIFICANT. Repast configuration files — same note.

**Observable notebooks:** .ojs, .omd — browser-only; cannot be reproduced headlessly

**Proprietary / opaque formats:** .czi, .lif, .nd2, .mex (compiled MATLAB), binary executables without source

**Model weights:** .pt, .pth, .ckpt, .pb, .h5 (Keras), .bin (Hugging Face), .safetensors — check upstream script; check `from_pretrained` without `local_files_only`

**Nested archives:** .zip, .tar.gz, .tar.bz2, .7z, .rar — flagged; contents not analysed

### File types ignored

System: .DS_Store, Thumbs.db, desktop.ini, __pycache__

`.git` directory: ignored in normal processing; presence in archive is Step 1 edge case (SIGNIFICANT)

Binary executables without source: .exe, .dll, .so — flagged; MATLAB Compiler Runtime check; repository with only these and no source → CRITICAL

---

## Section 9: Framing for the Research Community

**What it is:** A tool that accepts a messy research repository, generates missing packaging, and returns an improved draft for researcher verification — the first tool of its kind to attempt remediation rather than merely assessment.

**What makes it different:** Existing tools tell researchers what is wrong. Auto-Generate attempts to fix it, with confidence labels, evidence citations, `_DRAFT` naming, runtime-error-protected correction files, CrossRef API citation resolution, and DEPENDENCY EXTRACTION NOTICES — so researchers know exactly what has been inferred, what requires judgment, and what has not been validated.

**The epistemic commitment:** Reproducibility packaging is a technical problem. Scientific accuracy is a researcher responsibility. The tool handles the former; it refuses to claim the latter. If the cleaned repository runs but produces different results from the paper, that is a scientific discrepancy the tool cannot resolve.

**Relationship to ValiChord:** Auto-Generate is Stage A of ValiChord's pre-validation support. Stage B (Phase 2) adds empirically calibrated scoring from Phase 0 workload data.

---

## Appendix A: Before and After Examples

### v15 additions illustrated

**BK detection:** `results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv` in analysis script → SIGNIFICANT flag; validator's output file will have a different name.

**BL detection:** `pyproject.toml` containing `[tool.setuptools_scm]` → SIGNIFICANT flag; ZIP download from Zenodo will fail on first import.

**CrossRef resolution:** README contains "DOI: 10.1234/example" → CrossRef API lookup → `CITATION_DRAFT.cff` populated with author, title, year, journal at MEDIUM CONFIDENCE; source noted as `(CrossRef API — DOI resolution)`.

**Variable-based path:** `df = pd.read_csv(config['raw_path'])` → INVENTORY_DRAFT.md records: *"reads from `config['raw_path']` — path not resolvable from this file [UNCLASSIFIED]."* No cross-file lookup.

**File header comment:** `# Purpose: Preliminary cleanup of 2023 pilot data` → extracted at LOW CONFIDENCE with caveat *(Note: extracted from a code comment — may refer to a previous version of this analysis.)*

---

## Appendix B: Confidence, Evidence, and Action Reference

| Label | Meaning | Researcher action |
|---|---|---|
| HIGH CONFIDENCE | From explicit, unambiguous code evidence | Review; likely correct |
| MEDIUM CONFIDENCE | From reasonable inference, structured metadata, BibTeX parsing, or CrossRef API resolution | Verify before relying on |
| LOW CONFIDENCE | From weak evidence, comments, file header comments, README order, or demoted checks | Must verify; may be wrong |
| UNKNOWN | Cannot be determined | Researcher must supply |
| PROPOSED | Suggested; not applied | Accept or reject explicitly |
| FLAGGED | Attention required; no action taken | Researcher must address |
| AMBIGUOUS | Requires researcher confirmation | Researcher must confirm |
| [_DRAFT naming] | AI-generated file; not verified | Verify, then remove _DRAFT |

Evidence source types: `(code)`, `(comment — file header)`, `(comment — inline)`, `(comment — data dictionary format)`, `(filename)`, `(directory structure)`, `(README structured metadata)`, `(BibTeX — CITATION file)`, `(CrossRef API — DOI resolution)`

**Key rules (v15 additions):**
- System clock in filename generation or seed initialisation → SIGNIFICANT (BK)
- `setuptools_scm`, `versioneer`, `git describe` → SIGNIFICANT (BL)
- Pluto `[deps]` block present → positive indicator; absent → SIGNIFICANT
- CrossRef API DOI lookup → MEDIUM CONFIDENCE; failure → empty template
- Variable-based paths not resolvable across files → UNCLASSIFIED
- File header comments → LOW CONFIDENCE with mandatory caveat *(Note: may refer to a previous version)*
- HPC repositories: clean machine test must match node/core count (Form A)

---

## Appendix C: Glossary

*(Entries from v14 retained and stable. New entries below.)*

**System clock dependency (BK):** Use of `datetime.now()` or `time.time()` in output filename generation, seed initialisation, or timezone-sensitive date arithmetic, producing results that vary depending on when or where the code runs.

**Shallow clone / git history dependency (BL):** Packaging configurations (`setuptools_scm`, `versioneer`) or code (`git describe`, `subprocess(["git", ...])`) that determine version numbers from git history — failing immediately when the repository is downloaded as a ZIP archive, which strips the `.git` directory.

**CrossRef API DOI resolution:** A read-only lookup of `https://api.crossref.org/works/{DOI}` to retrieve canonical publication metadata for `CITATION_DRAFT.cff` population. Source type `(CrossRef API — DOI resolution)`. Not subject to the "never execute submitted code" prohibition — it is a read-only external registry call, not execution of submitted code.

**Pluto embedded `[deps]` block:** A TOML environment specification embedded directly in a Pluto notebook file (since Pluto ≥ 0.15), identifiable by a `# ╔═╡ 00000000-0000-0000-0000-000000000001` cell containing TOML. When present, the notebook is self-contained with respect to its Julia package environment.

**Variable-based path (UNCLASSIFIED):** A file read/write operation whose path argument is a variable not defined in the same file. The tool records the variable name and marks the I/O entry UNCLASSIFIED. The tool must not follow variable references across files to infer the path.

**File header comment semantic label (LOW CONFIDENCE, mandatory caveat):** A purpose statement extracted verbatim from a `# Purpose:`, `# Summary:`, or `# Description:` header comment in a code file. Always accompanied by the caveat: *(Note: extracted from a code comment — may refer to a previous version of this analysis.)*

*(All other glossary entries from v14 apply unchanged.)*

---

**Companion Documents:**
- *ValiChord Vision & Architecture*
- *ValiChord Phase 0 Proposal — Workload Discovery Pilot*
- *ValiChord at Home — Researcher-Facing Self-Assessment Tool*
- *ValiChord Governance Framework*

**Contact:** Ceri John — topeuph@gmail.com

**© 2026 Ceri John. All Rights Reserved.**

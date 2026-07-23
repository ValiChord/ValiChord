#!/usr/bin/env bash
# publish-coordinators.sh — Phase 3 of the coordinator auto-updater.
# Plan: docs/AUTO_UPDATER_SIDECAR_PLAN.md
#
# Publishes the packed coordinator manifest + WASMs (from pack-coordinators.mjs)
# as an IMMUTABLE GitHub release, so nodes can poll AUTOUPDATE_MANIFEST_URL.
# Release revisions are monotonic and never overwritten — to change coordinators,
# bump the revision (re-run pack-coordinators.mjs) and publish again. To revert,
# publish a new revision containing the previous-good WASMs (roll-forward).
#
# Prereq: `gh` authenticated, and `node demo/pack-coordinators.mjs` already run.
#
# Usage:
#   demo/publish-coordinators.sh [--dry-run] [--repo owner/name] [--dir <updates-dir>]
set -euo pipefail

DRY=0
REPO=""
DIR=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --repo) REPO="$2"; shift ;;
    --dir) DIR="$2"; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIR="${DIR:-$SCRIPT_DIR/coordinator-updates}"
MANIFEST="$DIR/coordinators-manifest.json"

command -v gh >/dev/null 2>&1 || { echo "ERROR: gh CLI not found" >&2; exit 1; }
[ -f "$MANIFEST" ] || { echo "ERROR: no manifest at $MANIFEST — run: node demo/pack-coordinators.mjs" >&2; exit 1; }

REV=$(node -e "process.stdout.write(String(JSON.parse(require('fs').readFileSync('$MANIFEST','utf8')).revision))")
HC=$(node -e "process.stdout.write(String(JSON.parse(require('fs').readFileSync('$MANIFEST','utf8')).holochain))")
TAG="coordinators-rev-${REV}"

if [ -z "$REPO" ]; then
  REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo 'ValiChord/ValiChord')"
fi

# Collect assets (manifest + every WASM in the dir).
shopt -s nullglob
WASMS=("$DIR"/*.wasm)
shopt -u nullglob
[ ${#WASMS[@]} -gt 0 ] || { echo "ERROR: no *.wasm in $DIR — run pack-coordinators.mjs" >&2; exit 1; }

echo "repo:     $REPO"
echo "tag:      $TAG   (revision $REV, holochain $HC)"
echo "assets:   $(basename "$MANIFEST"), ${#WASMS[@]} WASM(s)"

# Immutable: refuse to clobber an existing revision.
if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
  echo "ERROR: release $TAG already exists on $REPO." >&2
  echo "       Revisions are immutable — bump it (node demo/pack-coordinators.mjs) and retry." >&2
  exit 1
fi

MANIFEST_URL="https://github.com/${REPO}/releases/download/${TAG}/coordinators-manifest.json"
NOTES="Coordinator auto-updater bundle, revision ${REV}, built against holochain ${HC}. Consumed by demo/coordinator-autoupdate.mjs (see docs/AUTO_UPDATER_SIDECAR_PLAN.md)."

if [ "$DRY" = 1 ]; then
  echo
  echo "[dry-run] would run:"
  printf '  gh release create %q \\\n' "$TAG"
  printf '    %q \\\n' "$MANIFEST" "${WASMS[@]}"
  printf '    --repo %q --title %q \\\n' "$REPO" "Coordinator revision ${REV} (holochain ${HC})"
  printf '    --notes %q\n' "$NOTES"
  echo
  echo "[dry-run] nodes would then set:"
  echo "  AUTOUPDATE_MANIFEST_URL=$MANIFEST_URL"
  exit 0
fi

gh release create "$TAG" \
  "$MANIFEST" "${WASMS[@]}" \
  --repo "$REPO" \
  --title "Coordinator revision ${REV} (holochain ${HC})" \
  --notes "$NOTES"

echo
echo "Published. Point nodes at:"
echo "  AUTOUPDATE_MANIFEST_URL=$MANIFEST_URL"

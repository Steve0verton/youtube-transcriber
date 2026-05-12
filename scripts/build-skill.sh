#!/usr/bin/env bash
# Build the Claude skill bundle for distribution via GitHub Releases.
#
# Output: build/youtube-transcribe.skill (a zip of skill/youtube-transcribe/).
# Run from the repo root: ./scripts/build-skill.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_SRC="${REPO_ROOT}/skill/youtube-transcribe"
BUILD_DIR="${REPO_ROOT}/build"
OUTPUT="${BUILD_DIR}/youtube-transcribe.skill"

if [[ ! -d "${SKILL_SRC}" ]]; then
  echo "error: skill source not found at ${SKILL_SRC}" >&2
  exit 1
fi

mkdir -p "${BUILD_DIR}"
rm -f "${OUTPUT}"

# Zip from inside skill/ so the archive's top-level entry is youtube-transcribe/
# rather than skill/youtube-transcribe/. Excludes macOS metadata.
(cd "${REPO_ROOT}/skill" && zip -rq "${OUTPUT}" youtube-transcribe -x "*.DS_Store")

echo "built: ${OUTPUT}"
unzip -l "${OUTPUT}"

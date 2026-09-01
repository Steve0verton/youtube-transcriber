#!/usr/bin/env bash
# =============================================================================
# transcribe_local_videos.sh
# =============================================================================
# Ad-hoc utility: batch-transcribe all video files in a given directory using
# the youtube-transcriber project's local Whisper backend (mlx-whisper on Apple
# Silicon, faster-whisper on CPU/CUDA elsewhere). No internet connection needed;
# everything runs on-device.
#
# USAGE
#   bash scripts/transcribe_local_videos.sh <directory>
#
# ARGUMENTS
#   <directory>   Path to a folder containing video files. Searched one level
#                 deep (non-recursive). Supported formats: mp4, webm, mkv, mov, m4v.
#
# OUTPUT
#   A plain-text transcript is written next to each video file with the suffix
#   "_transcript.txt" appended before the file extension, e.g.:
#       my_video.mp4  -->  my_video_transcript.txt
#
#   Files that already have a corresponding transcript are skipped so the
#   script can be safely re-run after an interruption.
#
# DEPENDENCIES
#   - uv  (https://docs.astral.sh/uv/)
#   - Run from a clone of this repo; PROJECT_DIR is derived from the script's own
#     location, so no path configuration is needed.
#   - The transcription backend for this machine's auto-detected device:
#       Apple Silicon -> mlx-whisper, so `uv sync --extra mlx` is REQUIRED here.
#                        There is no CPU fallback; without it every file fails.
#       CPU / CUDA    -> faster-whisper, installed by a plain `uv sync`.
#
# NOTES
#   This script calls transcribe_audio() directly rather than the CLI, so it does
#   not take the single-instance PID lock and does not run the ffmpeg check. Do
#   not run it alongside a `youtube-transcriber transcribe` invocation.
#
# EXAMPLES
#   bash scripts/transcribe_local_videos.sh ~/Downloads/temp
#   bash scripts/transcribe_local_videos.sh /Volumes/Backup/recordings
# =============================================================================

set -euo pipefail

# --- Configuration ------------------------------------------------------------
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"   # repo root, relative to this script
# ------------------------------------------------------------------------------

# --- Argument handling --------------------------------------------------------
if [[ $# -ne 1 ]]; then
    echo "Usage: $(basename "$0") <directory>" >&2
    echo "  Transcribes all video files in <directory> to .txt transcripts." >&2
    exit 1
fi

VIDEOS_DIR="${1%/}"   # strip trailing slash for cleaner output

if [[ ! -d "$VIDEOS_DIR" ]]; then
    echo "Error: directory not found: $VIDEOS_DIR" >&2
    exit 1
fi

# Resolve to an absolute path: the loop below cds into the repo root, so a
# relative argument would stop resolving after the first iteration.
VIDEOS_DIR="$(cd "$VIDEOS_DIR" && pwd)"
# ------------------------------------------------------------------------------

echo "==> Source directory : $VIDEOS_DIR" >&2
echo "==> Project directory: $PROJECT_DIR" >&2
echo >&2

count=0
skipped=0
failed=0
index=0   # position in the batch, advances regardless of outcome

# uv resolves the project from the current directory, so run the whole loop there.
cd "$PROJECT_DIR"

while IFS= read -r -d '' video; do
    filename="$(basename "$video")"
    # Build output path: strip extension, append _transcript.txt
    transcript="${video%.*}_transcript.txt"

    if [[ -f "$transcript" ]]; then
        echo "  [skip] $filename  (transcript already exists)" >&2
        (( skipped++ )) || true
        continue
    fi

    (( index++ )) || true
    echo "==> [$index] Transcribing: $filename" >&2

    # A batch run must survive one bad file: `set -e` would otherwise abort the whole
    # directory on the first failure, which defeats the point of batching.
    if uv run python - "$video" "$transcript" <<'PYEOF'
import sys
from pathlib import Path
from youtube_transcriber.transcriber import transcribe_audio
from youtube_transcriber.formatters import format_text

video_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])

result = transcribe_audio(video_path)
output_path.write_text(format_text(result), encoding="utf-8")
print(
    f"  Saved : {output_path.name}\n"
    f"  Lang  : {result.language}  |  Duration: {result.duration:.0f}s  |  "
    f"Segments: {len(result.segments)}",
    file=sys.stderr,
)
PYEOF
    then
        (( count++ )) || true
    else
        echo "  [fail] $filename — see the error above; continuing with the next file" >&2
        (( failed++ )) || true
    fi
    echo >&2

done < <(find "$VIDEOS_DIR" -maxdepth 1 \
    \( -iname "*.mp4" -o -iname "*.webm" -o -iname "*.mkv" -o -iname "*.mov" -o -iname "*.m4v" \) \
    -print0 | sort -z)

echo "==> Done. Transcribed: $count  |  Skipped: $skipped  |  Failed: $failed" >&2

# Non-zero exit when anything failed, so a caller can branch on it.
[[ $failed -eq 0 ]] || exit 1

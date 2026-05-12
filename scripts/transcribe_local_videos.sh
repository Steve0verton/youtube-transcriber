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
#   - The youtube-transcriber project at ~/dev/youtube-transcriber (or override
#     PROJECT_DIR below)
#   - mlx-whisper extra installed: uv sync --extra mlx   (Apple Silicon)
#     OR faster-whisper: uv sync                         (CPU / CUDA)
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
# ------------------------------------------------------------------------------

echo "==> Source directory : $VIDEOS_DIR" >&2
echo "==> Project directory: $PROJECT_DIR" >&2
echo >&2

count=0
skipped=0

while IFS= read -r -d '' video; do
    filename="$(basename "$video")"
    # Build output path: strip extension, append _transcript.txt
    transcript="${video%.*}_transcript.txt"

    if [[ -f "$transcript" ]]; then
        echo "  [skip] $filename  (transcript already exists)" >&2
        (( skipped++ )) || true
        continue
    fi

    echo "==> [$((count+1))] Transcribing: $filename" >&2

    cd "$PROJECT_DIR"
    uv run python - "$video" "$transcript" <<'PYEOF'
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

    (( count++ )) || true
    echo >&2

done < <(find "$VIDEOS_DIR" -maxdepth 1 \
    \( -iname "*.mp4" -o -iname "*.webm" -o -iname "*.mkv" -o -iname "*.mov" -o -iname "*.m4v" \) \
    -print0 | sort -z)

echo "==> Done. Transcribed: $count  |  Skipped: $skipped" >&2

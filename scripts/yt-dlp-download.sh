#!/usr/bin/env bash

set -euo pipefail

usage() {
  printf 'Usage: %s <output_dir> <url1> [url2 ...]\n' "$(basename "$0")" >&2
  exit 1
}

if [[ $# -lt 2 ]]; then
  usage
fi

output_dir="$1"
shift
urls=("$@")

if ! command -v yt-dlp >/dev/null 2>&1; then
  printf 'ERROR: yt-dlp is not installed or not in PATH.\n' >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  printf 'ERROR: ffmpeg is not installed or not in PATH.\n' >&2
  exit 1
fi

mkdir -p "$output_dir"

yt-dlp \
  -f "bv*[height<=2160]+ba/b[height<=2160]" \
  --merge-output-format mkv \
  --write-subs \
  --write-auto-subs \
  --embed-subs \
  --sub-langs "all,-live_chat" \
  -o "${output_dir}/%(title)s [%(id)s].%(ext)s" \
  "${urls[@]}"

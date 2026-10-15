#!/bin/sh

set -eu

log() {
  printf '%s\n' "$*"
}

if [ "$#" -eq 1 ]; then
  CONTENT_PATH="$1"
  TORRENT_NAME=""
  case "$CONTENT_PATH" in
    /data/torrents/nsfw/*)
      performer_path="${CONTENT_PATH#/data/torrents/nsfw/}"
      performer_name="${performer_path%%/*}"
      if [ -n "$performer_name" ] && [ "$performer_name" != "$CONTENT_PATH" ]; then
        SAVE_PATH="/data/torrents/nsfw/$performer_name"
      else
        log "skip: unable to derive performer from nsfw path: $CONTENT_PATH"
        exit 0
      fi
      ;;
    /data/torrents/nsfw/*/*)
      SAVE_PATH="/data/torrents/nsfw/$(printf '%s' "$CONTENT_PATH" | cut -d/ -f5)"
      ;;
    *)
      log "skip: content path outside nsfw tree: $CONTENT_PATH"
      exit 0
      ;;
  esac
else
  SAVE_PATH="${1:-}"
  CONTENT_PATH="${2:-}"
  TORRENT_NAME="${3:-}"
fi

if [ -z "$SAVE_PATH" ] || [ -z "$CONTENT_PATH" ]; then
  log "usage: hardlink-nsfw.sh <content_path> OR hardlink-nsfw.sh <save_path> <content_path> [torrent_name]"
  exit 1
fi

case "$SAVE_PATH" in
  /data/torrents/nsfw/*) ;;
  *)
    log "skip: save path outside nsfw tree: $SAVE_PATH"
    exit 0
    ;;
esac

PERFORMER_NAME="$(basename "$SAVE_PATH")"
DEST_ROOT="/data/media/nsfw/$PERFORMER_NAME"
BACKFILL_PERFORMERS_FILE="${NSFW_BACKFILL_PERFORMERS_FILE:-/scripts/nsfw-backfill-performers.txt}"

if [ "${NSFW_DISABLE_BACKFILL_ALLOWLIST:-0}" != "1" ] && [ -f "$BACKFILL_PERFORMERS_FILE" ] && ! grep -Fxq "$PERFORMER_NAME" "$BACKFILL_PERFORMERS_FILE"; then
  log "skip: performer is not in backfill allowlist: $PERFORMER_NAME"
  exit 0
fi

is_video_file() {
  case "${1##*.}" in
    mp4|mkv|avi|mov|wmv|m4v|ts|webm|flv) return 0 ;;
    MP4|MKV|AVI|MOV|WMV|M4V|TS|WEBM|FLV) return 0 ;;
    *) return 1 ;;
  esac
}

link_one() {
  src="$1"
  dest="$2"

  mkdir -p "$(dirname "$dest")"

  if [ -e "$dest" ]; then
    if [ "$(stat -c '%d:%i' "$src")" = "$(stat -c '%d:%i' "$dest")" ]; then
      return 0
    fi
    log "skip: destination exists and is different: $dest"
    return 0
  fi

  ln "$src" "$dest"
  log "linked: $dest"
}

normalize_relative_dest() {
  rel="$1"
  case "$rel" in
    data/torrents/nsfw/"$PERFORMER_NAME"/*)
      printf '%s\n' "${rel#data/torrents/nsfw/$PERFORMER_NAME/}"
      ;;
    /data/torrents/nsfw/"$PERFORMER_NAME"/*)
      printf '%s\n' "${rel#/data/torrents/nsfw/$PERFORMER_NAME/}"
      ;;
    *)
      printf '%s\n' "$rel"
      ;;
  esac
}

if [ -d "$CONTENT_PATH" ]; then
  find "$CONTENT_PATH" -type f | while IFS= read -r src; do
    if ! is_video_file "$src"; then
      continue
    fi

    # Shell parameter expansion treats brackets in torrent paths as globs.
    # realpath keeps source-relative paths literal for names such as [Onlyfans].
    rel="$(realpath --relative-to="$CONTENT_PATH" -- "$src")"
    rel="$(normalize_relative_dest "$rel")"
    dest="$DEST_ROOT/$rel"
    link_one "$src" "$dest"
  done
elif [ -f "$CONTENT_PATH" ]; then
  if ! is_video_file "$CONTENT_PATH"; then
    log "skip: not a video file: $CONTENT_PATH"
    exit 0
  fi

  if [ -n "$TORRENT_NAME" ]; then
    dest="$DEST_ROOT/$TORRENT_NAME"
  else
    dest="$DEST_ROOT/$(basename "$CONTENT_PATH")"
  fi

  link_one "$CONTENT_PATH" "$dest"
else
  log "skip: content path missing: $CONTENT_PATH"
fi

if [ -x /scripts/dedupe-nsfw-media.py ]; then
  /scripts/dedupe-nsfw-media.py "$DEST_ROOT" "$PERFORMER_NAME"
fi

if [ "${NSFW_SKIP_STASH_SYNC:-0}" = "1" ]; then
  log "skip: stash sync disabled by NSFW_SKIP_STASH_SYNC"
elif [ -x /scripts/stash-nsfw-sync.py ]; then
  /scripts/stash-nsfw-sync.py "$PERFORMER_NAME" "/data/$PERFORMER_NAME" || log "warn: stash sync failed for $PERFORMER_NAME"
fi

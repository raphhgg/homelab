#!/usr/bin/env python3
"""
Smoked-Salmon Upload Helper with Auto-Deezer Selection

This script wraps salmon upload and automatically selects the first Deezer
result from metadata search, reducing manual interaction.

Usage: salmon-upload-auto [album-directory]
"""

import os
import re
import sys
import time
import pexpect

# Configuration
DEEMIX_HOST_PATH = "/volume2/downloads/music/tmp"
CONTAINER_PATH = "/app/music/tmp"
CONTAINER_NAME = "smoked-salmon"
SOURCE = "WEB"
COOLDOWN_SECONDS = 30

# Colors
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
CYAN = '\033[0;36m'
NC = '\033[0m'


def host_to_container_path(host_path: str) -> str:
    """Convert host path to container path."""
    if host_path.startswith(DEEMIX_HOST_PATH):
        return host_path.replace(DEEMIX_HOST_PATH, CONTAINER_PATH, 1)
    return host_path


def find_deezer_choice(output: str) -> str | None:
    """Parse salmon output to find the first Deezer result number."""
    deezer_choice = None
    in_deezer_section = False

    for line in output.split('\n'):
        if 'Results for Deezer:' in line:
            in_deezer_section = True
            continue
        if in_deezer_section and 'Results for' in line and 'Deezer' not in line:
            in_deezer_section = False
        if in_deezer_section:
            match = re.match(r'>\s*(\d+)\s+', line)
            if match and deezer_choice is None:
                deezer_choice = match.group(1)
    return deezer_choice


def get_creation_time(path: str) -> float:
    """Get creation time of a path. Falls back to mtime if birth time unavailable."""
    try:
        stat_info = os.stat(path)
        # Try birth time first (available on some systems)
        if hasattr(stat_info, 'st_birthtime'):
            return stat_info.st_birthtime
        # On Linux, try using stat command for birth time
        import subprocess
        result = subprocess.run(
            ['stat', '-c', '%W', path],
            capture_output=True, text=True
        )
        birth_time = result.stdout.strip()
        if birth_time and birth_time != '0':
            return float(birth_time)
    except:
        pass
    # Fall back to ctime (metadata change time on Linux)
    return os.path.getctime(path)


def get_oldest_album() -> str | None:
    """Get the oldest directory in the tmp folder (by creation time)."""
    if not os.path.isdir(DEEMIX_HOST_PATH):
        return None

    albums = []
    for name in os.listdir(DEEMIX_HOST_PATH):
        path = os.path.join(DEEMIX_HOST_PATH, name)
        if os.path.isdir(path):
            ctime = get_creation_time(path)
            albums.append((ctime, name, path))

    if not albums:
        return None

    # Sort by creation time (oldest first)
    albums.sort(key=lambda x: x[0])
    return albums[0][2]  # Return full path of oldest


def list_albums():
    """List available albums in the tmp folder."""
    print(f"{YELLOW}Available albums in tmp folder:{NC}")
    print()
    if os.path.isdir(DEEMIX_HOST_PATH):
        for album in sorted(os.listdir(DEEMIX_HOST_PATH)):
            album_path = os.path.join(DEEMIX_HOST_PATH, album)
            if os.path.isdir(album_path):
                print(f"  📁 {album}")
    else:
        print(f"{RED}Error: {DEEMIX_HOST_PATH} does not exist{NC}")
        sys.exit(1)
    print()
    print(f"{YELLOW}Usage: {os.path.basename(sys.argv[0])} \"Album Name\"   (upload specific album){NC}")
    print(f"{YELLOW}       {os.path.basename(sys.argv[0])}                    (auto-select oldest){NC}")
    print(f"{YELLOW}       {os.path.basename(sys.argv[0])} -l                 (list albums){NC}")


def resolve_path(album_dir: str) -> str:
    """Resolve the album directory to full host path."""
    if album_dir == ".":
        return os.getcwd()
    elif album_dir.startswith("/"):
        return album_dir
    elif os.getcwd().startswith(DEEMIX_HOST_PATH):
        return os.path.join(os.getcwd(), album_dir)
    else:
        return os.path.join(DEEMIX_HOST_PATH, album_dir)


class OutputFilter:
    """Filter that watches output and auto-responds to certain prompts."""

    def __init__(self, child):
        self.child = child
        self.buffer = ""
        self.deezer_selected = False
        self.new_group_accepted = False
        self.metadata_edit_accepted = False
        self.spectrals_accepted = False
        self.rename_accepted = False
        self.transcode_accepted = False

    def __call__(self, data):
        """Called for each chunk of output."""
        if isinstance(data, bytes):
            data = data.decode('utf-8', errors='replace')

        self.buffer += data

        # Auto-select new group when no existing group matches
        if "[N]ew group" in self.buffer and "[]:" in self.buffer and not self.new_group_accepted:
            self.new_group_accepted = True
            msg = f"\n{GREEN}>>> Auto-selecting new group{NC}\n"
            sys.stdout.write(msg)
            sys.stdout.flush()
            self.child.sendline("N")
            self.buffer = ""

        # Auto-select Deezer metadata
        if "Which metadata results would you like to use?" in self.buffer and not self.deezer_selected:
            deezer_choice = find_deezer_choice(self.buffer)
            if deezer_choice:
                self.deezer_selected = True
                msg = f"\n{GREEN}>>> Auto-selecting Deezer result #{deezer_choice}{NC}\n"
                sys.stdout.write(msg)
                sys.stdout.flush()
                self.child.sendline(f"*{deezer_choice}")
                self.buffer = ""
            else:
                msg = f"\n{YELLOW}>>> No Deezer result found, manual input required{NC}\n"
                sys.stdout.write(msg)
                sys.stdout.flush()
                self.buffer = ""

        # Auto-skip metadata editing
        if "Are there any metadata fields you would like to edit?" in self.buffer and not self.metadata_edit_accepted:
            self.metadata_edit_accepted = True
            msg = f"\n{GREEN}>>> Auto-skipping metadata edit (nothing){NC}\n"
            sys.stdout.write(msg)
            sys.stdout.flush()
            self.child.sendline("n")
            self.buffer = ""

        # Auto-accept spectrals viewing prompt
        if "Press enter once you are finished viewing" in self.buffer and not self.spectrals_accepted:
            self.spectrals_accepted = True
            msg = f"\n{GREEN}>>> Auto-continuing past spectrals{NC}\n"
            sys.stdout.write(msg)
            sys.stdout.flush()
            self.child.sendline("")
            self.buffer = ""

        # Auto-accept folder rename prompt
        if "Would you like to replace the original folder name?" in self.buffer and not self.rename_accepted:
            self.rename_accepted = True
            msg = f"\n{GREEN}>>> Auto-accepting folder rename{NC}\n"
            sys.stdout.write(msg)
            sys.stdout.flush()
            self.child.sendline("Y")
            self.buffer = ""

        # Auto-accept transcode/downconversion format selection (all formats)
        if 'Select formats to convert' in self.buffer and '[*]:' in self.buffer and not self.transcode_accepted:
            self.transcode_accepted = True
            msg = f"\n{GREEN}>>> Auto-selecting all transcode formats (*){NC}\n"
            sys.stdout.write(msg)
            sys.stdout.flush()
            self.child.sendline("*")
            self.buffer = ""

        # Always return the data to display it
        return data.encode('utf-8') if isinstance(data, str) else data


def run_upload(container_path: str):
    """Run salmon upload with auto-Deezer selection."""
    cmd = f'docker exec -it {CONTAINER_NAME} .venv/bin/salmon up "{container_path}" -s {SOURCE} -n'

    print(f"{CYAN}Running: {cmd}{NC}")
    print()

    # Spawn the process
    child = pexpect.spawn(cmd, encoding='utf-8', timeout=600)

    # Get terminal size and set it
    try:
        rows, cols = os.popen('stty size', 'r').read().split()
        child.setwinsize(int(rows), int(cols))
    except:
        child.setwinsize(40, 120)

    # Create output filter
    output_filter = OutputFilter(child)

    try:
        # Run interactively with output filter
        child.interact(output_filter=output_filter)
    except KeyboardInterrupt:
        print(f"\n{RED}Interrupted{NC}")
        child.close()
        sys.exit(130)

    child.close()
    return child.exitstatus or 0


def upload_album(host_path: str, album_num: int = 0, total: int = 0) -> int:
    """Upload a single album. Returns exit code."""
    container_path = host_to_container_path(host_path)
    album_name = os.path.basename(host_path)

    counter = f" [{album_num}/{total}]" if album_num else ""

    # Display info
    print(f"{GREEN}╔════════════════════════════════════════════════════════════════╗{NC}")
    print(f"{GREEN}║{NC}  🎵 Smoked-Salmon Upload (Auto-Deezer){counter:>24}{GREEN}║{NC}")
    print(f"{GREEN}╚════════════════════════════════════════════════════════════════╝{NC}")
    print()
    print(f"{YELLOW}Album:{NC}          {album_name}")
    print(f"{YELLOW}Container path:{NC} {container_path}")
    print(f"{YELLOW}Source:{NC}         {SOURCE}")
    print(f"{YELLOW}Auto-accept:{NC}    Deezer metadata, spectrals, folder rename, transcode (*)")
    print()

    exit_code = run_upload(container_path)

    print()
    if exit_code == 0:
        print(f"{GREEN}✓ Upload complete: {album_name}{NC}")
    else:
        print(f"{RED}✗ Upload failed (exit code: {exit_code}): {album_name}{NC}")

    return exit_code


def count_remaining_albums() -> int:
    """Count directories remaining in tmp folder."""
    if not os.path.isdir(DEEMIX_HOST_PATH):
        return 0
    return sum(1 for name in os.listdir(DEEMIX_HOST_PATH)
               if os.path.isdir(os.path.join(DEEMIX_HOST_PATH, name)))


def main():
    if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help"):
        print(f"Usage: {os.path.basename(sys.argv[0])} [album-directory]")
        print()
        print("Wraps salmon upload with automatic Deezer metadata selection.")
        print("If no album specified, loops through all albums in tmp (oldest first).")
        print("Files are auto-renamed (-n flag) and transcoded to all formats.")
        print()
        print("Options:")
        print("  -l            List available albums")
        print("  -h, --help    Show this help")
        sys.exit(0)

    if len(sys.argv) >= 2 and sys.argv[1] == "-l":
        list_albums()
        sys.exit(0)

    # Single album mode - specific path provided
    if len(sys.argv) >= 2:
        album_dir = sys.argv[1]
        host_path = resolve_path(album_dir)

        if not os.path.isdir(host_path):
            print(f"{RED}Error: Directory not found: {host_path}{NC}")
            sys.exit(1)
        if not host_path.startswith(DEEMIX_HOST_PATH):
            print(f"{RED}Error: Directory must be within {DEEMIX_HOST_PATH}{NC}")
            sys.exit(1)

        exit_code = upload_album(host_path)
        sys.exit(exit_code)

    # Loop mode - no argument, process all albums oldest first
    total = count_remaining_albums()
    if total == 0:
        print(f"{YELLOW}No albums found in {DEEMIX_HOST_PATH}{NC}")
        sys.exit(0)

    print(f"{GREEN}╔════════════════════════════════════════════════════════════════╗{NC}")
    print(f"{GREEN}║{NC}  🎵 Batch Upload Mode - {total} album(s) queued                     {GREEN}║{NC}")
    print(f"{GREEN}╚════════════════════════════════════════════════════════════════╝{NC}")
    print()

    uploaded = 0
    failed = 0

    try:
        while True:
            host_path = get_oldest_album()
            if not host_path:
                break

            remaining = count_remaining_albums()
            uploaded += 1
            album_name = os.path.basename(host_path)

            print(f"\n{CYAN}{'='*64}{NC}")
            print(f"{CYAN}  Next up: {album_name} ({remaining} remaining){NC}")
            print(f"{CYAN}{'='*64}{NC}\n")

            exit_code = upload_album(host_path, album_num=uploaded, total=total)

            if exit_code != 0:
                failed += 1
                print(f"{RED}Stopping batch due to upload failure.{NC}")
                break

            # Check if there are more albums
            if not get_oldest_album():
                break

            # Cooldown between uploads
            print(f"\n{YELLOW}>>> Waiting {COOLDOWN_SECONDS}s before next upload (Ctrl+C to stop)...{NC}")
            time.sleep(COOLDOWN_SECONDS)

    except KeyboardInterrupt:
        print(f"\n{YELLOW}Batch interrupted by user.{NC}")

    # Summary
    print(f"\n{GREEN}{'='*64}{NC}")
    print(f"{GREEN}  Batch complete: {uploaded - failed} uploaded, {failed} failed, {count_remaining_albums()} remaining{NC}")
    print(f"{GREEN}{'='*64}{NC}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

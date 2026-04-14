#!/usr/bin/env python3
"""
FTP Cleanup — El Camino Site
=============================
Removes legacy files/folders from the FTP server that are no longer needed
after the root deployment of the new Astro site.

SAFETY: This script has an explicit ALLOWLIST of what to delete. Any file
or folder NOT in the allowlist is NEVER touched.

What it deletes:
  - Old .htm pages (index.htm, la-compagnie-*.htm, la-face-cachee-*.htm,
    dates-concerts-*.htm, mentions-legales.htm)
  - /css/ folder (old w3css.css)
  - /img/ folder (old W3.CSS demo photos, legacy already saved to
    assets/ftp-legacy/)
  - /preview/ folder (superseded by root deploy)

What it PRESERVES (explicit safeguards, will refuse to delete):
  - logo-signature-fusiblesetdentelles.png
  - .well-known/ (Let's Encrypt)
  - .htaccess
  - .ftpquota
  - cgi-bin/
  - dossier-FetD2022.pdf (legacy reference)
  - Everything the new Astro build deployed (index.html, _astro/, etc.)

Usage:
    cd repos/el-camino-site
    python3 scripts/ftp-cleanup.py [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import ssl
import sys
from ftplib import FTP, FTP_TLS, error_perm
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env.deploy"

# Files at root that must NEVER be deleted
PROTECTED_FILES = {
    "logo-signature-fusiblesetdentelles.png",
    ".htaccess",
    ".ftpquota",
    "dossier-FetD2022.pdf",
    "index.html",
    ".ftp-deploy-sync-state.json",
}
PROTECTED_DIRS = {
    ".well-known",
    "cgi-bin",
    "_astro",
    "calendrier",
    "compagnie",
    "contact",
    "documents",
    "images",
    "logo",
    "print",
    "spectacle",
}

# Explicit deletion targets
LEGACY_FILES_AT_ROOT = [
    "index.htm",
    "la-compagnie-fusibles-et-dentelles.htm",
    "la-face-cachee-de-la-lune-de-miel.htm",
    "dates-concerts-fusibles-et-dentelles.htm",
    "mentions-legales.htm",
]
LEGACY_DIRS_AT_ROOT = [
    "css",
    "img",
    "preview",  # superseded by root deploy
]


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        m = re.match(r'^"([^"]*)"|^\'([^\']*)\'', value)
        if m:
            value = m.group(1) if m.group(1) is not None else m.group(2)
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0]
        env[key] = value
    return env


def connect(env: dict[str, str]) -> FTP:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ftp = FTP_TLS(context=ctx)
    ftp.connect(env["FTP_HOST"], int(env.get("FTP_PORT", "21")), timeout=30)
    ftp.login(env["FTP_USER"], env["FTP_PASS"])
    ftp.prot_p()
    ftp.set_pasv(True)
    return ftp


def list_dir(ftp: FTP, path: str) -> list[tuple[str, str]]:
    """Return list of (name, type) — type is 'file' or 'dir'."""
    entries: list[tuple[str, str]] = []
    try:
        for name, facts in ftp.mlsd(path):
            if name in (".", ".."):
                continue
            kind = "dir" if facts.get("type") in ("dir", "cdir", "pdir") else "file"
            entries.append((name, kind))
    except (error_perm, AttributeError):
        lines: list[str] = []
        ftp.retrlines(f"LIST {path}", lines.append)
        for line in lines:
            parts = line.split(None, 8)
            if len(parts) < 9:
                continue
            if parts[-1] in (".", ".."):
                continue
            kind = "dir" if parts[0].startswith("d") else "file"
            entries.append((parts[-1], kind))
    return entries


def delete_tree(ftp: FTP, path: str, dry_run: bool, depth: int = 0) -> int:
    """Recursively delete a directory and everything inside it."""
    count = 0
    entries = list_dir(ftp, path)
    for name, kind in entries:
        full = f"{path.rstrip('/')}/{name}"
        if kind == "dir":
            count += delete_tree(ftp, full, dry_run, depth + 1)
            print(f"  {'  ' * depth}[{'DRY' if dry_run else 'DEL'}] 📁 {full}/")
            if not dry_run:
                try:
                    ftp.rmd(full)
                except error_perm as e:
                    print(f"  {'  ' * depth}[!] cannot rmdir {full}: {e}")
        else:
            print(f"  {'  ' * depth}[{'DRY' if dry_run else 'DEL'}] 📄 {full}")
            if not dry_run:
                try:
                    ftp.delete(full)
                    count += 1
                except error_perm as e:
                    print(f"  {'  ' * depth}[!] cannot delete {full}: {e}")
            else:
                count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="List what would be deleted without touching anything")
    args = parser.parse_args()

    env = load_env(ENV_FILE)
    ftp = connect(env)

    prefix = "[DRY RUN] " if args.dry_run else ""
    print(f"\n{prefix}Cleanup plan:")
    print(f"  Files to delete at root: {LEGACY_FILES_AT_ROOT}")
    print(f"  Dirs to delete (recursive): {LEGACY_DIRS_AT_ROOT}")
    print(f"  Protected files: {sorted(PROTECTED_FILES)}")
    print(f"  Protected dirs:  {sorted(PROTECTED_DIRS)}")
    print()

    total = 0
    try:
        ftp.cwd("/")
        root_entries = {name: kind for name, kind in list_dir(ftp, "/")}

        # Delete legacy files at root
        print("== Root files ==")
        for fname in LEGACY_FILES_AT_ROOT:
            if fname in PROTECTED_FILES:
                print(f"  [SKIP] {fname}  (protected!)")
                continue
            if fname not in root_entries:
                print(f"  [--] {fname}  (not on server)")
                continue
            if root_entries[fname] != "file":
                print(f"  [SKIP] {fname}  (not a file, it's a {root_entries[fname]})")
                continue
            print(f"  [{'DRY' if args.dry_run else 'DEL'}] 📄 /{fname}")
            if not args.dry_run:
                try:
                    ftp.delete(f"/{fname}")
                    total += 1
                except error_perm as e:
                    print(f"  [!] cannot delete {fname}: {e}")
            else:
                total += 1

        # Delete legacy dirs recursively
        print("\n== Root dirs ==")
        for dname in LEGACY_DIRS_AT_ROOT:
            if dname in PROTECTED_DIRS:
                print(f"  [SKIP] {dname}/  (protected!)")
                continue
            if dname not in root_entries:
                print(f"  [--] {dname}/  (not on server)")
                continue
            if root_entries[dname] != "dir":
                print(f"  [SKIP] {dname}/  (not a dir)")
                continue
            print(f"  Walking /{dname}/ ...")
            total += delete_tree(ftp, f"/{dname}", args.dry_run)
            print(f"  [{'DRY' if args.dry_run else 'DEL'}] 📁 /{dname}/")
            if not args.dry_run:
                try:
                    ftp.rmd(f"/{dname}")
                except error_perm as e:
                    print(f"  [!] cannot rmdir /{dname}: {e}")

        print(f"\n{prefix}Done. {total} file(s) {'would be ' if args.dry_run else ''}deleted.")

    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())

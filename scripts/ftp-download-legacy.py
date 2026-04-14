#!/usr/bin/env python3
"""
FTP Legacy Download — El Camino Site
=====================================
Downloads the legacy assets from the current FTP site into
`assets/ftp-legacy/` so we can reuse the original artist photos
in the new flyer/dossier/site.

What it grabs:
  - /img/*                                → assets/ftp-legacy/img/
  - /logo-signature-fusiblesetdentelles.png (reference)
  - /dossier-FetD2022.pdf                  (reference)

Usage:
    cd repos/el-camino-site
    python3 scripts/ftp-download-legacy.py

Reads credentials from .env.deploy. No external deps (stdlib only).
"""

from __future__ import annotations

import os
import re
import ssl
import sys
from ftplib import FTP, FTP_TLS, error_perm
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env.deploy"
DEST_DIR = REPO_ROOT / "assets" / "ftp-legacy"


def load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        sys.exit(f"[ERROR] {path} not found.")
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
    host = env["FTP_HOST"]
    user = env["FTP_USER"]
    pwd = env["FTP_PASS"]
    port = int(env.get("FTP_PORT", "21") or "21")
    protocol = env.get("FTP_PROTOCOL", "ftps").lower()

    print(f"[→] Connecting to {host}:{port} as {user} ({protocol.upper()})")
    if protocol == "ftps":
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ftp = FTP_TLS(context=ctx)
        ftp.connect(host, port, timeout=30)
        ftp.login(user, pwd)
        ftp.prot_p()
    else:
        ftp = FTP()
        ftp.connect(host, port, timeout=30)
        ftp.login(user, pwd)
    ftp.set_pasv(True)
    print("[✓] Connected.")
    return ftp


def list_files(ftp: FTP, path: str) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    try:
        for name, facts in ftp.mlsd(path):
            if name in (".", "..") or facts.get("type") != "file":
                continue
            try:
                size = int(facts.get("size", "0"))
            except ValueError:
                size = 0
            entries.append((name, size))
    except (error_perm, AttributeError):
        lines: list[str] = []
        ftp.retrlines(f"LIST {path}", lines.append)
        for line in lines:
            parts = line.split(None, 8)
            if len(parts) < 9 or parts[0].startswith("d") or parts[0].startswith("l"):
                continue
            try:
                size = int(parts[4])
            except ValueError:
                size = 0
            entries.append((parts[-1], size))
    return entries


def download_file(ftp: FTP, remote: str, local: Path, size: int) -> None:
    local.parent.mkdir(parents=True, exist_ok=True)
    if local.exists() and local.stat().st_size == size:
        print(f"  [=] {remote}  (already downloaded, {size} bytes)")
        return
    print(f"  [↓] {remote} → {local.relative_to(REPO_ROOT)}  ({size} bytes)")
    with local.open("wb") as f:
        ftp.retrbinary(f"RETR {remote}", f.write)


def main() -> int:
    env = load_env(ENV_FILE)
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    ftp = connect(env)
    try:
        # 1. /img/* → assets/ftp-legacy/img/
        print("\n[IMG] Listing /img/")
        img_files = list_files(ftp, "/img")
        print(f"       {len(img_files)} files found")
        for name, size in img_files:
            download_file(ftp, f"/img/{name}", DEST_DIR / "img" / name, size)

        # 2. Signature reference
        print("\n[ROOT] Signature reference")
        download_file(
            ftp,
            "/logo-signature-fusiblesetdentelles.png",
            DEST_DIR / "logo-signature-fusiblesetdentelles.png",
            15000,  # size ignored if unknown, will re-download
        )

        # 3. Old dossier PDF (for content/style reference)
        print("\n[ROOT] Legacy dossier PDF")
        try:
            download_file(
                ftp,
                "/dossier-FetD2022.pdf",
                DEST_DIR / "dossier-FetD2022.pdf",
                16 * 1024 * 1024,
            )
        except error_perm as e:
            print(f"  [!] dossier skipped: {e}")

    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()

    print(f"\n[DONE] Files saved to {DEST_DIR}")
    print("     → will be committed to git so they're available for flyer/dossier/site integration.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

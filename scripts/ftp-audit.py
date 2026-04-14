#!/usr/bin/env python3
"""
FTP/FTPS Audit Script — El Camino Site
=======================================
Reads credentials from .env.deploy, connects to the server, walks the remote
tree recursively, and writes a human-readable report to audit/ftp-tree.txt.

Usage:
    cd repos/el-camino-site
    python3 scripts/ftp-audit.py

No external dependencies — uses stdlib only (ftplib, ssl).
"""

from __future__ import annotations

import os
import re
import ssl
import sys
from datetime import datetime
from ftplib import FTP, FTP_TLS, error_perm, error_temp
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env.deploy"
OUT_DIR = REPO_ROOT / "audit"
OUT_FILE = OUT_DIR / "ftp-tree.txt"
SUMMARY_FILE = OUT_DIR / "ftp-summary.txt"

# Hard safety caps
MAX_DEPTH = 6
MAX_ENTRIES = 5000


def load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        sys.exit(f"[ERROR] {path} not found. Copy .env.deploy.example and fill it in.")
    env: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # If value is quoted, take exactly what's between the quotes
        m = re.match(r'^"([^"]*)"|^\'([^\']*)\'', value)
        if m:
            value = m.group(1) if m.group(1) is not None else m.group(2)
        else:
            # Unquoted: strip inline comment (anything after whitespace + #)
            value = re.split(r"\s+#", value, maxsplit=1)[0]
        env[key] = value
    return env


def connect(env: dict[str, str]) -> FTP:
    host = env.get("FTP_HOST", "")
    user = env.get("FTP_USER", "")
    pwd = env.get("FTP_PASS", "")
    port = int(env.get("FTP_PORT", "21") or "21")
    protocol = env.get("FTP_PROTOCOL", "ftps").lower()

    if not host or not user or not pwd:
        sys.exit("[ERROR] Missing FTP_HOST/FTP_USER/FTP_PASS in .env.deploy")

    if protocol == "sftp":
        sys.exit("[ERROR] SFTP (port 22) requires paramiko. Use ftps instead for now.")

    print(f"[→] Connecting to {host}:{port} as {user} ({protocol.upper()})")
    if protocol == "ftps":
        ctx = ssl.create_default_context()
        # Some shared hosts use self-signed certs; relax verification for audit only
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ftp = FTP_TLS(context=ctx)
        ftp.connect(host, port, timeout=30)
        ftp.login(user, pwd)
        ftp.prot_p()  # secure data channel
    else:
        ftp = FTP()
        ftp.connect(host, port, timeout=30)
        ftp.login(user, pwd)

    ftp.set_pasv(True)
    print(f"[✓] Connected. Welcome: {ftp.getwelcome()[:120]}")
    return ftp


def list_dir(ftp: FTP, path: str) -> list[tuple[str, dict[str, str]]]:
    """Return list of (name, facts) using MLSD when available, else LIST parsing."""
    entries: list[tuple[str, dict[str, str]]] = []
    try:
        for name, facts in ftp.mlsd(path):
            if name in (".", ".."):
                continue
            entries.append((name, facts))
        return entries
    except (error_perm, error_temp, AttributeError):
        pass

    # Fallback: parse LIST output (unix-style)
    lines: list[str] = []
    ftp.retrlines(f"LIST {path}", lines.append)
    for line in lines:
        parts = line.split(None, 8)
        if len(parts) < 9:
            continue
        perm, _, _, _, size, m, d, t, name = parts
        if name in (".", ".."):
            continue
        kind = "dir" if perm.startswith("d") else ("link" if perm.startswith("l") else "file")
        entries.append((name, {"type": kind, "size": size, "modify": f"{m} {d} {t}"}))
    return entries


def fmt_size(raw: str) -> str:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return raw or "-"
    for unit in ("B", "K", "M", "G"):
        if n < 1024:
            return f"{n:>5}{unit}"
        n //= 1024
    return f"{n}T"


def walk(ftp: FTP, root: str, out_lines: list[str], stats: dict[str, int], signature_hits: list[str]) -> None:
    stack: list[tuple[str, int]] = [(root, 0)]
    while stack:
        if stats["entries"] >= MAX_ENTRIES:
            out_lines.append(f"... [truncated at {MAX_ENTRIES} entries]")
            return
        path, depth = stack.pop(0)
        indent = "  " * depth
        try:
            entries = list_dir(ftp, path)
        except Exception as e:
            out_lines.append(f"{indent}[!] cannot list {path}: {e}")
            continue

        # Sort: dirs first, then files
        entries.sort(key=lambda e: (e[1].get("type") != "dir", e[0].lower()))

        for name, facts in entries:
            stats["entries"] += 1
            kind = facts.get("type", "file")
            size = fmt_size(facts.get("size", "-"))
            mtime = facts.get("modify", "-")
            full = f"{path.rstrip('/')}/{name}"

            icon = "📁" if kind == "dir" else ("🔗" if kind == "link" else "📄")
            out_lines.append(f"{indent}{icon} {name}  [{size}  {mtime}]")

            if kind == "dir":
                stats["dirs"] += 1
                if depth + 1 < MAX_DEPTH:
                    stack.append((full, depth + 1))
                else:
                    out_lines.append(f"{indent}  ... [depth cap reached]")
            else:
                stats["files"] += 1
                # Signature heuristic
                lower = name.lower()
                if "signature" in lower or "signa" in lower:
                    signature_hits.append(full)


def detect_site_candidates(tree_lines: list[str]) -> list[str]:
    """Heuristic: detect folders that look like a website root (contain index.html)."""
    # Not perfect — just flags paths where "index.html" appears
    hits: list[str] = []
    for line in tree_lines:
        if "index.html" in line or "index.htm" in line or "index.php" in line:
            hits.append(line.strip())
    return hits


def main() -> int:
    env = load_env(ENV_FILE)
    OUT_DIR.mkdir(exist_ok=True)

    ftp = connect(env)
    try:
        start = env.get("FTP_REMOTE_DIR", "/") or "/"
        try:
            ftp.cwd(start)
        except error_perm:
            print(f"[!] cwd {start} failed, falling back to /")
            start = "/"
            ftp.cwd("/")

        print(f"[→] Walking remote tree from {start} (max depth {MAX_DEPTH}, cap {MAX_ENTRIES} entries)")
        tree_lines: list[str] = [f"# FTP tree audit — {datetime.now().isoformat(timespec='seconds')}"]
        tree_lines.append(f"# Host: {env.get('FTP_HOST')}  Start: {start}")
        tree_lines.append(f"# User: {env.get('FTP_USER')}")
        tree_lines.append("")
        tree_lines.append(f"📁 {start}")
        stats = {"dirs": 0, "files": 0, "entries": 0}
        signature_hits: list[str] = []
        walk(ftp, start, tree_lines, stats, signature_hits)

        OUT_FILE.write_text("\n".join(tree_lines) + "\n", encoding="utf-8")
        print(f"[✓] Tree written to {OUT_FILE}  ({stats['dirs']} dirs, {stats['files']} files)")

        # Summary
        summary: list[str] = []
        summary.append("# FTP Audit Summary — El Camino")
        summary.append(f"# Generated: {datetime.now().isoformat(timespec='seconds')}")
        summary.append(f"# Host: {env.get('FTP_HOST')}")
        summary.append("")
        summary.append("## Stats")
        summary.append(f"- Directories: {stats['dirs']}")
        summary.append(f"- Files: {stats['files']}")
        summary.append("")

        summary.append("## Signature file candidates (heuristic: 'signature' in name)")
        if signature_hits:
            for h in signature_hits:
                summary.append(f"- ⚠️  {h}  ← PRESERVE CANDIDATE")
        else:
            summary.append("- (none found — signature may have a different name, inspect tree)")
        summary.append("")

        summary.append("## Site root candidates (heuristic: index.html present)")
        site_hits = detect_site_candidates(tree_lines)
        if site_hits:
            for h in site_hits[:20]:
                summary.append(f"- {h}")
        else:
            summary.append("- (no index.html found)")
        summary.append("")

        summary.append("## Raw tree")
        summary.append(f"See: {OUT_FILE}")
        SUMMARY_FILE.write_text("\n".join(summary) + "\n", encoding="utf-8")
        print(f"[✓] Summary written to {SUMMARY_FILE}")

    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()

    print("\n[DONE] Share the summary with Marcus, keep .env.deploy private.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

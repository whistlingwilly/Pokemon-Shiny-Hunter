"""
updater.py — Auto-update support for Shiny Hunter

Checks GitHub Releases for a newer version on startup.
If found, prompts the user, downloads the new installer,
runs it, then exits so the installer can replace the app.

Usage (called from shiny_hunter.py before the UI opens):
    from updater import check_for_updates
    check_for_updates(current_version="0.5.11")

GitHub repo must have Releases with assets named:
    ShinyHunterSetup_vX.Y.Z.exe   (Windows installer)

The release tag must be a plain version string, e.g. "0.5.12"
Set GITHUB_REPO below to your own repo.
"""

import sys
import os
import threading
import tkinter as tk
from tkinter import messagebox

# ── Config ────────────────────────────────────────────────────────
# Change this to your actual GitHub username/repo
GITHUB_REPO    = "whistlingwilly/Pokemon-Shiny-Hunter"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
CHECK_TIMEOUT  = 5   # seconds — don't block startup if GitHub is slow


def _parse_version(v: str):
    """Turn '0.5.11' into (0, 5, 11) for comparison."""
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except Exception:
        return (0,)


def _fetch_latest_release():
    """Return (version_str, download_url) or (None, None) on failure."""
    try:
        import urllib.request, json
        req = urllib.request.Request(
            GITHUB_API_URL,
            headers={"User-Agent": "ShinyHunter-Updater/1.0",
                     "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=CHECK_TIMEOUT) as resp:
            data = json.loads(resp.read())
        tag     = data.get("tag_name", "").lstrip("v")
        assets  = data.get("assets", [])
        # Look for the Windows installer asset
        for asset in assets:
            name = asset.get("name", "")
            if name.lower().endswith(".exe") and "setup" in name.lower():
                return tag, asset["browser_download_url"]
        # Fallback: any .exe asset
        for asset in assets:
            if asset.get("name", "").lower().endswith(".exe"):
                return tag, asset["browser_download_url"]
        return tag, None
    except Exception:
        return None, None


def _download_and_run(url: str, version: str):
    """Download the installer to a temp file and launch it."""
    import urllib.request, tempfile, subprocess

    # Show a simple progress window
    win = tk.Toplevel()
    win.title("Downloading update…")
    win.geometry("380x100")
    win.configure(bg="#0a0a18")
    win.resizable(False, False)

    lbl = tk.Label(win, text=f"Downloading v{version}…",
                   font=("Courier New", 10), fg="#dde0ff", bg="#0a0a18")
    lbl.pack(pady=16)
    bar_frame = tk.Frame(win, bg="#1a1a38", height=14, width=340)
    bar_frame.pack_propagate(False)
    bar_frame.pack()
    bar = tk.Frame(bar_frame, bg="#FFD700", height=14, width=0)
    bar.place(x=0, y=0, height=14)
    win.update()

    tmp = tempfile.NamedTemporaryFile(
        suffix=f"_ShinyHunterSetup_v{version}.exe", delete=False)
    tmp_path = tmp.name
    tmp.close()

    def _progress(block_num, block_size, total_size):
        if total_size > 0:
            pct = min(1.0, block_num * block_size / total_size)
            bar.config(width=int(340 * pct))
            lbl.config(text=f"Downloading v{version}…  {pct*100:.0f}%")
            win.update()

    try:
        urllib.request.urlretrieve(url, tmp_path, _progress)
        win.destroy()

        # Write a small batch script that:
        # 1. Waits 2 seconds for this process to fully exit
        # 2. Runs the installer
        # 3. Deletes itself
        # This avoids the "Failed to load Python DLL" error caused by
        # the installer trying to overwrite files while they're still
        # loaded in memory.
        import os, tempfile
        bat = tempfile.NamedTemporaryFile(
            suffix="_shiny_update.bat", delete=False, mode="w")
        bat.write(f'@echo off\n'
                  f'ping 127.0.0.1 -n 3 > nul\n'   # wait ~2 seconds
                  f'start "" "{tmp_path}"\n'
                  f'del "%~f0"\n')                   # delete this bat file
        bat.close()
        subprocess.Popen(["cmd", "/c", bat.name],
                         creationflags=subprocess.CREATE_NO_WINDOW)
        import time; time.sleep(0.5)
        sys.exit(0)
    except Exception as e:
        win.destroy()
        messagebox.showerror("Download failed",
            f"Could not download update:\n{e}\n\n"
            "You can download it manually from:\n"
            f"https://github.com/{GITHUB_REPO}/releases/latest")


def check_for_updates(current_version: str,
                      silent_if_current: bool = True):
    """
    Check GitHub for a newer release.  Call this before tk.mainloop().

    If a newer version exists, show a prompt.
    If the user agrees, download and install it (app will exit).
    If they decline, or if the check fails, carry on silently.
    """
    result = {"version": None, "url": None}

    def _worker():
        v, url = _fetch_latest_release()
        result["version"] = v
        result["url"]     = url

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=CHECK_TIMEOUT + 1)

    latest  = result["version"]
    url     = result["url"]

    if not latest:
        # Network unavailable or rate-limited — silent fail
        return

    if _parse_version(latest) <= _parse_version(current_version):
        # Already up to date
        return

    # New version available — ask the user
    msg = (f"A new version of Shiny Hunter is available!\n\n"
           f"  Current:  v{current_version}\n"
           f"  Latest:   v{latest}\n\n"
           "Download and install now?")

    if not url:
        # Release exists but no installer asset found
        messagebox.showinfo("Update available",
            msg.replace("Download and install now?", "") +
            f"\nDownload it from:\n"
            f"https://github.com/{GITHUB_REPO}/releases/latest")
        return

    if messagebox.askyesno("Update available", msg):
        _download_and_run(url, latest)

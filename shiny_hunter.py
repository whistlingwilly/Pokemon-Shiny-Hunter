#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════╗
║        ✨  SHINY HUNTER — Universal Edition v0.4.0  ✨           ║
║     Epilogue GB Operator · Playback Software                     ║
║     Record your sequence once. Hunt forever.                     ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os, sys, json, queue, threading, time, struct, random
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from dataclasses import dataclass

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext, simpledialog

# ── Optional deps ──────────────────────────────────────────────────────────
MISSING: List[str] = []

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.01
except ImportError:
    MISSING.append("pyautogui")

try:
    import mss
except ImportError:
    MISSING.append("mss")

try:
    from PIL import Image, ImageChops, ImageStat
except ImportError:
    MISSING.append("pillow")

try:
    from pynput import keyboard as pynput_keyboard
    PYNPUT_OK = True
except ImportError:
    PYNPUT_OK = False

# ── numpy-free pixel math helpers ────────────────────────────────
# We use Pillow instead of numpy to avoid the ~30MB dependency.

def _mean_abs_diff(pil_a: "Image.Image", pil_b: "Image.Image") -> float:
    """Mean absolute pixel difference between two same-size PIL images."""
    diff = ImageChops.difference(pil_a, pil_b)
    stat = ImageStat.Stat(diff)
    return sum(stat.mean) / len(stat.mean)

def _dark_pixel_pct(pil_img: "Image.Image", threshold: int = 80) -> float:
    """Fraction of pixels where all RGB channels are below threshold."""
    arr = pil_img.tobytes()
    n = len(arr) // 3
    dark = sum(1 for i in range(0, len(arr), 3)
               if arr[i] < threshold and arr[i+1] < threshold
               and arr[i+2] < threshold)
    return dark / n if n else 0.0

def _bright_diff_pct(pil_cur: "Image.Image", pil_prev: "Image.Image",
                     bright_thresh: int = 230,
                     diff_thresh: int = 40) -> float:
    """
    Fraction of pixels that are both very bright AND changed significantly
    from the previous frame — used for sparkle detection.
    """
    diff  = ImageChops.difference(pil_cur, pil_prev)
    cur_b = pil_cur.tobytes()
    dif_b = diff.tobytes()
    n = len(cur_b) // 3
    count = 0
    for i in range(0, len(cur_b), 3):
        r, g, b = cur_b[i], cur_b[i+1], cur_b[i+2]
        dr, dg, db = dif_b[i], dif_b[i+1], dif_b[i+2]
        if (r > bright_thresh and g > bright_thresh and b > 200 and
                (dr + dg + db) // 3 > diff_thresh):
            count += 1
    return count / n if n else 0.0

try:
    import winsound
    WINSOUND_OK = True
except ImportError:
    WINSOUND_OK = False

DEPS_OK = len(MISSING) == 0

# ═══════════════════════════════════════════════════════════════════
# CONSTANTS & THEME
# ═══════════════════════════════════════════════════════════════════

APP_TITLE   = "✨ Shiny Hunter — Universal Edition"
APP_VERSION = "0.6.3"
SHINY_ODDS  = 8192

BG      = "#0a0a18"
BG2     = "#12122a"
BG3     = "#1a1a38"
FG      = "#dde0ff"
FG_DIM  = "#6666aa"
GOLD    = "#FFD700"
RED_HI  = "#ff4040"
GREEN_HI= "#39ff14"
FONT_MONO = ("Courier New", 9)
FONT_MED  = ("Courier New", 10)
FONT_BIG  = ("Courier New", 12, "bold")
FONT_HDR  = ("Courier New", 20, "bold")
TYPE_COLOR = {"Grass":"#4CAF50","Fire":"#FF6F3C","Water":"#4EA8DE",
              "Electric":"#F5C542","Normal":"#A8A878"}

DEFAULT_KEYS = {
    "a_button":"x","b_button":"z","start":"Return","select":"BackSpace",
    "l_button":"q","r_button":"e","up":"Up","down":"Down",
    "left":"Left","right":"Right","reset_key":"r",
}

SEQUENCES_DIR = "sequences"

# ═══════════════════════════════════════════════════════════════════
# GAME DATABASE
# ═══════════════════════════════════════════════════════════════════

@dataclass
class StarterInfo:
    name:str; type1:str; emoji:str

@dataclass
class GameDef:
    name:str; gen:int; platform:str; shiny:bool
    starters:List[StarterInfo]; theme:str; notes:str
    # detection_hint: "star" = fixed star icon on summary screen (Gen II + FR/LG)
    #                 "sprite" = whole-sprite colour shift on battle screen (RSE)
    # Defaults to "star" for gen≤2, "sprite" for gen≥3 unless overridden
    detection_hint:str = "auto"

G2 = "#B8960A"
G3 = "#227744"

GAMES:List[GameDef] = [
    GameDef("Pokémon Gold",2,"GBC",True,[
        StarterInfo("Chikorita","Grass","🌿"),
        StarterInfo("Cyndaquil","Fire","🔥"),
        StarterInfo("Totodile","Water","💧")],G2,
        "Save in front of target ball on Elm's desk.\nShiny starters MUST be male."),
    GameDef("Pokémon Silver",2,"GBC",True,[
        StarterInfo("Chikorita","Grass","🌿"),
        StarterInfo("Cyndaquil","Fire","🔥"),
        StarterInfo("Totodile","Water","💧")],G2,
        "Save in front of target ball on Elm's desk.\nShiny starters MUST be male."),
    GameDef("Pokémon Crystal",2,"GBC",True,[
        StarterInfo("Chikorita","Grass","🌿"),
        StarterInfo("Cyndaquil","Fire","🔥"),
        StarterInfo("Totodile","Water","💧")],G2,
        "Save in front of target ball on Elm's desk.\nShiny starters MUST be male."),
    GameDef("Pokémon Ruby",3,"GBA",True,[
        StarterInfo("Treecko","Grass","🌿"),
        StarterInfo("Torchic","Fire","🔥"),
        StarterInfo("Mudkip","Water","💧")],G3,
        "Save on Route 101 before Birch's bag."),
    GameDef("Pokémon Sapphire",3,"GBA",True,[
        StarterInfo("Treecko","Grass","🌿"),
        StarterInfo("Torchic","Fire","🔥"),
        StarterInfo("Mudkip","Water","💧")],G3,
        "Save on Route 101 before Birch's bag."),
    GameDef("Pokémon Emerald",3,"GBA",True,[
        StarterInfo("Treecko","Grass","🌿"),
        StarterInfo("Torchic","Fire","🔥"),
        StarterInfo("Mudkip","Water","💧")],G3,
        "Save on Route 101 before Birch's bag.\n⚡ RNG fixed — use Recording mode."),
    GameDef("Pokémon FireRed",3,"GBA",True,[
        StarterInfo("Bulbasaur","Grass","🌿"),
        StarterInfo("Charmander","Fire","🔥"),
        StarterInfo("Squirtle","Water","💧")],G3,
        "Save in Oak's lab facing the 3 Pokéballs.\n"
        "Pick ball → check Pokémon summary → gold ★ = shiny.",
        detection_hint="star"),
    GameDef("Pokémon LeafGreen",3,"GBA",True,[
        StarterInfo("Bulbasaur","Grass","🌿"),
        StarterInfo("Charmander","Fire","🔥"),
        StarterInfo("Squirtle","Water","💧")],G3,
        "Save in Oak's lab facing the 3 Pokéballs.\n"
        "Pick ball → check Pokémon summary → gold ★ = shiny.",
        detection_hint="star"),
]
GAME_BY_NAME = {g.name:g for g in GAMES}

# ═══════════════════════════════════════════════════════════════════
# MACRO RECORDER
# ═══════════════════════════════════════════════════════════════════

class MacroRecorder:
    """
    Records every tracked keypress + delay, saves to JSON.
    Replays with identical timing, focusing Playback before each key.
    """
    TRACKED = {"x","z","r","q","e","return","enter","backspace",
               "up","down","left","right","space","f5"}

    # Normalize pynput key names → pyautogui key names
    KEY_MAP = {
        "enter"    : "Return",   # pynput calls it "enter", pyautogui needs "Return"
        "return"   : "Return",
        "backspace": "BackSpace",
        "up"       : "Up",
        "down"     : "Down",
        "left"     : "Left",
        "right"    : "Right",
        "space"    : "space",
        "f5"       : "F5",
        # single letters pass through as-is
    }

    def __init__(self):
        self.events: List[dict] = []
        self._listener = None
        self._last_t   = 0.0
        self._active   = False
        self.log_fn    = lambda m: None

    # ── Recording ─────────────────────────────────────────────────

    def start_recording(self) -> bool:
        if not PYNPUT_OK:
            self.log_fn("❌  pynput not installed — run: pip install pynput")
            return False
        self.events  = []
        self._last_t = time.time()
        self._active = True

        def on_press(key):
            if not self._active:
                return False
            try:
                k = key.char.lower() if hasattr(key,"char") and key.char \
                    else str(key).replace("Key.","").lower()
            except:
                return
            if k not in self.TRACKED:
                return
            # Normalize to pyautogui-compatible name
            k = self.KEY_MAP.get(k, k)
            now   = time.time()
            delay = round(now - self._last_t, 3)
            self._last_t = now
            self.events.append({"key":k,"delay":delay})
            self.log_fn(f"⏺  [{len(self.events):03d}] key={k:12s}  wait={delay:.3f}s  "
                        f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}]")

        self._listener = pynput_keyboard.Listener(on_press=on_press)
        self._listener.start()
        return True

    def stop_recording(self) -> List[dict]:
        self._active = False
        if self._listener:
            self._listener.stop()
            self._listener = None
        return self.events.copy()

    # ── Persistence ───────────────────────────────────────────────

    def save(self, path: str, metadata: dict = None) -> bool:
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            data = {"version":APP_VERSION,
                    "metadata": metadata or {},
                    "events": self.events}
            with open(path,"w") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            self.log_fn(f"❌  Save failed: {e}")
            return False

    def load(self, path: str) -> bool:
        try:
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, list):
                self.events = data   # legacy format
            else:
                self.events = data.get("events", [])
            return len(self.events) > 0
        except Exception as e:
            self.log_fn(f"❌  Load failed: {e}")
            return False

    # ── Playback ──────────────────────────────────────────────────

    def _find_playback_hwnd(self):
        try:
            import ctypes
            u = ctypes.windll.user32
            found = []
            CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
            def cb(h,_):
                if u.IsWindowVisible(h):
                    n = u.GetWindowTextLengthW(h)
                    if n > 0:
                        b = ctypes.create_unicode_buffer(n+1)
                        u.GetWindowTextW(h, b, n+1)
                        if "Playback" in b.value:
                            found.append(h)
                return True
            u.EnumWindows(CB(cb), 0)
            return found[0] if found else None
        except:
            return None

    def _focus_and_key(self, key: str):
        """Focus Playback game viewport then send key via pyautogui."""
        try:
            import ctypes, ctypes.wintypes
            hwnd = self._find_playback_hwnd()
            if hwnd:
                u  = ctypes.windll.user32
                k  = ctypes.windll.kernel32
                fg_hwnd = u.GetForegroundWindow()
                fg_tid  = u.GetWindowThreadProcessId(fg_hwnd, None)
                my_tid  = k.GetCurrentThreadId()
                attached = (fg_tid != my_tid)
                if attached:
                    u.AttachThreadInput(my_tid, fg_tid, True)
                try:
                    u.AllowSetForegroundWindow(0xFFFFFFFF)
                    u.ShowWindow(hwnd, 9)
                    u.SetForegroundWindow(hwnd)
                    u.BringWindowToTop(hwnd)
                finally:
                    if attached:
                        u.AttachThreadInput(my_tid, fg_tid, False)
                rect = ctypes.wintypes.RECT()
                try:
                    dwmapi = ctypes.windll.dwmapi
                    hr = dwmapi.DwmGetWindowAttribute(hwnd, 9,
                                                      ctypes.byref(rect),
                                                      ctypes.sizeof(rect))
                    if hr != 0:
                        raise OSError
                except Exception:
                    u.GetWindowRect(hwnd, ctypes.byref(rect))
                pyautogui.click((rect.left + rect.right) // 2,
                                (rect.top  + rect.bottom) // 2)
                time.sleep(0.12)
        except:
            pass
        pyautogui.keyDown(key)
        time.sleep(0.06)
        pyautogui.keyUp(key)
        time.sleep(0.03)

    def replay_one_cycle(self, running_fn, log_fn) -> bool:
        """Replay recorded sequence once. Returns True if completed."""
        if not self.events:
            log_fn("❌  No events to replay.")
            return False
        for i, evt in enumerate(self.events):
            if not running_fn():
                raise StopIteration
            delay = evt["delay"]
            key   = evt["key"]
            log_fn(f"▶  [{i+1:03d}/{len(self.events)}] {key:12s}  "
                   f"wait={delay:.3f}s  [{datetime.now().strftime('%H:%M:%S.%f')[:-3]}]")
            # Interruptible wait
            elapsed = 0.0
            while elapsed < delay:
                if not running_fn():
                    raise StopIteration
                chunk = min(0.05, delay-elapsed)
                time.sleep(chunk)
                elapsed += chunk
            self._focus_and_key(key)
        return True


# ═══════════════════════════════════════════════════════════════════
# SHINY DETECTOR
# ═══════════════════════════════════════════════════════════════════

class ShinyDetector:
    """
    Watches a user-drawn zone for the shiny star icon (★✦).

    Setup flow:
      1. auto_detect_playback()  → finds the Playback game viewport
      2. set_star_zone(...)      → stores the small box the user drew over
                                   the top-right star area
      3. set_baseline()          → snapshots that zone right now (no stars
                                   visible) as the non-shiny reference
      4. check_shiny_star()      → compares the live zone to baseline;
                                   any significant diff = stars appeared = SHINY

    All detection is pixel-diff against the user-drawn zone — no heuristics,
    no pink-screen gating, no hard-coded coordinates.
    """

    # Mean pixel diff threshold: stars are bright white on pink BG →
    # produces a large diff even for a tiny zone.
    DIFF_THRESHOLD = 8.0
    # Need this many hits (out of samples) to confirm
    MIN_HITS = 3

    # ── Detection modes ──────────────────────────────────────────
    # "dark_pixel"  → Gen II method: count dark pixels in the star zone
    #                 (★✦ icon appears next to gender symbol on a shiny)
    # "sprite_diff" → Gen III method: pixel-diff a sprite zone against
    #                 baseline (whole Pokémon body shifts color when shiny)
    MODE_DARK_PIXEL  = "dark_pixel"
    MODE_SPRITE_DIFF = "sprite_diff"

    # Sprite-diff threshold: a full shiny color swap on a sprite zone
    # produces mean abs diff of ~8-30 depending on zone tightness.
    # Floor of 6 is safe above the observed noise (~0-0.2 on stable frames).
    SPRITE_DIFF_THRESHOLD = 6.0

    def __init__(self):
        self._sct          = None
        self.region        = None   # full Playback game viewport
        self._star_zone    = None   # absolute screen coords of drawn zone
        self._baseline     = None   # float32 snapshot (no shiny)
        self._baseline_set = False
        self._baseline_reject_reason = None
        # Auto-calibrated baseline stats — different metric per mode.
        self._baseline_dark_pct = 0.0       # used by dark_pixel mode
        self._baseline_diff_floor = 0.0     # used by sprite_diff mode
        # Per-baseline override of SPRITE_DIFF_THRESHOLD.  Auto-calibrated
        # at baseline capture time from measured noise floor.  Falls back
        # to class-level SPRITE_DIFF_THRESHOLD if not set.
        self._sprite_diff_threshold = None
        # Active detection mode (set by the app based on selected game)
        self.detection_mode = self.MODE_DARK_PIXEL

    # ── Init ──────────────────────────────────────────────────────

    def init(self) -> bool:
        try:
            if self._sct:
                try: self._sct.close()
                except: pass
            self._sct = mss.mss()
            return True
        except:
            return False

    # ── Region helpers ────────────────────────────────────────────

    def set_region(self, left, top, width, height):
        """Set the full Playback game viewport (used for screenshots)."""
        self.region = {"left": left, "top": top,
                       "width": width, "height": height}

    def set_star_zone(self, left, top, width, height):
        """
        Store the absolute screen coordinates of the user-drawn star zone.
        Only resets the baseline if the zone actually changed — calling
        this with the same coords as before is a no-op for the baseline.
        """
        new_zone = {"left": left, "top": top,
                    "width": width, "height": height}
        if self._star_zone != new_zone:
            # Real change — invalidate baseline
            self._baseline     = None
            self._baseline_set = False
        self._star_zone = new_zone

    # ── Window detection ──────────────────────────────────────────

    def _find_playback_hwnd(self):
        """Return the HWND of the Epilogue Playback window, or None."""
        try:
            import ctypes
            u = ctypes.windll.user32
            found = []
            CB = ctypes.WINFUNCTYPE(ctypes.c_bool,
                                    ctypes.c_size_t, ctypes.c_size_t)
            def _cb(h, _):
                if u.IsWindowVisible(h):
                    n = u.GetWindowTextLengthW(h)
                    if n > 0:
                        b = ctypes.create_unicode_buffer(n + 1)
                        u.GetWindowTextW(h, b, n + 1)
                        if "Playback" in b.value:
                            found.append(h)
                return True
            u.EnumWindows(CB(_cb), 0)
            return found[0] if found else None
        except:
            return None

    def auto_detect_playback(self):
        """
        Find the Epilogue Playback window and return its true visible bounds.

        On Windows 10/11, GetWindowRect includes invisible DWM shadow/border
        pixels (~8 px each side) that produce a black strip in captures.
        DwmGetWindowAttribute(DWMWA_EXTENDED_FRAME_BOUNDS) returns the real
        visible rectangle instead.  Falls back to GetWindowRect if DWM fails.

        Returns a dict {left, top, width, height} or None.
        """
        try:
            import ctypes, ctypes.wintypes
            hwnd = self._find_playback_hwnd()
            if not hwnd:
                return None

            rect = ctypes.wintypes.RECT()

            # Try DWM first (correct on Win10/11 with shadow borders)
            try:
                dwmapi = ctypes.windll.dwmapi
                DWMWA_EXTENDED_FRAME_BOUNDS = 9
                hr = dwmapi.DwmGetWindowAttribute(
                    hwnd,
                    DWMWA_EXTENDED_FRAME_BOUNDS,
                    ctypes.byref(rect),
                    ctypes.sizeof(rect),
                )
                if hr != 0:          # S_OK == 0; anything else → fallback
                    raise OSError
            except Exception:
                # Fallback: plain GetWindowRect
                ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))

            return {
                "left"  : rect.left,
                "top"   : rect.top,
                "width" : rect.right  - rect.left,
                "height": rect.bottom - rect.top,
            }
        except:
            return None

    # ── Screen capture ────────────────────────────────────────────

    def _grab(self) -> "Image.Image | None":
        """Grab the full game viewport as a PIL Image (RGB). Returns None on failure."""
        if not self._sct or not self.region:
            return None
        try:
            raw = self._sct.grab(self.region)
            return Image.frombytes("RGB", (raw.width, raw.height),
                                   raw.bgra, "raw", "BGRX")
        except Exception:
            return None

    def _grab_zone(self) -> "Image.Image | None":
        """Grab just the user-drawn star/sprite zone as a PIL Image. Returns None on failure."""
        if not self._sct or not self._star_zone:
            return None
        try:
            raw = self._sct.grab(self._star_zone)
            return Image.frombytes("RGB", (raw.width, raw.height),
                                   raw.bgra, "raw", "BGRX")
        except Exception:
            return None

    def grab_pil(self) -> "Image.Image | None":
        """Grab full viewport as a PIL Image (RGB)."""
        return self._grab()

    # ── Baseline ──────────────────────────────────────────────────

    BASELINE_FILE = "shiny_hunter_baseline.png"   # saved as PNG now

    def set_baseline(self) -> bool:
        if not self._sct:
            self.init()
        frame = self._grab_zone()
        if frame is None:
            self._baseline_reject_reason = "Capture failed — zone or screen not available"
            return False

        # Sanity check
        stat = ImageStat.Stat(frame)
        stddev = (sum(stat.stddev) / len(stat.stddev))
        dark_pct = _dark_pixel_pct(frame)

        if self.detection_mode == self.MODE_DARK_PIXEL:
            # Gen II: zone must contain the gender symbol (dark ink present)
            # FRLG exception: the star zone is blank white on a non-shiny
            # frame — that's correct. We only need the zone to be stable
            # (not completely black or totally random noise).
            # So we relax to: reject only if completely black or pure noise.
            game_hint = getattr(self, "_game_hint", "star")
            is_frlg_star = (game_hint == "star" and
                            getattr(self, "_game_gen", 2) >= 3)
            if is_frlg_star:
                # For FRLG: just need stddev to be low (stable blank area)
                # A uniform light background is exactly what we want
                if stddev > 30.0:
                    self._baseline_reject_reason = (
                        f"Zone looks too noisy — stddev={stddev:.1f}.  "
                        "Make sure Playback is on the summary screen with "
                        "a NON-shiny Pokémon and the star area is empty.")
                    return False
            else:
                # Gen II: must have dark ink (gender symbol in zone)
                if stddev < 5.0 or dark_pct < 0.01:
                    self._baseline_reject_reason = (
                        f"Zone looks blank — stddev={stddev:.1f}, "
                        f"dark={dark_pct*100:.2f}%.  "
                        "Re-draw with the gender/star symbol inside the zone.")
                    return False
        else:
            if stddev < 12.0:
                self._baseline_reject_reason = (
                    f"Sprite zone too uniform — stddev={stddev:.1f}.  "
                    "Re-draw over the Pokémon's actual body pixels.")
                return False

        self._baseline           = frame.copy()
        self._baseline_set       = True
        self._baseline_reject_reason = None

        # Calibrate dark-pixel pct
        self._baseline_dark_pct  = dark_pct
        self._baseline_diff_floor = 0.0

        try:
            frame.save(self.BASELINE_FILE)
            with open(self.BASELINE_FILE + ".meta", "w") as f:
                f.write(f"{self._baseline_dark_pct}\n"
                        f"{self.detection_mode}\n")
        except Exception:
            pass
        return True

    def load_baseline_from_disk(self) -> bool:
        try:
            if os.path.exists(self.BASELINE_FILE):
                self._baseline = Image.open(self.BASELINE_FILE).convert("RGB")
                self._baseline_set = True
                meta = self.BASELINE_FILE + ".meta"
                if os.path.exists(meta):
                    try:
                        with open(meta) as f:
                            lines = [l.strip() for l in f.readlines()]
                        if lines:
                            self._baseline_dark_pct = float(lines[0])
                        if len(lines) >= 2 and lines[1] in (
                                self.MODE_DARK_PIXEL, self.MODE_SPRITE_DIFF):
                            self.detection_mode = lines[1]
                        if len(lines) >= 3:
                            try:
                                self._sprite_diff_threshold = float(lines[2])
                            except Exception:
                                self._sprite_diff_threshold = None
                    except Exception:
                        pass
                else:
                    self._baseline_dark_pct = _dark_pixel_pct(self._baseline)
                return True
        except Exception:
            pass
        return False

    def clear_baseline(self):
        self._baseline           = None
        self._baseline_set       = False
        self._sprite_diff_threshold = None
        try:
            if os.path.exists(self.BASELINE_FILE):
                os.remove(self.BASELINE_FILE)
        except Exception:
            pass
        """
        Snapshot the current zone as the non-shiny reference.
        For dark_pixel mode (Gen II): zone shows star area on status screen.
        For sprite_diff mode (Gen III): zone shows Pokémon sprite on battle screen.
        Persists to disk so it survives app restarts.

        Returns True on success.  Returns False (and logs why) if the
        captured baseline looks degenerate.
        """
        # ── Detection ─────────────────────────────────────────────────

    def _zone_diff(self) -> float:
        """Mean absolute pixel diff vs baseline. Returns -1.0 if not available."""
        if not self._baseline_set or self._star_zone is None:
            return -1.0
        zone = self._grab_zone()
        if zone is None:
            return -1.0
        if zone.size != self._baseline.size:
            zone = zone.resize(self._baseline.size, Image.LANCZOS)
        return _mean_abs_diff(zone, self._baseline)

    def check_shiny_star(self, samples: int = 5,
                         interval: float = 0.10) -> tuple:
        """
        Sample the detection zone `samples` times and check for shiny.

        Two methods depending on detection_mode:

          MODE_DARK_PIXEL (Gen II):  Stars are dark ink that appears next
             to the gender icon on a shiny status screen.  We count dark
             pixels in the zone and trigger when the count rises ≥5pp
             above the calibrated baseline.

          MODE_SPRITE_DIFF (Gen III): The whole Pokémon body changes
             color when shiny (blue → purple for Mudkip, etc).  We
             pixel-diff the live sprite zone against the baseline; a
             diff above SPRITE_DIFF_THRESHOLD = shiny.  Signal is huge
             (30-80) because the entire sprite changes color.

        Requires MIN_HITS out of `samples` samples to confirm.
        Returns (is_shiny, confidence, pil_frame).
        """
        # Mode-specific thresholds
        if self.detection_mode == self.MODE_SPRITE_DIFF:
            return self._check_sprite_diff(samples, interval)
        else:
            return self._check_dark_pixel(samples, interval)

    def _check_dark_pixel(self, samples: int, interval: float) -> tuple:
        """Gen II dark-pixel-count detection using Pillow."""
        base_dark = self._baseline_dark_pct
        dark_threshold = base_dark + 0.05

        hits = 0
        last_diff = -1.0
        last_dark = -1.0

        for _ in range(samples):
            zone = self._grab_zone()
            if zone is None:
                time.sleep(interval)
                continue

            if self._baseline_set:
                bl = self._baseline
                if zone.size != bl.size:
                    zone = zone.resize(bl.size, Image.LANCZOS)
                diff = _mean_abs_diff(zone, bl)
            else:
                diff = -1.0

            dark_pct = _dark_pixel_pct(zone)
            last_diff = diff
            last_dark = dark_pct

            if dark_pct >= dark_threshold:
                hits += 1

            time.sleep(interval)

        frame = self._grab()
        confidence = hits / samples
        is_shiny   = hits >= self.MIN_HITS

        self._last_diff = last_diff
        self._last_dark_pct = last_dark
        self._last_dark_threshold = dark_threshold

        return is_shiny, confidence, frame

    def get_sprite_threshold(self) -> float:
        """Return the active sprite-diff threshold (calibrated or default)."""
        return (self._sprite_diff_threshold
                if self._sprite_diff_threshold is not None
                else self.SPRITE_DIFF_THRESHOLD)

    def _check_sprite_diff(self, samples: int, interval: float) -> tuple:
        """Gen III sprite colour-shift detection using Pillow."""
        threshold = (self._sprite_diff_threshold
                     if self._sprite_diff_threshold is not None
                     else self.SPRITE_DIFF_THRESHOLD)
        hits = 0
        last_diff = -1.0
        all_diffs = []

        for _ in range(samples):
            zone = self._grab_zone()
            if zone is None:
                time.sleep(interval)
                continue

            if self._baseline_set:
                bl = self._baseline
                if zone.size != bl.size:
                    zone = zone.resize(bl.size, Image.LANCZOS)
                diff = _mean_abs_diff(zone, bl)
            else:
                diff = -1.0

            last_diff = diff
            all_diffs.append(diff)

            if diff >= threshold:
                hits += 1

            time.sleep(interval)

        frame = self._grab()
        confidence = hits / samples
        is_shiny   = hits >= self.MIN_HITS

        self._last_diff = last_diff
        self._last_sprite_diffs = all_diffs
        self._last_dark_pct = -1.0
        self._last_sprite_threshold = threshold

        return is_shiny, confidence, frame

    def check_image_for_shiny(self, pil_image) -> tuple:
        """Test-mode: check a PIL image against the stored baseline."""
        if not self._baseline_set:
            return False, 0.0, 0.0
        try:
            img = pil_image.convert("RGB")
            if img.size != self._baseline.size:
                img = img.resize(self._baseline.size, Image.LANCZOS)
            diff = _mean_abs_diff(img, self._baseline)
            return diff >= self.get_sprite_threshold(), diff, 1.0
        except Exception:
            return False, 0.0, 0.0

    # ── Gen III sparkle detection ─────────────────────────────────

    def watch_sparkle(self, duration: float,
                      sensitivity: float = 1.0) -> bool:
        """
        Watch for the Gen III shiny sparkle animation during the
        Pokémon throw sequence.

        When a shiny appears, 4-6 white/yellow star shapes flash
        briefly across the battle field BEFORE the Pokémon's sprite
        is fully visible.  These stars are:
          - Very bright (R,G,B all > 230)
          - Appear as sudden NEW bright pixels vs the previous frame
          - Cluster together (not spread evenly = not just bg change)
          - Present for 3-5 frames (~120-200ms) then gone

        Detection method:
          1. Every 40ms grab the battle area (excluding HP/text bars)
          2. Count pixels that are very bright AND differ significantly
             from the rolling background frame
          3. If a sudden cluster of 100+ such pixels appears,
             that's a sparkle star burst

        Returns True the moment sparkle is detected.

        sensitivity: 1.0 = default, lower = more sensitive (more FP risk),
                     higher = stricter (less FP risk)
        """
        if not self.region:
            return False

        prev_frame = None
        t0 = time.time()
        SPARKLE_THRESHOLD = int(120 * sensitivity)

        while time.time() - t0 < duration:
            frame = self._grab()
            if frame is None:
                time.sleep(0.04)
                continue

            w, h = frame.size
            # Crop to battle field only (skip HP bar top 8%, bottom menus)
            field = frame.crop((0, int(h*0.08), w, int(h*0.65)))

            if prev_frame is not None:
                n_sparkle = int(_bright_diff_pct(field, prev_frame,
                                                 bright_thresh=230,
                                                 diff_thresh=40)
                                * field.width * field.height)
                if n_sparkle >= SPARKLE_THRESHOLD:
                    return True

            prev_frame = field
            time.sleep(0.04)

        return False


# ═══════════════════════════════════════════════════════════════════
# HUNTER LOOP
# ═══════════════════════════════════════════════════════════════════

class HunterLoop:
    """
    Core loop with screen-state sync:
      Reset → wait for title screen → press Continue → wait for overworld
      → replay macro with pixel-based sync between presses
      → check shiny → if shiny STOP (game untouched) → else reset
    """
    def __init__(self, recorder, detector, game, starter,
                 log_fn, status_fn, shiny_fn, reset_key="r",
                 region=None, use_screen_sync=True,
                 live_viewer=None):
        self.recorder        = recorder
        self.detector        = detector
        self.game            = game
        self.starter         = starter
        self._log            = log_fn
        self._status         = status_fn
        self._shiny_cb       = shiny_fn
        self.reset_key       = reset_key
        self.region          = region
        self.use_screen_sync = use_screen_sync
        self.live_viewer     = live_viewer
        self.running         = False
        self.count           = 0
        self._thread         = None
        self._watcher        = None

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def _focus(self):
        """
        Bring Epilogue Playback to the foreground and click inside the
        game viewport so Electron registers real input.
        Uses AttachThreadInput for reliable SetForegroundWindow on Win10/11.
        """
        try:
            import ctypes, ctypes.wintypes
            hwnd = self.detector._find_playback_hwnd()
            if not hwnd:
                return
            u  = ctypes.windll.user32
            k  = ctypes.windll.kernel32
            fg_hwnd = u.GetForegroundWindow()
            fg_tid  = u.GetWindowThreadProcessId(fg_hwnd, None)
            my_tid  = k.GetCurrentThreadId()
            attached = (fg_tid != my_tid)
            if attached:
                u.AttachThreadInput(my_tid, fg_tid, True)
            try:
                u.AllowSetForegroundWindow(0xFFFFFFFF)
                u.ShowWindow(hwnd, 9)   # SW_RESTORE
                u.SetForegroundWindow(hwnd)
                u.BringWindowToTop(hwnd)
            finally:
                if attached:
                    u.AttachThreadInput(my_tid, fg_tid, False)
            # Use DWM bounds for accurate click position (avoids shadow offset)
            cr = ctypes.wintypes.RECT()
            try:
                dwmapi = ctypes.windll.dwmapi
                hr = dwmapi.DwmGetWindowAttribute(hwnd, 9,
                                                  ctypes.byref(cr),
                                                  ctypes.sizeof(cr))
                if hr != 0:
                    raise OSError
            except Exception:
                u.GetWindowRect(hwnd, ctypes.byref(cr))
            cx = (cr.left + cr.right)  // 2
            cy = (cr.top  + cr.bottom) // 2
            pyautogui.click(cx, cy)
            time.sleep(0.12)
        except:
            pass

    def _press(self, key, hold=0.06):
        if not self.running: raise StopIteration
        self._focus()
        pyautogui.keyDown(key); time.sleep(hold); pyautogui.keyUp(key); time.sleep(0.03)

    def _wait(self, secs):
        elapsed = 0.0
        while elapsed < secs:
            if not self.running: raise StopIteration
            time.sleep(0.05); elapsed += 0.05

    def _soft_reset(self):
        self._focus()
        pyautogui.keyDown(self.reset_key)
        time.sleep(0.12)
        pyautogui.keyUp(self.reset_key)
        time.sleep(0.05)

    def _loop(self):
        self._log(f"🎮  {self.game.name}  |  {self.starter.emoji} {self.starter.name}")
        self._log(f"📊  Odds: 1 in {SHINY_ODDS:,}  |  {len(self.recorder.events)} macro steps")
        self._log("⚠️   SHINY SAFE — game will NOT reset if shiny found")
        self._log("⚠️   Emergency stop: move mouse to top-left corner\n")

        # Split script at the detection marker (if set) or soft-reset key (r)
        # Everything before the split = pick up pokemon + navigate to stats
        # Everything from the split onward = reset + reload back to save point
        events = self.recorder.events
        
        # Check if detection marker step is set (user-defined detection point)
        if hasattr(self, 'detection_marker_step') and self.detection_marker_step is not None:
            split_idx = self.detection_marker_step
            pre_reset    = events[:split_idx]     # up to detection point
            post_reset   = events[split_idx:]     # detection point onwards
            manual_reset = False
            self._log(f"🎯  Using marked detection point at step {split_idx+1}")
            self._log(f"ℹ️   Script split: {len(pre_reset)} steps → shiny check → "
                      f"{len(post_reset)} steps (continue+reset)")
        else:
            # Fallback to reset key detection
            r_idx  = next((i for i,e in enumerate(events)
                           if e["key"].lower() == self.reset_key.lower()), None)
            
            if r_idx is None:
                # No reset in script — play whole thing then reset manually
                self._log("ℹ️   No reset key found in script — will soft-reset after each run")
                pre_reset  = events
                post_reset = []
                manual_reset = True
            else:
                pre_reset    = events[:r_idx]    # ball → stats
                post_reset   = events[r_idx:]    # r + reload
                manual_reset = False
                self._log(f"ℹ️   Script split: {len(pre_reset)} steps → shiny check → "
                          f"{len(post_reset)} steps (reset+reload)")

        time.sleep(1.0)

        while self.running:
            self.count += 1
            n = self.count
            self._log(f"{'─'*44}")
            self._log(f"🔄  Cycle #{n:,}  [{datetime.now().strftime('%H:%M:%S.%f')[:-3]}]")
            self._status(f"Cycle #{n:,}  —  Running sequence…")

            try:
                # ── PART 1: play up to the shiny check ────────────
                self._log(f"▶  Playing {len(pre_reset)} steps (ball → stats)…")
                self._play_events(pre_reset)

                if not self.running: break

                # ── PRE-CHECK WAIT + SPARKLE WATCH ─────────────────
                # For Gen III: wait for the throw animation to finish
                # before the zone-diff check.  During this wait we also
                # run the sparkle detector in a background thread — if
                # the shiny sparkle fires EARLY we stop immediately
                # without waiting for the full pre_wait.
                pre_wait     = float(getattr(self, "pre_check_wait", 0.0))
                use_sparkle  = getattr(self, "use_sparkle_detection", False)
                sparkle_hit  = False

                if pre_wait > 0:
                    if (use_sparkle and
                            self.detector.detection_mode ==
                            ShinyDetector.MODE_SPRITE_DIFF):
                        self._log(f"⏳  Pre-wait {pre_wait:.1f}s — watching for ✦ sparkle…")
                        sparkle_result = [False]

                        def _sparkle_worker():
                            # Skip the first 40% of the wait — that's the
                            # Pokéball throw animation which has bright
                            # flashes that can false-trigger.  The real
                            # shiny sparkle appears at ~50-80% of the wait
                            # window, right as the Pokémon emerges.
                            skip = pre_wait * 0.40
                            time.sleep(skip)
                            if self.running:
                                watch_for = pre_wait - skip
                                sparkle_result[0] = self.detector.watch_sparkle(
                                    watch_for,
                                    sensitivity=getattr(self,
                                        "sparkle_sensitivity", 1.0))

                        import threading as _th
                        st = _th.Thread(target=_sparkle_worker, daemon=True)
                        st.start()

                        # Also sleep the full pre_wait so zone is stable
                        waited = 0.0
                        while self.running and waited < pre_wait:
                            time.sleep(0.1)
                            waited += 0.1

                        sparkle_hit = sparkle_result[0]
                        if sparkle_hit:
                            self._log("✨  SPARKLE DETECTED during throw!")
                    else:
                        # Plain wait (no sparkle, or Gen II)
                        if pre_wait > 0:
                            self._log(f"⏳  Pre-check wait: {pre_wait:.1f}s…")
                        waited = 0.0
                        while self.running and waited < pre_wait:
                            time.sleep(0.1)
                            waited += 0.1

                if not self.running: break

                # ── SHINY CHECK ────────────────────────────────────
                self._status(f"Cycle #{n:,}  —  Checking for ★ shiny…")

                if sparkle_hit:
                    # Sparkle already confirmed — grab a screenshot and stop
                    pil_frame  = self.detector.grab_pil()
                    is_shiny   = True
                    confidence = 1.0
                    self._log("🌟  SHINY CONFIRMED via sparkle detection!")
                else:
                    self._log(f"🔍  Shiny check (5 samples)  "
                              f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}]")
                    is_shiny, confidence, pil_frame = self.detector.check_shiny_star()

                # Log calibration & this cycle's measurements (mode-aware)
                last_diff = getattr(self.detector, "_last_diff", -1)
                if self.detector.detection_mode == ShinyDetector.MODE_SPRITE_DIFF:
                    thr = self.detector.get_sprite_threshold()
                    sparkle_str = ("  ✨sparkle=ON" if getattr(self,
                        "use_sparkle_detection", False) else "")
                    self._log(f"    [Gen III sprite]  shiny_threshold>{thr:.1f}  "
                              f"this_cycle_diff={last_diff:.2f}{sparkle_str}")
                else:
                    base_dark = self.detector._baseline_dark_pct * 100
                    last_dark = getattr(self.detector, "_last_dark_pct", -1) * 100
                    threshold = getattr(self.detector, "_last_dark_threshold", 0) * 100
                    self._log(f"    [Gen II stars]  baseline_dark={base_dark:.1f}%  "
                              f"shiny_threshold>{threshold:.1f}%  "
                              f"this_cycle_dark={last_dark:.1f}%  "
                              f"diff={last_diff:.1f}")

                # Always save the status screen screenshot for verification
                saved_fname = None
                if pil_frame is not None:
                    try:
                        import os
                        from PIL import ImageDraw as _ID
                        os.makedirs("screenshots", exist_ok=True)
                        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                        fname  = f"screenshots/cycle_{n:05d}_{ts_str}"
                        fname += "_SHINY" if is_shiny else "_normal"
                        fname += ".png"

                        # Draw zone overlay on the saved screenshot
                        save_img = pil_frame.copy()
                        zone    = self.detector._star_zone
                        region  = self.detector.region
                        if zone and region:
                            draw = _ID.Draw(save_img)
                            rx   = region["left"]
                            ry   = region["top"]
                            zx1  = zone["left"]  - rx
                            zy1  = zone["top"]   - ry
                            zx2  = zx1 + zone["width"]
                            zy2  = zy1 + zone["height"]
                            color = "#ff4444" if is_shiny else "#00ff88"
                            draw.rectangle([zx1, zy1, zx2, zy2],
                                           outline=color, width=3)
                            label = "SHINY ZONE" if is_shiny else f"zone diff={last_diff:.1f}"
                            draw.rectangle([zx1, zy1-14, zx1+len(label)*7+4, zy1-2],
                                           fill=color)
                            draw.text((zx1+2, zy1-13), label,
                                      fill="black")

                        save_img.save(fname)
                        saved_fname = fname
                        self._log(f"📸  Saved: {fname}  (confidence={confidence:.0%})")
                    except Exception as e:
                        self._log(f"⚠️   Screenshot save failed: {e}")

                # ── DOUBLE-CHECK: independent verification on saved file ──
                # If the live check returned negative, re-scan the screenshot
                # using a different method (raw dark-pixel count in the
                # star zone). This catches cases where the live baseline
                # is bad or the zone moved.  Cost: ~30ms per cycle.
                if not is_shiny and saved_fname and self.detector._star_zone:
                    try:
                        verify_shiny = self._double_check_screenshot(saved_fname)
                        if verify_shiny:
                            self._log("🚨  DOUBLE-CHECK CAUGHT A SHINY THE LIVE SCAN MISSED!")
                            self._log(f"    File: {saved_fname}")
                            is_shiny = True
                            confidence = 1.0
                            # Rename file so it's obvious
                            try:
                                new_name = saved_fname.replace("_normal.png", "_SHINY_DOUBLECHECK.png")
                                os.rename(saved_fname, new_name)
                                saved_fname = new_name
                            except Exception:
                                pass
                    except Exception as e:
                        self._log(f"⚠️   Double-check error: {e}")

                if is_shiny:
                    self._log(f"🌟  SHINY DETECTED  confidence={confidence:.0%}")
                    self._on_shiny(n)
                    return

                prob = (1-(1-1/SHINY_ODDS)**n)*100
                self._log(f"❌  Not shiny  |  {prob:.3f}%  |  ~{max(0,SHINY_ODDS-n):,} left")
                self._status(f"Cycle #{n:,}  —  Not shiny, resetting…")

                if not self.running: break

                # ── PART 2: reset + reload (back to save point) ───
                if manual_reset:
                    self._log("🔄  Manual soft reset…")
                    self._soft_reset()
                    self._wait(7.0)
                else:
                    self._log(f"▶  Playing {len(post_reset)} steps (reset+reload)…")
                    self._play_events(post_reset)

            except StopIteration:
                self._log("🛑  Stopped.")
                break

        self._log("🛑  Hunt stopped.")
        self._status("Stopped.")

    def _play_events(self, events):
        """
        Play a list of recorded events using their exact recorded delays.
        Simple and reliable — no screen detection, just your timing.
        """
        for i, evt in enumerate(events):
            if not self.running:
                raise StopIteration

            key   = evt["key"]
            delay = evt["delay"]

            self._log(f"  [{i+1:03d}/{len(events)}] {key:10s}  wait={delay:.3f}s  "
                      f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}]")

            # Wait the recorded delay (interruptible)
            elapsed = 0.0
            while elapsed < delay:
                if not self.running:
                    raise StopIteration
                time.sleep(0.05)
                elapsed += 0.05

            # Focus Playback and send key
            self._focus()
            pyautogui.keyDown(key)
            time.sleep(0.06)
            pyautogui.keyUp(key)
            time.sleep(0.03)

    def _double_check_screenshot(self, path):
        """
        Independent shiny verification on a saved screenshot.

        Two methods depending on detection_mode:

        - dark_pixel (Gen II): count dark pixels in the saved screenshot's
          zone area, compare to AUTO-CALIBRATED baseline dark-pixel ratio.
          Uses PIL/file I/O which is independent of the live mss capture
          path, providing a second-source check.

        - sprite_diff (Gen III): re-compute the pixel diff against the
          baseline on the saved file.  Verifies the live grab wasn't a
          fluke.

        Returns True if the file looks shiny by the independent method.
        """
        from PIL import Image as PI
        zone   = self.detector._star_zone
        region = self.detector.region
        if not zone or not region:
            return False

        # Translate absolute screen zone → screenshot (= game region) coords
        zx = zone["left"] - region["left"]
        zy = zone["top"]  - region["top"]
        zw = zone["width"]
        zh = zone["height"]
        try:
            img = PI.open(path).convert("RGB")
            w, h = img.size
            x1 = max(0, zx)
            y1 = max(0, zy)
            x2 = min(w, zx + zw)
            y2 = min(h, zy + zh)
            if x2 - x1 < 4 or y2 - y1 < 4:
                return False
            crop_pil = img.crop((x1, y1, x2, y2))

            if self.detector.detection_mode == ShinyDetector.MODE_SPRITE_DIFF:
                base = self.detector._baseline
                if crop_pil.size != base.size:
                    crop_pil = crop_pil.resize(base.size, PI.LANCZOS)
                diff = _mean_abs_diff(crop_pil, base)
                return bool(diff >= self.detector.get_sprite_threshold())
            else:
                base_dark = getattr(self.detector, "_baseline_dark_pct", 0.0)
                threshold = base_dark + 0.05
                dark_pct  = _dark_pixel_pct(crop_pil)
                return bool(dark_pct >= threshold)
        except Exception:
            return False

    def _on_shiny(self, n):
        self.running = False  # stop immediately before anything else
        self._log(f"\n{'★'*50}\n✨  SHINY {self.starter.name.upper()} FOUND!")
        self._log(f"🎉  {n:,} resets  |  {self.game.name}")
        self._log(f"⚠️   GAME NOT RESET — GO SAVE IN PLAYBACK NOW!")
        self._log(f"{'★'*50}\n")
        self._status(f"🌟 SHINY FOUND — SAVE NOW! DO NOT CLOSE PLAYBACK!")
        self._shiny_cb(n, self.starter, self.game)

    def _on_live_shiny(self):
        """Called by LiveViewer when it detects stars — full stop."""
        self._on_shiny(self.count)


# ═══════════════════════════════════════════════════════════════════
# LIVE VIEWER
# ═══════════════════════════════════════════════════════════════════

class LiveViewer:
    """
    A small always-on-top window that:
    - Shows a live feed of the game region at ~10 fps
    - Highlights detected star clusters with green boxes
    - Flashes red + sounds alarm the instant stars are found
    - Calls on_shiny_detected() callback immediately

    Runs on its own thread, completely independent of the hunt loop.
    """

    def __init__(self, detector, on_shiny_detected, log_fn):
        self.detector          = detector
        self.on_shiny_detected = on_shiny_detected
        self.log_fn            = log_fn
        self.running           = False
        self._thread           = None
        self._win              = None
        self._canvas           = None
        self._tk_img           = None
        self._status_var       = None

    def start(self, root):
        """Create the viewer window and start watching."""
        self.running = True
        self._create_window(root)
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        try:
            if self._win:
                self._win.destroy()
        except:
            pass

    def _create_window(self, root):
        """Create the floating viewer window."""
        self._win = tk.Toplevel(root)
        self._win.title("👁 Live Star Detector")
        self._win.attributes("-topmost", True)
        self._win.configure(bg=BG)
        self._win.geometry("400x320+20+20")
        self._win.resizable(True, True)
        self._win.protocol("WM_DELETE_WINDOW", self.stop)

        tk.Label(self._win,
                 text="👁  LIVE STAR DETECTOR",
                 font=("Courier New", 10, "bold"),
                 fg=GOLD, bg=BG).pack(pady=(6,2))

        self._status_var = tk.StringVar(value="Watching…")
        self._status_lbl = tk.Label(self._win,
                                    textvariable=self._status_var,
                                    font=("Courier New", 9, "bold"),
                                    fg=GREEN_HI, bg=BG)
        self._status_lbl.pack()

        self._canvas = tk.Canvas(self._win, bg="#000000",
                                 highlightthickness=0)
        self._canvas.pack(fill="both", expand=True, padx=6, pady=6)

        tk.Label(self._win,
                 text="Green box = star cluster detected  |  Red flash = SHINY STOP",
                 font=("Courier New", 7), fg=FG_DIM, bg=BG).pack(pady=(0,4))

    def _watch_loop(self):
        """
        Continuously compare the star zone to the baseline.
        Fires on_shiny_detected() the instant the diff exceeds threshold.
        """
        from PIL import ImageDraw, ImageTk, Image as PI

        while self.running:
            try:
                # ── Grab full frame for the live preview ──────────
                frame = self.detector._grab()
                if frame is None:
                    time.sleep(0.10)
                    continue

                # ── Check the zone (mode-aware) ──
                baseline_ok = self.detector._baseline_set
                zone_pil = self.detector._grab_zone()
                if zone_pil is None or not baseline_ok:
                    diff = -1.0
                    dark_pct = -1.0
                    is_shiny = False
                else:
                    bl = self.detector._baseline
                    if zone_pil.size != bl.size:
                        zone_pil = zone_pil.resize(bl.size, PI.LANCZOS)
                    diff = _mean_abs_diff(zone_pil, bl)
                    if self.detector.detection_mode == ShinyDetector.MODE_SPRITE_DIFF:
                        is_shiny = diff >= self.detector.get_sprite_threshold()
                        dark_pct = -1.0
                    else:
                        dark_pct = _dark_pixel_pct(zone_pil)
                        base_dark = self.detector._baseline_dark_pct
                        is_shiny = dark_pct >= base_dark + 0.05

                # ── Build annotated preview image ─────────────────
                pil  = frame   # frame is already a PIL Image now
                draw = ImageDraw.Draw(pil)
                h, w = pil.size[1], pil.size[0]

                # Draw the star zone box on the preview
                zone = self.detector._star_zone
                if zone and self.detector.region:
                    rx = self.detector.region["left"]
                    ry = self.detector.region["top"]
                    zx1 = zone["left"]  - rx
                    zy1 = zone["top"]   - ry
                    zx2 = zx1 + zone["width"]
                    zy2 = zy1 + zone["height"]
                    color = "#ff0000" if is_shiny else ("#ffff00" if baseline_ok else "#888888")
                    draw.rectangle([zx1, zy1, zx2, zy2], outline=color, width=3)
                    if is_shiny:
                        lbl = "SHINY!"
                    elif baseline_ok:
                        if dark_pct >= 0:
                            lbl = f"d={diff:.1f}  k={dark_pct*100:.0f}%"
                        else:
                            lbl = f"diff={diff:.1f}"
                    else:
                        lbl = "no baseline"
                    draw.text((max(0, zx1), max(0, zy1 - 14)), lbl, fill=color)

                diff_str = f"{diff:.1f}" if diff >= 0 else "n/a"
                status   = f"{'🌟 SHINY!' if is_shiny else '👁 Watching'}  diff={diff_str}"

                # Resize to canvas
                cw = max(self._canvas.winfo_width(),  200)
                ch = max(self._canvas.winfo_height(), 150)
                pil.thumbnail((cw, ch), PI.LANCZOS)
                tk_img = ImageTk.PhotoImage(pil)

                def _update(img=tk_img, shiny=is_shiny, s=status):
                    try:
                        self._canvas.delete("all")
                        self._canvas.create_image(0, 0, anchor="nw", image=img)
                        self._tk_img = img
                        self._canvas.configure(bg="#ff0000" if shiny else "#000000")
                        self._status_var.set(s)
                        self._status_lbl.configure(fg="#ff0000" if shiny else GREEN_HI)
                    except:
                        pass
                try:
                    self._win.after(0, _update)
                except:
                    break

                # ── Fire shiny callback ────────────────────────────
                if is_shiny and self.running:
                    self.log_fn("👁  LIVE VIEWER: star zone diff exceeded threshold — STOPPING!")
                    self.running = False
                    try:
                        self._win.after(0, lambda: self.on_shiny_detected())
                    except:
                        self.on_shiny_detected()
                    break

            except Exception as e:
                self.log_fn(f"⚠️  Viewer error: {e}")
                time.sleep(0.5)

            time.sleep(0.10)  # ~10 fps


# ═══════════════════════════════════════════════════════════════════
# ALARM
# ═══════════════════════════════════════════════════════════════════

def play_alarm():
    if WINSOUND_OK:
        for i in range(12):
            try:
                winsound.Beep(1320 if i%2==0 else 880, 400)
            except:
                break
        return
    for _ in range(12):
        print("\a", end="", flush=True)
        time.sleep(0.35)


# ═══════════════════════════════════════════════════════════════════
# GUI HELPERS
# ═══════════════════════════════════════════════════════════════════

def _btn(parent, text, cmd, bg="#1a4a8a", fg="white", **kw):
    return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                     activebackground=bg, activeforeground=fg,
                     relief="flat", cursor="hand2", **kw)


# ═══════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════

class ShinyHunterApp:
    def __init__(self, root: tk.Tk):
        self.root     = root
        self.root.title(APP_TITLE)
        self.root.geometry("900x700")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)

        self.cfg        = self._load_cfg()
        self.recorder   = MacroRecorder()
        self.detector   = ShinyDetector()
        self.hunter     = None
        self.viewer     = None
        self._log_q     = queue.Queue()
        self._t_start   = None
        self._cur_game  = None
        self._cur_start = None
        self.detection_marker_timestamp = None  # User-marked detection point
        self.detection_marker_step = None       # Corresponding step number

        os.makedirs(SEQUENCES_DIR, exist_ok=True)

        # Restore detector state from previous session
        self.detector.init()
        if self.cfg.get("game_region"):
            self.detector.set_region(**self.cfg["game_region"])
        if self.cfg.get("star_zone"):
            self.detector.set_star_zone(**self.cfg["star_zone"])
            # Try to load saved baseline from disk
            if self.detector.load_baseline_from_disk():
                pass  # baseline restored

        self._build_ui()
        self._poll_log()
        self._restore_selection()

        if self.detector._baseline_set:
            self._log("📐  Baseline loaded from previous session")

        if MISSING:
            self.root.after(800, lambda: messagebox.showwarning(
                "Missing dependencies",
                f"Run:  pip install {' '.join(MISSING)}\nthen rebuild the exe."))

    # ── Config ────────────────────────────────────────────────────

    def _load_cfg(self) -> dict:
        cfg = {}
        if os.path.exists("shiny_hunter_config.json"):
            try:
                with open("shiny_hunter_config.json") as f:
                    cfg = json.load(f)
            except:
                pass
        cfg["keys"] = DEFAULT_KEYS.copy()
        return cfg

    def _save_cfg(self):
        try:
            with open("shiny_hunter_config.json","w") as f:
                json.dump(self.cfg, f, indent=2)
        except:
            pass

    # ── UI Build ──────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg="#04040e", pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text="✨  SHINY HUNTER  ✨",
                 font=FONT_HDR, fg=GOLD, bg="#04040e").pack()
        tk.Label(hdr,
                 text=f"Universal Edition  ·  Epilogue GB Operator  ·  v{APP_VERSION}",
                 font=FONT_MONO, fg=FG_DIM, bg="#04040e").pack()

        # ── Main body ─────────────────────────────────────────────
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=6, pady=6)

        # Left sidebar — game/starter selector
        self._build_sidebar(body)

        # Right — notebook
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG3, foreground=FG_DIM,
                        font=FONT_MED, padding=[12,4])
        style.map("TNotebook.Tab",
                  background=[("selected",BG2)],
                  foreground=[("selected",GOLD)])

        nb = ttk.Notebook(body)
        self._tab_hunt    = self._build_hunt_tab(nb)
        self._tab_record  = self._build_record_tab(nb)
        self._tab_keys    = self._build_keys_tab(nb)
        self._tab_region  = self._build_region_tab(nb)
        self._tab_scanner = self._build_scanner_tab(nb)
        self._tab_guide   = tk.Frame(nb, bg=BG)

        nb.add(self._tab_hunt,    text="  🎮  Hunt  ")
        nb.add(self._tab_record,  text="  ⏺  Record  ")
        nb.add(self._tab_keys,    text="  ⌨️   Keys  ")
        nb.add(self._tab_region,  text="  📐  Region  ")
        nb.add(self._tab_scanner, text="  🔬  Scanner  ")
        nb.add(self._tab_guide,   text="  📖  Guide  ")
        
        # Build guide tab content
        self._build_guide_tab()

        nb.pack(side="left", fill="both", expand=True)

    # ── Sidebar ───────────────────────────────────────────────────

    def _build_sidebar(self, parent):
        sb = tk.Frame(parent, bg=BG2, width=200)
        sb.pack(side="left", fill="y", padx=(0,4))
        sb.pack_propagate(False)

        tk.Label(sb, text="SELECT GAME", font=("Courier New",8,"bold"),
                 fg=FG_DIM, bg=BG2).pack(pady=(10,2))

        # Gen tabs
        tabs = tk.Frame(sb, bg=BG2)
        tabs.pack(fill="x", padx=4)
        self._gen_btns = {}
        for g, lbl in [(2,"Game Boy"),(3,"GBA")]:
            b = tk.Button(tabs, text=lbl, font=("Courier New",8),
                          command=lambda x=g: self._switch_gen(x))
            b.pack(side="left", fill="x", expand=True, padx=1)
            self._gen_btns[g] = b
        self._highlight_gen(2)

        # Game list
        lf = tk.Frame(sb, bg=BG2)
        lf.pack(fill="x", padx=4, pady=4)
        self._game_lb = tk.Listbox(lf, font=("Courier New",9),
                                   bg=BG3, fg=FG, selectbackground="#2a2a6a",
                                   selectforeground=GOLD, borderwidth=0,
                                   highlightthickness=0, height=5)
        self._game_lb.pack(fill="x")
        self._game_lb.bind("<<ListboxSelect>>", self._on_game_sel)

        # Starter buttons
        tk.Label(sb, text="SELECT STARTER", font=("Courier New",8,"bold"),
                 fg=FG_DIM, bg=BG2).pack(pady=(8,2))
        self._starter_frame = tk.Frame(sb, bg=BG2)
        self._starter_frame.pack(fill="x", padx=4, pady=4)
        self._starter_btns = []

        # Notes
        self._notes_var = tk.StringVar()
        tk.Label(sb, textvariable=self._notes_var,
                 font=("Courier New",7), fg="#8888bb", bg=BG2,
                 wraplength=185, justify="left").pack(padx=6, pady=4, anchor="w")

        self._switch_gen(2)

    def _switch_gen(self, gen):
        self._highlight_gen(gen)
        games = [g for g in GAMES if g.gen==gen]
        self._game_lb.delete(0,"end")
        for g in games:
            self._game_lb.insert("end", g.name)
        if games:
            self._game_lb.selection_set(0)
            self._select_game(games[0])

    def _highlight_gen(self, gen):
        for g, b in self._gen_btns.items():
            b.config(bg="#2a2a5a" if g==gen else BG3,
                     fg=GOLD if g==gen else FG_DIM,
                     activebackground="#2a2a5a" if g==gen else BG3,
                     activeforeground=GOLD if g==gen else FG_DIM,
                     relief="flat")

    def _on_game_sel(self, _=None):
        sel = self._game_lb.curselection()
        if sel:
            g = GAME_BY_NAME.get(self._game_lb.get(sel[0]))
            if g:
                self._select_game(g)

    def _select_game(self, game):
        # Check if GBA game (Gen 3) - require password
        if game.gen == 3:  # Ruby, Sapphire, Emerald, FireRed, LeafGreen
            # Check if password already verified this session
            if not hasattr(self, '_gba_unlocked') or not self._gba_unlocked:
                from tkinter import simpledialog
                # Show password dialog
                password = simpledialog.askstring(
                    "GBA Games Access",
                    f"{game.name} is a Gen 3 GBA game.\n\n"
                    "GBA support is currently in testing.\n"
                    "Enter access code to continue:",
                    parent=self.root,
                    show='*'
                )
                
                if password != "3300":
                    messagebox.showwarning(
                        "Access Denied",
                        f"Incorrect code. {game.name} cannot be selected.\n\n"
                        "Only Gen 2 (Gold/Silver/Crystal) games are fully supported at this time."
                    )
                    return
                
                # Password correct - unlock GBA for this session
                self._gba_unlocked = True
                messagebox.showinfo(
                    "GBA Access Granted",
                    f"GBA games unlocked for this session.\n\n"
                    "Note: GBA detection is experimental. "
                    "Gen 2 games are recommended for best results."
                )
        
        self._cur_game  = game
        self._cur_start = None
        for w in self._starter_frame.winfo_children():
            w.destroy()
        self._starter_btns.clear()
        for s in game.starters:
            tc = TYPE_COLOR.get(s.type1,"#555577")
            b = tk.Button(self._starter_frame,
                          text=f"{s.emoji}  {s.name}\n{s.type1}",
                          font=("Courier New",9,"bold"), bg=BG3, fg=FG,
                          activebackground=tc, activeforeground="white",
                          relief="flat", cursor="hand2", padx=4, pady=5,
                          command=lambda _s=s: self._pick_starter(_s))
            b.pack(fill="x", pady=2)
            self._starter_btns.append((b, s, tc))
        self._notes_var.set(game.notes)
        self._log(f"📌  {game.name}")
        self.cfg["last_game"] = game.name
        self._save_cfg()

        # Set detection mode based on game's detection_hint
        old_mode = self.detector.detection_mode
        hint = game.detection_hint

        # "auto" → gen 2 = star, gen 3 = sprite
        if hint == "auto":
            hint = "star" if game.gen <= 2 else "sprite"

        if hint == "sprite":
            self.detector.detection_mode = ShinyDetector.MODE_SPRITE_DIFF
            self.detector._game_hint = "sprite"
            self.detector._game_gen  = game.gen
            if hasattr(self, "_pre_check_wait_var"):
                if self._pre_check_wait_var.get() == 0.0:
                    self._pre_check_wait_var.set(3.0)
            if hasattr(self, "_use_sparkle_var"):
                self._use_sparkle_var.set(False)
        elif hint == "star" and game.gen >= 3:
            # FireRed / LeafGreen — gold ★ on summary screen.
            # Use sprite_diff: baseline = blank corner, shiny = gold star.
            # Dark-pixel mode won't work because the star is bright YELLOW.
            self.detector.detection_mode = ShinyDetector.MODE_SPRITE_DIFF
            self.detector._game_hint = "star"
            self.detector._game_gen  = game.gen
            if hasattr(self, "_pre_check_wait_var"):
                self._pre_check_wait_var.set(0.0)
            if hasattr(self, "_use_sparkle_var"):
                self._use_sparkle_var.set(False)
        else:
            # Gen II — ✦ star icon, dark ink, on status screen
            self.detector.detection_mode = ShinyDetector.MODE_DARK_PIXEL
            self.detector._game_hint = "star"
            self.detector._game_gen  = game.gen
            if hasattr(self, "_pre_check_wait_var"):
                self._pre_check_wait_var.set(0.0)
            if hasattr(self, "_use_sparkle_var"):
                self._use_sparkle_var.set(False)
        if old_mode != self.detector.detection_mode:
            # Mode changed → previous baseline is invalid
            self.detector.clear_baseline()
            self._log(f"🔄  Detection mode → {self.detector.detection_mode} "
                      f"(re-capture baseline)")
        # Refresh region tab labels if it's been built
        self._refresh_region_labels()
        self._update_scanner_mode_label()

    def _pick_starter(self, s):
        self._cur_start = s
        tc = TYPE_COLOR.get(s.type1,"#555577")
        for b, st, col in self._starter_btns:
            b.config(bg=col if st is s else BG3,
                     fg="white" if st is s else FG)
        self._log(f"🎯  {s.emoji} {s.name}")
        self.cfg["last_starter"] = s.name
        self._save_cfg()

    def _restore_selection(self):
        gn = self.cfg.get("last_game","Pokémon Silver")
        sn = self.cfg.get("last_starter","Cyndaquil")
        game = GAME_BY_NAME.get(gn)
        if not game:
            return
        self._switch_gen(game.gen)
        for i in range(self._game_lb.size()):
            if self._game_lb.get(i) == gn:
                self._game_lb.selection_clear(0,"end")
                self._game_lb.selection_set(i)
                self._select_game(game)
                break
        for b, s, col in self._starter_btns:
            if s.name == sn:
                self._pick_starter(s)
                break

    # ── Hunt Tab ──────────────────────────────────────────────────

    def _build_hunt_tab(self, nb):
        f = tk.Frame(nb, bg=BG)

        # Status banner
        top = tk.Frame(f, bg="#080820", pady=6)
        top.pack(fill="x")
        self._status_var = tk.StringVar(value="Load a sequence, then press START HUNTING ▶")
        tk.Label(top, textvariable=self._status_var,
                 font=("Courier New",11,"bold"), fg=GREEN_HI, bg="#080820").pack()

        # Stats row
        sr = tk.Frame(f, bg=BG, pady=3)
        sr.pack(fill="x", padx=12)
        self._resets_var  = tk.StringVar(value="Resets: 0")
        self._prob_var    = tk.StringVar(value="Probability: 0.000%")
        self._elapsed_var = tk.StringVar(value="Elapsed: 0:00:00.000")
        for v in (self._resets_var, self._prob_var, self._elapsed_var):
            tk.Label(sr, textvariable=v, font=FONT_MONO,
                     fg=FG_DIM, bg=BG).pack(side="left", expand=True)

        style = ttk.Style()
        style.configure("Gold.Horizontal.TProgressbar",
                        troughcolor=BG3, background=GOLD,
                        bordercolor=BG, lightcolor=GOLD, darkcolor=GOLD)
        self._pbar = ttk.Progressbar(f, maximum=100,
                                     style="Gold.Horizontal.TProgressbar")
        self._pbar.pack(fill="x", padx=12, pady=(2,4))

        # Countdown label
        self._countdown_var = tk.StringVar(value="")
        tk.Label(f, textvariable=self._countdown_var,
                 font=("Courier New",28,"bold"), fg=GOLD, bg=BG).pack(pady=(0,2))

        # Sequence info bar
        seq_bar = tk.Frame(f, bg=BG3, pady=4)
        seq_bar.pack(fill="x", padx=12, pady=(0,4))
        self._seq_name_var = tk.StringVar(value="No sequence loaded")
        self._seq_steps_var = tk.StringVar(value="0 steps")
        tk.Label(seq_bar, text="Sequence:", font=FONT_MONO,
                 fg=FG_DIM, bg=BG3).pack(side="left", padx=8)
        tk.Label(seq_bar, textvariable=self._seq_name_var,
                 font=("Courier New",9,"bold"), fg=GOLD, bg=BG3).pack(side="left")
        tk.Label(seq_bar, textvariable=self._seq_steps_var,
                 font=FONT_MONO, fg=FG_DIM, bg=BG3).pack(side="right", padx=8)

        # Buttons
        br = tk.Frame(f, bg=BG, pady=4)
        br.pack()
        self._start_btn = _btn(br, "▶  START HUNTING", self.start_hunting,
                               bg="#1a7a3a", padx=16, pady=8, font=FONT_BIG)
        self._start_btn.pack(side="left", padx=6)
        self._stop_btn = _btn(br, "■  STOP", self.stop_hunting,
                              bg="#7a1a1a", padx=16, pady=8,
                              font=FONT_BIG, state="disabled")
        self._stop_btn.pack(side="left", padx=6)

        # Pre-check wait (critical for Gen III battle animation)
        wait_row = tk.Frame(f, bg=BG, pady=2)
        wait_row.pack()
        tk.Label(wait_row, text="Pre-check wait:",
                 font=FONT_MONO, fg=FG_DIM, bg=BG).pack(side="left", padx=(0,4))
        self._pre_check_wait_var = tk.DoubleVar(value=0.0)
        tk.Spinbox(wait_row, from_=0.0, to=10.0, increment=0.5,
                   textvariable=self._pre_check_wait_var, width=5,
                   font=FONT_MONO, bg=BG3, fg=FG,
                   buttonbackground=BG3).pack(side="left")
        tk.Label(wait_row,
                 text="seconds  (Gen II: 0   Gen III: 3–4)",
                 font=FONT_MONO, fg=FG_DIM, bg=BG).pack(side="left", padx=6)

        # Sparkle detection (Gen III only — runs during the pre-check wait)
        sparkle_row = tk.Frame(f, bg=BG, pady=2)
        sparkle_row.pack()
        self._use_sparkle_var = tk.BooleanVar(value=False)
        tk.Checkbutton(sparkle_row, text="✨  Sparkle detection (enable for Torchic)",
                       variable=self._use_sparkle_var,
                       font=FONT_MONO, fg=FG, bg=BG,
                       selectcolor=BG3,
                       activebackground=BG,
                       activeforeground=GOLD).pack(side="left", padx=(0,12))
        tk.Label(sparkle_row, text="Sensitivity:",
                 font=FONT_MONO, fg=FG_DIM, bg=BG).pack(side="left")
        self._sparkle_sens_var = tk.DoubleVar(value=1.0)
        tk.Spinbox(sparkle_row, from_=0.5, to=3.0, increment=0.1,
                   textvariable=self._sparkle_sens_var, width=5,
                   font=FONT_MONO, bg=BG3, fg=FG,
                   buttonbackground=BG3).pack(side="left", padx=4)
        tk.Label(sparkle_row,
                 text="(lower = more sensitive  |  1.0 = default)",
                 font=FONT_MONO, fg=FG_DIM, bg=BG).pack(side="left", padx=4)

        # Log
        lf = tk.LabelFrame(f, text=" Log ", font=FONT_MONO, bg=BG, fg=FG_DIM)
        lf.pack(fill="both", expand=True, padx=10, pady=4)
        self._log_box = scrolledtext.ScrolledText(
            lf, font=("Courier New",8), bg="#060612", fg="#aaaacc",
            insertbackground="#aaaacc", height=14, wrap="word")
        self._log_box.pack(fill="both", expand=True, padx=2, pady=2)

        # Test / Viewer row
        test_row = tk.Frame(f, bg=BG, pady=2)
        test_row.pack()
        self._viewer_btn = _btn(test_row, "👁  Open Live Viewer",
             self.toggle_live_viewer,
             bg="#1a3a2a", fg="#aaffaa", padx=10, pady=5,
             font=("Courier New",9,"bold"))
        self._viewer_btn.pack(side="left", padx=4)
        _btn(test_row, "🧪  Test (live screen)",
             self.test_detection_live,
             bg="#2a3a5a", fg="#aaccff", padx=10, pady=5,
             font=("Courier New",9)).pack(side="left", padx=4)
        _btn(test_row, "🖼  Test (load image)",
             self.test_detection_image,
             bg="#2a3a5a", fg="#aaccff", padx=10, pady=5,
             font=("Courier New",9)).pack(side="left", padx=4)

        tk.Label(f,
                 text="① Record sequence in Record tab  "
                      "② Set game region in Region tab  "
                      "③ START HUNTING\n"
                      "📸 Every status screen is saved to screenshots/ folder  "
                      "|  Emergency stop: move mouse to top-left corner",
                 font=("Courier New",7), fg="#334455", bg=BG,
                 justify="left", wraplength=560
                 ).pack(padx=10, pady=(0,4), anchor="w")

        return f

    # ── Record Tab ────────────────────────────────────────────────

    def _build_record_tab(self, nb):
        f = tk.Frame(nb, bg=BG)
        outer = tk.Frame(f, bg=BG, padx=16, pady=14)
        outer.pack(fill="both", expand=True)

        # Title
        tk.Label(outer, text="Macro Recorder",
                 font=("Courier New",14,"bold"), fg=GOLD, bg=BG).pack(pady=(0,4))
        tk.Label(outer,
                 text="Record your own playthrough once — the app replays it forever.\n"
                      "Your timing is perfect because YOU recorded it.",
                 font=FONT_MONO, fg=FG_DIM, bg=BG, justify="center").pack(pady=(0,12))

        # How-to steps
        steps_frame = tk.LabelFrame(outer, text=" How to Record ",
                                    font=FONT_MONO, bg=BG, fg=FG_DIM, padx=10, pady=8)
        steps_frame.pack(fill="x", pady=(0,12))
        instructions = [
            "① Load your game in Playback and reach your save point",
            "② Select your game and starter in the left sidebar",
            "③ Click RECORD (5-second countdown — switch to Playback during it)",
            "④ Play through the FULL sequence manually in Playback:",
            "      Pick up ball → decline nickname → talk to Prof → open menu → check stats",
            "⑤ Click STOP RECORDING",
            "⑥ Give it a name and SAVE SEQUENCE",
            "⑦ Go to Hunt tab and click START HUNTING",
        ]
        for step in instructions:
            tk.Label(steps_frame, text=step, font=("Courier New",8),
                     fg=FG, bg=BG, anchor="w", justify="left").pack(fill="x", pady=1)

        # Record controls
        rec_frame = tk.Frame(outer, bg=BG2, padx=10, pady=10)
        rec_frame.pack(fill="x", pady=(0,10))

        br = tk.Frame(rec_frame, bg=BG2)
        br.pack()
        self._rec_btn = _btn(br, "⏺  RECORD  (5s countdown)",
                             self._start_record_countdown,
                             bg="#7a1a1a", padx=14, pady=8, font=FONT_BIG)
        self._rec_btn.pack(side="left", padx=6)
        self._stop_rec_btn = _btn(br, "⏹  STOP RECORDING",
                                  self._stop_record,
                                  bg="#3a3a3a", padx=14, pady=8,
                                  font=FONT_BIG, state="disabled")
        self._stop_rec_btn.pack(side="left", padx=6)

        self._rec_status_var = tk.StringVar(value="Ready to record")
        tk.Label(rec_frame, textvariable=self._rec_status_var,
                 font=("Courier New",9,"bold"), fg=GOLD, bg=BG2).pack(pady=(6,0))

        self._rec_steps_var = tk.StringVar(value="0 steps recorded")
        tk.Label(rec_frame, textvariable=self._rec_steps_var,
                 font=FONT_MONO, fg=FG_DIM, bg=BG2).pack()

        # Review & Mark Detection Point
        review_frame = tk.LabelFrame(outer, text=" 🎯 Review & Mark Detection Point ",
                                     font=FONT_MONO, bg=BG, fg=GOLD, padx=10, pady=8)
        review_frame.pack(fill="x", pady=(10,10))
        
        tk.Label(review_frame,
                 text="After recording, playback your sequence and press 'O' when the status screen fully loads.\n"
                      "This tells the app exactly when to check for shinies.",
                 font=FONT_MONO, fg=FG_DIM, bg=BG, justify="center").pack(pady=(0,8))
        
        playback_btn_row = tk.Frame(review_frame, bg=BG)
        playback_btn_row.pack()
        
        self._review_playback_btn = _btn(playback_btn_row, "▶  Playback Sequence",
                                        self._review_playback,
                                        bg="#2a5a2a", padx=12, pady=6, font=FONT_MED,
                                        state="disabled")
        self._review_playback_btn.pack(side="left", padx=4)
        
        self._clear_marker_btn = _btn(playback_btn_row, "✖  Clear Marker",
                                     self._clear_detection_marker,
                                     bg="#5a2a2a", padx=12, pady=6, font=FONT_MED,
                                     state="disabled")
        self._clear_marker_btn.pack(side="left", padx=4)
        
        # Live playback display
        live_frame = tk.Frame(review_frame, bg=BG2, relief="solid", bd=1)
        live_frame.pack(fill="x", pady=8, padx=4)
        
        tk.Label(live_frame, text="Live Playback:", font=("Courier New",9,"bold"),
                 fg=GOLD, bg=BG2, anchor="w").pack(fill="x", padx=6, pady=(4,2))
        
        self._live_playback_var = tk.StringVar(value="Press 'Playback Sequence' to start")
        live_label = tk.Label(live_frame, textvariable=self._live_playback_var,
                             font=("Courier New",10), fg=GREEN_HI, bg=BG2,
                             anchor="w", justify="left", height=3)
        live_label.pack(fill="x", padx=6, pady=(0,4))
        
        # Detection marker status
        marker_status_frame = tk.Frame(review_frame, bg=BG)
        marker_status_frame.pack(fill="x")
        
        tk.Label(marker_status_frame, text="Detection Point:",
                 font=FONT_MED, fg=FG, bg=BG).pack(side="left", padx=(0,6))
        
        self._detection_marker_var = tk.StringVar(value="Not Set")
        tk.Label(marker_status_frame, textvariable=self._detection_marker_var,
                 font=("Courier New",10,"bold"), fg="#ff6666", bg=BG).pack(side="left")
        
        tk.Label(review_frame,
                 text="💡 Tip: Press 'O' the moment stars/sprite appear fully rendered on screen",
                 font=("Courier New",8), fg="#8888aa", bg=BG, justify="center").pack(pady=(6,0))

        # Save / Load
        sl_frame = tk.LabelFrame(outer, text=" Save & Load Sequences ",
                                 font=FONT_MONO, bg=BG, fg=FG_DIM, padx=10, pady=8)
        sl_frame.pack(fill="x", pady=(0,10))

        name_row = tk.Frame(sl_frame, bg=BG)
        name_row.pack(fill="x", pady=(0,6))
        tk.Label(name_row, text="Name:", font=FONT_MED, bg=BG, fg=FG).pack(side="left")
        self._seq_name_entry = tk.Entry(name_row, font=FONT_MED, bg=BG3, fg=FG,
                                        insertbackground=FG, width=28)
        self._seq_name_entry.insert(0, "my_sequence")
        self._seq_name_entry.pack(side="left", padx=8)

        btn_row = tk.Frame(sl_frame, bg=BG)
        btn_row.pack()
        _btn(btn_row, "💾  Save Sequence", self._save_sequence,
             bg="#1a4a8a", padx=10, pady=6, font=FONT_MED).pack(side="left", padx=4)
        _btn(btn_row, "📂  Load Sequence", self._load_sequence,
             bg="#2a3a6a", padx=10, pady=6, font=FONT_MED).pack(side="left", padx=4)
        _btn(btn_row, "🗂  Browse Saved", self._browse_sequences,
             bg="#1a3a2a", padx=10, pady=6, font=FONT_MED).pack(side="left", padx=4)

        # Sequence editor / viewer
        edit_frame = tk.LabelFrame(outer, text=" Recorded Steps (click to edit delay) ",
                                   font=FONT_MONO, bg=BG, fg=FG_DIM, padx=8, pady=6)
        edit_frame.pack(fill="both", expand=True)

        # Treeview of steps
        cols = ("step","key","delay","notes")
        self._seq_tree = ttk.Treeview(edit_frame, columns=cols, show="headings", height=8)
        style = ttk.Style()
        style.configure("Treeview", background=BG3, fieldbackground=BG3,
                        foreground=FG, rowheight=20)
        style.configure("Treeview.Heading", background=BG2, foreground=GOLD)
        for col, w, lbl in [("step",45,"#"),("key",80,"Key"),
                             ("delay",80,"Delay (s)"),("notes",200,"Notes")]:
            self._seq_tree.heading(col, text=lbl)
            self._seq_tree.column(col, width=w, anchor="center" if col!="notes" else "w")
        self._seq_tree.pack(side="left", fill="both", expand=True)
        sb2 = ttk.Scrollbar(edit_frame, orient="vertical",
                            command=self._seq_tree.yview)
        sb2.pack(side="right", fill="y")
        self._seq_tree.configure(yscrollcommand=sb2.set)
        self._seq_tree.bind("<Double-1>", self._edit_step)

        return f

    # ── Keys Tab ──────────────────────────────────────────────────

    def _build_keys_tab(self, nb):
        f = tk.Frame(nb, bg=BG)
        outer = tk.Frame(f, bg=BG, padx=20, pady=14)
        outer.pack(fill="both", expand=True)

        tk.Label(outer, text="GBA / GBC  →  Keyboard",
                 font=("Courier New",13,"bold"), fg=GOLD, bg=BG).grid(
            row=0, column=0, columnspan=2, pady=8)
        tk.Label(outer,
                 text="Match to Playback → Settings → Controls.\n"
                      "Playback defaults: A=X  B=Z  Start=Return  Select=Backspace\n"
                      "L=Q  R=E  Arrows=D-Pad  Soft Reset=R",
                 font=("Courier New",8), fg=FG_DIM, bg=BG, justify="left"
                 ).grid(row=1, column=0, columnspan=2, pady=4, sticky="w")

        self._key_vars = {}
        rows = [("a_button","A Button"),("b_button","B Button"),
                ("start","Start"),("select","Select"),
                ("l_button","L Button"),("r_button","R Button"),
                ("up","D-Pad Up"),("down","D-Pad Down"),
                ("left","D-Pad Left"),("right","D-Pad Right"),
                ("reset_key","Soft Reset")]
        saved = self.cfg.get("keys", DEFAULT_KEYS)
        for i,(k,lbl) in enumerate(rows):
            tk.Label(outer, text=lbl+":", font=FONT_MED, bg=BG, fg=FG,
                     anchor="e").grid(row=i+2, column=0, sticky="e", padx=8, pady=3)
            v = tk.StringVar(value=saved.get(k, DEFAULT_KEYS.get(k,"")))
            self._key_vars[k] = v
            tk.Entry(outer, textvariable=v, width=14, font=FONT_MED,
                     bg=BG3, fg=FG, insertbackground=FG).grid(row=i+2, column=1, padx=4)

        br = tk.Frame(outer, bg=BG)
        br.grid(row=len(rows)+2, column=0, columnspan=2, pady=14)
        _btn(br, "💾  Save Keys", self._save_keys,
             font=FONT_BIG, padx=12, pady=6).pack(side="left", padx=6)
        _btn(br, "↺  Reset Defaults", self._reset_keys,
             bg="#3a2a0a", fg=GOLD, padx=10, pady=6,
             font=FONT_MED).pack(side="left", padx=6)
        return f

    # ── Region Tab ────────────────────────────────────────────────

    def _build_region_tab(self, nb):
        f = tk.Frame(nb, bg=BG)
        outer = tk.Frame(f, bg=BG, padx=16, pady=14)
        outer.pack(fill="both", expand=True)

        tk.Label(outer, text="Detection Setup",
                 font=("Courier New",14,"bold"), fg=GOLD, bg=BG).pack(pady=(0,4))
        tk.Label(outer,
                 text="Two manual zones.  Draw both with your mouse — what you trace\n"
                      "is exactly what gets captured.  No auto-detect, no guessing.",
                 font=FONT_MONO, fg=FG_DIM, bg=BG, justify="center").pack(pady=(0,14))

        # ── STEP 1 — Game area ─────────────────────────────────────
        step1 = tk.LabelFrame(outer, text="  STEP 1 — Game Area  ",
                              font=("Courier New",10,"bold"),
                              bg=BG, fg=GOLD, padx=12, pady=8)
        step1.pack(fill="x", pady=(0,10))

        tk.Label(step1,
                 text="Drag a box around the ENTIRE Playback game area.\n"
                      "(Just the game viewport — exclude the PLAY/DATA toolbar.)\n"
                      "Used for the live preview + saved screenshots.",
                 font=("Courier New",9), fg=FG, bg=BG,
                 justify="center").pack(pady=(0,8))

        _btn(step1, "🟦  Draw Game Area",
             self._pick_region, bg="#1a4a8a", fg="white",
             padx=14, pady=8,
             font=("Courier New",11,"bold")).pack()

        self._region_var = tk.StringVar(
            value="No game area set — draw one above")
        if self.cfg.get("game_region"):
            r = self.cfg["game_region"]
            self._region_var.set(
                f"✅  Game area: {r['width']}×{r['height']}px  "
                f"@ ({r['left']},{r['top']})")
        tk.Label(step1, textvariable=self._region_var,
                 font=("Courier New",9,"bold"), fg=GOLD, bg=BG).pack(pady=(8,0))

        # ── STEP 2 — Detection zone (label/text depends on game gen) ──
        # LabelFrame's title can't be a textvariable, so we drive both the
        # frame label and the instruction text via stored references and
        # update them in _refresh_region_labels().
        self._step2_frame = tk.LabelFrame(outer,
                              text="  STEP 2 — Detection Zone  ",
                              font=("Courier New",10,"bold"),
                              bg=BG, fg=GOLD, padx=12, pady=8)
        self._step2_frame.pack(fill="x", pady=(0,10))

        self._step2_text_var = tk.StringVar()
        tk.Label(self._step2_frame, textvariable=self._step2_text_var,
                 font=("Courier New",9), fg=FG, bg=BG,
                 justify="center").pack(pady=(0,8))

        self._step2_btn_var = tk.StringVar()
        self._step2_btn = _btn(self._step2_frame, "",
             self._pick_star_zone, bg="#4a3a0a", fg=GOLD,
             padx=14, pady=8,
             font=("Courier New",11,"bold"))
        self._step2_btn.config(textvariable=self._step2_btn_var)
        self._step2_btn.pack()

        self._star_zone_var = tk.StringVar(
            value="No zone set — draw one above")
        if self.cfg.get("star_zone"):
            z = self.cfg["star_zone"]
            self._star_zone_var.set(
                f"✅  Zone: {z['width']}×{z['height']}px  "
                f"@ ({z['left']},{z['top']})")
        tk.Label(self._step2_frame, textvariable=self._star_zone_var,
                 font=("Courier New",9,"bold"), fg=GOLD, bg=BG).pack(pady=(8,0))

        # ── STEP 3 — Capture baseline ──────────────────────────────
        self._step3_frame = tk.LabelFrame(outer,
                              text="  STEP 3 — Capture Baseline  ",
                              font=("Courier New",10,"bold"),
                              bg=BG, fg=GOLD, padx=12, pady=8)
        self._step3_frame.pack(fill="x", pady=(0,10))

        self._step3_text_var = tk.StringVar()
        tk.Label(self._step3_frame, textvariable=self._step3_text_var,
                 font=("Courier New",9), fg=FG, bg=BG,
                 justify="center").pack(pady=(0,8))

        _btn(self._step3_frame, "📐  Capture Baseline",
             self._capture_baseline, bg="#2a5a2a", fg="white",
             padx=14, pady=8,
             font=("Courier New",11,"bold")).pack()

        self._baseline_var = tk.StringVar(
            value="✅  Baseline captured" if self.detector._baseline_set
            else "No baseline — capture one above")
        tk.Label(self._step3_frame, textvariable=self._baseline_var,
                 font=("Courier New",9,"bold"),
                 fg=GREEN_HI if self.detector._baseline_set else GOLD,
                 bg=BG).pack(pady=(8,0))
        self._baseline_lbl = self._step3_frame.pack_slaves()[-1]

        # Apply mode-specific labels now
        self._refresh_region_labels()

        # ── Preview ────────────────────────────────────────────────
        preview_frame = tk.LabelFrame(outer, text=" Latest Screenshot Preview  (zone overlay shown) ",
                                       font=FONT_MONO, bg=BG, fg=FG_DIM,
                                       padx=8, pady=6)
        preview_frame.pack(fill="both", expand=True)
        self._preview_lbl = tk.Label(preview_frame,
                                     text="Capture a preview to see the zone overlay",
                                     font=FONT_MONO, fg=FG_DIM, bg=BG3,
                                     width=60, height=10, relief="sunken")
        self._preview_lbl.pack(fill="both", expand=True, pady=4)
        self._preview_img_ref = None
        self._preview_pil     = None   # keep original PIL for export

        btn_row = tk.Frame(preview_frame, bg=BG)
        btn_row.pack(pady=(0, 4))
        _btn(btn_row, "📸  Capture Preview",
             self._capture_preview, bg=BG3, fg=FG_DIM,
             padx=10, pady=4, font=FONT_MONO).pack(side="left", padx=4)
        _btn(btn_row, "💾  Export Preview",
             self._export_preview, bg=BG3, fg=FG_DIM,
             padx=10, pady=4, font=FONT_MONO).pack(side="left", padx=4)

        return f

    # ── Log pump ──────────────────────────────────────────────────

    def _log(self, msg: str):
        self._log_q.put(msg)

    def _poll_log(self):
        try:
            while True:
                msg = self._log_q.get_nowait()
                ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                self._log_box.insert("end", f"[{ts}] {msg}\n")
                self._log_box.see("end")
        except queue.Empty:
            pass
        finally:
            if self.hunter and self.hunter.running and self._t_start:
                elapsed = time.time() - self._t_start
                n = self.hunter.count
                prob = (1-(1-1/SHINY_ODDS)**n)*100 if n else 0.0
                h,r = divmod(int(elapsed),3600); m,s = divmod(r,60)
                ms = int((elapsed-int(elapsed))*1000)
                self._resets_var.set(f"Resets: {n:,}")
                self._prob_var.set(f"Probability: {prob:.3f}%")
                self._elapsed_var.set(f"Elapsed: {h}:{m:02d}:{s:02d}.{ms:03d}")
                self._pbar["value"] = min(prob, 100)
            self.root.after(50, self._poll_log)

    # ── Hunt actions ──────────────────────────────────────────────

    def start_hunting(self):
        if not DEPS_OK:
            messagebox.showerror("Missing deps",
                                 f"pip install {' '.join(MISSING)}")
            return
        if not self._cur_game:
            messagebox.showwarning("No game","Select a game first."); return
        if not self._cur_start:
            messagebox.showwarning("No starter","Select a starter first."); return
        if not self.recorder.events:
            messagebox.showwarning("No sequence",
                "No sequence loaded.\n\nGo to the Record tab, "
                "record your playthrough, then come back here.")
            return

        star_zone = self.cfg.get("star_zone")
        if not star_zone:
            messagebox.showwarning("No detection zone",
                "No detection zone set.\n\n"
                "Go to the Region tab and complete Steps 2 & 3 first.")
            return

        if not self.detector._baseline_set:
            messagebox.showwarning("No baseline",
                "Baseline not captured.\n\n"
                "Go to the Region tab → Step 3 → Capture Baseline.\n\n"
                "Make sure Playback is showing a NON-shiny Pokémon "
                "in the correct screen state (battle screen for Ruby/Sapphire/Emerald, "
                "summary screen for FireRed/LeafGreen/Gold/Silver/Crystal).")
            return

        region = self.cfg.get("game_region")
        if not region:
            if not messagebox.askyesno("No region set",
                "Game region not set — shiny detection may be less accurate.\n\n"
                "Continue anyway?"):
                return

        # Init detector
        self.detector.init()
        if region:
            self.detector.set_region(**region)
        else:
            try:
                with mss.mss() as sct:
                    m = sct.monitors[1]
                    self.detector.set_region(m["left"],m["top"],m["width"],m["height"])
            except:
                pass

        self._start_btn.config(state="disabled")
        self._stop_btn.config(state="normal")

        def _launch():
            self._t_start = time.time()
            self.hunter = HunterLoop(
                recorder  = self.recorder,
                detector  = self.detector,
                game      = self._cur_game,
                starter   = self._cur_start,
                log_fn    = self._log,
                status_fn = lambda m: self.root.after(0,
                              lambda: self._status_var.set(m)),
                shiny_fn  = lambda n,s,g: self.root.after(0,
                              lambda: self._on_shiny(n,s,g)),
                reset_key       = self.cfg.get("keys",DEFAULT_KEYS).get("reset_key","r"),
                region          = self.cfg.get("game_region"),
                use_screen_sync = self.cfg.get("use_screen_sync", True),
                live_viewer     = self.viewer,
            )
            # Pass the pre-check wait and sparkle settings into the loop
            self.hunter.pre_check_wait       = float(self._pre_check_wait_var.get())
            self.hunter.use_sparkle_detection = bool(self._use_sparkle_var.get())
            self.hunter.sparkle_sensitivity   = float(self._sparkle_sens_var.get())
            # Pass detection marker step if set
            if hasattr(self, 'detection_marker_step') and self.detection_marker_step is not None:
                self.hunter.detection_marker_step = self.detection_marker_step
                self._log(f"🎯  Using detection marker at step {self.detection_marker_step+1}")
            self.hunter.start()

        self._countdown(5, _launch)

    def _countdown(self, n, callback):
        self._countdown_var.set(f"Starting in  {n}…")
        self._status_var.set(f"⏱  Switch to Playback now!  Starting in {n}s…")
        if n > 0:
            self.root.after(1000, lambda: self._countdown(n-1, callback))
        else:
            self._countdown_var.set("")
            callback()

    def stop_hunting(self):
        if self.hunter:
            self.hunter.stop()
        self._start_btn.config(state="normal")
        self._stop_btn.config(state="disabled")

    def toggle_live_viewer(self):
        """Open or close the live star detection viewer window."""
        if self.viewer and self.viewer.running:
            self.viewer.stop()
            self.viewer = None
            self._viewer_btn.config(text="👁  Open Live Viewer", bg="#1a3a2a", fg="#aaffaa")
            self._log("👁  Live viewer closed")
            return

        self.detector.init()
        star_zone = self.cfg.get("star_zone")
        if star_zone:
            self.detector.set_star_zone(**star_zone)
            self._log(f"Star zone loaded: {star_zone['width']}x{star_zone['height']}px")
        else:
            messagebox.showwarning("No star zone",
                "No star detection zone set.\n\n"
                "Go to the Region tab and draw the star zone first.")
            return
        region = self.cfg.get("game_region")
        if not region:
            messagebox.showwarning("No game area",
                "No game area set.\n\n"
                "Go to the Region tab and draw the game area first.")
            return
        self.detector.set_region(**region)

        def _on_viewer_shiny():
            # Live viewer saw stars — trigger full stop
            self._log("👁  Live viewer detected stars — STOPPING HUNT!")
            if self.hunter:
                self.hunter.stop()
            n = self.hunter.count if self.hunter else 0
            starter = self._cur_start
            game    = self._cur_game
            if starter and game:
                self.root.after(0, lambda: self._on_shiny(n, starter, game))

        self.viewer = LiveViewer(
            detector           = self.detector,
            on_shiny_detected  = _on_viewer_shiny,
            log_fn             = self._log,
        )
        self.viewer.start(self.root)
        self._viewer_btn.config(text="👁  Close Live Viewer", bg="#7a1a1a", fg="white")
        self._log("👁  Live viewer opened — watching for stars")
        self._log("    Green boxes = detected star clusters")
        self._log("    Red flash + full stop = shiny found!")

    def test_detection_live(self):
        """
        Grab the star zone RIGHT NOW and compare it to the baseline.
        Shows baseline preview + current preview side by side.
        """
        star_zone = self.cfg.get("star_zone")
        if not star_zone:
            messagebox.showwarning("No star zone",
                "Draw the star detection zone on the Region tab first.")
            return

        # Ensure detector is set up
        self.detector.init()
        self.detector.set_star_zone(**star_zone)
        if self.cfg.get("game_region"):
            self.detector.set_region(**self.cfg["game_region"])

        # Grab current state of the star zone
        cur_zone = self.detector._grab_zone()
        if cur_zone is None:
            messagebox.showerror("Capture failed",
                "Could not capture the star zone.\n\n"
                "Re-draw the star detection zone on the Region tab.")
            return

        # Baseline check
        if not self.detector._baseline_set:
            self._show_no_baseline_popup(cur_zone)
            return

        # Compute diff (used by both modes)
        bl = self.detector._baseline
        if cur_zone.size != bl.size:
            cur_zone = cur_zone.resize(bl.size, Image.LANCZOS)
        diff = _mean_abs_diff(cur_zone, bl)

        if self.detector.detection_mode == ShinyDetector.MODE_SPRITE_DIFF:
            threshold = self.detector.get_sprite_threshold()
            is_shiny  = diff >= threshold
            self._log(
                f"🧪  TEST (Gen III sprite) — diff: {diff:.2f}  "
                f"(>{threshold:.1f} = shiny)  "
                f"→ {'🌟 SHINY' if is_shiny else '❌ not shiny'}")
            self._show_test_popup(cur_zone, diff, is_shiny,
                                  dark_pct=None,
                                  hit_diff=is_shiny,
                                  hit_dark=None)
        else:
            dark_pct = _dark_pixel_pct(cur_zone)
            base_dark = self.detector._baseline_dark_pct
            dark_threshold = base_dark + 0.05
            hit_dark = dark_pct >= dark_threshold
            is_shiny = hit_dark
            self._log(
                f"🧪  TEST (Gen II stars) — dark: {dark_pct*100:.1f}% "
                f"(>{dark_threshold*100:.1f}%={'YES' if hit_dark else 'no'})  "
                f"diff={diff:.2f} (informational)  "
                f"→ {'🌟 SHINY' if is_shiny else '❌ not shiny'}")
            self._show_test_popup(cur_zone, diff, is_shiny,
                                  dark_pct=dark_pct,
                                  hit_diff=True,
                                  hit_dark=hit_dark)

    def test_detection_image(self):
        """Load an image file and test shiny detection on it."""
        path = filedialog.askopenfilename(
            title="Open status screen image",
            filetypes=[("Images","*.png *.jpg *.jpeg *.bmp"),("All","*.*")])
        if not path:
            return
        if not self.detector._baseline_set:
            messagebox.showwarning("No baseline",
                "Capture a baseline first (Region tab → Capture Baseline).")
            return
        try:
            pil = Image.open(path).convert("RGB")
            bl  = self.detector._baseline
            pil_r = pil.resize(bl.size, Image.LANCZOS)
            diff = _mean_abs_diff(pil_r, bl)
            if self.detector.detection_mode == ShinyDetector.MODE_SPRITE_DIFF:
                threshold = self.detector.get_sprite_threshold()
                is_shiny  = diff >= threshold
            else:
                threshold = self.detector.DIFF_THRESHOLD
                is_shiny  = diff >= threshold
            self._log(f"🧪  TEST (file) — diff: {diff:.2f}  "
                      f"(>{threshold:.1f}={is_shiny})  "
                      f"→ {'🌟 SHINY' if is_shiny else '❌ not shiny'}")
            self._show_test_popup(pil_r, diff, is_shiny)
        except Exception as e:
            messagebox.showerror("Load failed", str(e))

    def _show_no_baseline_popup(self, cur_zone):
        """Big clear popup: no baseline, here's how to fix it."""
        popup = tk.Toplevel(self.root)
        popup.title("Baseline Not Set")
        popup.configure(bg=BG)
        popup.geometry("480x420")

        tk.Label(popup, text="⚠️  Baseline Not Set",
                 font=("Courier New",14,"bold"), fg="#ff8800", bg=BG).pack(pady=10)
        tk.Label(popup,
                 text="Detection compares the live zone to a NON-shiny snapshot\n"
                      "of the same zone.  No snapshot exists yet.\n\n"
                      "To fix:\n"
                      "  1.  Open Playback on a NON-shiny status screen\n"
                      "  2.  Go to the Region tab\n"
                      "  3.  Click  📐  Capture Baseline",
                 font=FONT_MONO, fg=FG, bg=BG, justify="left").pack(pady=8, padx=16)

        # Show what the zone currently sees
        try:
            from PIL import ImageTk, Image as PI
            zone_pil = PI.fromarray(cur_zone[:, :, ::-1])  # BGR → RGB
            zw, zh = zone_pil.size
            scale = max(1, 200 // max(zw, zh))
            zone_pil = zone_pil.resize((zw * scale, zh * scale), PI.NEAREST)
            tkimg = ImageTk.PhotoImage(zone_pil)
            tk.Label(popup, text=f"Star zone currently sees ({zw}×{zh}px):",
                     font=FONT_MONO, fg=FG_DIM, bg=BG).pack(pady=(8,2))
            lbl = tk.Label(popup, image=tkimg, bg=BG, relief="solid", borderwidth=1)
            lbl.image = tkimg
            lbl.pack()
        except Exception:
            pass

        _btn(popup, "Close", popup.destroy,
             bg=BG3, fg=FG, padx=12, pady=6, font=FONT_MED).pack(pady=12)

    def _show_test_popup(self, cur_zone_arr, diff, is_shiny,
                         dark_pct=None, hit_diff=None, hit_dark=None):
        """Show baseline preview + current zone preview + result."""
        popup = tk.Toplevel(self.root)
        popup.title("Shiny Detection Test")
        popup.configure(bg=BG)
        popup.geometry("580x520")

        result = "🌟 SHINY DETECTED" if is_shiny else "❌ Not shiny"
        color  = "#FFD700" if is_shiny else "#ff6666"

        tk.Label(popup, text="🧪  Detection Test Result",
                 font=("Courier New",13,"bold"), fg=GOLD, bg=BG).pack(pady=8)
        tk.Label(popup, text=result,
                 font=("Courier New",16,"bold"), fg=color, bg=BG).pack(pady=4)

        # Show BOTH method results
        base_dark = self.detector._baseline_dark_pct
        dt = self.detector.DIFF_THRESHOLD
        kt = base_dark + 0.06

        if dark_pct is None:
            tk.Label(popup,
                     text=(f"Zone diff: {diff:.2f}  "
                           f"(threshold {dt})"),
                     font=FONT_MONO, fg=FG, bg=BG).pack(pady=2)
        else:
            check_d = "✓" if hit_diff else "✗"
            check_k = "✓" if hit_dark else "✗"
            tk.Label(popup,
                     text=(f"Method 1 — pixel diff:  {diff:6.2f}  "
                           f"(>{dt}={check_d})"),
                     font=FONT_MONO, fg="#aaffaa" if hit_diff else "#ffaaaa",
                     bg=BG).pack(pady=1)
            tk.Label(popup,
                     text=(f"Method 2 — dark pixels: {dark_pct*100:5.1f}%  "
                           f"(>{kt*100:.1f}%={check_k})"),
                     font=FONT_MONO, fg="#aaffaa" if hit_dark else "#ffaaaa",
                     bg=BG).pack(pady=1)
            tk.Label(popup,
                     text=("BOTH methods must agree to trigger SHINY"),
                     font=FONT_MONO, fg=FG_DIM, bg=BG).pack(pady=(2,4))

        # Side-by-side: baseline | current
        try:
            from PIL import ImageTk, Image as PI
            wrap = tk.Frame(popup, bg=BG)
            wrap.pack(pady=12)

            def _make_preview(pil_img, label, parent):
                if not isinstance(pil_img, Image.Image):
                    return
                img = pil_img.convert("RGB")
                w, h = img.size
                scale = max(1, 180 // max(w, h))
                img = img.resize((w * scale, h * scale), Image.NEAREST)
                tkimg = ImageTk.PhotoImage(img)
                col = tk.Frame(parent, bg=BG)
                col.pack(side="left", padx=14)
                tk.Label(col, text=label, font=FONT_MONO,
                         fg=FG_DIM, bg=BG).pack()
                ilbl = tk.Label(col, image=tkimg, bg=BG,
                                relief="solid", borderwidth=1)
                ilbl.image = tkimg
                ilbl.pack()

            _make_preview(self.detector._baseline,
                          "BASELINE (non-shiny)", wrap)
            _make_preview(cur_zone_arr,
                          "CURRENT (live)", wrap)
        except Exception as e:
            tk.Label(popup, text=f"(Preview unavailable: {e})",
                     font=FONT_MONO, fg=FG_DIM, bg=BG).pack()

        if is_shiny:
            tk.Label(popup,
                     text="⚠️  SHINY detected! Hunt would stop and alarm would sound.",
                     font=FONT_MONO, fg=GOLD, bg=BG, justify="center"
                     ).pack(pady=6)
            threading.Thread(target=play_alarm, daemon=True).start()

        _btn(popup, "Close", popup.destroy,
             bg=BG3, fg=FG, padx=12, pady=6, font=FONT_MED).pack(pady=8)

    def _on_shiny(self, n, starter, game):
        self._start_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
        threading.Thread(target=play_alarm, daemon=True).start()
        # Big warning dialog — stays on screen until dismissed
        messagebox.showwarning(
            "🌟  SHINY FOUND — DO NOT CLOSE PLAYBACK!",
            f"✨  SHINY {starter.name.upper()} FOUND! ✨\n\n"
            f"Game: {game.name}\n"
            f"Resets: {n:,}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️   THE GAME HAS NOT BEEN RESET\n"
            f"⚠️   GO TO PLAYBACK AND SAVE NOW!\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Do NOT click OK until AFTER you have saved in Playback!"
        )

    # ── Record actions ────────────────────────────────────────────

    def _start_record_countdown(self):
        if not PYNPUT_OK:
            messagebox.showerror("Missing dep",
                "pynput not installed.\nRun: pip install pynput  then rebuild.")
            return
        self._rec_btn.config(state="disabled")
        self._rec_status_var.set("Get ready — switching to Playback…")

        def _cd(n):
            if n > 0:
                self._rec_status_var.set(
                    f"⏺  Recording starts in {n}s — switch to Playback!")
                self.root.after(1000, lambda: _cd(n-1))
            else:
                self._rec_status_var.set("⏺  RECORDING — play through the sequence!")
                self.recorder.log_fn = self._log
                if self.recorder.start_recording():
                    self._stop_rec_btn.config(state="normal")
                    self._log("⏺  Recording started!")
                    self._log("    Ball → nickname NO → professor → menu → stats")
                    self._log("    Click STOP RECORDING when done")

        _cd(5)

    def _stop_record(self):
        events = self.recorder.stop_recording()
        self._rec_btn.config(state="normal")
        self._stop_rec_btn.config(state="disabled")
        if not events:
            self._rec_status_var.set("⚠️  Nothing recorded")
            self._review_playback_btn.config(state="disabled")
            return
        self._rec_status_var.set(f"✅  Recorded {len(events)} steps")
        self._rec_steps_var.set(f"{len(events)} steps recorded")
        self._refresh_tree()
        self._update_hunt_seq_bar()
        self._log(f"✅  Recorded {len(events)} steps")
        self._log("    Give it a name and click Save Sequence")
        self._log("    Or playback to mark detection point")
        # Enable playback button for review
        self._review_playback_btn.config(state="normal")

    def _refresh_tree(self):
        self._seq_tree.delete(*self._seq_tree.get_children())
        for i, evt in enumerate(self.recorder.events):
            notes = ""
            if i == 0:
                notes = "First press — ball interaction"
            elif evt["key"] == "down":
                notes = "Navigate to NO (nickname)"
            elif evt["key"] == "return":
                notes = "Open START menu"
            self._seq_tree.insert("", "end", iid=str(i),
                values=(i+1, evt["key"], f"{evt['delay']:.3f}", notes))

    def _edit_step(self, event):
        """Double-click a step to edit its delay."""
        sel = self._seq_tree.selection()
        if not sel:
            return
        idx   = int(sel[0])
        evt   = self.recorder.events[idx]
        popup = tk.Toplevel(self.root)
        popup.title(f"Edit Step {idx+1}")
        popup.configure(bg=BG)
        popup.geometry("300x160")
        popup.resizable(False, False)

        tk.Label(popup, text=f"Step {idx+1}:  key = {evt['key']}",
                 font=FONT_MED, bg=BG, fg=FG).pack(pady=(12,4))
        tk.Label(popup, text="Delay (seconds):", font=FONT_MED,
                 bg=BG, fg=FG).pack()
        delay_var = tk.StringVar(value=str(evt["delay"]))
        e = tk.Entry(popup, textvariable=delay_var, font=FONT_MED,
                     bg=BG3, fg=FG, insertbackground=FG, width=12,
                     justify="center")
        e.pack(pady=4)
        e.focus()
        e.select_range(0,"end")

        def _save():
            try:
                self.recorder.events[idx]["delay"] = float(delay_var.get())
                self._refresh_tree()
                popup.destroy()
                self._log(f"✏️  Step {idx+1} delay → {delay_var.get()}s")
            except:
                messagebox.showerror("Invalid","Enter a number e.g. 1.5",parent=popup)

        _btn(popup, "✔  Save", _save, bg="#1a7a3a",
             padx=12, pady=6, font=FONT_MED).pack(pady=8)
        popup.bind("<Return>", lambda e: _save())

    def _review_playback(self):
        """Play back the recorded sequence with live display, allowing user to mark detection point."""
        if not self.recorder.events:
            messagebox.showwarning("No Sequence","Record a sequence first.")
            return
        
        self._live_playback_var.set("▶ Starting playback...\nPress 'O' when status screen loads")
        self._review_playback_btn.config(state="disabled")
        self._log("▶ Review playback started — Press 'O' to mark detection point")
        
        # Flag to track if we're in review mode
        self._review_mode = True
        self._review_start_time = time.time()
        
        # Bind 'O' key globally during review
        self.root.bind('o', self._mark_detection_point)
        self.root.bind('O', self._mark_detection_point)
        
        def _playback_thread():
            try:
                import pyautogui
                
                for i, evt in enumerate(self.recorder.events):
                    if not self._review_mode:
                        break
                    
                    # Update live display
                    elapsed = time.time() - self._review_start_time
                    next_step = f"Step {i+2}/{len(self.recorder.events)}: {self.recorder.events[i+1]['key'].upper()}" if i < len(self.recorder.events)-1 else "End of sequence"
                    self.root.after(0, lambda s=i, e=elapsed, n=next_step: 
                        self._live_playback_var.set(
                            f"▶ Step {s+1}/{len(self.recorder.events)}: {evt['key'].upper()}\n"
                            f"  Elapsed: {e:.2f}s | Next: {n}\n"
                            f"  Press 'O' when status screen fully loads"
                        ))
                    
                    # Execute the keystroke using pyautogui
                    try:
                        pyautogui.press(evt["key"])
                    except:
                        # If key name doesn't work, try lowercase
                        try:
                            pyautogui.press(evt["key"].lower())
                        except:
                            pass
                    
                    # Wait for the delay
                    time.sleep(evt["delay"])
                
                # Playback complete
                self.root.after(0, self._finish_review_playback)
            except Exception as ex:
                self.root.after(0, lambda: self._log(f"⚠️  Playback error: {ex}"))
                self.root.after(0, self._finish_review_playback)
        
        threading.Thread(target=_playback_thread, daemon=True).start()
    
    def _mark_detection_point(self, event=None):
        """Mark the current timestamp as the detection point."""
        if not hasattr(self, '_review_mode') or not self._review_mode:
            return
        
        elapsed = time.time() - self._review_start_time
        self.detection_marker_timestamp = elapsed
        
        # Calculate which step this corresponds to
        cumulative_time = 0.0
        detection_step = 0
        for i, evt in enumerate(self.recorder.events):
            cumulative_time += evt["delay"]
            if cumulative_time >= elapsed:
                detection_step = i
                break
        
        self.detection_marker_step = detection_step
        
        # Update UI
        self._detection_marker_var.set(f"✅ {elapsed:.2f}s (step {detection_step+1})")
        self._detection_marker_var.master.config(fg=GREEN_HI)
        self._clear_marker_btn.config(state="normal")
        
        self._log(f"🎯  Detection point marked at {elapsed:.2f}s (step {detection_step+1}/{len(self.recorder.events)})")
        self._live_playback_var.set(
            f"✅ Detection marked at {elapsed:.2f}s\n"
            f"Step {detection_step+1}/{len(self.recorder.events)}\n"
            f"Continue playback or stop review..."
        )
    
    def _finish_review_playback(self):
        """Clean up after review playback."""
        self._review_mode = False
        self.root.unbind('o')
        self.root.unbind('O')
        self._review_playback_btn.config(state="normal")
        
        if hasattr(self, 'detection_marker_timestamp') and self.detection_marker_timestamp is not None:
            self._live_playback_var.set(
                f"✅ Review complete\n"
                f"Detection point: {self.detection_marker_timestamp:.2f}s\n"
                f"Ready for hunting!"
            )
            self._log("✅  Review complete — detection point set")
        else:
            self._live_playback_var.set("Review complete (no marker set)")
            self._log("ℹ️  Review complete — no detection point marked")
    
    def _clear_detection_marker(self):
        """Clear the detection marker."""
        self.detection_marker_timestamp = None
        self.detection_marker_step = None
        self._detection_marker_var.set("Not Set")
        self._detection_marker_var.master.config(fg="#ff6666")
        self._clear_marker_btn.config(state="disabled")
        self._log("✖  Detection marker cleared")
        self._live_playback_var.set("Press 'Playback Sequence' to mark detection point")

    def _save_sequence(self):
        name = self._seq_name_entry.get().strip() or "my_sequence"
        name = name.replace(" ","_").replace("/","_")
        if not self.recorder.events:
            messagebox.showwarning("Nothing to save","Record a sequence first.")
            return
        meta = {
            "name":    name,
            "game":    self._cur_game.name if self._cur_game else "Unknown",
            "starter": self._cur_start.name if self._cur_start else "Unknown",
            "recorded": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "detection_marker": self.detection_marker_timestamp,  # Save marker timestamp
        }
        path = os.path.join(SEQUENCES_DIR, f"{name}.json")
        if self.recorder.save(path, meta):
            self._log(f"💾  Saved: {path}  ({len(self.recorder.events)} steps)")
            self._update_hunt_seq_bar(name)
            messagebox.showinfo("Saved", f"Sequence saved as:\n{path}")

    def _load_sequence(self):
        path = filedialog.askopenfilename(
            title="Load Sequence",
            initialdir=SEQUENCES_DIR,
            filetypes=[("Sequence files","*.json"),("All files","*.*")])
        if not path:
            return
        if self.recorder.load(path):
            # Load metadata to restore detection marker
            try:
                with open(path) as f:
                    data = json.load(f)
                meta = data.get("metadata", {})
                self.detection_marker_timestamp = meta.get("detection_marker")
                
                # Recalculate step number from timestamp
                if self.detection_marker_timestamp is not None:
                    cumulative_time = 0.0
                    self.detection_marker_step = 0
                    for i, evt in enumerate(self.recorder.events):
                        cumulative_time += evt["delay"]
                        if cumulative_time >= self.detection_marker_timestamp:
                            self.detection_marker_step = i
                            break
                    
                    # Update UI
                    self._detection_marker_var.set(f"✅ {self.detection_marker_timestamp:.2f}s (step {self.detection_marker_step+1})")
                    self._detection_marker_var.master.config(fg=GREEN_HI)
                    self._clear_marker_btn.config(state="normal")
                    self._log(f"🎯  Detection marker loaded: {self.detection_marker_timestamp:.2f}s (step {self.detection_marker_step+1})")
                else:
                    self.detection_marker_step = None
                    self._detection_marker_var.set("Not Set")
                    self._detection_marker_var.master.config(fg="#ff6666")
                    self._clear_marker_btn.config(state="disabled")
            except:
                pass
            
            name = Path(path).stem
            self._seq_name_entry.delete(0,"end")
            self._seq_name_entry.insert(0, name)
            self._refresh_tree()
            self._update_hunt_seq_bar(name)
            self._rec_status_var.set(f"✅  Loaded: {name}  ({len(self.recorder.events)} steps)")
            self._rec_steps_var.set(f"{len(self.recorder.events)} steps")
            self._log(f"📂  Loaded: {path}  ({len(self.recorder.events)} steps)")
            # Enable playback for review
            self._review_playback_btn.config(state="normal")

    def _browse_sequences(self):
        files = list(Path(SEQUENCES_DIR).glob("*.json")) if os.path.isdir(SEQUENCES_DIR) else []
        if not files:
            messagebox.showinfo("No sequences",
                f"No saved sequences found.\nSave your recordings to the '{SEQUENCES_DIR}' folder.")
            return
        popup = tk.Toplevel(self.root)
        popup.title("Saved Sequences")
        popup.configure(bg=BG)
        popup.geometry("420x300")

        tk.Label(popup, text="Saved Sequences", font=FONT_BIG,
                 fg=GOLD, bg=BG).pack(pady=8)
        lb = tk.Listbox(popup, font=FONT_MONO, bg=BG3, fg=FG,
                        selectbackground="#2a2a6a", selectforeground=GOLD,
                        borderwidth=0, highlightthickness=0)
        lb.pack(fill="both", expand=True, padx=10)
        for fp in sorted(files):
            lb.insert("end", fp.stem)

        def _load():
            sel = lb.curselection()
            if not sel:
                return
            path = os.path.join(SEQUENCES_DIR, lb.get(sel[0])+".json")
            popup.destroy()
            if self.recorder.load(path):
                name = Path(path).stem
                self._seq_name_entry.delete(0,"end")
                self._seq_name_entry.insert(0, name)
                self._refresh_tree()
                self._update_hunt_seq_bar(name)
                self._log(f"📂  Loaded: {path}  ({len(self.recorder.events)} steps)")

        _btn(popup, "📂  Load Selected", _load, bg="#1a4a8a",
             padx=10, pady=6, font=FONT_MED).pack(pady=8)

    def _update_hunt_seq_bar(self, name=None):
        if name:
            self._seq_name_var.set(name)
        self._seq_steps_var.set(f"  {len(self.recorder.events)} steps")

    # ── Keys actions ──────────────────────────────────────────────

    def _save_keys(self):
        self.cfg["keys"] = {k: v.get() for k,v in self._key_vars.items()}
        self._save_cfg()
        messagebox.showinfo("Saved","Keys saved ✔")

    def _reset_keys(self):
        for k,v in self._key_vars.items():
            v.set(DEFAULT_KEYS.get(k,""))
        self._save_keys()
        messagebox.showinfo("Reset","Keys reset to Playback defaults ✔")

    # ── Region actions ────────────────────────────────────────────

    def _on_sync_toggle(self):
        self.cfg["use_screen_sync"] = self._sync_var.get()
        self._save_cfg()
        self._log(f"🔍  Screen sync: {'ON' if self._sync_var.get() else 'OFF'}")

    def _pick_star_zone(self):
        """User draws a detection zone."""
        is_sprite = (self.detector.detection_mode ==
                     ShinyDetector.MODE_SPRITE_DIFF)
        is_frlg   = (is_sprite and
                     getattr(self.detector, "_game_hint", "") == "star")

        # ── Instruction popup ────────────────────────────────────
        if is_frlg:
            messagebox.showinfo("Star Zone — FireRed/LeafGreen",
                "Navigate to the SUMMARY SCREEN in Playback.\n\n"
                "Then click OK and draw a SMALL box (~40×40px) over ONLY "
                "the top-right corner of the portrait — where the gold ★ "
                "appears on a shiny.\n\n"
                "💡 See the 'Guide' tab for reference images showing exactly where to draw.")
        elif is_sprite:
            messagebox.showinfo("Sprite Zone",
                "Navigate to the BATTLE SCREEN in Playback "
                "(\"What should X do?\" / FIGHT-BAG menu).\n\n"
                "Then click OK and drag a box over the Pokémon's "
                "full body sprite.\n\n"
                "💡 See the 'Guide' tab for reference images showing exactly where to draw.")
        else:
            messagebox.showinfo("Star Zone",
                "Navigate to the STATUS SCREEN in Playback, "
                "then click OK and drag a box over where the "
                "shiny stars appear next to the gender symbol.\n\n"
                "💡 See the 'Guide' tab for reference images showing exactly where to draw.")
        ov = tk.Toplevel(self.root)
        ov.attributes("-fullscreen",True,"-alpha",0.3,"-topmost",True)
        ov.configure(bg="black"); ov.overrideredirect(True)
        cv = tk.Canvas(ov, bg="black", cursor="crosshair", highlightthickness=0)
        cv.pack(fill="both", expand=True)

        if is_sprite:
            guide_text = (
                "GEN III — DRAW A BOX OVER THE POKÉMON SPRITE\n"
                "┌──────────────────────┐\n"
                "│   [Pokémon body]     │  ← cover the colored body\n"
                "└──────────────────────┘\n"
                "Include the main color areas, exclude HP bar/menus.  Esc = cancel."
            )
        elif (self.detector.detection_mode == ShinyDetector.MODE_SPRITE_DIFF and
              getattr(self.detector, "_game_hint", "") == "star"):
            # FRLG gold star — tiny zone only
            guide_text = (
                "FIRE RED / LEAF GREEN — DRAW A TINY BOX OVER THE STAR CORNER\n"
                "┌─────────────────────────────┐\n"
                "│  [Pokémon portrait]    [★]  │  ← star is top-RIGHT corner\n"
                "└─────────────────────────────┘\n"
                "Draw ONLY over the small top-right corner (~40×40px).\n"
                "Do NOT cover the Pokémon sprite or the portrait background.\n"
                "Esc = cancel."
            )
        else:
            guide_text = (
                "DRAW THE ZONE LIKE THIS — symbol on LEFT, space on RIGHT for stars\n"
                "┌──────────────────────┐\n"
                "│  ♂      (space)      │  ← stars appear in the right portion\n"
                "└──────────────────────┘\n"
                "Make it about 2-3× as wide as the gender symbol.  Esc = cancel."
            )
        tk.Label(cv, text=guide_text,
                 font=("Courier New",11,"bold"), fg=GOLD, bg="black",
                 justify="center"
                 ).place(relx=0.5, rely=0.05, anchor="center")

        # Two coordinate systems:
        #   sx_w, sy_w  = widget-local coords (for drawing the rect on canvas)
        #   sx_s, sy_s  = absolute screen coords (what we save & capture from)
        # Using x_root/y_root makes the captured zone match the actual pixels
        # the user clicked on, even if the overlay window isn't at (0,0).
        state = {"sx_w": 0, "sy_w": 0, "sx_s": 0, "sy_s": 0, "rect": None}

        def press(e):
            state["sx_w"], state["sy_w"] = e.x, e.y
            state["sx_s"], state["sy_s"] = e.x_root, e.y_root
            if state["rect"]:
                cv.delete(state["rect"])
            state["rect"] = cv.create_rectangle(e.x, e.y, e.x, e.y,
                                                outline=GOLD, width=3)
        def drag(e):
            if state["rect"]:
                cv.coords(state["rect"],
                          state["sx_w"], state["sy_w"], e.x, e.y)
        def release(e):
            # Use SCREEN-absolute coords for the saved zone
            x1 = min(state["sx_s"], e.x_root)
            y1 = min(state["sy_s"], e.y_root)
            x2 = max(state["sx_s"], e.x_root)
            y2 = max(state["sy_s"], e.y_root)
            ov.destroy()
            if x2 - x1 > 5 and y2 - y1 > 5:
                zone = {"left": x1, "top": y1,
                        "width": x2 - x1, "height": y2 - y1}
                self.cfg["star_zone"] = zone
                self._save_cfg()
                self.detector.init()
                self.detector.set_star_zone(**zone)
                # Small delay so the overlay is fully torn down before
                # we grab the baseline (otherwise we'd snapshot our own UI)
                self.root.update_idletasks()
                self.root.after(250, lambda: self._finalize_star_zone(zone))
            else:
                self._log("Zone too small — try again.")

        cv.bind("<ButtonPress-1>", press)
        cv.bind("<B1-Motion>",     drag)
        cv.bind("<ButtonRelease-1>", release)
        cv.bind("<Escape>", lambda e: ov.destroy())
        ov.focus_force()

    def _finalize_star_zone(self, zone):
        """Capture the baseline after the overlay window is fully gone."""
        is_sprite = (self.detector.detection_mode ==
                     ShinyDetector.MODE_SPRITE_DIFF)
        is_frlg   = (is_sprite and
                     getattr(self.detector, "_game_hint", "") == "star")

        # For FRLG: warn if zone is too large — the star is tiny (~40x40px)
        # and a large zone will capture animated portrait content causing
        # constant false positives.
        if is_frlg:
            w, h = zone["width"], zone["height"]
            if w > 120 or h > 120:
                messagebox.showwarning("Zone too large for FRLG",
                    f"Your zone is {w}×{h}px — that's too large.\n\n"
                    "For FireRed/LeafGreen the gold ★ star is a tiny icon "
                    "in the top-right corner of the portrait box.\n\n"
                    "Draw a SMALL box (~40-80px) over ONLY that corner.\n"
                    "Do not cover the Pokémon sprite or the striped background.\n\n"
                    "A large zone captures the animated portrait background "
                    "which looks different every reset, causing false positives.")
                self._log(f"⚠️  Zone {w}×{h}px is too large for FRLG — re-draw smaller")
                return

        ok = self.detector.set_baseline()
        kind = "Sprite zone" if is_sprite else "Star zone"
        txt = (f"{kind} set + baseline captured!" if ok
               else f"{kind} set (baseline FAILED — see error)")
        self._star_zone_var.set(
            f"OK  {zone['width']}x{zone['height']}px @ "
            f"({zone['left']},{zone['top']}) — {txt}")
        self._log(f"⭐  {txt}")
        self._log(f"    Zone: ({zone['left']},{zone['top']})  "
                  f"{zone['width']}×{zone['height']}px")
        if is_sprite:
            self._log("    Baseline = normal-coloured Pokémon sprite.")
            self._log("    Shiny palette = large pixel diff = SHINY detected.")
        else:
            self._log("    This is the NON-SHINY reference for that zone.")
            self._log("    Stars appearing = pixel change = SHINY detected.")
        self._refresh_baseline_label()

    def _capture_baseline(self):
        """User clicked Capture Baseline — snapshot the zone right now."""
        star_zone = self.cfg.get("star_zone")
        if not star_zone:
            messagebox.showwarning("No zone",
                "Draw the detection zone first (Step 2).")
            return
        self.detector.init()
        self.detector.set_star_zone(**star_zone)
        # Force-recapture even if baseline already exists
        self.detector.clear_baseline()
        ok = self.detector.set_baseline()
        is_sprite = (self.detector.detection_mode ==
                     ShinyDetector.MODE_SPRITE_DIFF)
        if ok:
            self._log("📐  Baseline captured — non-shiny reference saved")

            # Measure the noise floor: take 5 more samples and see how
            # much the LIVE zone drifts from baseline due to animation.
            # Use this to AUTO-CALIBRATE the shiny threshold instead of
            # hardcoding a value — every zone has different noise.
            if is_sprite:
                noise_samples = []
                for _ in range(5):
                    z = self.detector._grab_zone()
                    if z is not None:
                        bl = self.detector._baseline
                        if z.size != bl.size:
                            z = z.resize(bl.size, Image.LANCZOS)
                        d = _mean_abs_diff(z, bl)
                        noise_samples.append(d)
                    time.sleep(0.15)

                if noise_samples:
                    noise_max = max(noise_samples)
                    noise_avg = sum(noise_samples) / len(noise_samples)
                    # Auto-calibrated threshold: max noise × 3, with a
                    # floor of 6.  Real shiny color swaps produce ~9-30
                    # depending on zone tightness; noise floor is ~0-0.5
                    # on stable frames.
                    auto_thr = max(6.0, noise_max * 3.0)
                    self.detector._sprite_diff_threshold = auto_thr

                    self._log(f"📊  Noise floor:  avg={noise_avg:.2f}  "
                              f"max={noise_max:.2f}  "
                              f"auto_threshold={auto_thr:.1f}  "
                              f"samples={[f'{d:.1f}' for d in noise_samples]}")

                    # Persist the threshold alongside the baseline
                    try:
                        with open(self.detector.BASELINE_FILE + ".meta", "w") as f:
                            f.write(f"{self.detector._baseline_dark_pct}\n"
                                    f"{self.detector.detection_mode}\n"
                                    f"{auto_thr}\n")
                    except Exception:
                        pass

                    if noise_max > 30.0:
                        messagebox.showwarning("Very noisy zone",
                            f"✅  Baseline saved, but this zone has VERY "
                            f"high animation noise:\n\n"
                            f"   max noise: {noise_max:.1f}\n"
                            f"   auto-set threshold: {auto_thr:.1f}\n\n"
                            f"That's high enough that real shiny detection "
                            f"may be unreliable.  Recommend re-drawing the "
                            f"zone TIGHTER over ONLY the Pokémon's body, "
                            f"avoiding HP bars, EXP bars, text boxes, the "
                            f"enemy Pokémon, and the menu cursor.")
                    else:
                        messagebox.showinfo("Baseline captured",
                            f"✅  Sprite baseline saved.\n\n"
                            f"Noise floor: avg {noise_avg:.1f}, max {noise_max:.1f}\n"
                            f"Auto-calibrated threshold: {auto_thr:.1f}\n\n"
                            f"Detection triggers when zone diff exceeds "
                            f"the threshold — gives ~3x margin above noise.")
                else:
                    messagebox.showinfo("Baseline captured",
                        "✅  Sprite baseline saved.\n\n"
                        "Could not measure noise floor — test it on the "
                        "Hunt tab → Test (live screen) before running a hunt.")
            else:
                messagebox.showinfo("Baseline captured",
                    "✅  Baseline saved.\n\n"
                    "Detection will now flag stars appearing in the zone.\n\n"
                    "Test it on the Hunt tab → Test (live screen).")
        else:
            reason = (self.detector._baseline_reject_reason
                      or "Could not capture the zone.")
            if is_sprite:
                tip = ("  • Playback is open on the BATTLE SCREEN\n"
                       "  • Zone covers the Pokémon's body sprite\n"
                       "    (not just empty background)\n"
                       "  • No other window is covering Playback")
            else:
                tip = ("  • Playback is open on a NON-shiny status screen\n"
                       "  • Zone drawn tightly over the gender icon\n"
                       "    (where stars appear immediately next to it)\n"
                       "  • No other window is covering Playback")
            messagebox.showerror("Baseline rejected",
                "❌  Baseline NOT saved.\n\n"
                f"{reason}\n\n"
                "Make sure:\n" + tip)
            self._log(f"❌  Baseline rejected: {reason}")
        self._refresh_baseline_label()

    def _refresh_baseline_label(self):
        """Update the baseline status text + color."""
        if not hasattr(self, "_baseline_var"):
            return
        if self.detector._baseline_set:
            self._baseline_var.set("✅  Baseline captured")
            try: self._baseline_lbl.configure(fg=GREEN_HI)
            except: pass
        else:
            self._baseline_var.set("No baseline — capture one above")
            try: self._baseline_lbl.configure(fg=GOLD)
            except: pass

    def _refresh_region_labels(self):
        """
        Update Region tab labels based on selected game's generation.
        Gen II = star icon on status screen.
        Gen III = sprite color shift on battle screen.
        Called whenever the game selection changes.
        """
        if not hasattr(self, "_step2_text_var"):
            return  # Region tab not built yet
        mode = self.detector.detection_mode
        # Also check the current game hint for more specific instructions
        game = getattr(self, "_cur_game", None)
        hint = getattr(game, "detection_hint", "auto") if game else "auto"
        if hint == "auto":
            hint = "star" if (game and game.gen <= 2) else "sprite"

        if mode == ShinyDetector.MODE_SPRITE_DIFF:
            self._step2_frame.configure(text="  STEP 2 — Sprite Detection Zone  ")
            self._step2_text_var.set(
                "Open the BATTLE SCREEN in Playback (\"What should X do?\").\n"
                "Drag a box over the Pokémon's body sprite.\n"
                "Cover the main colored area (the body), not the menus.\n"
                "Detection watches for color shift (normal → shiny palette).")
            self._step2_btn_var.set("🎨  Draw Sprite Detection Zone")
            self._step3_text_var.set(
                "With Playback showing the NORMAL Pokémon on the battle\n"
                "screen, click below to snapshot the zone as the reference.\n"
                "Detection diffs every live frame against this snapshot —\n"
                "a shiny Pokémon will look very different (e.g. blue → purple).")
        elif hint == "star" and game and game.gen >= 3:
            # FR/LG gold star on summary screen
            self._step2_frame.configure(text="  STEP 2 — Gold Star Zone  ")
            self._step2_text_var.set(
                "Pick up a starter, open its SUMMARY SCREEN.\n"
                "Drag a TIGHT box over the top-right of the portrait\n"
                "where the gold ★ appears when shiny.\n"
                "The box should be about 40×40px — just the star area.")
            self._step2_btn_var.set("⭐  Draw Star Detection Zone")
            self._step3_text_var.set(
                "With Playback showing a NON-SHINY summary screen,\n"
                "click below to snapshot the zone (star area will be blank).\n"
                "When a shiny appears the gold star fills that zone —\n"
                "a large pixel diff vs the blank baseline = SHINY.")
        else:
            # Gen II star on status screen
            self._step2_frame.configure(text="  STEP 2 — Star Detection Zone  ")
            self._step2_text_var.set(
                "Open the STATUS SCREEN in Playback (Pokémon must be NOT shiny).\n"
                "Drag a tight box over the top-right corner where the shiny ✦\n"
                "stars appear — right beside the gender symbol.\n"
                "Symbol on the LEFT, empty space on the RIGHT for the stars.")
            self._step2_btn_var.set("⭐  Draw Star Detection Zone")
            self._step3_text_var.set(
                "With Playback showing a NON-SHINY status screen,\n"
                "click below to snapshot the current zone as the reference.\n"
                "Detection compares every live frame against this snapshot.")
        self._refresh_baseline_label()

    def _pick_region(self):
        ov = tk.Toplevel(self.root)
        ov.attributes("-fullscreen",True,"-alpha",0.25,"-topmost",True)
        ov.configure(bg="navy"); ov.overrideredirect(True)
        cv = tk.Canvas(ov, bg="navy", cursor="crosshair", highlightthickness=0)
        cv.pack(fill="both", expand=True)
        tk.Label(cv,
                 text="Drag over the GAME AREA only (not Playback toolbar)  ·  Esc = cancel",
                 font=("Courier New",12,"bold"), fg="white", bg="navy"
                 ).place(relx=0.5, rely=0.05, anchor="center")
        state = {"sx_w": 0, "sy_w": 0, "sx_s": 0, "sy_s": 0, "rect": None}

        def press(e):
            state["sx_w"], state["sy_w"] = e.x, e.y
            state["sx_s"], state["sy_s"] = e.x_root, e.y_root
            if state["rect"]:
                cv.delete(state["rect"])
            state["rect"] = cv.create_rectangle(e.x, e.y, e.x, e.y,
                                                outline="lime", width=3)
        def drag(e):
            if state["rect"]:
                cv.coords(state["rect"],
                          state["sx_w"], state["sy_w"], e.x, e.y)
        def release(e):
            x1 = min(state["sx_s"], e.x_root)
            y1 = min(state["sy_s"], e.y_root)
            x2 = max(state["sx_s"], e.x_root)
            y2 = max(state["sy_s"], e.y_root)
            ov.destroy()
            if x2 - x1 > 30 and y2 - y1 > 30:
                self.cfg["game_region"] = {"left": x1, "top": y1,
                                           "width": x2 - x1, "height": y2 - y1}
                self._save_cfg()
                self.detector.init()
                self.detector.set_region(**self.cfg["game_region"])
                txt = (f"✅  Game area: {x2 - x1}×{y2 - y1}px  "
                       f"@ ({x1},{y1})")
                self._region_var.set(txt)
                self._log(txt)
                # Auto-capture preview so user sees what was grabbed
                self.root.after(200, self._capture_preview)
            else:
                self._log("⚠️   Region too small — try again.")

        cv.bind("<ButtonPress-1>", press)
        cv.bind("<B1-Motion>",     drag)
        cv.bind("<ButtonRelease-1>", release)
        cv.bind("<Escape>", lambda e: ov.destroy())
        ov.focus_force()

    def _capture_preview(self):
        try:
            self.detector.init()
            region = self.cfg.get("game_region")
            if region:
                self.detector.set_region(**region)
            raw = self.detector.grab_pil()
            if raw is None:
                self._log("⚠️  No region set or screen capture failed.")
                return
            from PIL import ImageTk, Image as PI, ImageDraw

            orig_w, orig_h = raw.size

            # ── Draw zone overlay on a copy ────────────────────────
            annotated = raw.copy()
            draw = ImageDraw.Draw(annotated)

            zone   = self.cfg.get("star_zone")
            region = self.cfg.get("game_region")
            if zone and region:
                # Convert absolute screen coords → game-region-relative
                rx = region["left"]
                ry = region["top"]
                zx1 = zone["left"]  - rx
                zy1 = zone["top"]   - ry
                zx2 = zx1 + zone["width"]
                zy2 = zy1 + zone["height"]

                # Clamp to image bounds
                zx1 = max(0, zx1);  zy1 = max(0, zy1)
                zx2 = min(orig_w, zx2);  zy2 = min(orig_h, zy2)

                # Choose colour based on mode and baseline state
                is_sprite = (self.detector.detection_mode ==
                             ShinyDetector.MODE_SPRITE_DIFF)
                if self.detector._baseline_set:
                    color = "#00ff88"    # green = baseline captured ✓
                    label = ("SPRITE ZONE ✓" if is_sprite
                             else "STAR ZONE ✓")
                else:
                    color = "#ffdd00"    # yellow = no baseline yet
                    label = ("SPRITE ZONE (no baseline)"
                             if is_sprite else "STAR ZONE (no baseline)")

                # Thick box + corner ticks for visibility at small sizes
                draw.rectangle([zx1, zy1, zx2, zy2],
                               outline=color, width=3)
                # Corner ticks (10px)
                tick = 10
                for cx, cy in [(zx1, zy1), (zx2, zy1),
                               (zx1, zy2), (zx2, zy2)]:
                    dx = tick if cx == zx1 else -tick
                    dy = tick if cy == zy1 else -tick
                    draw.line([cx, cy, cx+dx, cy], fill=color, width=4)
                    draw.line([cx, cy, cx, cy+dy], fill=color, width=4)

                # Semi-transparent label background
                lx = max(0, zx1)
                ly = max(0, zy1 - 16)
                draw.rectangle([lx, ly, lx + len(label)*7 + 4, ly + 14],
                               fill=(0, 0, 0, 160) if hasattr(draw, 'alpha') else "black")
                draw.text((lx + 2, ly + 1), label, fill=color)

                self._log(f"📸  Preview: {orig_w}×{orig_h}px  |  "
                          f"Zone overlay: ({zx1},{zy1})→({zx2},{zy2})  "
                          f"{zx2-zx1}×{zy2-zy1}px  "
                          f"{'✅ baseline' if self.detector._baseline_set else '⚠ no baseline'}")
            else:
                self._log(f"📸  Preview: {orig_w}×{orig_h}px  "
                          f"(no zone set — draw one in Step 2)")

            # Keep the full-resolution annotated image for export
            self._preview_pil = annotated

            # Scale down for display
            target_w = 540
            target_h = max(50, int(orig_h * (target_w / orig_w)))
            display  = annotated.resize((target_w, target_h), PI.LANCZOS)
            tk_img   = ImageTk.PhotoImage(display)
            self._preview_img_ref = tk_img
            self._preview_lbl.config(image=tk_img, text="")

        except Exception as e:
            self._log(f"⚠️  Preview failed: {e}")

    def _export_preview(self):
        """Save the annotated preview to a file the user can share."""
        if not hasattr(self, "_preview_pil") or self._preview_pil is None:
            messagebox.showwarning("No preview",
                "Capture a preview first, then export.")
            return
        from tkinter import filedialog
        from datetime import datetime
        default = f"zone_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path = filedialog.asksaveasfilename(
            title="Save zone preview",
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("All", "*.*")],
            initialfile=default)
        if not path:
            return
        try:
            self._preview_pil.save(path)
            self._log(f"💾  Zone preview saved: {path}")
            messagebox.showinfo("Saved",
                f"Saved to:\n{path}\n\n"
                "You can share this image to verify zone placement.")
        except Exception as e:
            messagebox.showerror("Save failed", str(e))


    # ═══════════════════════════════════════════════════════════════════
    # SCANNER TAB — embedded post-hunt screenshot verifier
    # ═══════════════════════════════════════════════════════════════════

    def _build_scanner_tab(self, nb):
        """Build the Scanner tab — post-hunt screenshot verification."""
        import threading, os, csv
        from tkinter import filedialog as _fd

        f = tk.Frame(nb, bg=BG)
        f.columnconfigure(0, weight=1)

        # Header
        tk.Label(f, text="🔬  Shiny Scanner",
                 font=("Courier New", 13, "bold"),
                 fg=GOLD, bg=BG).pack(pady=(12, 2))
        tk.Label(f,
                 text="Scan every saved screenshot for missed shinies.\n"
                      "Load your screenshots folder, draw a zone on the\n"
                      "sample frame, then click Scan.",
                 font=FONT_MONO, fg=FG_DIM, bg=BG,
                 justify="center").pack(pady=(0, 10))

        # ── Mode indicator ────────────────────────────────────────
        mode_frame = tk.Frame(f, bg=BG3, pady=6)
        mode_frame.pack(fill="x", padx=18, pady=(0, 6))
        tk.Label(mode_frame, text="Detection mode:",
                 font=FONT_MONO, fg=FG_DIM, bg=BG3).pack(side="left", padx=8)
        self._scan_mode_var = tk.StringVar(value="")
        self._scan_mode_lbl = tk.Label(mode_frame,
                 textvariable=self._scan_mode_var,
                 font=("Courier New", 9, "bold"),
                 fg=GOLD, bg=BG3)
        self._scan_mode_lbl.pack(side="left")
        tk.Label(mode_frame,
                 text="  (set by selected game — switches automatically)",
                 font=FONT_MONO, fg=FG_DIM, bg=BG3).pack(side="left")
        self._update_scanner_mode_label()

        # ── Folder selector ───────────────────────────────────────
        row1 = tk.Frame(f, bg=BG)
        row1.pack(fill="x", padx=18, pady=2)
        self._scan_folder_var = tk.StringVar(value="No folder selected")
        self._scan_folder     = None
        self._scan_images     = []

        _btn(row1, "📂  Select Screenshots Folder",
             lambda: self._scanner_pick_folder(), bg="#1a4a8a", fg="white",
             padx=12, pady=6, font=FONT_MONO).pack(side="left")
        tk.Label(row1, textvariable=self._scan_folder_var,
                 font=FONT_MONO, fg=GOLD, bg=BG,
                 wraplength=340).pack(side="left", padx=10)

        # ── Sample preview + zone draw ────────────────────────────
        preview_outer = tk.LabelFrame(f, text="  Sample Frame (drag to set zone)  ",
                                      font=FONT_MONO, fg=FG_DIM, bg=BG,
                                      padx=6, pady=6)
        preview_outer.pack(fill="both", expand=True, padx=18, pady=6)

        self._scan_canvas = tk.Canvas(preview_outer, bg=BG3,
                                      cursor="crosshair",
                                      highlightthickness=1,
                                      highlightbackground=BG3)
        self._scan_canvas.pack(fill="both", expand=True)
        self._scan_canvas.bind("<ButtonPress-1>",   self._scan_zone_press)
        self._scan_canvas.bind("<B1-Motion>",        self._scan_zone_drag)
        self._scan_canvas.bind("<ButtonRelease-1>", self._scan_zone_release)

        self._scan_preview_img = None   # ImageTk reference
        self._scan_sample_pil  = None   # full PIL of first screenshot
        self._scan_rect_id     = None   # canvas rectangle id
        self._scan_rect_start  = None
        self._scan_zone        = None   # (x1,y1,x2,y2) in image coords
        self._scan_baseline    = None   # PIL crop of zone

        self._scan_zone_var = tk.StringVar(value="No zone — drag on preview above")
        tk.Label(preview_outer, textvariable=self._scan_zone_var,
                 font=FONT_MONO, fg=GOLD, bg=BG).pack(pady=(4, 0))

        # ── Controls row ──────────────────────────────────────────
        ctrl = tk.Frame(f, bg=BG)
        ctrl.pack(fill="x", padx=18, pady=4)

        self._scan_btn = _btn(ctrl, "🔍  Scan All Screenshots",
                              self._scanner_run,
                              bg="#1a6a1a", fg="white",
                              padx=14, pady=7, font=FONT_BIG)
        self._scan_btn.pack(side="left")

        self._scan_stop_flag = threading.Event()
        _btn(ctrl, "⏹  Stop",
             lambda: self._scan_stop_flag.set(),
             bg="#6a1a1a", fg="white",
             padx=10, pady=7, font=FONT_MONO).pack(side="left", padx=6)

        self._scan_progress_var = tk.StringVar(value="")
        tk.Label(ctrl, textvariable=self._scan_progress_var,
                 font=FONT_MONO, fg=FG_DIM, bg=BG).pack(side="left", padx=8)

        # ── Results log ───────────────────────────────────────────
        res_frame = tk.LabelFrame(f, text="  Results  ",
                                  font=FONT_MONO, fg=FG_DIM, bg=BG,
                                  padx=4, pady=4)
        res_frame.pack(fill="both", expand=True, padx=18, pady=(0, 10))

        self._scan_log = tk.Text(res_frame, bg=BG3, fg=FG,
                                 font=FONT_MONO, height=8,
                                 state="disabled", wrap="none")
        sb = tk.Scrollbar(res_frame, command=self._scan_log.yview, bg=BG3)
        self._scan_log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._scan_log.pack(fill="both", expand=True)
        self._scan_log.tag_configure("hit",  foreground=GREEN_HI)
        self._scan_log.tag_configure("dim",  foreground=FG_DIM)
        self._scan_log.tag_configure("err",  foreground="#ff6666")

        return f

    def _build_guide_tab(self):
        """Build the step-by-step guide tab with embedded zone reference images."""
        import os, sys
        from PIL import ImageTk, Image as PI
        
        guide = tk.Frame(self._tab_guide, bg=BG)
        guide.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Scrollable container
        canvas = tk.Canvas(guide, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(guide, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Title
        tk.Label(scrollable_frame, text="📖  How to Hunt Shiny Pokémon",
                 font=("Courier New", 16, "bold"), fg=GOLD, bg=BG).pack(pady=(0, 10))
        
        # Step-by-step guide
        steps = [
            ("1️⃣  SELECT GAME", [
                "Choose your game from the left sidebar",
                "Gen 2 (Gold/Silver/Crystal) fully supported",
                "Gen 3 (GBA games) require access code - experimental",
                "Select your starter Pokémon",
            ]),
            ("2️⃣  LOAD GAME IN PLAYBACK", [
                "Open the Epilogue GB Operator Playback software",
                "Navigate to the Pokémon's STATUS SCREEN (Gen 2) or SUMMARY (Gen 3)",
                "Save your game in front of the target ball/Pokémon",
            ]),
            ("3️⃣  SET GAME AREA", [
                "Go to the 'Region' tab",
                "Click 'Draw Game Area'",
                "Draw a box around the ENTIRE Playback game window",
                "(Exclude the PLAY/DATA toolbar at the top)",
            ]),
            ("4️⃣  SET DETECTION ZONE", [
                "This is the area the app watches for shiny indicators",
                "Click 'Draw Star Detection Zone' in the Region tab",
                "Use the reference images below to see where to draw",
                "Keep the zone SMALL and precise for best results",
            ]),
            ("5️⃣  CAPTURE BASELINE", [
                "The baseline is the 'normal' reference image",
                "Make sure Pokémon is on screen (not shiny)",
                "Click 'Capture Baseline' in Region tab",
                "This helps the app detect shiny vs normal",
            ]),
            ("6️⃣  RECORD BUTTON SEQUENCE", [
                "Go to the 'Record' tab",
                "Click 'Start Recording'",
                "In Playback, perform these steps:",
                "  • Pick up starter ball / interact with Pokémon",
                "  • Navigate to status/summary screen",
                "  • Soft reset (your configured reset keys)",
                "Click 'Stop Recording' when done",
            ]),
            ("7️⃣  CONFIGURE HUNT SETTINGS", [
                "Return to the 'Hunt' tab",
                "✅ Enable Reset checkbox",
                "⚡ Optionally enable Double Speed",
                "Review your sequence playback speed",
            ]),
            ("8️⃣  START HUNTING!", [
                "Click 'Start Hunt' button",
                "The app will loop your recorded sequence",
                "When a shiny is detected:",
                "  • Alarm will sound",
                "  • Hunt will pause",
                "  • Screenshot will be saved",
                "Save your shiny in the game!",
            ]),
        ]
        
        for title, items in steps:
            # Step header
            hdr = tk.Frame(scrollable_frame, bg="#1a1a2a")
            hdr.pack(fill="x", pady=(15, 5), padx=5)
            tk.Label(hdr, text=title,
                     font=("Courier New", 11, "bold"),
                     fg=GOLD, bg="#1a1a2a", anchor="w",
                     padx=8, pady=4).pack(fill="x")
            
            # Step content
            for item in items:
                tk.Label(scrollable_frame, text=f"  • {item}",
                         font=FONT_MONO, fg=FG, bg=BG,
                         anchor="w", justify="left").pack(fill="x", padx=15, pady=1)
        
        # Zone Reference Images Section
        tk.Label(scrollable_frame, text="═" * 60,
                 font=FONT_MONO, fg=FG_DIM, bg=BG).pack(pady=(20, 5))
        
        tk.Label(scrollable_frame, text="🎨  DETECTION ZONE REFERENCE",
                 font=("Courier New", 13, "bold"),
                 fg=GOLD, bg=BG).pack(pady=5)
        
        tk.Label(scrollable_frame,
                 text="These images show exactly where to draw your detection zone.\n"
                      "Select a game to see the reference guide:",
                 font=FONT_MONO, fg=FG_DIM, bg=BG, justify="center").pack(pady=5)
        
        # Helper function to load zone images
        def _asset_path(name):
            if getattr(sys, "frozen", False):
                base = sys._MEIPASS
            else:
                base = os.path.dirname(os.path.abspath(__file__))
            return os.path.join(base, "assets", "zones", name)
        
        # Image container
        img_container = tk.Frame(scrollable_frame, bg=BG2, relief="solid", bd=2)
        img_container.pack(pady=10, padx=20, fill="x")
        
        image_label = tk.Label(img_container, bg=BG2)
        image_label.pack(pady=15, padx=15)
        
        # Current selection
        self._current_guide_img = tk.StringVar(value="gen2")
        
        # Load and display images
        def load_guide_image(key):
            image_map = {
                "gen2": ("gen2_star.png", "Gen 2: Gold/Silver/Crystal - Star Zone"),
                "frlg": ("frlg_star.png", "Gen 3: FireRed/LeafGreen - Gold Star"),
                "treecko": ("rse_treecko.png", "Gen 3: Treecko - Sprite Zone"),
                "mudkip": ("rse_mudkip.png", "Gen 3: Mudkip - Sprite Zone"),
                "torchic": ("rse_torchic.png", "Gen 3: Torchic - Sprite Zone"),
            }
            
            if key not in image_map:
                return
            
            filename, desc = image_map[key]
            path = _asset_path(filename)
            
            if not os.path.exists(path):
                image_label.config(
                    text=f"📸  {desc}\n\n(Image not found at {filename})\n\n"
                         "Make sure guide images are included in assets/zones/",
                    fg=FG_DIM, font=FONT_MONO, justify="center"
                )
                return
            
            try:
                img = PI.open(path)
                # Resize if too large
                max_w = 550
                if img.width > max_w:
                    ratio = max_w / img.width
                    new_size = (max_w, int(img.height * ratio))
                    img = img.resize(new_size, PI.LANCZOS)
                
                photo = ImageTk.PhotoImage(img)
                image_label.config(image=photo, text="")
                image_label.image = photo  # Keep reference
            except Exception as e:
                image_label.config(
                    text=f"Error loading {filename}:\n{e}",
                    fg="#ff6666", font=FONT_MONO
                )
        
        # Selector buttons frame
        selector_frame = tk.Frame(scrollable_frame, bg=BG)
        selector_frame.pack(pady=(5, 15))
        
        selector_buttons = []
        
        def make_selector(key, label):
            def select():
                self._current_guide_img.set(key)
                load_guide_image(key)
                # Update button colors
                for btn, k in selector_buttons:
                    if k == key:
                        btn.config(bg=GOLD, fg="black", relief="solid")
                    else:
                        btn.config(bg=BG3, fg=FG, relief="flat")
            
            btn = tk.Button(selector_frame, text=label,
                           font=FONT_MONO, bg=BG3, fg=FG,
                           command=select, cursor="hand2",
                           relief="flat", padx=10, pady=5, bd=0)
            btn.pack(side="left", padx=3)
            selector_buttons.append((btn, key))
            return btn
        
        make_selector("gen2", "Gen 2 (GSC)")
        make_selector("frlg", "FRLG")
        make_selector("treecko", "Treecko")
        make_selector("mudkip", "Mudkip")
        make_selector("torchic", "Torchic")
        
        # Load default image
        load_guide_image("gen2")
        selector_buttons[0][0].config(bg=GOLD, fg="black", relief="solid")
        
        # Tips section
        tk.Label(scrollable_frame, text="═" * 60,
                 font=FONT_MONO, fg=FG_DIM, bg=BG).pack(pady=(15, 5))
        
        tk.Label(scrollable_frame, text="💡  IMPORTANT TIPS",
                 font=("Courier New", 12, "bold"),
                 fg=GOLD, bg=BG).pack(pady=5)
        
        tips = [
            "Keep your detection zone SMALL and PRECISE - larger zones cause false positives",
            "Test with 3-5 manual resets before starting a long hunt",
            "Use the Scanner tab to review screenshots and verify you haven't missed shinies",
            "Gen 2: Shiny starters MUST be male (stars appear next to ♂ symbol only)",
            "Gen 3 (GBA): Currently experimental - Gen 2 recommended for best results",
        ]
        
        for tip in tips:
            frm = tk.Frame(scrollable_frame, bg=BG)
            frm.pack(fill="x", padx=15, pady=3)
            tk.Label(frm, text="  ⚠️", font=FONT_MONO, fg=GOLD, bg=BG).pack(side="left")
            tk.Label(frm, text=tip,
                     font=FONT_MONO, fg=FG, bg=BG,
                     anchor="w", justify="left", wraplength=650).pack(side="left", padx=5)
        
        # Bottom padding
        tk.Label(scrollable_frame, text="", bg=BG).pack(pady=20)

    def _update_scanner_mode_label(self):
        """Update the Scanner tab's mode indicator to match the current game."""
        if not hasattr(self, "_scan_mode_var"):
            return
        mode = self.detector.detection_mode
        if mode == ShinyDetector.MODE_SPRITE_DIFF:
            self._scan_mode_var.set(
                "🎨  Gen III — Sprite colour diff  "
                "(Ruby / Sapphire / Emerald / FireRed / LeafGreen)")
        else:
            self._scan_mode_var.set(
                "⭐  Gen II — Star icon dark-pixel  "
                "(Gold / Silver / Crystal)")

    def _scanner_log(self, msg, tag="", filepath=None):
        """Append a line to the scanner results log.
        If filepath is given, the line is clickable and opens the file."""
        def _do():
            self._scan_log.configure(state="normal")
            if filepath:
                # Insert as a clickable link tag
                link_tag = f"link_{id(filepath)}_{self._scan_log.index('end')}"
                self._scan_log.tag_configure(
                    link_tag,
                    foreground=GREEN_HI,
                    underline=True)
                self._scan_log.tag_bind(
                    link_tag, "<Button-1>",
                    lambda e, p=filepath: self._scanner_open_file(p))
                self._scan_log.tag_bind(
                    link_tag, "<Enter>",
                    lambda e: self._scan_log.configure(cursor="hand2"))
                self._scan_log.tag_bind(
                    link_tag, "<Leave>",
                    lambda e: self._scan_log.configure(cursor=""))
                self._scan_log.insert("end", msg + "\n", (tag, link_tag))
            else:
                self._scan_log.insert("end", msg + "\n", tag)
            self._scan_log.see("end")
            self._scan_log.configure(state="disabled")
        self.root.after(0, _do)

    def _scanner_open_file(self, path):
        """Open an image file with the default system viewer."""
        import subprocess, os
        try:
            os.startfile(path)
        except Exception:
            try:
                subprocess.Popen(["explorer", "/select,", path])
            except Exception:
                pass

    def _scanner_pick_folder(self):
        from tkinter import filedialog as _fd
        folder = _fd.askdirectory(title="Select screenshots folder")
        if not folder:
            return
        import glob, os
        exts   = ("*.png", "*.jpg", "*.jpeg", "*.bmp")
        images = []
        for e in exts:
            images += glob.glob(os.path.join(folder, e))
        images.sort()
        self._scan_folder  = folder
        self._scan_images  = images
        self._scan_folder_var.set(
            f"{os.path.basename(folder)}  ({len(images)} images)")
        self._scan_log.configure(state="normal")
        self._scan_log.delete("1.0", "end")
        self._scan_log.configure(state="disabled")
        self._scan_progress_var.set("")

        # ── Auto-load the hunter's saved baseline ─────────────────
        # The main hunter saves a baseline PNG when you click
        # "Capture Baseline" in the Region tab.  The scanner can use
        # that same reference directly — no manual zone-drawing needed
        # if the baseline file exists.
        baseline_loaded = False
        self._scan_using_hunter_baseline = False
        if self.detector._baseline_set and self.detector._baseline is not None:
            # Baseline already in memory from the running hunt session
            self._scan_baseline = self.detector._baseline.copy()
            self._scan_using_hunter_baseline = True
            # Work out the zone coords from the saved star_zone config
            zone = self.cfg.get("star_zone")
            region = self.cfg.get("game_region")
            if zone and region:
                rx, ry = region["left"], region["top"]
                zx = zone["left"] - rx
                zy = zone["top"]  - ry
                self._scan_zone = (zx, zy,
                                   zx + zone["width"],
                                   zy + zone["height"])
                self._scan_zone_var.set(
                    f"Zone: {zone['width']}×{zone['height']}px  "
                    f"@ ({zx},{zy})  ✅  (loaded from hunter baseline)")
                self._scanner_log(
                    "📐  Baseline loaded from current hunt session  "
                    f"mode={self.detector.detection_mode}", "dim")
                baseline_loaded = True

        if images:
            try:
                pil = Image.open(images[0]).convert("RGB")
                self._scan_sample_pil = pil
                self._scanner_show_preview(pil)
                # Draw the loaded zone on the preview if we have one
                if baseline_loaded and self._scan_zone:
                    ix1, iy1, ix2, iy2 = self._scan_zone
                    s = getattr(self, "_scan_scale", 1.0)
                    if self._scan_rect_id:
                        self._scan_canvas.delete(self._scan_rect_id)
                    self._scan_rect_id = self._scan_canvas.create_rectangle(
                        ix1*s, iy1*s, ix2*s, iy2*s,
                        outline="#00ff88", width=2)
                if not baseline_loaded:
                    self._scanner_log(
                        f"📂  {len(images)} screenshots loaded — "
                        f"drag a zone on the preview to set baseline", "dim")
                else:
                    self._scanner_log(
                        f"📂  {len(images)} screenshots loaded — "
                        f"ready to scan!", "dim")
            except Exception as e:
                self._scanner_log(f"⚠️  Could not load sample: {e}", "err")

    def _scanner_show_preview(self, pil):
        """Display a PIL image on the scan canvas, scaled to fit."""
        from PIL import ImageTk
        canvas = self._scan_canvas
        canvas.update_idletasks()
        cw = max(100, canvas.winfo_width())
        ch = max(80,  canvas.winfo_height())
        scale = min(cw / pil.width, ch / pil.height, 1.0)
        disp  = pil.resize((int(pil.width  * scale),
                             int(pil.height * scale)), Image.LANCZOS)
        tkimg = ImageTk.PhotoImage(disp)
        canvas.delete("all")
        canvas.create_image(0, 0, anchor="nw", image=tkimg)
        self._scan_preview_img = tkimg
        self._scan_scale       = scale   # image → canvas scale factor
        self._scan_rect_id     = None

    def _scan_zone_press(self, e):
        self._scan_rect_start = (e.x, e.y)
        if self._scan_rect_id:
            self._scan_canvas.delete(self._scan_rect_id)

    def _scan_zone_drag(self, e):
        if not self._scan_rect_start:
            return
        x0, y0 = self._scan_rect_start
        if self._scan_rect_id:
            self._scan_canvas.delete(self._scan_rect_id)
        self._scan_rect_id = self._scan_canvas.create_rectangle(
            x0, y0, e.x, e.y, outline="#00ff88", width=2)

    def _scan_zone_release(self, e):
        if not self._scan_rect_start or self._scan_sample_pil is None:
            return
        x0, y0 = self._scan_rect_start
        x1, y1 = e.x, e.y
        cx1, cy1 = min(x0, x1), min(y0, y1)
        cx2, cy2 = max(x0, x1), max(y0, y1)
        if cx2 - cx1 < 4 or cy2 - cy1 < 4:
            return
        # Convert canvas coords → image coords
        s  = getattr(self, "_scan_scale", 1.0)
        ix1, iy1 = int(cx1 / s), int(cy1 / s)
        ix2, iy2 = int(cx2 / s), int(cy2 / s)
        pil   = self._scan_sample_pil
        ix2   = min(ix2, pil.width);  iy2 = min(iy2, pil.height)
        self._scan_zone = (ix1, iy1, ix2, iy2)

        # Only update baseline from the drawn zone if we DON'T already
        # have the hunter's baseline loaded.  If the hunter baseline is
        # in memory we keep it — the zone just tells us WHERE to crop
        # from each screenshot.
        hunter_baseline_active = (
            self.detector._baseline_set and
            self.detector._baseline is not None and
            getattr(self, "_scan_using_hunter_baseline", False))

        if not hunter_baseline_active:
            self._scan_baseline = pil.crop(
                (ix1, iy1, ix2, iy2)).convert("RGB")
            self._scanner_log(
                f"📐  Zone set: ({ix1},{iy1})→({ix2},{iy2})  "
                f"{ix2-ix1}×{iy2-iy1}px  baseline from sample frame", "dim")
        else:
            # Resize the stored baseline to match the new zone size if needed
            new_w, new_h = ix2 - ix1, iy2 - iy1
            if self._scan_baseline.size != (new_w, new_h):
                self._scan_baseline = self._scan_baseline.resize(
                    (new_w, new_h), Image.LANCZOS)
            self._scanner_log(
                f"📐  Zone updated: ({ix1},{iy1})→({ix2},{iy2})  "
                f"{ix2-ix1}×{iy2-iy1}px  ✅ using hunter baseline", "dim")

        self._scan_zone_var.set(
            f"Zone: ({ix1},{iy1}) → ({ix2},{iy2})  "
            f"{ix2-ix1}×{iy2-iy1}px  "
            f"{'✅ hunter baseline' if hunter_baseline_active else '✅ sample baseline'}")

    def _scanner_run(self):
        """Start the scan in a background thread."""
        if not self._scan_images:
            messagebox.showwarning("No images",
                "Select a screenshots folder first.")
            return
        if self._scan_baseline is None:
            messagebox.showwarning("No zone",
                "Drag a detection zone on the sample image first.")
            return

        self._scan_stop_flag.clear()
        self._scan_log.configure(state="normal")
        self._scan_log.delete("1.0", "end")
        self._scan_log.configure(state="disabled")

        import threading
        threading.Thread(target=self._scanner_worker, daemon=True).start()

    def _scanner_worker(self):
        """Scan all screenshots and report hits."""
        images   = self._scan_images
        zone     = self._scan_zone
        baseline = self._scan_baseline
        total    = len(images)
        ix1, iy1, ix2, iy2 = zone
        zw, zh   = ix2 - ix1, iy2 - iy1

        # Use the current detector's threshold/mode
        mode      = self.detector.detection_mode
        threshold = self.detector.get_sprite_threshold()
        base_dark = _dark_pixel_pct(baseline)
        dark_thr  = base_dark + 0.05

        self._scanner_log(
            f"📊  Scanning {total} screenshots  mode={mode}  "
            f"threshold={threshold:.1f}", "dim")

        hits = []
        for i, path in enumerate(images, 1):
            if self._scan_stop_flag.is_set():
                self._scanner_log("⏹  Scan stopped.", "err")
                break
            try:
                img  = Image.open(path).convert("RGB")
                crop = img.crop((ix1, iy1, ix2, iy2))
                if crop.size != baseline.size:
                    crop = crop.resize(baseline.size, Image.LANCZOS)

                diff = _mean_abs_diff(crop, baseline)

                if mode == ShinyDetector.MODE_SPRITE_DIFF:
                    is_hit = diff >= threshold
                    detail = f"diff={diff:.2f}"
                    if i <= 5 or is_hit:
                        self._scanner_log(
                            f"  [{i:04d}]  {detail}  "
                            f"{'🌟 HIT' if is_hit else 'normal'}  "
                            f"{os.path.basename(path)[:40]}",
                            "hit" if is_hit else "dim",
                            filepath=path if is_hit else None)
                else:
                    dark   = _dark_pixel_pct(crop)
                    is_hit = diff >= threshold or dark >= dark_thr
                    detail = f"diff={diff:.2f}  dark={dark*100:.1f}%"
                    if i <= 5 or is_hit:
                        self._scanner_log(
                            f"  [{i:04d}]  {detail}  "
                            f"{'🌟 HIT' if is_hit else 'normal'}  "
                            f"{os.path.basename(path)[:40]}",
                            "hit" if is_hit else "dim",
                            filepath=path if is_hit else None)

                if is_hit:
                    hits.append(path)

            except Exception as ex:
                self._scanner_log(
                    f"  ⚠️  {os.path.basename(path)}: {ex}", "err")

            if i % 10 == 0 or i == total:
                self.root.after(0,
                    lambda v=f"{i}/{total}  hits:{len(hits)}":
                    self._scan_progress_var.set(v))

        self._scanner_log(
            f"\n✅  Done — {total} scanned, {len(hits)} hit(s)")
        if hits:
            self._scanner_log(
                "\nReview the hits above — any marked 🌟 may be a shiny.",
                "hit")


# ═══════════════════════════════════════════════════════════════════
# DPI AWARENESS
# ═══════════════════════════════════════════════════════════════════
#
# Windows 10/11 scales coordinates for DPI-unaware processes — every
# window API (GetWindowRect, DwmGetWindowAttribute, etc.) returns
# scaled "virtual" pixels, but mss captures real physical pixels.
# That mismatch is why our captured region kept getting cropped.
#
# Calling this BEFORE creating any window or Tk root tells Windows the
# process handles DPI itself, so all subsequent calls return raw
# physical coordinates that match what mss captures.

def _enable_dpi_awareness():
    """Make this process per-monitor DPI aware. Must run before any UI."""
    try:
        import ctypes
        # Try Per-Monitor V2 first (Win 10 1703+, best behavior)
        try:
            # -4 = DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
            ctypes.windll.user32.SetProcessDpiAwarenessContext(
                ctypes.c_void_p(-4))
            return "per_monitor_v2"
        except (AttributeError, OSError):
            pass
        # Fallback: Per-Monitor DPI Aware (Win 8.1+)
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            return "per_monitor"
        except (AttributeError, OSError):
            pass
        # Last resort: System DPI Aware (any Vista+)
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            return "system"
        except (AttributeError, OSError):
            pass
    except Exception:
        pass
    return "none"


# Call BEFORE Tk, BEFORE mss, BEFORE anything else creates a window
_DPI_MODE = _enable_dpi_awareness()


# ═══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def main():
    root = tk.Tk()

    # Check for updates in the background before showing the main window.
    # Runs silently if GitHub is unreachable — never blocks startup.
    try:
        from updater import check_for_updates
        check_for_updates(current_version=APP_VERSION)
    except ImportError:
        pass   # updater.py not present — skip silently
    except Exception:
        pass   # network issue — skip silently

    app  = ShinyHunterApp(root)

    def on_close():
        if app.hunter and app.hunter.running:
            if not messagebox.askyesno("Quit",
                "Hunt is running. Are you sure you want to quit?\n\n"
                "If a shiny was found it is safe — the game is paused."):
                return
        if app.hunter:
            app.hunter.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback; err = traceback.format_exc()
        try:
            import tkinter as _tk, tkinter.messagebox as _mb
            _r = _tk.Tk(); _r.withdraw()
            _mb.showerror("Shiny Hunter — Crash", err); _r.destroy()
        except: pass
        try:
            log_dir = os.path.dirname(sys.executable) \
                if getattr(sys,"frozen",False) \
                else os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(log_dir,"shiny_hunter_crash.log"),"w") as f:
                f.write(err)
        except: pass
        raise

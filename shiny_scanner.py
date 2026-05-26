"""
Shiny Scanner — Companion tool for Shiny Hunter

Loads a folder of screenshots from a hunt, lets you drag a star detection
zone on a sample frame, then scans every screenshot for star activity
in that same zone.  Anything above the threshold is flagged.

Usage:
  python shiny_scanner.py

Build a standalone exe with:
  pyinstaller --onefile --windowed --name ShinyScanner shiny_scanner.py
"""

import os
import sys
import json
import threading
import queue
from pathlib import Path

from PIL import Image, ImageTk, ImageDraw, ImageChops, ImageStat

def _mean_abs_diff(a, b):
    """Mean absolute pixel difference between two same-size PIL images."""
    diff = ImageChops.difference(a, b)
    stat = ImageStat.Stat(diff)
    return sum(stat.mean) / max(1, len(stat.mean))

def _dark_pct(pil_img, threshold=80):
    b = pil_img.tobytes()
    n = len(b) // 3
    dark = sum(1 for i in range(0, len(b), 3)
               if b[i] < threshold and b[i+1] < threshold
               and b[i+2] < threshold)
    return dark / n if n else 0.0

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ─── Theme (matches Shiny Hunter) ─────────────────────────────────
BG       = "#0a0a18"
BG2      = "#12122a"
BG3      = "#1a1a38"
FG       = "#dde0ff"
FG_DIM   = "#6666aa"
GOLD     = "#FFD700"
GREEN_HI = "#39ff14"
RED_HI   = "#ff4444"

FONT_MONO = ("Courier New", 9)
FONT_MED  = ("Courier New", 10)
FONT_BIG  = ("Courier New", 12, "bold")
FONT_HDR  = ("Courier New", 18, "bold")

IMG_EXTS = (".png", ".jpg", ".jpeg", ".bmp")

# Detection modes (matches shiny_hunter.py)
MODE_DARK_PIXEL  = "dark_pixel"     # Gen II — count dark ink in star zone
MODE_SPRITE_DIFF = "sprite_diff"    # Gen III — pixel-diff against sprite baseline

# Default thresholds per mode
THRESHOLDS = {
    MODE_DARK_PIXEL : 8.0,    # pixel-diff threshold, paired with dark-pct margin
    MODE_SPRITE_DIFF: 10.0,   # pure pixel-diff threshold
}
DARK_PCT_MARGIN  = 0.05       # Gen II — auto-calibrated: baseline_dark + 5pp


def _btn(parent, text, cmd, bg=BG3, fg=FG, **kw):
    b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                  activebackground=BG2, activeforeground=GOLD,
                  borderwidth=0, highlightthickness=0, cursor="hand2",
                  **kw)
    return b


# ═════════════════════════════════════════════════════════════════
# APP
# ═════════════════════════════════════════════════════════════════

class ShinyScannerApp:

    CONFIG_FILE = "shiny_scanner_config.json"

    def __init__(self, root):
        self.root = root
        root.title("Shiny Scanner — Shiny Hunter companion")
        root.configure(bg=BG)
        root.geometry("1000x720")

        # State
        self.folder         = None
        self.image_paths    = []
        self.sample_image   = None
        self.zone           = None
        self.baseline       = None
        self.baseline_dark  = 0.0
        self.mode           = tk.StringVar(value=MODE_SPRITE_DIFF)
        self.threshold      = tk.DoubleVar(value=THRESHOLDS[MODE_SPRITE_DIFF])
        self.results        = []

        self.scan_thread   = None
        self.cancel_flag   = threading.Event()
        self.log_q         = queue.Queue()

        self._load_cfg()
        self._build_ui()
        self._poll_log()

    # ── Config persistence ────────────────────────────────────────

    def _load_cfg(self):
        self.cfg = {}
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE) as f:
                    self.cfg = json.load(f)
            except Exception:
                self.cfg = {}

    def _save_cfg(self):
        try:
            with open(self.CONFIG_FILE, "w") as f:
                json.dump(self.cfg, f, indent=2)
        except Exception:
            pass

    # ── UI ────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg=BG, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="✨  SHINY SCANNER  ✨",
                 font=FONT_HDR, fg=GOLD, bg=BG).pack()
        tk.Label(hdr, text="Post-hunt verification · scans every screenshot for missed shinies",
                 font=FONT_MONO, fg=FG_DIM, bg=BG).pack()

        # Main split: left controls / right preview
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=6)

        # Left column — controls
        left = tk.Frame(body, bg=BG, width=380)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)
        self._build_controls(left)

        # Right column — preview + log
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        self._build_preview(right)

    def _build_controls(self, parent):
        # Detection mode toggle (at top — affects everything below)
        mode_frame = tk.LabelFrame(parent, text="  Detection Mode  ",
                                   font=FONT_BIG, fg=GOLD, bg=BG, padx=10, pady=6)
        mode_frame.pack(fill="x", pady=(0, 8))
        tk.Radiobutton(mode_frame, variable=self.mode, value=MODE_DARK_PIXEL,
                       text="Gen II — star icon (Gold / Silver / Crystal)",
                       font=FONT_MONO, fg=FG, bg=BG,
                       selectcolor=BG3, activebackground=BG, activeforeground=GOLD,
                       command=self._on_mode_change).pack(anchor="w")
        tk.Radiobutton(mode_frame, variable=self.mode, value=MODE_SPRITE_DIFF,
                       text="Gen III — sprite color (Ruby / Sapphire / Emerald / FR/LG)",
                       font=FONT_MONO, fg=FG, bg=BG,
                       selectcolor=BG3, activebackground=BG, activeforeground=GOLD,
                       command=self._on_mode_change).pack(anchor="w")

        # Step 1 — pick folder
        s1 = tk.LabelFrame(parent, text="  STEP 1 — Screenshots Folder  ",
                          font=FONT_BIG, fg=GOLD, bg=BG, padx=10, pady=8)
        s1.pack(fill="x", pady=(0, 8))
        _btn(s1, "📂  Select Folder…", self._pick_folder,
             bg="#1a4a8a", fg="white", padx=14, pady=8,
             font=FONT_BIG).pack(fill="x")
        self.folder_var = tk.StringVar(value="No folder selected")
        tk.Label(s1, textvariable=self.folder_var, font=FONT_MONO,
                 fg=GOLD, bg=BG, wraplength=340,
                 justify="left").pack(pady=(8, 0), anchor="w")
        self.count_var = tk.StringVar(value="")
        tk.Label(s1, textvariable=self.count_var, font=FONT_MONO,
                 fg=FG, bg=BG).pack(anchor="w")

        # Step 2 — draw star/sprite zone on sample
        self._s2_frame = tk.LabelFrame(parent, text="  STEP 2 — Detection Zone  ",
                          font=FONT_BIG, fg=GOLD, bg=BG, padx=10, pady=8)
        self._s2_frame.pack(fill="x", pady=(0, 8))
        self._s2_text_var = tk.StringVar(value=
            "Drag a box on the preview (right side) over\n"
            "the top-right corner where shiny ✦ stars\n"
            "appear next to the gender symbol.\n"
            "Use a NON-shiny frame as the sample.")
        tk.Label(self._s2_frame, textvariable=self._s2_text_var,
                 font=FONT_MONO, fg=FG, bg=BG,
                 justify="left").pack(anchor="w", pady=(0, 6))
        self.zone_var = tk.StringVar(value="No zone set — drag on preview")
        tk.Label(self._s2_frame, textvariable=self.zone_var, font=FONT_MONO,
                 fg=GOLD, bg=BG).pack(anchor="w")

        # Step 3 — threshold + scan
        s3 = tk.LabelFrame(parent, text="  STEP 3 — Scan  ",
                          font=FONT_BIG, fg=GOLD, bg=BG, padx=10, pady=8)
        s3.pack(fill="x", pady=(0, 8))

        thr_row = tk.Frame(s3, bg=BG)
        thr_row.pack(fill="x", pady=(0, 6))
        tk.Label(thr_row, text="Threshold:", font=FONT_MONO,
                 fg=FG, bg=BG).pack(side="left")
        tk.Spinbox(thr_row, from_=1.0, to=100.0, increment=0.5,
                   textvariable=self.threshold, width=6,
                   font=FONT_MONO, bg=BG3, fg=FG,
                   buttonbackground=BG3).pack(side="left", padx=6)
        self._threshold_hint_var = tk.StringVar(value="(Gen II default: 8.0)")
        tk.Label(thr_row, textvariable=self._threshold_hint_var, font=FONT_MONO,
                 fg=FG_DIM, bg=BG).pack(side="left")

        self.scan_btn = _btn(s3, "🔍  Scan All Screenshots",
                             self._start_scan,
                             bg="#2a5a2a", fg="white",
                             padx=14, pady=8, font=FONT_BIG)
        self.scan_btn.pack(fill="x")

        self.progress = ttk.Progressbar(s3, mode="determinate")
        self.progress.pack(fill="x", pady=(8, 0))
        self.progress_var = tk.StringVar(value="")
        tk.Label(s3, textvariable=self.progress_var, font=FONT_MONO,
                 fg=FG_DIM, bg=BG).pack(anchor="w")

        # Step 4 — results
        s4 = tk.LabelFrame(parent, text="  RESULTS  ",
                          font=FONT_BIG, fg=GOLD, bg=BG, padx=10, pady=8)
        s4.pack(fill="both", expand=True, pady=(0, 8))

        self.summary_var = tk.StringVar(value="No scan run yet")
        tk.Label(s4, textvariable=self.summary_var, font=FONT_MONO,
                 fg=FG, bg=BG, justify="left",
                 wraplength=340).pack(anchor="w", pady=(0, 6))

        # Listbox of hits
        list_frame = tk.Frame(s4, bg=BG)
        list_frame.pack(fill="both", expand=True)
        sb = tk.Scrollbar(list_frame)
        sb.pack(side="right", fill="y")
        self.hits_box = tk.Listbox(list_frame,
                                    bg=BG3, fg=GOLD,
                                    selectbackground=GOLD,
                                    selectforeground=BG,
                                    font=FONT_MONO,
                                    yscrollcommand=sb.set,
                                    activestyle="none")
        self.hits_box.pack(side="left", fill="both", expand=True)
        sb.config(command=self.hits_box.yview)
        self.hits_box.bind("<<ListboxSelect>>", self._show_selected_hit)

        _btn(s4, "💾  Export results to CSV",
             self._export_csv, bg=BG3, fg=FG,
             padx=8, pady=4, font=FONT_MONO).pack(fill="x", pady=(6, 0))

    def _build_preview(self, parent):
        wrap = tk.LabelFrame(parent, text=" Sample Preview — drag to set star zone ",
                            font=FONT_MED, fg=FG_DIM, bg=BG, padx=6, pady=6)
        wrap.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(wrap, bg="black",
                                 highlightthickness=1,
                                 highlightbackground=BG3,
                                 cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas_img_ref = None
        self.canvas_rect    = None
        self.canvas_image_size = (0, 0)   # rendered W,H
        self.canvas_image_offset = (0, 0) # x,y offset of image in canvas
        self.canvas_scale  = 1.0          # display→original

        # Drag state
        self._drag = {"sx": 0, "sy": 0, "active": False}
        self.canvas.bind("<ButtonPress-1>",   self._on_press)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # Log box below
        log_frame = tk.LabelFrame(parent, text=" Log ",
                                   font=FONT_MED, fg=FG_DIM, bg=BG,
                                   padx=6, pady=4)
        log_frame.pack(fill="x", pady=(6, 0))
        self.log_widget = tk.Text(log_frame, bg=BG3, fg=FG,
                                   font=FONT_MONO, height=8,
                                   borderwidth=0, highlightthickness=0)
        self.log_widget.pack(fill="x")
        self.log_widget.tag_configure("hit", foreground=GOLD)
        self.log_widget.tag_configure("dim", foreground=FG_DIM)
        self.log_widget.tag_configure("err", foreground=RED_HI)

    # ── Log queue ─────────────────────────────────────────────────

    def _log(self, msg, tag=None):
        self.log_q.put((msg, tag))

    def _poll_log(self):
        try:
            while True:
                msg, tag = self.log_q.get_nowait()
                self.log_widget.insert("end", msg + "\n", tag or ())
                self.log_widget.see("end")
        except queue.Empty:
            pass
        self.root.after(120, self._poll_log)

    # ── Step 1: pick folder ──────────────────────────────────────

    def _pick_folder(self):
        last = self.cfg.get("last_folder", "")
        folder = filedialog.askdirectory(
            title="Select the screenshots folder",
            initialdir=last if os.path.isdir(last) else os.getcwd())
        if not folder:
            return
        self.cfg["last_folder"] = folder
        self._save_cfg()
        self._load_folder(folder)

    def _load_folder(self, folder):
        self.folder = folder
        self.image_paths = sorted([
            str(p) for p in Path(folder).iterdir()
            if p.is_file() and p.suffix.lower() in IMG_EXTS
        ])
        n = len(self.image_paths)
        short = folder if len(folder) <= 40 else "…" + folder[-37:]
        self.folder_var.set(short)
        self.count_var.set(f"Found {n} screenshot{'s' if n != 1 else ''}")
        self._log(f"📂  Loaded {n} screenshots from {folder}",
                  tag=None if n else "err")
        if n == 0:
            return
        # Show first screenshot for zone selection
        try:
            self.sample_image = Image.open(self.image_paths[0]).convert("RGB")
            self._render_sample()
            self._log(f"    Preview: {self.image_paths[0]}", tag="dim")
        except Exception as e:
            self._log(f"⚠️  Failed to load sample: {e}", tag="err")

    def _render_sample(self):
        """Fit sample image to canvas, store scale + offset for coord math."""
        if not self.sample_image:
            return
        self.canvas.update_idletasks()
        cw = max(self.canvas.winfo_width(), 100)
        ch = max(self.canvas.winfo_height(), 100)

        ow, oh = self.sample_image.size
        scale = min(cw / ow, ch / oh)
        nw, nh = int(ow * scale), int(oh * scale)

        resized = self.sample_image.resize((nw, nh), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(resized)
        self.canvas_img_ref = tk_img
        self.canvas.delete("all")
        # Center the image
        ox = (cw - nw) // 2
        oy = (ch - nh) // 2
        self.canvas.create_image(ox, oy, anchor="nw", image=tk_img)
        self.canvas_image_size = (nw, nh)
        self.canvas_image_offset = (ox, oy)
        self.canvas_scale = scale

        # Re-draw any existing zone outline on top
        self._redraw_zone_outline()

    def _redraw_zone_outline(self):
        if not self.zone:
            return
        z = self.zone
        ox, oy = self.canvas_image_offset
        s = self.canvas_scale
        x1 = ox + int(z["left"] * s)
        y1 = oy + int(z["top"] * s)
        x2 = ox + int((z["left"] + z["width"]) * s)
        y2 = oy + int((z["top"] + z["height"]) * s)
        if self.canvas_rect:
            self.canvas.delete(self.canvas_rect)
        self.canvas_rect = self.canvas.create_rectangle(
            x1, y1, x2, y2, outline=GOLD, width=2)

    # ── Step 2: drag zone on sample ──────────────────────────────

    def _on_press(self, e):
        if not self.sample_image:
            return
        self._drag["sx"] = e.x
        self._drag["sy"] = e.y
        self._drag["active"] = True
        if self.canvas_rect:
            self.canvas.delete(self.canvas_rect)
            self.canvas_rect = None

    def _on_drag(self, e):
        if not self._drag["active"]:
            return
        if self.canvas_rect:
            self.canvas.delete(self.canvas_rect)
        self.canvas_rect = self.canvas.create_rectangle(
            self._drag["sx"], self._drag["sy"], e.x, e.y,
            outline=GOLD, width=2)

    def _on_release(self, e):
        if not self._drag["active"]:
            return
        self._drag["active"] = False
        if not self.sample_image:
            return

        # Convert canvas coords to original-image coords
        ox, oy = self.canvas_image_offset
        nw, nh = self.canvas_image_size
        s = self.canvas_scale
        if s == 0:
            return

        # Clamp to image bounds
        def clamp_x(x): return max(ox, min(ox + nw, x))
        def clamp_y(y): return max(oy, min(oy + nh, y))
        x1c, y1c = clamp_x(self._drag["sx"]), clamp_y(self._drag["sy"])
        x2c, y2c = clamp_x(e.x), clamp_y(e.y)

        x1 = int(min(x1c, x2c) - ox) / s
        y1 = int(min(y1c, y2c) - oy) / s
        x2 = int(max(x1c, x2c) - ox) / s
        y2 = int(max(y1c, y2c) - oy) / s

        w = int(x2 - x1)
        h = int(y2 - y1)
        if w < 4 or h < 4:
            self._log("⚠️  Zone too small — try again", tag="err")
            return

        self.zone = {"left": int(x1), "top": int(y1),
                     "width": w, "height": h}
        self.zone_var.set(f"✅  Zone: {w}×{h}px @ ({int(x1)},{int(y1)})")
        self._log(f"⭐  Zone set: {w}×{h}px at ({int(x1)},{int(y1)})")

        # Capture baseline from sample image
        try:
            crop = self.sample_image.crop(
                (int(x1), int(y1), int(x1) + w, int(y1) + h))
            self.baseline = crop.convert("RGB")
            self.baseline_dark = _dark_pct(self.baseline)
            self._log(f"📐  Baseline captured  size={self.baseline.size}  "
                      f"dark={self.baseline_dark*100:.1f}%", tag="dim")
        except Exception as ex:
            self._log(f"⚠️  Baseline capture failed: {ex}", tag="err")

    def _on_mode_change(self):
        """Switch threshold default and instructions when user changes mode."""
        m = self.mode.get()
        # Snap threshold to mode's default
        self.threshold.set(THRESHOLDS[m])
        if m == MODE_SPRITE_DIFF:
            self._threshold_hint_var.set("(Gen III default: 10.0)")
            self._s2_text_var.set(
                "Drag a box on the preview over the\n"
                "POKÉMON'S BODY on the battle screen.\n"
                "Use a NON-shiny frame as the sample.\n"
                "Shiny detected by big color shift in the zone.")
            self._s2_frame.configure(text="  STEP 2 — Sprite Zone  ")
        else:
            self._threshold_hint_var.set("(Gen II default: 8.0)")
            self._s2_text_var.set(
                "Drag a box on the preview (right side) over\n"
                "the top-right corner where shiny ✦ stars\n"
                "appear next to the gender symbol.\n"
                "Use a NON-shiny frame as the sample.")
            self._s2_frame.configure(text="  STEP 2 — Star Zone  ")
        self._log(f"🔀  Detection mode → {m}")

    # ── Step 3: scan ──────────────────────────────────────────────

    def _start_scan(self):
        if not self.image_paths:
            messagebox.showwarning("No folder", "Select a screenshots folder first.")
            return
        if self.zone is None or self.baseline is None:
            messagebox.showwarning("No zone",
                "Drag a star detection zone on the preview first.")
            return
        if self.scan_thread and self.scan_thread.is_alive():
            self.cancel_flag.set()
            return

        self.cancel_flag.clear()
        self.results = []
        self.hits_box.delete(0, "end")
        self.summary_var.set("Scanning…")
        self.scan_btn.configure(text="⏹  Cancel scan", bg="#5a2a2a")

        self.scan_thread = threading.Thread(
            target=self._scan_worker, daemon=True)
        self.scan_thread.start()

    def _scan_worker(self):
        """
        Scan dispatches on detection mode:

        Gen II (dark_pixel):
          - Method 1: baseline pixel-diff
          - Method 2: dark-pixel-count signature (auto-calibrated against
            the sample frame's baseline dark%)
          - Hit if EITHER crosses threshold; method shown in results

        Gen III (sprite_diff):
          - Pure baseline pixel-diff.  A shiny color swap produces a
            massive diff (30-80) vs noise (1-5), so a single threshold
            cleanly separates them.
        """
        mode      = self.mode.get()
        threshold = float(self.threshold.get())
        zone      = self.zone
        baseline  = self.baseline
        paths     = self.image_paths
        total     = len(paths)
        bx, by    = zone["left"], zone["top"]
        bw, bh    = zone["width"], zone["height"]

        # Auto-calibrated dark threshold from sample frame (Gen II only)
        base_dark   = self.baseline_dark
        dark_thresh = base_dark + DARK_PCT_MARGIN

        hits         = []   # (path, diff, dark_pct, method)
        all_results  = []   # (path, diff, dark_pct)
        errors       = 0

        self.root.after(0, lambda: self.progress.configure(
            maximum=total, value=0))

        self._log(f"📊  Scanning in {mode} mode  "
                  f"threshold={threshold}  "
                  f"{'dark_baseline=' + format(base_dark*100, '.1f') + '%' if mode == MODE_DARK_PIXEL else ''}")

        for i, path in enumerate(paths, 1):
            if self.cancel_flag.is_set():
                self._log("⏹  Scan cancelled", tag="err")
                break
            try:
                img  = Image.open(path).convert("RGB")
                crop = img.crop((bx, by, bx + bw, by + bh))
                if crop.size != baseline.size:
                    crop = crop.resize(baseline.size, Image.LANCZOS)

                diff = _mean_abs_diff(crop, baseline)

                if mode == MODE_SPRITE_DIFF:
                    dark_pct = -1.0
                    all_results.append((path, diff, dark_pct))
                    if diff >= threshold:
                        method = "DIFF"
                        hits.append((path, diff, dark_pct, method))
                        self._log(
                            f"  🌟 HIT [{method}]  diff={diff:6.2f}  "
                            f"{os.path.basename(path)}", tag="hit")
                else:
                    dark_pct = _dark_pct(crop)
                    all_results.append((path, diff, dark_pct))
                    hit_diff = diff     >= threshold
                    hit_dark = dark_pct >= dark_thresh
                    if hit_diff or hit_dark:
                        method = ("BOTH"     if hit_diff and hit_dark else
                                  "DIFF"     if hit_diff              else
                                  "DARK-PIX")
                        hits.append((path, diff, dark_pct, method))
                        icon = "🌟" if method == "BOTH" else "⚠️ "
                        self._log(
                            f"  {icon} HIT [{method:8s}]  "
                            f"diff={diff:6.2f}  dark={dark_pct*100:5.1f}%  "
                            f"{os.path.basename(path)}", tag="hit")
            except Exception as e:
                errors += 1
                self._log(f"  ⚠️  {os.path.basename(path)}: {e}",
                          tag="err")

            if i % 5 == 0 or i == total:
                progress_msg = f"{i}/{total}   "
                if hits:
                    progress_msg += f"hits: {len(hits)}"
                self.root.after(0, self._update_progress, i, progress_msg)

        # Sort hits by strongest signal
        if mode == MODE_SPRITE_DIFF:
            hits.sort(key=lambda p: -p[1])  # by diff descending
        else:
            hits.sort(key=lambda p: -p[2])  # by dark_pct descending
        self.results   = hits
        self.all_diffs = all_results

        self.root.after(0, self._scan_finished, total, hits, errors)

    def _update_progress(self, i, msg):
        self.progress.configure(value=i)
        self.progress_var.set(msg)

    def _scan_finished(self, total, hits, errors):
        self.scan_btn.configure(text="🔍  Scan All Screenshots",
                                bg="#2a5a2a")
        # Populate hits listbox
        for path, diff, dark_pct, method in hits:
            self.hits_box.insert(
                "end", f"dark {dark_pct*100:5.1f}%  diff {diff:6.2f}  "
                       f"[{method:8s}]  {os.path.basename(path)}")

        if hits:
            top = hits[0]
            summary = (f"⚠️  {len(hits)} POSSIBLE HIT{'S' if len(hits) > 1 else ''} "
                       f"in {total} screenshots.\n"
                       f"Top: dark={top[2]*100:.1f}%  diff={top[1]:.1f}\n"
                       f"Method legend:\n"
                       f"  BOTH      = both signals agree → strongest\n"
                       f"  DIFF      = baseline-diff only\n"
                       f"  DARK-PIX  = dark pixel count only\n"
                       f"Click a row to view.")
            self.summary_var.set(summary)
            self._log("")
            self._log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", tag="hit")
            self._log(f"  Scan complete: {len(hits)} hit(s) of {total}",
                      tag="hit")
            self._log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", tag="hit")
        else:
            top = sorted(self.all_diffs, key=lambda p: -p[2])[:5]
            tops_str = "\n".join(
                f"   dark {dp*100:4.1f}%  diff {d:5.2f}  {os.path.basename(p)}"
                for p, d, dp in top)
            summary = (f"✅  Clean — no shinies detected.\n"
                       f"Scanned {total} screenshots, errors: {errors}.\n"
                       f"Highest dark-pixel %s:\n"
                       f"{tops_str}")
            self.summary_var.set(summary)
            self._log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            self._log(f"  Scan complete: 0 hits of {total}  ✅")
            self._log(f"  Noise-floor (top dark-pct):", tag="dim")
            for p, d, dp in top:
                self._log(f"    dark={dp*100:5.1f}%  diff={d:5.2f}  "
                          f"{os.path.basename(p)}", tag="dim")
            self._log(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    def _show_selected_hit(self, _evt):
        sel = self.hits_box.curselection()
        if not sel:
            return
        idx = sel[0]
        path, diff, dark_pct, method = self.results[idx]
        try:
            img = Image.open(path).convert("RGB")
        except Exception as e:
            messagebox.showerror("Open failed", str(e))
            return

        marked = img.copy()
        draw = ImageDraw.Draw(marked)
        z = self.zone
        draw.rectangle(
            [z["left"], z["top"],
             z["left"] + z["width"], z["top"] + z["height"]],
            outline="#ff4444", width=3)

        popup = tk.Toplevel(self.root)
        popup.title(f"Hit [{method}] — dark {dark_pct*100:.1f}% diff {diff:.1f}")
        popup.configure(bg=BG)

        tk.Label(popup,
                 text=f"🌟  Possible shiny — method [{method}]",
                 font=FONT_BIG, fg=GOLD, bg=BG).pack(pady=8)
        tk.Label(popup,
                 text=(f"Dark pixels: {dark_pct*100:.2f}%   "
                       f"Baseline diff: {diff:.2f}"),
                 font=FONT_MONO, fg=FG, bg=BG).pack()
        tk.Label(popup, text=path, font=FONT_MONO,
                 fg=FG_DIM, bg=BG).pack()

        mw, mh = marked.size
        scale = min(1.0, 800 / mw)
        if scale < 1.0:
            marked = marked.resize(
                (int(mw * scale), int(mh * scale)), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(marked)
        lbl = tk.Label(popup, image=tk_img, bg=BG)
        lbl.image = tk_img
        lbl.pack(pady=6)

        try:
            crop = img.crop(
                (z["left"], z["top"],
                 z["left"] + z["width"], z["top"] + z["height"]))
            cw, ch = crop.size
            zoom = max(1, 240 // max(cw, ch))
            crop_big = crop.resize((cw * zoom, ch * zoom), Image.NEAREST)
            tk_crop = ImageTk.PhotoImage(crop_big)
            tk.Label(popup, text="Zone (zoomed):", font=FONT_MONO,
                     fg=FG_DIM, bg=BG).pack(pady=(8, 2))
            clbl = tk.Label(popup, image=tk_crop, bg=BG,
                            relief="solid", borderwidth=1)
            clbl.image = tk_crop
            clbl.pack(pady=(0, 8))
        except Exception:
            pass

        _btn(popup, "Close", popup.destroy,
             bg=BG3, fg=FG, padx=12, pady=4, font=FONT_MONO).pack(pady=8)

    def _export_csv(self):
        if not getattr(self, "all_diffs", None):
            messagebox.showwarning("Nothing to export",
                "Run a scan first.")
            return
        out = filedialog.asksaveasfilename(
            title="Save scan report",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")],
            initialfile="shiny_scan_results.csv")
        if not out:
            return
        try:
            with open(out, "w", encoding="utf-8") as f:
                f.write("filename,pixel_diff,dark_pct,is_hit,threshold\n")
                thr = float(self.threshold.get())
                for path, diff, dark_pct in sorted(
                        self.all_diffs, key=lambda p: -p[2]):
                    name = os.path.basename(path).replace(",", "_")
                    is_hit = (diff >= thr) or (dark_pct >= 0.13)
                    f.write(f"{name},{diff:.4f},{dark_pct:.4f},"
                            f"{'YES' if is_hit else 'no'},"
                            f"{thr:.2f}\n")
            self._log(f"💾  Exported to {out}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))


# ═════════════════════════════════════════════════════════════════
# ENTRY
# ═════════════════════════════════════════════════════════════════

def main():
    root = tk.Tk()
    app  = ShinyScannerApp(root)
    # Re-render the sample when the window resizes
    def on_resize(e):
        if e.widget is root and app.sample_image:
            app._render_sample()
    root.bind("<Configure>", on_resize)
    root.mainloop()


if __name__ == "__main__":
    main()

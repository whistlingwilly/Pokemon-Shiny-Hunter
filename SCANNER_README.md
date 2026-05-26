# Shiny Scanner

Companion verification tool for **Shiny Hunter**. Loads a folder full of
screenshots (the ones the hunter saves to `screenshots/` every cycle),
lets you mark the same star detection zone, and scans every image to
flag anything suspicious.

Use it as a post-hunt safety net — if anything got missed live, this will
catch it.

---

## Run it

```
scan.bat
```

Or build a standalone executable:

```
build_scanner.bat        →  dist\ShinyScanner.exe
```

Only dependencies: `numpy`, `Pillow`. Both will install automatically on
first run via `scan.bat`.

---

## Workflow

1. **Step 1 — Select folder.** Point it at your `screenshots/` directory
   (the one the hunter writes to each cycle).
2. **Step 2 — Draw the star zone.** The first screenshot loads into the
   preview pane on the right. Drag a tight box over the top-right corner
   where the shiny ✦ stars would appear, just right of the gender icon.
   This frame is used as the **baseline** — make sure the first
   screenshot is a NON-shiny one (it almost certainly is).
3. **Step 3 — Scan.** Click *Scan All Screenshots*. The progress bar
   walks through every file, comparing the zone against the baseline.
   Anything with a pixel diff ≥ threshold (default 8.0, same as the live
   hunter) is flagged as a hit.
4. **Inspect hits.** The Results panel lists every hit, sorted by diff
   value (highest first). Click any row to open a popup with the full
   screenshot, the star zone outlined in red, and a zoomed-in crop of
   that zone so you can verify with your eyes.
5. **Export to CSV** if you want a permanent record of every screenshot
   and its diff value.

---

## What "hit" means

A hit is *not* a guaranteed shiny — it's "something changed in the zone
versus the baseline beyond the threshold." Real causes of a hit:

* Actual shiny stars appeared (the thing we're looking for)
* A status screen frame caught mid-transition (text scrolling, cursor
  blinking, animation frame)
* Different Pokémon shown in the slot (different sprite colors)
* Screenshot taken mid-fade, mid-menu, etc.

That's why hits open a viewer: you eyeball them. Stars look like
distinct white pixels; transition artifacts look smeared or like
gibberish.

If you see zero hits across a 1000+ screenshot folder, that's strong
evidence the hunt didn't miss anything.

---

## Threshold tuning

* **Default 8.0** matches the live hunter exactly.
* **Lower** (e.g. 4.0) to be paranoid — you'll get more false hits to
  review, but you definitely won't miss anything.
* **Higher** (e.g. 15.0) to filter out minor transition noise if the
  default flags too much.

The scan log shows the "noise floor" of the top 5 non-hit diffs after a
clean scan, so you can see how close your real data sat to the threshold.

---

## File layout

```
shiny_scanner.py         — the app
scan.bat                 — run with Python
build_scanner.bat        — make a standalone exe
shiny_scanner_config.json — remembers last folder selected
```

No shiny_hunter coupling — runs completely standalone, no shared
config, no shared baseline.

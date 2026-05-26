# 🌟 Pokémon Shiny Hunter — Universal Edition

Automated shiny Pokémon hunting using the **Epilogue GB Operator** + **Playback** software.

Record your button sequence once. Let it run thousands of times. Walk away. The app watches the screen and stops the instant a shiny is found — game never reset, Pokémon never lost.

**[⬇️ Download Latest Release](https://github.com/whistlingwilly/Pokemon-Shiny-Hunter/releases/latest)**

---

## ⚠️ **IMPORTANT: GBA Games Currently in Testing**

**Gen 3 (GBA) games are password-protected while we verify detection accuracy.**

| Status | Games | Notes |
|--------|-------|-------|
| ✅ **Fully Supported** | Gold · Silver · Crystal | Proven reliable, recommended for all users |
| 🔒 **Testing Phase** | Ruby · Sapphire · Emerald · FireRed · LeafGreen | Requires password (experimental) |

**For best results, use Gen 2 games.** GBA support is being actively tested with the community.

---

## 💛 Support the Project

If this app helped you catch a shiny, consider buying me a coffee!

**[💰 Donate via PayPal](https://www.paypal.com/donate/?hosted_button_id=NAC6SGJENDJEA)**

### 🎮 Looking for game donations!

I'm always hunting for cartridges to test new features on. If you have a spare copy collecting dust, send me a message — every donation directly helps expand support to more games!

Currently looking for: **Pokémon Ruby · Pokémon Crystal · Pokémon Emerald**

---

## 📺 Video Tutorial

New to the app? Start here:

**[▶️ How to set up Shiny Hunter for Gold / Silver / Crystal](https://youtu.be/mJ6YPVF4HQQ)**

*Ruby / Sapphire / Emerald and FireRed / LeafGreen guides coming soon!*

---

## 📥 Installation

1. Go to the [Releases page](https://github.com/whistlingwilly/Pokemon-Shiny-Hunter/releases/latest)
2. Download `ShinyHunterSetup_vX.Y.Z.exe`
3. Double-click and follow the setup wizard
4. Launch from your Start Menu or Desktop shortcut

No Python required — everything is bundled into a single installer. The app will automatically notify you when a new version is available.

---

## 🎮 Supported Games

### ✅ Gen 2 — Fully Supported (Recommended)

| Game | Platform | Starters | Detection Method |
|------|----------|----------|------------------|
| Pokémon Gold | Game Boy Color | Chikorita · Cyndaquil · Totodile | ✦ star icon next to gender symbol |
| Pokémon Silver | Game Boy Color | Chikorita · Cyndaquil · Totodile | ✦ star icon next to gender symbol |
| Pokémon Crystal | Game Boy Color | Chikorita · Cyndaquil · Totodile | ✦ star icon next to gender symbol |

### 🔒 Gen 3 — Testing Phase (Password Required)

| Game | Platform | Starters | Detection Method |
|------|----------|----------|------------------|
| Pokémon Ruby | Game Boy Advance | Treecko · Torchic · Mudkip | Full sprite color shift |
| Pokémon Sapphire | Game Boy Advance | Treecko · Torchic · Mudkip | Full sprite color shift |
| Pokémon Emerald | Game Boy Advance | Treecko · Torchic · Mudkip | Full sprite color shift |
| Pokémon FireRed | Game Boy Advance | Bulbasaur · Charmander · Squirtle | Gold ★ in portrait corner |
| Pokémon LeafGreen | Game Boy Advance | Bulbasaur · Charmander · Squirtle | Gold ★ in portrait corner |

---

## 🤔 What is shiny hunting?

In Pokémon games, every Pokémon has a **1 in 8,192** chance of being a rare alternate-colour "shiny" variant. For starters — the Pokémon you pick at the beginning of the game — the only way to hunt is to:

1. Save in front of the starter ball
2. Pick it up and check its stats
3. If it's not shiny, soft-reset and do it again
4. Repeat potentially thousands of times

At ~30 seconds per reset, hunting to the statistical average of ~5,600 resets would take over **46 hours of repetitive manual button pressing.**

This app automates every reset while you sleep, work, or do anything else — and stops the moment a shiny appears.

---

## 🚀 How to Use

The app includes a built-in **📖 Guide tab** with step-by-step instructions and reference images. Here's a quick overview:

### Step 1 — Install & Select Game
- Download and run the installer from the [Releases page](https://github.com/whistlingwilly/Pokemon-Shiny-Hunter/releases/latest)
- Launch the app
- Select your game and starter from the left sidebar
  - Gen 2 games work immediately
  - Gen 3 games require password (testing phase)

### Step 2 — Prepare Your Save
In Playback, load your game and save in the right spot:
- **Gen 2:** In front of Elm's desk, facing your target ball
- **Gen 3 RSE:** On Route 101 just before Birch's bag
- **Gen 3 FRLG:** In Oak's lab facing the starter table

### Step 3 — Set Up Detection (Region tab)

**Draw Game Area** — Drag a box around the Playback game viewport (exclude PLAY/DATA toolbar)

**Draw Detection Zone** — The app shows where based on your game:
- *Gen 2:* Status screen → draw around gender symbol area
- *Gen 3 RSE:* Battle screen → draw over full Pokémon body
- *Gen 3 FRLG:* Summary screen → tiny box over top-right portrait corner

> 💡 **Check the Guide tab** for reference images showing exactly where to draw!

**Capture Baseline** — With a non-shiny frame visible, click Capture Baseline

### Step 4 — Record Your Sequence (Record tab)
1. Click "Start Recording"
2. In Playback, perform one complete cycle:
   - Pick up the ball
   - Navigate to check screen
   - Soft reset
3. Click "Stop Recording"

### Step 5 — Start Hunting! (Hunt tab)
1. ✅ Enable "Reset" checkbox
2. ⚡ Optionally enable "Double Speed"
3. Click **▶ Start Hunt**

When a shiny is found:
- 🔔 Alarm sounds
- 🛑 Macro stops immediately
- ⚠️ Popup warns you NOT to reset
- ✅ **Go to Playback and SAVE your game** before clicking OK

---

## 🔬 Shiny Scanner

The **Scanner tab** (built into the app) lets you verify past hunts:

1. Click the "🔬 Scanner" tab
2. Select your screenshots folder
3. The scanner analyzes all frames
4. Shows which resets triggered as "shiny"
5. Click any hit to open the screenshot

This is your safety net — run it after every session to confirm you haven't missed anything.

---

## 🔍 How Detection Works

The app watches a small region of the Playback screen and compares it against a baseline reference you capture. Detection methods adapt automatically based on which game you select.

### Gen 2 — Gold / Silver / Crystal ✅

When a shiny appears on the status screen, a pair of ✦ sparkle stars show up next to the gender symbol. On a normal Pokémon this area is blank.

**Method:** Pixel difference detection. Stars appearing causes a sharp spike that triggers detection.

### Gen 3 — Ruby / Sapphire / Emerald 🔒

No star indicator — the entire Pokémon changes colour:
- Blue Mudkip → purple
- Green Treecko → teal-blue
- Orange Torchic → yellow

**Method:** Full sprite color shift detection. Different palette produces a massive pixel difference.

### Gen 3 — FireRed / LeafGreen 🔒

A small gold ★ appears in the top-right corner of the Pokémon portrait on the summary screen.

**Method:** Bright gold star vs. blank corner provides high-contrast signal.

### Two-Layer Verification

Every cycle:
1. **Live check** runs during hunt
2. If triggered → **Screenshot re-examined** independently
3. Both checks must agree before alarm sounds

This eliminates false positives while ensuring real shinies are never missed.

---

## 💡 Tips for Success

### ⚠️ Keep Detection Zones Small!
- Larger zones = more false positives
- Use the **Guide tab** reference images as templates
- FRLG star zone should be ~30-40 pixels only

### 🧪 Test Before Long Hunts
- Do 3-5 manual test resets
- Verify the app detects correctly
- Adjust zone if getting false positives

### 📊 Use the Scanner Tab
- Review screenshots after every session
- Confirm you haven't missed shinies
- Scanner auto-loads your hunt baseline

### 🎯 Gen 2 Shiny Starters Must Be Male
- Shiny stars (✦) only appear next to ♂ symbol
- Female starters cannot be shiny in Gen 2
- This is a game limitation, not an app issue

### 💻 Run Overnight
- The app never resets when a shiny is found
- Emergency stop: move mouse to top-left corner
- Perfect for unattended hunting while you sleep

---

## ❓ FAQ

**Do I need the Epilogue GB Operator?**
Yes. This app sends keystrokes to the Epilogue Playback software, which requires the GB Operator hardware running your cartridge.

**Can I run this overnight unattended?**
Yes — that's the primary use case. The app never resets the game when a shiny is found, and the emergency stop (move mouse to top-left corner) aborts the macro instantly.

**What if it misses a shiny?**
Between the post-cycle screenshot double-check and the Scanner tab, a missed shiny with a correctly configured zone is essentially impossible. Run the scanner after every session for extra confidence.

**What are the odds?**
1 in 8,192 per reset across all Gen 1–3 games. You have roughly a 50% chance within ~5,678 resets. Some people find one on reset 3. Some go past 15,000. The only losing strategy is stopping.

**Why are GBA games password-protected?**
We're actively testing detection accuracy with the community. Gen 2 games have been proven reliable through thousands of resets. GBA support works, but we want more testing data before opening it to everyone.

---

## 🗺️ What's Coming

### 🏆 Legendary Hunting
The same loop works for stationary legendaries — save in front of them, encounter, check, reset. Coming soon:
- **Gen 2:** Ho-Oh · Lugia · Suicune · Raikou · Entei · Lake of Rage Gyarados
- **Gen 3 RSE:** Groudon · Kyogre · Rayquaza · Latios · Latias · Regirock · Regice · Registeel
- **Gen 3 FRLG:** Mewtwo · Articuno · Zapdos · Moltres

### 🎰 Game Corner Pokémon
Automate the coin/token exchange loop for Pokémon like Abra, Scyther, Porygon, and Dratini.

### 🥚 Egg & Breeding Hunts
Masuda method egg hatching automation. Record the hatch cycle, let the app hatch thousands of eggs automatically.

### 📡 Multi-Device Parallel Hunting
Run simultaneous hunts on different games with a unified dashboard tracking all sessions.

### 🐧 Linux Support
Raspberry Pi 4/5 dedicated hunting station support is in progress — run hunts 24/7 on a tiny silent Pi.

---

## ⚙️ Building from Source

```bash
# Install dependencies
pip install -r requirements.txt

# Run directly
python shiny_hunter.py

# Build standalone .exe (Windows)
build_exe.bat

# Build Windows installer (requires Inno Setup)
build_installer.bat
```

Releases are built and published automatically via GitHub Actions when a version tag is pushed.

---

## 📁 Project Structure

```
Pokemon-Shiny-Hunter/
├── shiny_hunter.py          # Main application
├── shiny_scanner.py          # Scanner module (embedded in main app)
├── updater.py                # Auto-update system
├── assets/
│   └── zones/                # Zone reference guide images
│       ├── gen2_star.png     # Gen 2 status screen guide
│       ├── frlg_star.png     # FRLG summary screen guide
│       ├── rse_treecko.png   # Treecko sprite guide
│       ├── rse_mudkip.png    # Mudkip sprite guide
│       └── rse_torchic.png   # Torchic sprite guide
├── .github/
│   └── workflows/
│       └── build_release.yml # Auto-build on release
├── requirements.txt          # Python dependencies
└── README.md
```

---

## 🐛 Troubleshooting

### "Reference image not found"
- Make sure you've captured a baseline in the Region tab
- Baseline must be taken with Pokémon visible (not shiny)

### False Positives (Stops when not shiny)
- Detection zone is too large
- Check the **Guide tab** for reference images
- Make zone smaller and more precise
- FRLG: Zone must be tiny (~30-40px)

### Hunt Doesn't Start
- Verify you've recorded a sequence (Record tab)
- Check that game area is drawn (Region tab)
- Enable "Reset" checkbox in Hunt tab

### App Crashes
- Make sure Epilogue Playback is running
- Check that game area covers the full window
- Try restarting both Playback and Shiny Hunter

### Need More Help?
- Check the built-in **Guide tab** in the app
- Watch the [video tutorial](https://youtu.be/mJ6YPVF4HQQ)
- Open an issue on GitHub with your version number and game

---

## 📊 Community Stats

- 🏆 Highest confirmed reset count: 8,200+ (Sapphire Mudkip hunt)
- ✅ Gen 2 proven reliable across thousands of community resets
- 🧪 Gen 3 testing actively ongoing with promising results

---

## ⚠️ Requirements

- Windows 10 or 11
- [Epilogue GB Operator](https://www.epilogue.co/) + Playback software
- The Pokémon cartridge you want to hunt

*Not affiliated with Epilogue, Nintendo, or The Pokémon Company.*

---

## 🤝 Contributing

Found a bug or have a suggestion?
- Open an issue on GitHub
- Include your app version, game, and screenshots if applicable
- Check existing issues first to avoid duplicates

---

## 📜 License

This project is provided as-is for personal use with legally owned Pokémon games and Epilogue GB Operator hardware.

---

Made with ❤️ and too many soft resets

**[⬆️ Back to top](#-pokémon-shiny-hunter--universal-edition)** · **[💰 Support via PayPal](https://www.paypal.com/donate/?hosted_button_id=NAC6SGJENDJEA)** · **[⭐ Star this repo](https://github.com/whistlingwilly/Pokemon-Shiny-Hunter)**

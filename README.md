# AFK-Community

A desktop app for **AFK Arena** players. It helps you build your fastest **Nightmare Corridor** rotation from the heroes you actually own, compare your teams with your friends' teams, and see exactly what you're missing to go faster.

Everything runs on your PC. Your data stays in the app folder and is never uploaded anywhere.

## ⬇ Download (Windows)

| | |
|---|---|
| **[Installer — AFK-Community-setup.exe](https://github.com/shredia/AFK-Community/releases/latest/download/AFK-Community-setup.exe)** | Recommended. Run it and you're done. |
| [Portable — AFK-Community-portable.zip](https://github.com/shredia/AFK-Community/releases/latest/download/AFK-Community-portable.zip) | No installation: unzip it and open the `.exe`. |

All versions and their changes: [Releases](https://github.com/shredia/AFK-Community/releases).

> **Note:** the direct connection to esperianarchive.com (login, fetch, run downloads) is **in development**. Meanwhile, the app works with the files you download from the site yourself (see *Getting started*).

---

## Installation

**Installer (recommended):**

1. Download **AFK-Community-setup.exe** (link above) and run it. It doesn't need administrator rights.
2. Open **AFK-Community** from the Start menu (or the desktop shortcut).

The app is installed in `%LOCALAPPDATA%\Programs\AFK-Community`, and your data is kept in that folder. To uninstall it, use *Settings → Apps*; it asks whether to keep your data.

**Portable (no installation):**

1. Download **AFK-Community-portable.zip** (link above).
2. Unzip it anywhere you can write, for example in `Documents` (not in `C:\Program Files`).
3. Open `AFK-Community.exe`. The folder contains just the `.exe`, the `app` folder and this README: keep them together, the `.exe` doesn't work on its own.

The app checks GitHub for new versions and offers to update itself.

## Getting started

### Step 1: refresh your data on the site

Before downloading anything, ask the site to read your latest game data:

1. Log in to **esperianarchive.com**.
2. Open your account options → **[Game accounts](https://esperianarchive.com/game-accounts)**.
3. **①** Select the character (server) you play on.
4. **②** Press **Fetch … inventory and runs** and wait until it finishes (usually less than a minute).

<p align="center">
  <img src="docs/img/game-accounts-fetch.png" alt="Game accounts: ① choose your character, ② press Fetch" width="360">
</p>

### Step 2: download the files

- `afk-runs.json` from **[My runs](https://esperianarchive.com/my-runs)**: your runs.
- `afk-inventory.json` from **[Inventory](https://esperianarchive.com/inventory)**: your account (heroes, collections, pets, resources).

The **🌐 My runs** and **🌐 Inventory** buttons in the app open those pages for you.

### Step 3: import them into the app

1. Go to **Settings → Import / export → Choose file and import…** and import both files.
2. Open **Optimizer** and press **▶ Optimize**.

Repeat these steps whenever you play new runs or upgrade your heroes. Importing again only adds what's new.

## What you can do

The menu on the left has three groups: **Nightmare Corridor**, **Account** and **Other**. **⚙ Settings** is at the bottom.

### ⌂ Home
A quick status of your data: whether your account is imported, how many runs with details you have and on how many servers, and how many friends you've added (with how many runs). It also has shortcuts to the site pages and to each section.

## Nightmare Corridor (NC)

### ★ Optimizer
Finds the best team for each of this week's 6 bosses **without repeating heroes** (and, optionally, without repeating pets). Press **▶ Optimize** to run it.

- **★ Summary:** one card per boss showing the chosen team, its time and the total time. If a friend clears a boss faster, the card tells you, and whether you could copy that team.
- **Boss tabs:** your teams next to another source's teams. You see the differences between the two teams and between the builds of the heroes they share (SI, engraving, furniture, collection, gear). You also get a table of every hero used against that boss and who is faster with it.
- **🎯 What I'm missing:** your friends' teams that beat yours, how many seconds you'd gain and what you lack to build them: a hero, SI level, engraving, furniture, collection or pet. At the top it lists the single upgrades that gain you the most time.
- **📊 Statistics:** damage, % of total damage, healing, defense, kills, energy and HP for each hero in every round, plus your pet's damage and the boss's remaining HP.
- **Hero detail:** click any portrait to see its full build, which collections the guide recommends for it, and buttons to ban or limit it.

### ⚙ Configure (inside the optimizer)
- **Sources:** what to optimize with. Your runs, another server of yours, one friend, all friends, or any mix. Each boss can come from a different source.
- **Blocks:** heroes or pets you don't want to use, collections you don't have, and build limits (for example, "Dracula: SI max 20" or "any collection: max ★2"). Each rule can apply to all teams, only yours or only your friends'. Active rules show up as chips under the optimizer header; click a chip's ✕ to disable that rule.
- **My roster:** what you own, taken from your inventory. You can fix anything by hand, which helps when the inventory is outdated.
- **Search:** complete runs only; no borrowed or trial heroes; use only friends' teams you can build (✅) or almost build (🟡).
- **View:** portrait size.

### ⌕ Explore teams
Browse every team used against any boss, or your full runs sorted by total time. Useful to look for ideas outside the optimizer's choice.

### ↗ Weekly progress
A chart and a table of your best complete run each week, plus the sum of your best time on each boss that week. It also compares each week with the last time you faced the same bosses.

### Special Power (SP)
Only special heroes (Fawkes, Thoran, Eluard, …) have an SP. Their portraits show an **SP** badge:

- **Gold:** the hero used its SP that round.
- **Gray and crossed out:** the hero didn't use it.
- **Red "SP?":** the team had two or more special heroes and the file doesn't say which one was chosen. Open the hero's detail and click **"{hero} used it"** to save your answer.

If a team has only one special hero, the app marks that hero automatically, because its SP activates on its own.

### Borrowed, rented and trial heroes
- **Borrowed** (mercenaries) come as their owner built them. They're labeled, and you can exclude them.
- **Rented dimensional heroes** (e.g. Albedo) are **yours**: you ascend and equip them. The app treats them as your own heroes.

## Account

### ◉ My account
Your resources, heroes, collections, gear and pets from your last `afk-inventory.json` import. For each hero you see its build, whether its collection meets the guide's recommendation, and how you've done with it in NC.

### ☺ Friends
Import a friend's `afk-runs.json`, or a shared runs file they send you (see *Import / export*). The optimizer can mix their teams with yours, and **What I'm missing** shows what to copy from them. In this section you can also rename friends, optimize with their runs, or send them to the Recycle Bin.

Friends' runs are kept apart: they never mix with your own runs or with *My account*.

## Other

### ◈ Temporal Rift
A planner for the Temporal Rift event: what each floor gives you, which chest options to pick, what to buy in the medal shops, and whether your medals are enough to reach your goal by Friday. Your progress is saved per account and server.

**Top bar**
- **Account:** which of your servers you're planning.
- **Floor reached** and **Medals in game:** type what the game shows. Everything else is calculated from these two numbers.
- **🎯 Goal for Friday:** the floor you want to reach. **Current floor + 20** sets it quickly. The app shows what you'll earn between your floor and your goal.
- **⟲ Reset:** *Reset purchases (done and planned)*, *Remove only the planned purchases*, or *Reset the whole Rift (new season)*, which clears purchases, chosen chests and spent items and asks for your new floor.
- **Import from Excel…:** optional. Loads rewards, shops and your progress from a `fractura_temporal_*.xlsx` sheet (sheets `pisos`, `Total` and `Tienda`). The app already includes the rewards table, so you don't need it to start.

**Medals:** a summary of *Medals earned*, *Spent*, *Current balance*, *To earn on floors*, *Planned purchases* and *Balance at the end*. It tells you if you'll have medals left over, or how many you're short and on which floor.

**Tabs.** Each one has a view that looks like the game (**🎮 Visual**, or **🛒 As in the game** in the shops) and a **📋 Table** view.
- **Summary per resource:** for every resource, how much is *In your bag*, *Obtained* in the Rift, still coming *To the goal* and *Still obtainable*, and how much **You'll have** (bag + floors left + planned chests and purchases). **Shop and chest resources only** hides the rest.
- **Choice chests:** each chest opens by choosing **one** option. *Now* = chests you already have and chose; *Planned* = chests you'll get before your goal and what you'll pick. Click an option to choose 1; right-click for more (choose all, plan, remove). If you opened chests in the game without recording them here, use **I already spent the missing ones** so the counts match.
- **Medal shops:** switch between **🛒 Buy** (what you already bought) and **📝 Plan** (what you'll buy with the medals you still have to earn). Locked shops show how many floors unlock them, and you can plan them in advance. Click an item to buy or plan 1; right-click for more.
- **Rewards per floor:** every floor and its rewards. ✓ = obtained, highlighted = what you'll earn until your Friday goal, light = locked. Right-click a floor to mark it as **your current floor** or as **Friday's goal**.

**🔗 Link to the bag…:** connects a Rift resource to the matching item of your inventory (some show up as "Item 100000xx"), so the app can read how many you have. Your bag comes from your last `afk-inventory.json` import.

### ✎ Guides
Coming soon.

## ⚙ Settings

- **General:** language (English or Spanish), your installed version and **Check for updates…**
- **Import / export:** see below.
- **Site access:** logging in to esperianarchive.com from the app. *In development.*

### Import / export
Works with the files you download from the site by hand; you don't need to log in.

**Import** with **Choose file and import…**. The app recognizes the file by itself:
- **`afk-runs.json`:** your NC runs. The file doesn't say which character played them, so the app asks **whose runs they are**:
  - **They're mine:** pick the site account and server. The app suggests the server that already has runs from those dates.
  - **They're a friend's:** type their name (and server, if you want).

  Only missing runs are added. Runs you already had get their statistics (damage, healing, energy…) added. Runs from other modes are skipped.
- **`afk-inventory.json`:** a snapshot of your account (resources, heroes, collections, gear, pets). It replaces *My account*; the previous one is kept as `cuenta_actual.anterior.json`.
- **Shared runs (`.json` exported by this app):** runs that include who used the SP in each round, plus statistics.
- **`.zip` backup** exported by this app. Its files replace the ones you have with the same name.

The **🌐 Game accounts (Fetch)**, **🌐 My runs** and **🌐 Inventory** buttons open the site pages where you refresh and download those files.

**Export**, choosing one of your servers or a friend:
- **Export runs to share (.json):** only the NC runs, with **who used the SP in each round** and the statistics. This is the file to send to a friend, because plain `afk-runs.json` doesn't record the SP.
- **Export .zip:** everything from that server or friend (runs, details, My account, Temporal Rift, blocks), to move it to another PC or keep a backup.

**What the files don't include:** both site files share each hero's build (quality, SI, engraving, furniture, gear and collection). They don't include the hero's role (tank/marksman/mage), engraving nodes, pet level or which slot each piece of furniture goes in. The app fills those in from what you already have for the same hero or pet.

### Updates
The app checks GitHub for new versions. When there is one, a **⬆ A new version is available** notice and an **Update now** button show up. Updating replaces only the app's code. A copy of the previous code is saved in `datos_usuario/respaldos/`, and your data isn't touched. Restart the app when it finishes.

## Privacy

- Everything is stored in one folder, `app/datos_usuario/` (`cuentas/`, `preferencias.json`, …). To back up your data or move it to another PC, copy that folder.
- If you used the site login, the password is stored in the Windows Credential Manager, not in a file.
- The app only goes online to check GitHub for updates (and, once it's re-enabled, to connect to esperianarchive.com).
- The portable build ships **without any personal data**.

## For developers

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py                        # run from source
.venv\Scripts\python -m idiomas actualizar          # add new UI strings to idiomas/*.json
.venv\Scripts\python herramientas\construir_exe.py  # build dist/AFK-Community, the portable .zip and setup.exe (needs Inno Setup 6)
.venv\Scripts\python -m navegador.actualizador publicar X.Y.Z   # tag and publish a version
```

The `.exe` is only a launcher. Its `app/` folder holds Python and its libraries, the app code (`aplicacion/`, `navegador/`, `idiomas/`, `recursos/`) as `.py` files, so it can be updated from GitHub, and the user's data in `datos_usuario/`.

When you run from source, your data also lives in `datos_usuario/` (ignored by git). Older versions kept it loose in the root; the app moves it there automatically on start.

To publish a version: `publicar X.Y.Z` (above), then build, then upload `dist/AFK-Community-setup.exe` and `dist/AFK-Community-portable.zip` to the GitHub Release of tag `vX.Y.Z`, keeping those exact file names (the download links point to them).

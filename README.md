# 🎬 Episode Checker

**Missing an episode? Let's find it! 🍿**

A small Python GUI app that scans your TV series folder and tells you which episodes are missing.

### ✨ Features

* 📁 Scan your entire series folder
* 🔎 Detect missing episodes
* 🌐 Use online episode data when internet is available
* 📴 Automatically fall back to offline checking
* 📺 Supports multiple seasons
* 🖥️ Simple Windows GUI
* 🚀 Standalone `.exe` — no Python required

### 🎯 How it works

**Internet available:**

`Your Folder → TVmaze → Compare Episodes → Missing Episodes`

**No internet:**

`Your Folder → Detect Episodes → Find Gaps`

### 🚀 Download

Go to **[Releases](../../releases)** and download the latest `.exe`.

No installation required. Just download, run, and find those missing episodes. 😎

### 🛠️ Run from Source

```bash
pip install -r requirements.txt
python episode_checker.py
```

### 📦 Build the EXE

```bash
pip install pyinstaller
pyinstaller --clean --onefile --windowed episode_checker.py
```

The executable will be created inside the `dist/` folder.

### ❤️ Made for

People who download an entire season...

...and somehow still manage to miss Episode 7. 😂

### 🌐 Episode Data

Online episode information is provided by **TVmaze**.

---

⭐ If you find it useful, give the project a star!

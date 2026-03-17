# SOCRATES-DL — WSG — V2

## Requirements
- [Node.js](https://nodejs.org/) v18+ only if building from source
- [.NET Runtime](https://dotnet.microsoft.com/en-us/download) required anyways

## Setup

```bash
# 1. Install dependencies
run install.bat

# 2. Run
run start.bat
# 3. Build Simpler
run build.bat
```

## File structure
```
SOCRATES-DL/
├── main.js          ← Electron main process
├── preload.js       ← Secure IPC bridge 
├── renderer/
│   └── index.html   ← Full GUI
│
└── package.json
```

## Building a distributable (.exe / .dmg)
```bash
npm install --save-dev electron-builder

# Add to package.json scripts:
# "build": "electron-builder"
# Then:
npm run build
```

## What changed from Python's V1
- `customtkinter` → native HTML/CSS dark UI
- `urllib` → Node.js built-in `https` module
- `subprocess.Popen` → Node.js `child_process.spawn`
- `threading` → async/await + IPC
- `zipfile` → PowerShell `Expand-Archive` (Windows) / `unzip` (Linux/Mac)
- Config still saved to `~/Downloads/ddgui_config.json`

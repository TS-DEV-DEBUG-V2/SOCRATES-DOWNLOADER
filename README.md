# SOCRATES-DL

<p align="center">
  <img src="https://private-user-images.githubusercontent.com/266275506/565099780-3e4bb4c6-433d-43e6-bc9c-88695d5d7bef.png?jwt=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3Nzg4NzAwNzIsIm5iZiI6MTc3ODg2OTc3MiwicGF0aCI6Ii8yNjYyNzU1MDYvNTY1MDk5NzgwLTNlNGJiNGM2LTQzM2QtNDNlNi1iYzljLTg4Njk1ZDVkN2JlZi5wbmc_WC1BbXotQWxnb3JpdGhtPUFXUzQtSE1BQy1TSEEyNTYmWC1BbXotQ3JlZGVudGlhbD1BS0lBVkNPRFlMU0E1M1BRSzRaQSUyRjIwMjYwNTE1JTJGdXMtZWFzdC0xJTJGczMlMkZhd3M0X3JlcXVlc3QmWC1BbXotRGF0ZT0yMDI2MDUxNVQxODI5MzJaJlgtQW16LUV4cGlyZXM9MzAwJlgtQW16LVNpZ25hdHVyZT0xMmU3OGE5M2U3M2FhYWFkNjI3ZTMyNTM0YTRmMWQwMDI2OGY5MDMzYTNlYmYyNDdkZDQyZGZhY2ZkYmVlMjZkJlgtQW16LVNpZ25lZEhlYWRlcnM9aG9zdCZyZXNwb25zZS1jb250ZW50LXR5cGU9aW1hZ2UlMkZwbmcifQ.wmCzN-kSx4dvU5vUw-4URxxrsyC9mKIVlzrqCqGg2TM" alt="SOCRATES-DL Preview">
</p>

[![Download](https://img.shields.io/badge/Download-Latest-blue?style=for-the-badge)](https://github.com/TS-DEV-DEBUG-V2/SOCRATES-DOWNLOADER/releases)
[![Version](https://img.shields.io/github/v/release/TS-DEV-DEBUG-V2/SOCRATES-DOWNLOADER?style=for-the-badge)](https://github.com/TS-DEV-DEBUG-V2/SOCRATES-DOWNLOADER/releases)
![Status](https://img.shields.io/badge/status-active-success?style=for-the-badge)
[![License](https://img.shields.io/github/license/TS-DEV-DEBUG-V2/SOCRATES-DOWNLOADER?style=for-the-badge)](https://github.com/TS-DEV-DEBUG-V2/SOCRATES-DOWNLOADER/blob/main/LICENSE)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey?style=for-the-badge)
![GUI](https://img.shields.io/badge/interface-GUI-blueviolet?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-V1-blue?style=for-the-badge\&logo=python)
![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-ff69b4?style=for-the-badge)
![Node.js](https://img.shields.io/badge/Node.js-V2-339933?style=for-the-badge\&logo=node.js)
![Electron](https://img.shields.io/badge/Electron-GUI-47848F?style=for-the-badge\&logo=electron)
![Build](https://img.shields.io/badge/build-passing-brightgreen?style=for-the-badge)
![Maintained](https://img.shields.io/badge/maintained-yes-success?style=for-the-badge)
![Open Source](https://img.shields.io/badge/open--source-true-blue?style=for-the-badge)
![Performance](https://img.shields.io/badge/performance-optimized-orange?style=for-the-badge)
![Downloads](https://img.shields.io/github/downloads/TS-DEV-DEBUG-V2/SOCRATES-DOWNLOADER/total?style=for-the-badge)
![Security](https://img.shields.io/badge/security-stable-green?style=for-the-badge)
![Updates](https://img.shields.io/badge/updates-frequent-yellow?style=for-the-badge)
![Modules](https://img.shields.io/badge/modules-extensible-purple?style=for-the-badge)
![CLI Support](https://img.shields.io/badge/CLI-not--supported-lightgrey?style=for-the-badge)
![Cross Platform](https://img.shields.io/badge/cross--platform-no-blue?style=for-the-badge)

---
# NOTE
You need to get an API key from https://manifest.morrenus.xyz/ and also you need to join their discord
## Overview

**SOCRATES-DL** is a GUI-based game downloader designed for speed, simplicity, and control. It provides a streamlined interface for downloading and managing game files while maintaining a clean and efficient user experience.

The project is built across two distinct versions, each using different technologies to explore performance, UI design, and extensibility.

---

## Versions

### V1 — Python (CustomTkinter)

The first version is built using Python with **CustomTkinter**, focusing on simplicity and performance.

**Highlights:**

* Lightweight desktop application
* Very Slow
* Minimal resource usage
* Clean and simple GUI
* Ideal for basic downloading tasks

---

### V2 — Node.js + Electron

The second version is built using Node.js and Electron, offering a more advanced and scalable interface.

**Highlights:**

* Modern desktop UI powered by web technologies
* More flexible and expandable architecture
* Improved UI/UX design capabilities
* Better suited for future feature expansion

---

## Features

* High-speed downloading with stable performance
* Fully graphical user interface (no CLI required)
* Organized file handling and directory management

---

## Installation
* Download the latest release of v2 or v1
* for v1 just launch SOCRATES-DL-WSG-V1.exe NOTE, v1 has NO support
* for v2 launch SOCRATES-DL.exe, This is the best version

### Building v2 from source

```bash id="repo1"
git clone https://github.com/TS-DEV-DEBUG-V2/SOCRATES-DOWNLOADER.git
cd SOCRATES-DOWNLOADER
cd v2
install.bat
install-for-building.bat
build.bat
```

---

### Run V1 (Python) from source

```bash id="repo2"
cd v1
pip install customtkinter
python main.py
```

---

### Run V2 (no building to exe)

```bash id="repo3"
cd v2
install.bat
start.bat
```

---

## Project Structure

```id="repo4"
SOCRATES-DOWNLOADER/
│── v1/          # Python (CustomTkinter GUI)
│── v2/          # better version (built with elecronn)
│── assets/
│── README.md
```

---

## Roadmap

* Improved UI design for V2
* Performance optimizations

---

## Contributing

Contributions are welcome. Fork the repository and submit a pull request with clear changes and explanations.

---

## License

See the LICENSE file in the repository for details.

---

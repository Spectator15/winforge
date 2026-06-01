# WinForge

A lightweight, all-in-one Windows toolkit for system maintenance, optimization, and setup.

Built for personal use. Portable. Runs as a single `.exe` with no dependencies.

---

## Features

### System Info
View detailed hardware and software specs at a glance — CPU, GPU, RAM, storage, motherboard, BIOS, Secure Boot, TPM, Defender status, network, and more. One-click copy to clipboard.

### System Repair
- DISM RestoreHealth
- System File Checker (SFC)
- Check Disk (CHKDSK)
- Full automated repair (DISM + SFC with restore point)

### Cleanup
- Temp files, Windows Update cache, Prefetch
- Built-in Disk Cleanup (automated)
- DNS flush and full network stack reset

### Dependencies
Install common runtimes in one click — .NET 6/7/8/9, Visual C++ Redistributables, DirectX, WebView2.

### Install Apps
28 popular apps across browsers, communication, media, gaming, productivity, dev tools, and utilities. Supports both **winget** and **Chocolatey** as install methods. Auto-installs the package manager if missing. Search bar to filter.

### Tweaks & Debloat
- **Essential Tweaks** — telemetry, activity history, consumer features, services optimization, and more
- **Advanced Tweaks** — background apps, fullscreen optimizations, IPv6, Copilot removal, Windows AI/Recall, and more
- **Preferences** — dark mode, file extensions, mouse acceleration, sticky keys, taskbar layout, snap controls, and more
- **Browser Debloat** — strips telemetry and bloat from Edge and Brave
- **App Removal** — remove pre-installed Windows apps with safety warnings on sensitive items
- **Presets** — Gaming PC, Privacy, Fresh Install, Performance
- **Search** — filter tweaks instantly by name

### DNS Settings
Switch between popular DNS providers — Cloudflare, Google, Quad9, OpenDNS, AdGuard, Cloudflare Family, or DHCP automatic. Applied to all active network adapters.

### Windows Updates
Three modes: Default (reset to stock), Security Only (delay features, keep patches), or Disable All (with clear warnings).

### Registry Health
Safe, targeted registry maintenance. Scans for broken uninstall entries and empty leftover keys. Always backs up to a `.reg` file before cleaning. Does not touch COM references or file path validation.

### System Tools
Quick-launch buttons for legacy Windows panels — Control Panel, Device Manager, Network Connections, Sound, Power, Region, System Properties, and more.

### Restore Points
Create manual restore points with custom labels. Bypasses the Windows 24-hour frequency limit. Automatically created before tweaks and app removal. Session-aware — won't silently create duplicates.

---

## How to Use

1. Download `WinForge.exe` from the latest build
2. Double-click to run
3. Click **Yes** when Windows asks for admin rights
4. That's it

---

## Technical Details

- Written in Python with CustomTkinter
- Packaged as a standalone `.exe` via PyInstaller
- Requires administrator privileges (auto-prompts on launch)
- Dependencies tab uses `winget` (built into Windows 11 and modern Windows 10)
- No internet required except for app installation and dependency downloads

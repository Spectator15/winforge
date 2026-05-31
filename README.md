# WinForge - Windows Toolkit

A personal Windows maintenance and tweaking tool.

---

## First Time Setup (to build the .exe)

### Step 1 - Install Python
Download and install Python 3.10 or newer from https://python.org
When installing, tick the box that says **"Add Python to PATH"**

### Step 2 - Run the build script
Double-click `build.bat` inside the WinForge folder.
It will automatically install the required libraries and package everything into a single `.exe` file.

### Step 3 - Find your exe
After the build finishes, your `WinForge.exe` will be inside the `dist` folder.
You can move this `.exe` anywhere, including your desktop or a USB drive.

---

## Running WinForge
Just double-click `WinForge.exe`.
Windows will ask for admin rights - click Yes. It needs admin to do anything useful.

---

## What It Can Do

| Section | What it does |
|---|---|
| System Repair | DISM, SFC, CHKDSK |
| Cleanup | Temp files, update cache, prefetch, DNS, network reset |
| Dependencies | .NET runtimes, VC++ Redists, DirectX, WebView2 |
| Tweaks | Privacy, performance, UI improvements - pick and apply |
| Restore Point | Create a Windows restore point manually |

---

## Notes
- A restore point is automatically created before tweaks are applied.
- The Dependencies tab uses winget (built into Windows 11 and modern Windows 10).
- Nothing is irreversible. You can always roll back using the restore point.

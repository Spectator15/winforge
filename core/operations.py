import subprocess
import os
import sys
import ctypes
import urllib.request
import tempfile
import threading
from datetime import datetime


def run_powershell(command, callback=None):
    """Run a PowerShell command and optionally stream output to a callback."""
    full_cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command]
    try:
        process = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        output_lines = []
        for line in process.stdout:
            line = line.rstrip()
            if line:
                output_lines.append(line)
                if callback:
                    callback(line)
        process.wait()
        return process.returncode == 0, "\n".join(output_lines)
    except Exception as e:
        return False, str(e)


def run_cmd(command, callback=None):
    """Run a CMD command."""
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        output_lines = []
        for line in process.stdout:
            line = line.rstrip()
            if line:
                output_lines.append(line)
                if callback:
                    callback(line)
        process.wait()
        return process.returncode == 0, "\n".join(output_lines)
    except Exception as e:
        return False, str(e)


# ─── RESTORE POINT ────────────────────────────────────────────────────────────

def create_restore_point(description="WinForge Pre-Operation", callback=None):
    if callback:
        callback("Creating system restore point...")
    cmd = f'''
    Enable-ComputerRestore -Drive "C:\\"
    Checkpoint-Computer -Description "{description}" -RestorePointType "MODIFY_SETTINGS"
    '''
    success, output = run_powershell(cmd, callback)
    if success:
        if callback:
            callback("Restore point created successfully.")
    else:
        if callback:
            callback(f"Restore point may have failed (Windows limits frequency): {output}")
    return success


# ─── SYSTEM REPAIR ────────────────────────────────────────────────────────────

def run_dism(callback=None):
    if callback:
        callback("Running DISM RestoreHealth... this can take 5-15 minutes.")
    return run_cmd("DISM /Online /Cleanup-Image /RestoreHealth", callback)


def run_sfc(callback=None):
    if callback:
        callback("Running System File Checker...")
    return run_cmd("sfc /scannow", callback)


def run_chkdsk(callback=None):
    if callback:
        callback("Scheduling CHKDSK on next boot...")
    return run_cmd("echo Y | chkdsk C: /f /r /x", callback)


def run_full_repair(callback=None):
    if callback:
        callback("=== Starting Full System Repair ===")
    create_restore_point("WinForge Full Repair", callback)
    run_dism(callback)
    run_sfc(callback)
    if callback:
        callback("=== Full Repair Complete. Restart recommended. ===")
    return True, "Done"


# ─── CLEANUP ──────────────────────────────────────────────────────────────────

def clean_temp_files(callback=None):
    if callback:
        callback("Cleaning temp files...")
    cmd = r"""
    Remove-Item -Path "$env:TEMP\*" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -Path "C:\Windows\Temp\*" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Output "Temp files cleaned."
    """
    return run_powershell(cmd, callback)


def clean_windows_update_cache(callback=None):
    if callback:
        callback("Stopping Windows Update service and clearing cache...")
    cmd = r"""
    Stop-Service -Name wuauserv -Force -ErrorAction SilentlyContinue
    Stop-Service -Name bits -Force -ErrorAction SilentlyContinue
    Remove-Item -Path "C:\Windows\SoftwareDistribution\Download\*" -Recurse -Force -ErrorAction SilentlyContinue
    Start-Service -Name wuauserv -ErrorAction SilentlyContinue
    Start-Service -Name bits -ErrorAction SilentlyContinue
    Write-Output "Windows Update cache cleared."
    """
    return run_powershell(cmd, callback)


def clean_prefetch(callback=None):
    if callback:
        callback("Clearing prefetch files...")
    cmd = r"Remove-Item -Path 'C:\Windows\Prefetch\*' -Force -ErrorAction SilentlyContinue; Write-Output 'Prefetch cleared.'"
    return run_powershell(cmd, callback)


def run_disk_cleanup(callback=None):
    if callback:
        callback("Running Windows Disk Cleanup (automated)...")
    cmd = r"""
    $regPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\VolumeCaches"
    $keys = Get-ChildItem $regPath
    foreach ($key in $keys) {
        Set-ItemProperty -Path $key.PSPath -Name StateFlags0064 -Value 2 -ErrorAction SilentlyContinue
    }
    Start-Process cleanmgr -ArgumentList "/sagerun:64" -Wait
    Write-Output "Disk Cleanup complete."
    """
    return run_powershell(cmd, callback)


def flush_dns(callback=None):
    if callback:
        callback("Flushing DNS cache...")
    return run_cmd("ipconfig /flushdns", callback)


def reset_network(callback=None):
    if callback:
        callback("Resetting network stack...")
    cmds = [
        "netsh winsock reset",
        "netsh int ip reset",
        "ipconfig /flushdns",
        "ipconfig /release",
        "ipconfig /renew"
    ]
    for c in cmds:
        run_cmd(c, callback)
    if callback:
        callback("Network reset complete. Restart recommended.")
    return True, "Done"


# ─── DEPENDENCIES ─────────────────────────────────────────────────────────────

DEPENDENCY_URLS = {
    "dotnet6": ("https://dotnet.microsoft.com/download/dotnet/6.0", "winget install Microsoft.DotNet.Runtime.6"),
    "dotnet7": ("https://dotnet.microsoft.com/download/dotnet/7.0", "winget install Microsoft.DotNet.Runtime.7"),
    "dotnet8": ("https://dotnet.microsoft.com/download/dotnet/8.0", "winget install Microsoft.DotNet.Runtime.8"),
    "vcredist": ("https://aka.ms/vs/17/release/vc_redist.x64.exe", None),
    "directx": (None, "winget install Microsoft.DirectX"),
    "webview2": (None, "winget install Microsoft.EdgeWebView2Runtime"),
    "xna": (None, None),
}


def install_via_winget(package_id, callback=None):
    if callback:
        callback(f"Installing {package_id} via winget...")
    return run_cmd(f"winget install --id {package_id} --silent --accept-package-agreements --accept-source-agreements", callback)


def install_dotnet(version, callback=None):
    package_map = {
        "6": "Microsoft.DotNet.Runtime.6",
        "7": "Microsoft.DotNet.Runtime.7",
        "8": "Microsoft.DotNet.Runtime.8",
        "9": "Microsoft.DotNet.Runtime.9",
    }
    pkg = package_map.get(str(version))
    if pkg:
        return install_via_winget(pkg, callback)
    return False, "Unknown .NET version"


def install_vcredist(callback=None):
    if callback:
        callback("Installing Visual C++ Redistributables (2015-2022)...")
    pkgs = [
        "Microsoft.VCRedist.2015+.x64",
        "Microsoft.VCRedist.2015+.x86",
    ]
    for p in pkgs:
        install_via_winget(p, callback)
    return True, "Done"


def install_directx(callback=None):
    return install_via_winget("Microsoft.DirectX", callback)


def install_webview2(callback=None):
    return install_via_winget("Microsoft.EdgeWebView2Runtime", callback)


# ─── TWEAKS ───────────────────────────────────────────────────────────────────

def tweak_disable_telemetry(callback=None):
    if callback:
        callback("Disabling Windows telemetry...")
    cmd = r"""
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection" -Name AllowTelemetry -Value 0 -Force -ErrorAction SilentlyContinue
    Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection" -Name AllowTelemetry -Value 0 -Force -ErrorAction SilentlyContinue
    Stop-Service -Name DiagTrack -Force -ErrorAction SilentlyContinue
    Set-Service -Name DiagTrack -StartupType Disabled -ErrorAction SilentlyContinue
    Write-Output "Telemetry disabled."
    """
    return run_powershell(cmd, callback)


def tweak_disable_cortana(callback=None):
    if callback:
        callback("Disabling Cortana...")
    cmd = r"""
    $path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Windows Search"
    If (!(Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
    Set-ItemProperty -Path $path -Name AllowCortana -Value 0 -Force
    Write-Output "Cortana disabled."
    """
    return run_powershell(cmd, callback)


def tweak_disable_xbox_gamebar(callback=None):
    if callback:
        callback("Disabling Xbox Game Bar...")
    cmd = r"""
    Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR" -Name AppCaptureEnabled -Value 0 -Force -ErrorAction SilentlyContinue
    Set-ItemProperty -Path "HKCU:\System\GameConfigStore" -Name GameDVR_Enabled -Value 0 -Force -ErrorAction SilentlyContinue
    Write-Output "Xbox Game Bar disabled."
    """
    return run_powershell(cmd, callback)


def tweak_set_high_performance(callback=None):
    if callback:
        callback("Setting power plan to High Performance...")
    return run_cmd("powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", callback)


def tweak_disable_search_indexing(callback=None):
    if callback:
        callback("Disabling Windows Search indexing service...")
    cmd = r"""
    Stop-Service -Name WSearch -Force -ErrorAction SilentlyContinue
    Set-Service -Name WSearch -StartupType Disabled -ErrorAction SilentlyContinue
    Write-Output "Search indexing disabled."
    """
    return run_powershell(cmd, callback)


def tweak_disable_superfetch(callback=None):
    if callback:
        callback("Disabling SysMain (Superfetch)...")
    cmd = r"""
    Stop-Service -Name SysMain -Force -ErrorAction SilentlyContinue
    Set-Service -Name SysMain -StartupType Disabled -ErrorAction SilentlyContinue
    Write-Output "SysMain disabled."
    """
    return run_powershell(cmd, callback)


def tweak_show_file_extensions(callback=None):
    if callback:
        callback("Showing file extensions in Explorer...")
    cmd = r"""
    Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name HideFileExt -Value 0 -Force
    Write-Output "File extensions visible."
    """
    return run_powershell(cmd, callback)


def tweak_show_hidden_files(callback=None):
    if callback:
        callback("Showing hidden files in Explorer...")
    cmd = r"""
    Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name Hidden -Value 1 -Force
    Write-Output "Hidden files visible."
    """
    return run_powershell(cmd, callback)


def tweak_disable_tips(callback=None):
    if callback:
        callback("Disabling Windows tips and suggestions...")
    cmd = r"""
    Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" -Name SubscribedContent-338389Enabled -Value 0 -Force -ErrorAction SilentlyContinue
    Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager" -Name SilentInstalledAppsEnabled -Value 0 -Force -ErrorAction SilentlyContinue
    Write-Output "Tips and suggestions disabled."
    """
    return run_powershell(cmd, callback)


def tweak_classic_context_menu(callback=None):
    if callback:
        callback("Restoring classic right-click context menu (Win11)...")
    cmd = r"""
    $path = "HKCU:\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32"
    If (!(Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
    Set-ItemProperty -Path $path -Name "(Default)" -Value "" -Force
    Write-Output "Classic context menu restored. Restart Explorer to apply."
    Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
    """
    return run_powershell(cmd, callback)


def tweak_disable_onedrive(callback=None):
    if callback:
        callback("Disabling OneDrive startup...")
    cmd = r"""
    $path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\OneDrive"
    If (!(Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
    Set-ItemProperty -Path $path -Name DisableFileSyncNGSC -Value 1 -Force
    Stop-Process -Name OneDrive -Force -ErrorAction SilentlyContinue
    Write-Output "OneDrive disabled."
    """
    return run_powershell(cmd, callback)


def tweak_enable_dark_mode(callback=None):
    if callback:
        callback("Enabling Windows dark mode...")
    cmd = r"""
    Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize" -Name AppsUseLightTheme -Value 0 -Force
    Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize" -Name SystemUsesLightTheme -Value 0 -Force
    Write-Output "Dark mode enabled."
    """
    return run_powershell(cmd, callback)


def tweak_disable_startup_delay(callback=None):
    if callback:
        callback("Disabling startup delay...")
    cmd = r"""
    $path = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize"
    If (!(Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
    Set-ItemProperty -Path $path -Name StartupDelayInMSec -Value 0 -Force
    Write-Output "Startup delay disabled."
    """
    return run_powershell(cmd, callback)


# ─── PRESET DEFINITIONS ───────────────────────────────────────────────────────

PRESETS = {
    "Gaming PC": {
        "description": "Optimised for gaming. Disables background services that eat resources.",
        "tweaks": [
            "disable_telemetry",
            "disable_xbox_gamebar",
            "set_high_performance",
            "disable_superfetch",
            "disable_search_indexing",
            "disable_tips",
            "disable_startup_delay",
        ]
    },
    "Privacy Focused": {
        "description": "Locks down data collection and disables Microsoft tracking services.",
        "tweaks": [
            "disable_telemetry",
            "disable_cortana",
            "disable_onedrive",
            "disable_tips",
        ]
    },
    "Fresh Install Setup": {
        "description": "Quality of life fixes for a brand new Windows install.",
        "tweaks": [
            "show_file_extensions",
            "show_hidden_files",
            "enable_dark_mode",
            "disable_tips",
            "disable_cortana",
            "disable_telemetry",
            "disable_startup_delay",
            "classic_context_menu",
        ]
    },
    "Performance Boost": {
        "description": "Strips out background noise for a snappier, leaner system.",
        "tweaks": [
            "set_high_performance",
            "disable_superfetch",
            "disable_search_indexing",
            "disable_startup_delay",
            "disable_telemetry",
        ]
    }
}

TWEAK_FUNCTIONS = {
    "disable_telemetry": tweak_disable_telemetry,
    "disable_cortana": tweak_disable_cortana,
    "disable_xbox_gamebar": tweak_disable_xbox_gamebar,
    "set_high_performance": tweak_set_high_performance,
    "disable_search_indexing": tweak_disable_search_indexing,
    "disable_superfetch": tweak_disable_superfetch,
    "show_file_extensions": tweak_show_file_extensions,
    "show_hidden_files": tweak_show_hidden_files,
    "disable_tips": tweak_disable_tips,
    "classic_context_menu": tweak_classic_context_menu,
    "disable_onedrive": tweak_disable_onedrive,
    "enable_dark_mode": tweak_enable_dark_mode,
    "disable_startup_delay": tweak_disable_startup_delay,
}

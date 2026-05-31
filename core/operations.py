import subprocess
import threading
from datetime import datetime


def run_powershell(command, callback=None):
    full_cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command]
    try:
        process = subprocess.Popen(
            full_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, creationflags=subprocess.CREATE_NO_WINDOW
        )
        output_lines = []
        for line in process.stdout:
            line = line.rstrip()
            if line and not _is_garbage_line(line):
                output_lines.append(line)
                if callback:
                    callback(line)
        process.wait()
        return process.returncode == 0, "\n".join(output_lines)
    except Exception as e:
        return False, str(e)


def run_cmd(command, callback=None):
    try:
        process = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, creationflags=subprocess.CREATE_NO_WINDOW
        )
        output_lines = []
        for line in process.stdout:
            line = line.rstrip()
            if line and not _is_garbage_line(line):
                output_lines.append(line)
                if callback:
                    callback(line)
        process.wait()
        return process.returncode == 0, "\n".join(output_lines)
    except Exception as e:
        return False, str(e)


def _is_garbage_line(line):
    """Filter out junk output from SFC/DISM."""
    stripped = line.strip()
    if not stripped:
        return True
    # SFC spams timestamps like [21:27:08] [21:27:08] [21:27:08]
    import re
    if re.match(r'^(\[\d{2}:\d{2}:\d{2}\]\s*){2,}$', stripped):
        return True
    # Lines that are just repeated timestamps with nothing else
    if re.match(r'^(\[\d{2}:\d{2}:\d{2}\]\s*)+$', stripped):
        return True
    return False


# ─── RESTORE POINT ────────────────────────────────────────────────────────────

def create_restore_point(description="WinForge Pre-Operation", callback=None):
    if callback: callback("[INFO] Creating system restore point...")
    cmd = f'''
    Enable-ComputerRestore -Drive "C:\\"
    Checkpoint-Computer -Description "{description}" -RestorePointType "MODIFY_SETTINGS"
    Write-Host "Restore point created successfully."
    '''
    success, output = run_powershell(cmd, callback)
    if not success:
        if callback: callback("[WARN] Restore point may have been skipped (Windows limits one per 24hrs)")
    return success


# ─── SYSTEM REPAIR ────────────────────────────────────────────────────────────

def run_dism(callback=None):
    if callback: callback("[INFO] Running DISM RestoreHealth... this can take 5-15 minutes.")
    return run_cmd("DISM /Online /Cleanup-Image /RestoreHealth", callback)

def run_sfc(callback=None):
    if callback: callback("[INFO] Running System File Checker...")
    success, output = run_cmd("sfc /scannow", callback)
    if callback: callback("[OK] SFC scan complete.")
    return success, output

def run_chkdsk(callback=None):
    if callback: callback("[INFO] Scheduling CHKDSK on next boot...")
    return run_cmd("echo Y | chkdsk C: /f /r /x", callback)

def run_full_repair(callback=None):
    if callback: callback("[INFO] Starting Full System Repair...")
    create_restore_point("WinForge Full Repair", callback)
    run_dism(callback)
    run_sfc(callback)
    if callback: callback("[OK] Full repair complete. Restart recommended.")
    return True, "Done"


# ─── CLEANUP ──────────────────────────────────────────────────────────────────

def clean_temp_files(callback=None):
    if callback: callback("[INFO] Cleaning temp files...")
    cmd = r'''
    $before = (Get-ChildItem "$env:TEMP" -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    Remove-Item -Path "$env:TEMP\*" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -Path "C:\Windows\Temp\*" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Temp files cleaned."
    '''
    return run_powershell(cmd, callback)

def clean_windows_update_cache(callback=None):
    if callback: callback("[INFO] Clearing Windows Update cache...")
    cmd = r'''
    Stop-Service -Name wuauserv -Force -ErrorAction SilentlyContinue
    Stop-Service -Name bits -Force -ErrorAction SilentlyContinue
    Remove-Item -Path "C:\Windows\SoftwareDistribution\Download\*" -Recurse -Force -ErrorAction SilentlyContinue
    Start-Service -Name wuauserv -ErrorAction SilentlyContinue
    Start-Service -Name bits -ErrorAction SilentlyContinue
    Write-Host "Windows Update cache cleared."
    '''
    return run_powershell(cmd, callback)

def clean_prefetch(callback=None):
    if callback: callback("[INFO] Clearing prefetch files...")
    return run_powershell(r"Remove-Item -Path 'C:\Windows\Prefetch\*' -Force -ErrorAction SilentlyContinue; Write-Host 'Prefetch cleared.'", callback)

def run_disk_cleanup(callback=None):
    if callback: callback("[INFO] Running Windows Disk Cleanup...")
    cmd = r'''
    $regPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\VolumeCaches"
    $keys = Get-ChildItem $regPath
    foreach ($key in $keys) { Set-ItemProperty -Path $key.PSPath -Name StateFlags0064 -Value 2 -ErrorAction SilentlyContinue }
    Start-Process cleanmgr -ArgumentList "/sagerun:64" -Wait
    Write-Host "Disk Cleanup complete."
    '''
    return run_powershell(cmd, callback)

def flush_dns(callback=None):
    if callback: callback("[INFO] Flushing DNS cache...")
    return run_cmd("ipconfig /flushdns", callback)

def reset_network(callback=None):
    if callback: callback("[INFO] Resetting network stack...")
    for c in ["netsh winsock reset", "netsh int ip reset", "ipconfig /flushdns", "ipconfig /release", "ipconfig /renew"]:
        run_cmd(c, callback)
    if callback: callback("[OK] Network reset complete. Restart recommended.")
    return True, "Done"


# ─── DEPENDENCIES ─────────────────────────────────────────────────────────────

def install_via_winget(package_id, callback=None):
    if callback: callback(f"[INFO] Installing {package_id}...")
    return run_cmd(f'winget install --id {package_id} --silent --accept-package-agreements --accept-source-agreements', callback)

def install_dotnet(version, callback=None):
    pkgs = {"6": "Microsoft.DotNet.Runtime.6", "7": "Microsoft.DotNet.Runtime.7",
            "8": "Microsoft.DotNet.Runtime.8", "9": "Microsoft.DotNet.Runtime.9"}
    pkg = pkgs.get(str(version))
    if pkg: return install_via_winget(pkg, callback)
    return False, "Unknown version"

def install_vcredist(callback=None):
    for p in ["Microsoft.VCRedist.2015+.x64", "Microsoft.VCRedist.2015+.x86"]:
        install_via_winget(p, callback)
    return True, "Done"

def install_directx(callback=None):
    return install_via_winget("Microsoft.DirectX", callback)

def install_webview2(callback=None):
    return install_via_winget("Microsoft.EdgeWebView2Runtime", callback)


# ─── SYSTEM TOOLS ─────────────────────────────────────────────────────────────

def open_panel(command, callback=None):
    if callback: callback(f"[INFO] Opening panel...")
    import subprocess
    subprocess.Popen(command, shell=True)
    return True, "Done"


# ─── UPDATES ──────────────────────────────────────────────────────────────────

def updates_default(callback=None):
    if callback: callback("[INFO] Resetting Windows Update to default settings...")
    cmd = r'''
    Remove-Item -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" -Recurse -Force -ErrorAction SilentlyContinue
    Set-Service -Name wuauserv -StartupType Automatic -ErrorAction SilentlyContinue
    Start-Service -Name wuauserv -ErrorAction SilentlyContinue
    Write-Host "Windows Update reset to defaults."
    '''
    return run_powershell(cmd, callback)

def updates_security_only(callback=None):
    if callback: callback("[INFO] Configuring security-only updates...")
    cmd = r'''
    $wuPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"
    If (!(Test-Path $wuPath)) { New-Item -Path $wuPath -Force | Out-Null }
    Set-ItemProperty -Path $wuPath -Name NoAutoUpdate -Value 0 -Force
    Set-ItemProperty -Path $wuPath -Name AUOptions -Value 3 -Force
    Set-ItemProperty -Path $wuPath -Name AutoInstallMinorUpdates -Value 1 -Force
    $wuPath2 = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"
    If (!(Test-Path $wuPath2)) { New-Item -Path $wuPath2 -Force | Out-Null }
    Set-ItemProperty -Path $wuPath2 -Name DeferFeatureUpdates -Value 1 -Force
    Set-ItemProperty -Path $wuPath2 -Name DeferFeatureUpdatesPeriodInDays -Value 365 -Force
    Set-ItemProperty -Path $wuPath2 -Name DeferQualityUpdates -Value 1 -Force
    Set-ItemProperty -Path $wuPath2 -Name DeferQualityUpdatesPeriodInDays -Value 4 -Force
    Set-ItemProperty -Path $wuPath2 -Name ExcludeWUDriversInQualityUpdate -Value 1 -Force
    Write-Host "Security-only updates configured."
    '''
    return run_powershell(cmd, callback)

def updates_disable_all(callback=None):
    if callback: callback("[WARN] Disabling ALL Windows Updates...")
    cmd = r'''
    $wuPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"
    If (!(Test-Path $wuPath)) { New-Item -Path $wuPath -Force | Out-Null }
    Set-ItemProperty -Path $wuPath -Name NoAutoUpdate -Value 1 -Force
    Set-ItemProperty -Path $wuPath -Name AUOptions -Value 1 -Force
    $wuPath2 = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"
    If (!(Test-Path $wuPath2)) { New-Item -Path $wuPath2 -Force | Out-Null }
    Set-ItemProperty -Path $wuPath2 -Name DisableWindowsUpdateAccess -Value 1 -Force
    Stop-Service -Name wuauserv -Force -ErrorAction SilentlyContinue
    Set-Service -Name wuauserv -StartupType Disabled -ErrorAction SilentlyContinue
    Write-Host "All Windows Updates disabled."
    '''
    return run_powershell(cmd, callback)


# ─── DEBLOAT ──────────────────────────────────────────────────────────────────

BLOATWARE = {
    # Safe to remove
    "Microsoft.3DBuilder":               ("3D Builder",              False, "Old 3D printing app. Rarely used."),
    "Microsoft.BingWeather":             ("Bing Weather",            False, "Weather widget app."),
    "Microsoft.GetHelp":                 ("Get Help",                False, "Microsoft support app."),
    "Microsoft.Getstarted":              ("Tips",                    False, "Windows tips and suggestions app."),
    "Microsoft.MicrosoftOfficeHub":      ("Office Hub",              False, "Office promotional app, not actual Office."),
    "Microsoft.MicrosoftSolitaireCollection": ("Solitaire Collection", False, "Built-in card games with ads."),
    "Microsoft.MixedReality.Portal":     ("Mixed Reality Portal",    False, "VR/AR portal. Useless without a headset."),
    "Microsoft.Movies.TV":               ("Movies & TV",             False, "Microsoft's video player app."),
    "Microsoft.MSPaint":                 ("Paint 3D",                False, "3D version of Paint. Not the classic one."),
    "Microsoft.People":                  ("People",                  False, "Contacts app tied to Microsoft account."),
    "Microsoft.SkypeApp":                ("Skype",                   False, "Skype consumer app."),
    "Microsoft.Todos":                   ("Microsoft To Do",         False, "Microsoft's task management app."),
    "Microsoft.WindowsAlarms":           ("Alarms & Clock",          False, "Built-in alarm app."),
    "Microsoft.WindowsFeedbackHub":      ("Feedback Hub",            False, "Used to send feedback to Microsoft."),
    "Microsoft.WindowsMaps":             ("Maps",                    False, "Microsoft Maps app."),
    "Microsoft.WindowsSoundRecorder":    ("Sound Recorder",          False, "Basic audio recorder."),
    "Microsoft.YourPhone":               ("Phone Link",              False, "Phone Link / Your Phone companion app."),
    "Microsoft.ZuneMusic":               ("Groove Music",            False, "Microsoft's old music player. Discontinued."),
    "Microsoft.ZuneVideo":               ("Groove Video",            False, "Microsoft's old video app."),
    "MicrosoftTeams":                    ("Microsoft Teams (Personal)", False, "Personal Teams, not the work version."),
    "Microsoft.PowerAutomateDesktop":    ("Power Automate",          False, "Microsoft's automation tool."),
    "Microsoft.Whiteboard":              ("Microsoft Whiteboard",    False, "Digital whiteboard app."),
    "Clipchamp.Clipchamp":               ("Clipchamp",               False, "Microsoft's video editor."),
    "Microsoft.BingNews":                ("Microsoft News",          False, "News feed app."),
    "Microsoft.GamingApp":               ("Xbox App",                True,  "CAUTION: Removing may break Game Pass and Xbox game installations."),
    "Microsoft.XboxGameOverlay":         ("Xbox Game Overlay",       True,  "CAUTION: Part of Xbox gaming services. May affect game features."),
    "Microsoft.XboxGamingOverlay":       ("Xbox Gaming Overlay",     True,  "CAUTION: Xbox overlay. May affect Game Bar features."),
    "Microsoft.XboxIdentityProvider":    ("Xbox Identity Provider",  True,  "CAUTION: Required for Xbox/Game Pass login. Remove with caution."),
    "Microsoft.XboxSpeechToTextOverlay": ("Xbox Speech to Text",     False, "Xbox speech overlay. Safe to remove if not used."),
    "Microsoft.OneDrive":                ("OneDrive",                True,  "CAUTION: Removing OneDrive is permanent without reinstalling. Backup data first."),
    "Microsoft.WindowsCommunicationsApps": ("Mail & Calendar",       False, "Built-in mail and calendar apps."),
    "Microsoft.Cortana":                 ("Cortana",                 True,  "CAUTION: Cortana removal may affect Windows Search on some builds."),
}


def remove_app(package_id, callback=None):
    if callback: callback(f"[INFO] Removing {package_id}...")
    cmd = f'''
    Get-AppxPackage -Name "{package_id}" | Remove-AppxPackage -ErrorAction SilentlyContinue
    Get-AppxProvisionedPackage -Online | Where-Object DisplayName -like "{package_id}" | Remove-AppxProvisionedPackage -Online -ErrorAction SilentlyContinue
    Write-Host "Removed: {package_id}"
    '''
    return run_powershell(cmd, callback)


# ─── TWEAKS ───────────────────────────────────────────────────────────────────

TWEAKS = {
    # ── ESSENTIAL ──
    "activity_history": {
        "label": "Activity History - Disable",
        "category": "essential",
        "tooltip": "Stops Windows from tracking apps and files you open. Clears the Timeline feature.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\System" -Name EnableActivityFeed -Value 0 -Force -ErrorAction SilentlyContinue
            Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\System" -Name PublishUserActivities -Value 0 -Force -ErrorAction SilentlyContinue
            Write-Host "Activity History disabled."
        ''', cb)
    },
    "consumer_features": {
        "label": "ConsumerFeatures - Disable",
        "category": "essential",
        "tooltip": "Prevents Microsoft from silently installing suggested apps like Candy Crush on your system.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            $path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\CloudContent"
            If (!(Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
            Set-ItemProperty -Path $path -Name DisableWindowsConsumerFeatures -Value 1 -Force
            Write-Host "ConsumerFeatures disabled."
        ''', cb)
    },
    "end_task_right_click": {
        "label": "End Task With Right Click - Enable",
        "category": "essential",
        "tooltip": "Adds an 'End Task' option when you right-click apps in the taskbar. Handy for killing frozen apps.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            $path = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced\TaskbarDeveloperSettings"
            If (!(Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
            Set-ItemProperty -Path $path -Name TaskbarEndTask -Value 1 -Force
            Write-Host "End Task on right-click enabled."
        ''', cb)
    },
    "disable_hibernation": {
        "label": "Hibernation - Disable",
        "category": "essential",
        "tooltip": "Disables hibernation and deletes hiberfil.sys, freeing several GB of disk space. Not recommended on laptops.",
        "dangerous": False,
        "fn": lambda cb: run_cmd("powercfg /h off", cb)
    },
    "disable_location": {
        "label": "Location Tracking - Disable",
        "category": "essential",
        "tooltip": "Disables Windows location services system-wide. Apps won't be able to request your location.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location" -Name Value -Value "Deny" -Force -ErrorAction SilentlyContinue
            Write-Host "Location tracking disabled."
        ''', cb)
    },
    "disable_store_suggestions": {
        "label": "Microsoft Store Recommended Search Results - Disable",
        "category": "essential",
        "tooltip": "Stops the Start Menu search from showing Microsoft Store app suggestions when you search.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            $path = "HKCU:\SOFTWARE\Policies\Microsoft\Windows\Explorer"
            If (!(Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
            Set-ItemProperty -Path $path -Name NoUseStoreOpenWith -Value 1 -Force
            Write-Host "Store search suggestions disabled."
        ''', cb)
    },
    "disable_ps_telemetry": {
        "label": "PowerShell 7 Telemetry - Disable",
        "category": "essential",
        "tooltip": "Sets an environment variable that tells PowerShell 7 not to send telemetry data to Microsoft.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            [Environment]::SetEnvironmentVariable("POWERSHELL_TELEMETRY_OPTOUT", "1", "Machine")
            Write-Host "PowerShell telemetry disabled."
        ''', cb)
    },
    "set_services_manual": {
        "label": "Services - Set to Manual",
        "category": "essential",
        "tooltip": "Sets several background services to Manual startup instead of Automatic. They start only when needed, saving resources.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            $services = @("DiagTrack","dmwappushservice","HomeGroupListener","HomeGroupProvider","lfsvc","MapsBroker","NetTcpPortSharing","RemoteAccess","RemoteRegistry","SharedAccess","TrkWks","WbioSrvc","WMPNetworkSvc","XblAuthManager","XblGameSave","XboxNetApiSvc","ndu")
            foreach ($s in $services) { Set-Service -Name $s -StartupType Manual -ErrorAction SilentlyContinue }
            Write-Host "Services set to manual."
        ''', cb)
    },
    "disable_telemetry": {
        "label": "Telemetry - Disable",
        "category": "essential",
        "tooltip": "Disables Windows diagnostic data collection and the DiagTrack service that sends data to Microsoft.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            Set-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection" -Name AllowTelemetry -Value 0 -Force -ErrorAction SilentlyContinue
            Stop-Service -Name DiagTrack -Force -ErrorAction SilentlyContinue
            Set-Service -Name DiagTrack -StartupType Disabled -ErrorAction SilentlyContinue
            Write-Host "Telemetry disabled."
        ''', cb)
    },
    "remove_widgets": {
        "label": "Widgets - Remove",
        "category": "essential",
        "tooltip": "Removes the Windows 11 Widgets button from the taskbar.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name TaskbarDa -Value 0 -Force -ErrorAction SilentlyContinue
            Write-Host "Widgets removed from taskbar."
        ''', cb)
    },
    "disable_wpbt": {
        "label": "Windows Platform Binary Table (WPBT) - Disable",
        "category": "essential",
        "tooltip": "Disables WPBT, a feature that allows OEM vendors to run executables on boot. Can be a security risk on some systems.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            $path = "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager"
            Set-ItemProperty -Path $path -Name DisableWpbtExecution -Value 1 -Force -ErrorAction SilentlyContinue
            Write-Host "WPBT disabled."
        ''', cb)
    },

    # ── ADVANCED / CAUTION ──
    "disable_background_apps": {
        "label": "Background Apps - Disable",
        "category": "advanced",
        "tooltip": "Stops all apps from running in the background. They only run when you open them. Saves RAM and battery.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications" -Name GlobalUserDisabled -Value 1 -Force -ErrorAction SilentlyContinue
            Write-Host "Background apps disabled."
        ''', cb)
    },
    "debloat_edge": {
        "label": "Microsoft Edge - Debloat",
        "category": "advanced",
        "tooltip": "Disables Edge telemetry, shopping assistant, sidebar, and other bloat features built into Edge.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            $edgePath = "HKLM:\SOFTWARE\Policies\Microsoft\Edge"
            If (!(Test-Path $edgePath)) { New-Item -Path $edgePath -Force | Out-Null }
            Set-ItemProperty -Path $edgePath -Name MetricsReportingEnabled -Value 0 -Force
            Set-ItemProperty -Path $edgePath -Name PersonalizationReportingEnabled -Value 0 -Force
            Set-ItemProperty -Path $edgePath -Name EdgeShoppingAssistantEnabled -Value 0 -Force
            Set-ItemProperty -Path $edgePath -Name HubsSidebarEnabled -Value 0 -Force
            Write-Host "Edge debloated."
        ''', cb)
    },
    "disable_fullscreen_optimizations": {
        "label": "Fullscreen Optimizations - Disable",
        "category": "advanced",
        "tooltip": "Disables fullscreen optimizations globally. Can improve gaming performance and reduce input lag in some games.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            Set-ItemProperty -Path "HKCU:\System\GameConfigStore" -Name GameDVR_DXGIHonorFSEWindowsCompatible -Value 1 -Force -ErrorAction SilentlyContinue
            Set-ItemProperty -Path "HKCU:\System\GameConfigStore" -Name GameDVR_FSEBehavior -Value 2 -Force -ErrorAction SilentlyContinue
            Write-Host "Fullscreen optimizations disabled."
        ''', cb)
    },
    "disable_ipv6": {
        "label": "IPv6 - Disable",
        "category": "advanced",
        "tooltip": "Disables IPv6 on all network adapters. Only do this if you know your network doesn't use IPv6.",
        "dangerous": True,
        "fn": lambda cb: run_powershell(r'''
            Get-NetAdapter | foreach { Disable-NetAdapterBinding -Name $_.Name -ComponentID ms_tcpip6 -ErrorAction SilentlyContinue }
            Write-Host "IPv6 disabled on all adapters."
        ''', cb)
    },
    "prefer_ipv4": {
        "label": "IPv6 - Set IPv4 as Preferred",
        "category": "advanced",
        "tooltip": "Keeps IPv6 enabled but tells Windows to prefer IPv4. Safer than fully disabling IPv6.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters" -Name DisabledComponents -Value 32 -Force -ErrorAction SilentlyContinue
            Write-Host "IPv4 set as preferred."
        ''', cb)
    },
    "remove_onedrive": {
        "label": "Microsoft OneDrive - Remove",
        "category": "advanced",
        "tooltip": "Fully uninstalls OneDrive. Make sure your files are synced or backed up before doing this.",
        "dangerous": True,
        "fn": lambda cb: run_powershell(r'''
            Stop-Process -Name OneDrive -Force -ErrorAction SilentlyContinue
            Start-Process "$env:SYSTEMROOT\SysWOW64\OneDriveSetup.exe" -ArgumentList "/uninstall" -Wait -ErrorAction SilentlyContinue
            Start-Process "$env:SYSTEMROOT\System32\OneDriveSetup.exe" -ArgumentList "/uninstall" -Wait -ErrorAction SilentlyContinue
            Write-Host "OneDrive removed."
        ''', cb)
    },
    "disable_rdp_warnings": {
        "label": "RDP Unsigned File Warnings - Disable",
        "category": "advanced",
        "tooltip": "Stops the warning popup when opening unsigned RDP files. Useful if you use Remote Desktop frequently.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            Set-ItemProperty -Path "HKCU:\Software\Microsoft\Terminal Server Client" -Name AuthenticationLevelOverride -Value 0 -Force -ErrorAction SilentlyContinue
            Write-Host "RDP unsigned file warnings disabled."
        ''', cb)
    },
    "disable_storage_sense": {
        "label": "Storage Sense - Disable",
        "category": "advanced",
        "tooltip": "Disables Storage Sense, the feature that automatically deletes temp files and empties the recycle bin.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\StorageSense\Parameters\StoragePolicy" -Name 01 -Value 0 -Force -ErrorAction SilentlyContinue
            Write-Host "Storage Sense disabled."
        ''', cb)
    },
    "disable_systray_clock": {
        "label": "System Tray Notifications and Calendar - Disable",
        "category": "advanced",
        "tooltip": "Hides the notification bell and calendar flyout from the system tray.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer" -Name HideSCAHealth -Value 1 -Force -ErrorAction SilentlyContinue
            Write-Host "System tray notifications hidden."
        ''', cb)
    },
    "disable_teredo": {
        "label": "Teredo - Disable",
        "category": "advanced",
        "tooltip": "Disables Teredo, a tunnelling protocol. Can slightly improve network performance if you don't need IPv6 tunnelling.",
        "dangerous": False,
        "fn": lambda cb: run_cmd("netsh interface teredo set state disabled", cb)
    },
    "visual_effects_performance": {
        "label": "Visual Effects - Set to Best Performance",
        "category": "advanced",
        "tooltip": "Disables animations and visual effects for maximum performance. Makes Windows feel snappier but less pretty.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects" -Name VisualFXSetting -Value 2 -Force -ErrorAction SilentlyContinue
            Write-Host "Visual effects set to best performance."
        ''', cb)
    },
    "disable_windows_ai": {
        "label": "Windows AI - Disable",
        "category": "advanced",
        "tooltip": "Disables Windows AI features including Recall (the screenshot memory feature). Recommended for privacy.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            $path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsAI"
            If (!(Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
            Set-ItemProperty -Path $path -Name AllowRecallEnablement -Value 0 -Force
            Set-ItemProperty -Path $path -Name DisableAIDataAnalysis -Value 1 -Force
            Write-Host "Windows AI and Recall disabled."
        ''', cb)
    },
    "remove_xbox_components": {
        "label": "Xbox and Gaming Components - Remove",
        "category": "advanced",
        "tooltip": "Removes Xbox apps and gaming overlay components. CAUTION: This will break Game Pass and Xbox game features.",
        "dangerous": True,
        "fn": lambda cb: run_powershell(r'''
            Get-AppxPackage -Name "Microsoft.XboxGameOverlay" | Remove-AppxPackage -ErrorAction SilentlyContinue
            Get-AppxPackage -Name "Microsoft.XboxGamingOverlay" | Remove-AppxPackage -ErrorAction SilentlyContinue
            Get-AppxPackage -Name "Microsoft.XboxIdentityProvider" | Remove-AppxPackage -ErrorAction SilentlyContinue
            Get-AppxPackage -Name "Microsoft.XboxSpeechToTextOverlay" | Remove-AppxPackage -ErrorAction SilentlyContinue
            Write-Host "Xbox gaming components removed."
        ''', cb)
    },

    # ── PREFERENCES ──
    "pref_dark_mode": {
        "label": "Dark Theme for Windows",
        "category": "preference",
        "tooltip": "Enables the system-wide dark theme for Windows apps and the taskbar.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize" -Name AppsUseLightTheme -Value 0 -Force
            Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize" -Name SystemUsesLightTheme -Value 0 -Force
            Write-Host "Dark mode enabled."
        ''', cb)
    },
    "pref_file_extensions": {
        "label": "File Explorer File Extensions",
        "category": "preference",
        "tooltip": "Shows file extensions in Explorer (e.g. file.exe, document.pdf). Highly recommended to have on.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name HideFileExt -Value 0 -Force
            Write-Host "File extensions visible."
        ''', cb)
    },
    "pref_hidden_files": {
        "label": "File Explorer Hidden Files",
        "category": "preference",
        "tooltip": "Shows hidden files and folders in Explorer. Useful for power users and troubleshooting.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name Hidden -Value 1 -Force
            Write-Host "Hidden files visible."
        ''', cb)
    },
    "pref_mouse_acceleration": {
        "label": "Mouse Acceleration - Disable",
        "category": "preference",
        "tooltip": "Disables mouse acceleration (Enhance Pointer Precision). Recommended for gaming for consistent aim.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            Set-ItemProperty -Path "HKCU:\Control Panel\Mouse" -Name MouseSpeed -Value 0 -Force
            Set-ItemProperty -Path "HKCU:\Control Panel\Mouse" -Name MouseThreshold1 -Value 0 -Force
            Set-ItemProperty -Path "HKCU:\Control Panel\Mouse" -Name MouseThreshold2 -Value 0 -Force
            Write-Host "Mouse acceleration disabled."
        ''', cb)
    },
    "pref_numlock": {
        "label": "Num Lock on Startup",
        "category": "preference",
        "tooltip": "Enables Num Lock automatically when Windows starts.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            Set-ItemProperty -Path "HKCU:\Control Panel\Keyboard" -Name InitialKeyboardIndicators -Value 2 -Force
            Write-Host "Num Lock on startup enabled."
        ''', cb)
    },
    "pref_sticky_keys": {
        "label": "Sticky Keys - Disable",
        "category": "preference",
        "tooltip": "Disables the Sticky Keys prompt that appears when you press Shift 5 times. Annoying during gaming.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            Set-ItemProperty -Path "HKCU:\Control Panel\Accessibility\StickyKeys" -Name Flags -Value "506" -Force
            Write-Host "Sticky Keys disabled."
        ''', cb)
    },
    "pref_taskbar_search": {
        "label": "Taskbar Search Icon - Hide",
        "category": "preference",
        "tooltip": "Hides the Search icon/box from the taskbar. You can still search by pressing the Windows key.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Search" -Name SearchboxTaskbarMode -Value 0 -Force
            Write-Host "Taskbar search hidden."
        ''', cb)
    },
    "pref_taskbar_taskview": {
        "label": "Taskbar Task View Icon - Hide",
        "category": "preference",
        "tooltip": "Hides the Task View button from the taskbar.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name ShowTaskViewButton -Value 0 -Force
            Write-Host "Task View icon hidden."
        ''', cb)
    },
    "pref_center_taskbar": {
        "label": "Taskbar Centered Icons - Disable",
        "category": "preference",
        "tooltip": "Moves taskbar icons back to the left side instead of centered (Windows 11 default).",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            Set-ItemProperty -Path "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name TaskbarAl -Value 0 -Force
            Write-Host "Taskbar icons moved to left."
        ''', cb)
    },
    "pref_classic_context_menu": {
        "label": "Right-Click Menu Previous Layout - Enable",
        "category": "preference",
        "tooltip": "Restores the full classic right-click context menu in Windows 11 instead of the simplified version.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            $path = "HKCU:\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32"
            If (!(Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
            Set-ItemProperty -Path $path -Name "(Default)" -Value "" -Force
            Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
            Write-Host "Classic context menu restored."
        ''', cb)
    },
    "pref_disable_startup_delay": {
        "label": "Startup Delay - Remove",
        "category": "preference",
        "tooltip": "Removes the artificial delay Windows adds before launching startup programs.",
        "dangerous": False,
        "fn": lambda cb: run_powershell(r'''
            $path = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize"
            If (!(Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
            Set-ItemProperty -Path $path -Name StartupDelayInMSec -Value 0 -Force
            Write-Host "Startup delay removed."
        ''', cb)
    },
    "pref_high_performance": {
        "label": "High Performance Power Plan",
        "category": "preference",
        "tooltip": "Sets the power plan to High Performance. Good for desktop PCs. Not recommended on laptops running on battery.",
        "dangerous": False,
        "fn": lambda cb: run_cmd("powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", cb)
    },
}

PRESETS = {
    "Gaming PC": {
        "description": "Optimised for gaming. Disables background services that eat resources.",
        "tweaks": ["disable_telemetry", "end_task_right_click", "disable_fullscreen_optimizations",
                   "pref_mouse_acceleration", "pref_sticky_keys", "disable_background_apps",
                   "visual_effects_performance", "pref_disable_startup_delay", "pref_high_performance",
                   "remove_widgets", "disable_windows_ai"]
    },
    "Privacy Focused": {
        "description": "Locks down data collection and disables Microsoft tracking.",
        "tweaks": ["disable_telemetry", "activity_history", "consumer_features", "disable_location",
                   "disable_ps_telemetry", "disable_windows_ai", "remove_onedrive", "debloat_edge",
                   "disable_store_suggestions"]
    },
    "Fresh Install Setup": {
        "description": "Quality of life fixes for a brand new Windows install.",
        "tweaks": ["pref_file_extensions", "pref_hidden_files", "pref_dark_mode", "pref_sticky_keys",
                   "disable_telemetry", "consumer_features", "pref_classic_context_menu",
                   "pref_disable_startup_delay", "end_task_right_click", "remove_widgets"]
    },
    "Performance Boost": {
        "description": "Strips out background noise for a snappier, leaner system.",
        "tweaks": ["pref_high_performance", "disable_background_apps", "visual_effects_performance",
                   "pref_disable_startup_delay", "disable_telemetry", "set_services_manual",
                   "disable_storage_sense"]
    }
}

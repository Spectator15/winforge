import subprocess, re, threading
from datetime import datetime

def run_ps(command, callback=None):
    full_cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command]
    try:
        p = subprocess.Popen(full_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        lines = []
        for line in p.stdout:
            line = line.rstrip()
            if line and not _junk(line):
                lines.append(line)
                if callback: callback(line)
        p.wait()
        return p.returncode == 0, "\n".join(lines)
    except Exception as e:
        return False, str(e)

def run_cmd(command, callback=None):
    try:
        p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        lines = []
        for line in p.stdout:
            line = line.rstrip()
            if line and not _junk(line):
                lines.append(line)
                if callback: callback(line)
        p.wait()
        return p.returncode == 0, "\n".join(lines)
    except Exception as e:
        return False, str(e)

def _junk(line):
    s = line.strip()
    if not s: return True
    if re.match(r'^(\[\d{2}:\d{2}:\d{2}\]\s*){2,}$', s): return True
    if re.match(r'^(\[\d{2}:\d{2}:\d{2}\]\s*)+$', s): return True
    return False

# ═══ RESTORE POINT ════════════════════════════════════════════════════════════

def create_restore_point(desc="WinForge Pre-Operation", cb=None):
    if cb: cb("[INFO] Creating system restore point...")
    cmd = f'''
    Enable-ComputerRestore -Drive "C:\\" -ErrorAction SilentlyContinue
    Set-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SystemRestore" -Name "SystemRestorePointCreationFrequency" -Value 0 -Type DWord -Force -ErrorAction SilentlyContinue
    $before = (Get-ComputerRestorePoint -ErrorAction SilentlyContinue | Measure-Object).Count
    try {{ Checkpoint-Computer -Description "{desc}" -RestorePointType "MODIFY_SETTINGS" -ErrorAction Stop }}
    catch {{ Write-Host "[ERROR] $($_.Exception.Message)"; exit 1 }}
    $after = (Get-ComputerRestorePoint -ErrorAction SilentlyContinue | Measure-Object).Count
    if ($after -gt $before) {{
        $rp = Get-ComputerRestorePoint | Sort-Object SequenceNumber -Descending | Select-Object -First 1
        Write-Host "Restore point created: $($rp.Description) (ID $($rp.SequenceNumber))"
    }} else {{ Write-Host "[WARN] Command ran but no new restore point detected." }}
    '''
    s, o = run_ps(cmd, cb)
    if not s and cb: cb("[WARN] Restore point may have failed. Check System Protection is ON for C:")
    return s

# ═══ SYSTEM REPAIR ════════════════════════════════════════════════════════════

def run_dism(cb=None):
    if cb: cb("[INFO] Running DISM RestoreHealth (5-15 min)...")
    return run_cmd("DISM /Online /Cleanup-Image /RestoreHealth", cb)

def run_sfc(cb=None):
    if cb: cb("[INFO] Running System File Checker...")
    s, o = run_cmd("sfc /scannow", cb)
    if cb: cb("[OK] SFC complete.")
    return s, o

def run_chkdsk(cb=None):
    if cb: cb("[INFO] Scheduling CHKDSK on next boot...")
    return run_cmd("echo Y | chkdsk C: /f /r /x", cb)

def run_full_repair(cb=None):
    if cb: cb("[INFO] Starting Full System Repair...")
    create_restore_point("WinForge Full Repair", cb)
    run_dism(cb)
    run_sfc(cb)
    if cb: cb("[OK] Full repair complete. Restart recommended.")
    return True, "Done"

# ═══ CLEANUP ══════════════════════════════════════════════════════════════════

CLEANUP_ITEMS = {
    "temp": ("Temp Files", "Deletes %TEMP% and C:\\Windows\\Temp contents.", False),
    "wucache": ("Update Cache", "Clears Windows Update download cache.", False),
    "prefetch": ("Prefetch", "Clears prefetch cache. Rebuilds automatically.", False),
    "diskclean": ("Disk Cleanup", "Runs built-in Disk Cleanup with all categories.", False),
    "dns": ("Flush DNS", "Clears the DNS resolver cache.", False),
    "network": ("Network Reset", "Resets Winsock, TCP/IP, DNS. Needs restart.", True),
}

def clean_temp(cb=None):
    if cb: cb("[INFO] Cleaning temp files...")
    return run_ps(r'Remove-Item "$env:TEMP\*" -Recurse -Force -EA SilentlyContinue; Remove-Item "C:\Windows\Temp\*" -Recurse -Force -EA SilentlyContinue; Write-Host "Temp files cleaned."', cb)

def clean_wucache(cb=None):
    if cb: cb("[INFO] Clearing update cache...")
    return run_ps(r'Stop-Service wuauserv,bits -Force -EA SilentlyContinue; Remove-Item "C:\Windows\SoftwareDistribution\Download\*" -Recurse -Force -EA SilentlyContinue; Start-Service wuauserv,bits -EA SilentlyContinue; Write-Host "Update cache cleared."', cb)

def clean_prefetch(cb=None):
    if cb: cb("[INFO] Clearing prefetch...")
    return run_ps(r"Remove-Item 'C:\Windows\Prefetch\*' -Force -EA SilentlyContinue; Write-Host 'Prefetch cleared.'", cb)

def clean_diskclean(cb=None):
    if cb: cb("[INFO] Running Disk Cleanup...")
    return run_ps(r'$k=Get-ChildItem "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\VolumeCaches"; foreach($i in $k){Set-ItemProperty $i.PSPath -Name StateFlags0064 -Value 2 -EA SilentlyContinue}; Start-Process cleanmgr -ArgumentList "/sagerun:64" -Wait; Write-Host "Disk Cleanup complete."', cb)

def clean_dns(cb=None):
    if cb: cb("[INFO] Flushing DNS...")
    return run_cmd("ipconfig /flushdns", cb)

def clean_network(cb=None):
    if cb: cb("[INFO] Resetting network stack...")
    for c in ["netsh winsock reset","netsh int ip reset","ipconfig /flushdns","ipconfig /release","ipconfig /renew"]:
        run_cmd(c, cb)
    if cb: cb("[OK] Network reset complete. Restart needed.")
    return True, "Done"

CLEANUP_FNS = {"temp": clean_temp, "wucache": clean_wucache, "prefetch": clean_prefetch,
               "diskclean": clean_diskclean, "dns": clean_dns, "network": clean_network}

# ═══ DEPENDENCIES ═════════════════════════════════════════════════════════════

DEP_ITEMS = [
    (".NET 6", "Microsoft.DotNet.Runtime.6"), (".NET 7", "Microsoft.DotNet.Runtime.7"),
    (".NET 8 (LTS)", "Microsoft.DotNet.Runtime.8"), (".NET 9", "Microsoft.DotNet.Runtime.9"),
    ("VC++ 2015-2022 x64", "Microsoft.VCRedist.2015+.x64"), ("VC++ 2015-2022 x86", "Microsoft.VCRedist.2015+.x86"),
    ("DirectX", "Microsoft.DirectX"), ("WebView2", "Microsoft.EdgeWebView2Runtime"),
]

def install_winget_pkg(pkg, cb=None):
    if cb: cb(f"[INFO] Installing {pkg}...")
    return run_cmd(f'winget install --id {pkg} --silent --accept-package-agreements --accept-source-agreements', cb)

# ═══ APP INSTALLATION ═════════════════════════════════════════════════════════

APP_LIST = {
    "Brave Browser":     {"winget": "Brave.Brave",             "choco": "brave",           "cat": "Browsers"},
    "Firefox":           {"winget": "Mozilla.Firefox",          "choco": "firefox",         "cat": "Browsers"},
    "Google Chrome":     {"winget": "Google.Chrome",            "choco": "googlechrome",    "cat": "Browsers"},
    "Zen Browser":       {"winget": "Zen-Team.Zen-Browser",    "choco": None,              "cat": "Browsers"},
    "Discord":           {"winget": "Discord.Discord",          "choco": "discord",         "cat": "Communication"},
    "Telegram":          {"winget": "Telegram.TelegramDesktop", "choco": "telegram",        "cat": "Communication"},
    "Zoom":              {"winget": "Zoom.Zoom",                "choco": "zoom",            "cat": "Communication"},
    "Spotify":           {"winget": "Spotify.Spotify",          "choco": "spotify",         "cat": "Media"},
    "VLC":               {"winget": "VideoLAN.VLC",             "choco": "vlc",             "cat": "Media"},
    "OBS Studio":        {"winget": "OBSProject.OBSStudio",     "choco": "obs-studio",      "cat": "Media"},
    "Steam":             {"winget": "Valve.Steam",              "choco": "steam",           "cat": "Gaming"},
    "Epic Games":        {"winget": "EpicGames.EpicGamesLauncher", "choco": "epicgameslauncher", "cat": "Gaming"},
    "GOG Galaxy":        {"winget": "GOG.Galaxy",               "choco": "goggalaxy",       "cat": "Gaming"},
    "Obsidian":          {"winget": "Obsidian.Obsidian",        "choco": "obsidian",        "cat": "Productivity"},
    "Notion":            {"winget": "Notion.Notion",            "choco": "notion",          "cat": "Productivity"},
    "VS Code":           {"winget": "Microsoft.VisualStudioCode", "choco": "vscode",        "cat": "Development"},
    "Git":               {"winget": "Git.Git",                  "choco": "git",             "cat": "Development"},
    "Python":            {"winget": "Python.Python.3.12",       "choco": "python",          "cat": "Development"},
    "Node.js LTS":       {"winget": "OpenJS.NodeJS.LTS",        "choco": "nodejs-lts",      "cat": "Development"},
    "Notepad++":         {"winget": "Notepad++.Notepad++",      "choco": "notepadplusplus",  "cat": "Development"},
    "7-Zip":             {"winget": "7zip.7zip",                "choco": "7zip",            "cat": "Utilities"},
    "WinRAR":            {"winget": "RARLab.WinRAR",            "choco": "winrar",          "cat": "Utilities"},
    "PowerToys":         {"winget": "Microsoft.PowerToys",      "choco": "powertoys",       "cat": "Utilities"},
    "qBittorrent":       {"winget": "qBittorrent.qBittorrent",  "choco": "qbittorrent",     "cat": "Utilities"},
    "Everything Search": {"winget": "voidtools.Everything",     "choco": "everything",      "cat": "Utilities"},
    "ShareX":            {"winget": "ShareX.ShareX",            "choco": "sharex",          "cat": "Utilities"},
    "Bitwarden":         {"winget": "Bitwarden.Bitwarden",      "choco": "bitwarden",       "cat": "Utilities"},
    "TreeSize Free":     {"winget": "JAMSoftware.TreeSize.Free","choco": "treesizefree",    "cat": "Utilities"},
}

def check_winget(cb=None):
    s, _ = run_cmd("winget --version", cb)
    return s

def check_choco(cb=None):
    s, _ = run_cmd("choco --version", cb)
    return s

def install_winget_itself(cb=None):
    if cb: cb("[INFO] Installing/repairing winget...")
    return run_ps(r'Add-AppxPackage -RegisterByFamilyName -MainPackage Microsoft.DesktopAppInstaller_8wekyb3d8bbwe -ErrorAction SilentlyContinue; Write-Host "Winget install attempted."', cb)

def install_choco_itself(cb=None):
    if cb: cb("[INFO] Installing Chocolatey...")
    return run_ps(r"Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))", cb)

def install_app(name, method="winget", cb=None):
    info = APP_LIST.get(name)
    if not info:
        if cb: cb(f"[ERROR] Unknown app: {name}")
        return False, "Unknown"
    if method == "winget":
        pkg = info["winget"]
        if not pkg:
            if cb: cb(f"[WARN] {name} not available via winget")
            return False, "N/A"
        return run_cmd(f'winget install --id {pkg} --silent --accept-package-agreements --accept-source-agreements', cb)
    else:
        pkg = info["choco"]
        if not pkg:
            if cb: cb(f"[WARN] {name} not available via Chocolatey")
            return False, "N/A"
        return run_cmd(f'choco install {pkg} -y', cb)

# ═══ DNS ══════════════════════════════════════════════════════════════════════

DNS_SERVERS = {
    "Cloudflare (1.1.1.1)":           ("1.1.1.1", "1.0.0.1"),
    "Google (8.8.8.8)":               ("8.8.8.8", "8.8.4.4"),
    "Quad9 (9.9.9.9)":                ("9.9.9.9", "149.112.112.112"),
    "OpenDNS (208.67.222.222)":       ("208.67.222.222", "208.67.220.220"),
    "AdGuard (94.140.14.14)":         ("94.140.14.14", "94.140.15.15"),
    "Cloudflare Family (1.1.1.3)":    ("1.1.1.3", "1.0.0.3"),
    "Automatic (DHCP)":               (None, None),
}

def set_dns(dns_name, cb=None):
    primary, secondary = DNS_SERVERS.get(dns_name, (None, None))
    if primary is None:
        if cb: cb("[INFO] Setting DNS to automatic (DHCP)...")
        cmd = r'''
        $adapters = Get-NetAdapter | Where-Object {$_.Status -eq "Up"}
        foreach ($a in $adapters) {
            Set-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ResetServerAddresses
        }
        Write-Host "DNS set to automatic (DHCP)."
        '''
    else:
        if cb: cb(f"[INFO] Setting DNS to {dns_name}...")
        cmd = f'''
        $adapters = Get-NetAdapter | Where-Object {{$_.Status -eq "Up"}}
        foreach ($a in $adapters) {{
            Set-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ServerAddresses ("{primary}","{secondary}")
        }}
        Write-Host "DNS set to {dns_name} ({primary}, {secondary})"
        '''
    s, o = run_ps(cmd, cb)
    run_cmd("ipconfig /flushdns", cb)
    return s

def get_current_dns(cb=None):
    s, o = run_ps(r'Get-DnsClientServerAddress -AddressFamily IPv4 | Where-Object {$_.ServerAddresses.Count -gt 0} | Select-Object -First 1 -ExpandProperty ServerAddresses | Write-Host', cb)
    return o

# ═══ UPDATES ══════════════════════════════════════════════════════════════════

def updates_default(cb=None):
    if cb: cb("[INFO] Resetting Windows Update to defaults...")
    return run_ps(r'Remove-Item "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate" -Recurse -Force -EA SilentlyContinue; Set-Service wuauserv -StartupType Automatic -EA SilentlyContinue; Start-Service wuauserv -EA SilentlyContinue; Write-Host "Windows Update reset to defaults."', cb)

def updates_security(cb=None):
    if cb: cb("[INFO] Configuring security-only updates...")
    cmd = r'''
    $p="HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"
    $p2="HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"
    If(!(Test-Path $p)){New-Item -Path $p -Force|Out-Null}
    If(!(Test-Path $p2)){New-Item -Path $p2 -Force|Out-Null}
    Set-ItemProperty $p -Name NoAutoUpdate -Value 0 -Force
    Set-ItemProperty $p -Name AUOptions -Value 3 -Force
    Set-ItemProperty $p2 -Name DeferFeatureUpdates -Value 1 -Force
    Set-ItemProperty $p2 -Name DeferFeatureUpdatesPeriodInDays -Value 365 -Force
    Set-ItemProperty $p2 -Name DeferQualityUpdates -Value 1 -Force
    Set-ItemProperty $p2 -Name DeferQualityUpdatesPeriodInDays -Value 4 -Force
    Set-ItemProperty $p2 -Name ExcludeWUDriversInQualityUpdate -Value 1 -Force
    Write-Host "Security-only updates configured."
    '''
    return run_ps(cmd, cb)

def updates_disable(cb=None):
    if cb: cb("[WARN] Disabling ALL Windows Updates...")
    cmd = r'''
    $p="HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"
    $p2="HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"
    If(!(Test-Path $p)){New-Item -Path $p -Force|Out-Null}
    If(!(Test-Path $p2)){New-Item -Path $p2 -Force|Out-Null}
    Set-ItemProperty $p -Name NoAutoUpdate -Value 1 -Force
    Set-ItemProperty $p -Name AUOptions -Value 1 -Force
    Set-ItemProperty $p2 -Name DisableWindowsUpdateAccess -Value 1 -Force
    Stop-Service wuauserv -Force -EA SilentlyContinue
    Set-Service wuauserv -StartupType Disabled -EA SilentlyContinue
    Write-Host "All Windows Updates disabled."
    '''
    return run_ps(cmd, cb)

# ═══ SYSTEM TOOLS ═════════════════════════════════════════════════════════════

def open_panel(cmd, cb=None):
    subprocess.Popen(cmd, shell=True)
    return True, "Done"

# ═══ DEBLOAT ══════════════════════════════════════════════════════════════════

BLOATWARE = {
    "Microsoft.3DBuilder":             ("3D Builder",              False, "Old 3D printing app."),
    "Microsoft.BingWeather":           ("Bing Weather",            False, "Weather widget app."),
    "Microsoft.BingNews":              ("Microsoft News",          False, "News feed app."),
    "Microsoft.GetHelp":               ("Get Help",                False, "Microsoft support app."),
    "Microsoft.Getstarted":            ("Tips",                    False, "Windows tips and suggestions."),
    "Microsoft.MicrosoftOfficeHub":    ("Office Hub",              False, "Office promotional hub."),
    "Microsoft.MicrosoftSolitaireCollection": ("Solitaire", False, "Built-in card games with ads."),
    "Microsoft.MixedReality.Portal":   ("Mixed Reality Portal",    False, "VR/AR portal."),
    "Microsoft.Movies.TV":             ("Movies & TV",             False, "Video player app."),
    "Microsoft.MSPaint":               ("Paint 3D",                False, "3D Paint. Not the classic."),
    "Microsoft.People":                ("People",                  False, "Contacts app."),
    "Microsoft.SkypeApp":              ("Skype",                   False, "Skype consumer app."),
    "Microsoft.Todos":                 ("Microsoft To Do",         False, "Task management app."),
    "Microsoft.WindowsAlarms":         ("Alarms & Clock",          False, "Alarm/timer app."),
    "Microsoft.WindowsFeedbackHub":    ("Feedback Hub",            False, "Sends feedback to Microsoft."),
    "Microsoft.WindowsMaps":           ("Maps",                    False, "Microsoft Maps."),
    "Microsoft.WindowsSoundRecorder":  ("Sound Recorder",          False, "Basic audio recorder."),
    "Microsoft.YourPhone":             ("Phone Link",              False, "Phone companion app."),
    "Microsoft.ZuneMusic":             ("Groove Music",            False, "Old music player."),
    "Microsoft.ZuneVideo":             ("Groove Video",            False, "Old video app."),
    "MicrosoftTeams":                  ("Teams (Personal)",        False, "Personal Teams."),
    "Microsoft.PowerAutomateDesktop":  ("Power Automate",          False, "Automation tool."),
    "Microsoft.Whiteboard":            ("Whiteboard",              False, "Digital whiteboard."),
    "Clipchamp.Clipchamp":             ("Clipchamp",               False, "Video editor."),
    "Microsoft.WindowsCommunicationsApps": ("Mail & Calendar",     False, "Mail and calendar apps."),
    "Microsoft.XboxSpeechToTextOverlay": ("Xbox Speech",           False, "Xbox speech overlay."),
    "Microsoft.GamingApp":             ("Xbox App",                True,  "May break Game Pass."),
    "Microsoft.XboxGameOverlay":       ("Xbox Game Overlay",       True,  "Part of Xbox services."),
    "Microsoft.XboxGamingOverlay":     ("Xbox Gaming Overlay",     True,  "Affects Game Bar."),
    "Microsoft.XboxIdentityProvider":  ("Xbox Identity",           True,  "Required for Xbox login."),
    "Microsoft.OneDrive":              ("OneDrive",                True,  "Backup data first."),
    "Microsoft.Cortana":               ("Cortana",                 True,  "May affect search."),
}

def remove_app(pkg, cb=None):
    if cb: cb(f"[INFO] Removing {pkg}...")
    return run_ps(f'Get-AppxPackage -Name "{pkg}" | Remove-AppxPackage -EA SilentlyContinue; Get-AppxProvisionedPackage -Online | Where-Object DisplayName -like "{pkg}" | Remove-AppxProvisionedPackage -Online -EA SilentlyContinue; Write-Host "Removed: {pkg}"', cb)

# Browser debloat
def debloat_edge(cb=None):
    if cb: cb("[INFO] Debloating Microsoft Edge...")
    cmd = r'''
    $p="HKLM:\SOFTWARE\Policies\Microsoft\Edge"
    If(!(Test-Path $p)){New-Item -Path $p -Force|Out-Null}
    Set-ItemProperty $p -Name MetricsReportingEnabled -Value 0 -Force
    Set-ItemProperty $p -Name PersonalizationReportingEnabled -Value 0 -Force
    Set-ItemProperty $p -Name EdgeShoppingAssistantEnabled -Value 0 -Force
    Set-ItemProperty $p -Name HubsSidebarEnabled -Value 0 -Force
    Set-ItemProperty $p -Name EdgeCollectionsEnabled -Value 0 -Force
    Set-ItemProperty $p -Name BrowserSignin -Value 0 -Force
    Set-ItemProperty $p -Name UserFeedbackAllowed -Value 0 -Force
    Set-ItemProperty $p -Name DiagnosticData -Value 0 -Force
    Set-ItemProperty $p -Name SpotlightExperiencesAndRecommendationsEnabled -Value 0 -Force
    Set-ItemProperty $p -Name ShowRecommendationsEnabled -Value 0 -Force
    Write-Host "Edge debloated: telemetry, shopping, sidebar, collections, recommendations disabled."
    '''
    return run_ps(cmd, cb)

def debloat_brave(cb=None):
    if cb: cb("[INFO] Debloating Brave Browser...")
    cmd = r'''
    $p="HKLM:\SOFTWARE\Policies\BraveSoftware\Brave"
    If(!(Test-Path $p)){New-Item -Path $p -Force|Out-Null}
    Set-ItemProperty $p -Name BraveRewardsDisabled -Value 1 -Force -EA SilentlyContinue
    Set-ItemProperty $p -Name BraveWalletDisabled -Value 1 -Force -EA SilentlyContinue
    Set-ItemProperty $p -Name BraveVPNDisabled -Value 1 -Force -EA SilentlyContinue
    Set-ItemProperty $p -Name MetricsReportingEnabled -Value 0 -Force -EA SilentlyContinue
    Set-ItemProperty $p -Name BraveAIChatEnabled -Value 0 -Force -EA SilentlyContinue
    Write-Host "Brave debloated: rewards, wallet, VPN, AI chat, telemetry disabled."
    '''
    return run_ps(cmd, cb)

# ═══ TWEAKS ═══════════════════════════════════════════════════════════════════

TWEAKS = {
    "activity_history":       {"label": "Activity History - Disable", "cat": "essential", "tip": "Stops Windows from tracking apps/files you open.", "danger": False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Windows\System" -Name EnableActivityFeed -Value 0 -Force -EA SilentlyContinue; Set-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Windows\System" -Name PublishUserActivities -Value 0 -Force -EA SilentlyContinue; Write-Host "Activity History disabled."', cb)},
    "consumer_features":      {"label": "ConsumerFeatures - Disable", "cat": "essential", "tip": "Prevents Microsoft from silently installing apps like Candy Crush.", "danger": False,
        "fn": lambda cb: run_ps(r'$p="HKLM:\SOFTWARE\Policies\Microsoft\Windows\CloudContent"; If(!(Test-Path $p)){New-Item $p -Force|Out-Null}; Set-ItemProperty $p -Name DisableWindowsConsumerFeatures -Value 1 -Force; Write-Host "ConsumerFeatures disabled."', cb)},
    "end_task_rightclick":    {"label": "End Task With Right Click - Enable", "cat": "essential", "tip": "Adds End Task to the taskbar right-click menu.", "danger": False,
        "fn": lambda cb: run_ps(r'$p="HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced\TaskbarDeveloperSettings"; If(!(Test-Path $p)){New-Item $p -Force|Out-Null}; Set-ItemProperty $p -Name TaskbarEndTask -Value 1 -Force; Write-Host "End Task enabled."', cb)},
    "disable_hibernation":    {"label": "Hibernation - Disable", "cat": "essential", "tip": "Disables hibernation and frees several GB. Not for laptops.", "danger": False,
        "fn": lambda cb: run_cmd("powercfg /h off", cb)},
    "disable_location":       {"label": "Location Tracking - Disable", "cat": "essential", "tip": "Disables Windows location services system-wide.", "danger": False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location" -Name Value -Value "Deny" -Force -EA SilentlyContinue; Write-Host "Location disabled."', cb)},
    "disable_store_search":   {"label": "Store Search Results - Disable", "cat": "essential", "tip": "Stops Start Menu from showing Store app suggestions.", "danger": False,
        "fn": lambda cb: run_ps(r'$p="HKCU:\SOFTWARE\Policies\Microsoft\Windows\Explorer"; If(!(Test-Path $p)){New-Item $p -Force|Out-Null}; Set-ItemProperty $p -Name NoUseStoreOpenWith -Value 1 -Force; Write-Host "Store suggestions disabled."', cb)},
    "disable_ps7_telemetry":  {"label": "PowerShell 7 Telemetry - Disable", "cat": "essential", "tip": "Tells PowerShell 7 not to send telemetry.", "danger": False,
        "fn": lambda cb: run_ps(r'[Environment]::SetEnvironmentVariable("POWERSHELL_TELEMETRY_OPTOUT","1","Machine"); Write-Host "PS telemetry disabled."', cb)},
    "services_manual":        {"label": "Services - Set to Manual", "cat": "essential", "tip": "Sets background services to Manual startup. They run only when needed.", "danger": False,
        "fn": lambda cb: run_ps(r'$s=@("DiagTrack","dmwappushservice","lfsvc","MapsBroker","NetTcpPortSharing","RemoteAccess","RemoteRegistry","TrkWks","WMPNetworkSvc","XblAuthManager","XblGameSave","XboxNetApiSvc","ndu"); foreach($i in $s){Set-Service $i -StartupType Manual -EA SilentlyContinue}; Write-Host "Services set to manual."', cb)},
    "disable_telemetry":      {"label": "Telemetry - Disable", "cat": "essential", "tip": "Disables diagnostic data collection and DiagTrack service.", "danger": False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection" -Name AllowTelemetry -Value 0 -Force -EA SilentlyContinue; Stop-Service DiagTrack -Force -EA SilentlyContinue; Set-Service DiagTrack -StartupType Disabled -EA SilentlyContinue; Write-Host "Telemetry disabled."', cb)},
    "remove_widgets":         {"label": "Widgets - Remove", "cat": "essential", "tip": "Removes the Widgets button from the Win11 taskbar.", "danger": False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name TaskbarDa -Value 0 -Force -EA SilentlyContinue; Write-Host "Widgets removed."', cb)},
    "disable_wpbt":           {"label": "WPBT - Disable", "cat": "essential", "tip": "Disables Windows Platform Binary Table, an OEM security risk.", "danger": False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager" -Name DisableWpbtExecution -Value 1 -Force -EA SilentlyContinue; Write-Host "WPBT disabled."', cb)},

    "disable_bg_apps":        {"label": "Background Apps - Disable", "cat": "advanced", "tip": "Stops all apps from running in background. Saves RAM.", "danger": False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications" -Name GlobalUserDisabled -Value 1 -Force -EA SilentlyContinue; Write-Host "Background apps disabled."', cb)},
    "disable_fullscreen_opt": {"label": "Fullscreen Optimizations - Disable", "cat": "advanced", "tip": "Can improve gaming performance and reduce input lag.", "danger": False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\System\GameConfigStore" -Name GameDVR_DXGIHonorFSEWindowsCompatible -Value 1 -Force -EA SilentlyContinue; Set-ItemProperty "HKCU:\System\GameConfigStore" -Name GameDVR_FSEBehavior -Value 2 -Force -EA SilentlyContinue; Write-Host "Fullscreen optimizations disabled."', cb)},
    "disable_ipv6":           {"label": "IPv6 - Disable", "cat": "advanced", "tip": "Fully disables IPv6. Only if your network doesn't use it.", "danger": True,
        "fn": lambda cb: run_ps(r'Get-NetAdapter | foreach { Disable-NetAdapterBinding -Name $_.Name -ComponentID ms_tcpip6 -EA SilentlyContinue }; Write-Host "IPv6 disabled."', cb)},
    "prefer_ipv4":            {"label": "IPv6 - Prefer IPv4", "cat": "advanced", "tip": "Keeps IPv6 but prefers IPv4. Safer than disabling.", "danger": False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters" -Name DisabledComponents -Value 32 -Force -EA SilentlyContinue; Write-Host "IPv4 preferred."', cb)},
    "remove_onedrive":        {"label": "OneDrive - Remove", "cat": "advanced", "tip": "Fully uninstalls OneDrive. Backup your data first.", "danger": True,
        "fn": lambda cb: run_ps(r'Stop-Process -Name OneDrive -Force -EA SilentlyContinue; Start-Process "$env:SYSTEMROOT\SysWOW64\OneDriveSetup.exe" -ArgumentList "/uninstall" -Wait -EA SilentlyContinue; Start-Process "$env:SYSTEMROOT\System32\OneDriveSetup.exe" -ArgumentList "/uninstall" -Wait -EA SilentlyContinue; Write-Host "OneDrive removed."', cb)},
    "disable_storage_sense":  {"label": "Storage Sense - Disable", "cat": "advanced", "tip": "Stops auto-deletion of temp files and recycle bin.", "danger": False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\StorageSense\Parameters\StoragePolicy" -Name 01 -Value 0 -Force -EA SilentlyContinue; Write-Host "Storage Sense disabled."', cb)},
    "disable_teredo":         {"label": "Teredo - Disable", "cat": "advanced", "tip": "Disables IPv6 tunnelling protocol.", "danger": False,
        "fn": lambda cb: run_cmd("netsh interface teredo set state disabled", cb)},
    "visual_performance":     {"label": "Visual Effects - Best Performance", "cat": "advanced", "tip": "Disables all animations. Snappier but less pretty.", "danger": False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects" -Name VisualFXSetting -Value 2 -Force -EA SilentlyContinue; Write-Host "Visual effects set to performance."', cb)},
    "disable_windows_ai":     {"label": "Windows AI - Disable", "cat": "advanced", "tip": "Disables Recall and AI features. Recommended for privacy.", "danger": False,
        "fn": lambda cb: run_ps(r'$p="HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsAI"; If(!(Test-Path $p)){New-Item $p -Force|Out-Null}; Set-ItemProperty $p -Name AllowRecallEnablement -Value 0 -Force; Set-ItemProperty $p -Name DisableAIDataAnalysis -Value 1 -Force; Write-Host "Windows AI disabled."', cb)},
    "remove_xbox":            {"label": "Xbox Components - Remove", "cat": "advanced", "tip": "Removes Xbox apps and overlay. Breaks Game Pass.", "danger": True,
        "fn": lambda cb: run_ps(r'@("Microsoft.XboxGameOverlay","Microsoft.XboxGamingOverlay","Microsoft.XboxIdentityProvider","Microsoft.XboxSpeechToTextOverlay") | foreach { Get-AppxPackage -Name $_ | Remove-AppxPackage -EA SilentlyContinue }; Write-Host "Xbox components removed."', cb)},

    "pref_dark_mode":         {"label": "Dark Theme", "cat": "preference", "tip": "Enables system-wide dark theme.", "danger": False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize" -Name AppsUseLightTheme -Value 0 -Force; Set-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize" -Name SystemUsesLightTheme -Value 0 -Force; Write-Host "Dark mode enabled."', cb)},
    "pref_file_ext":          {"label": "Show File Extensions", "cat": "preference", "tip": "Shows .exe, .pdf, etc. in Explorer. Highly recommended.", "danger": False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name HideFileExt -Value 0 -Force; Write-Host "File extensions visible."', cb)},
    "pref_hidden_files":      {"label": "Show Hidden Files", "cat": "preference", "tip": "Shows hidden files in Explorer.", "danger": False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name Hidden -Value 1 -Force; Write-Host "Hidden files visible."', cb)},
    "pref_no_mouse_accel":    {"label": "Disable Mouse Acceleration", "cat": "preference", "tip": "Removes pointer acceleration. Better for gaming.", "danger": False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\Control Panel\Mouse" -Name MouseSpeed -Value 0 -Force; Set-ItemProperty "HKCU:\Control Panel\Mouse" -Name MouseThreshold1 -Value 0 -Force; Set-ItemProperty "HKCU:\Control Panel\Mouse" -Name MouseThreshold2 -Value 0 -Force; Write-Host "Mouse accel disabled."', cb)},
    "pref_numlock":           {"label": "Num Lock on Startup", "cat": "preference", "tip": "Auto-enables Num Lock when Windows starts.", "danger": False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\Control Panel\Keyboard" -Name InitialKeyboardIndicators -Value 2 -Force; Write-Host "Num Lock enabled."', cb)},
    "pref_no_sticky_keys":    {"label": "Disable Sticky Keys", "cat": "preference", "tip": "Stops the Shift x5 popup. Great for gaming.", "danger": False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\Control Panel\Accessibility\StickyKeys" -Name Flags -Value "506" -Force; Write-Host "Sticky Keys disabled."', cb)},
    "pref_hide_search":       {"label": "Hide Taskbar Search", "cat": "preference", "tip": "Hides search from taskbar. Win key still opens search.", "danger": False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Search" -Name SearchboxTaskbarMode -Value 0 -Force; Write-Host "Search hidden."', cb)},
    "pref_hide_taskview":     {"label": "Hide Task View Button", "cat": "preference", "tip": "Hides Task View from the taskbar.", "danger": False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name ShowTaskViewButton -Value 0 -Force; Write-Host "Task View hidden."', cb)},
    "pref_left_taskbar":      {"label": "Taskbar Icons - Move Left", "cat": "preference", "tip": "Moves taskbar icons to the left (Win11).", "danger": False,
        "fn": lambda cb: run_ps(r'Set-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name TaskbarAl -Value 0 -Force; Write-Host "Taskbar left-aligned."', cb)},
    "pref_classic_menu":      {"label": "Classic Right-Click Menu", "cat": "preference", "tip": "Restores the full context menu in Win11.", "danger": False,
        "fn": lambda cb: run_ps(r'$p="HKCU:\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32"; If(!(Test-Path $p)){New-Item $p -Force|Out-Null}; Set-ItemProperty $p -Name "(Default)" -Value "" -Force; Stop-Process -Name explorer -Force -EA SilentlyContinue; Write-Host "Classic context menu restored."', cb)},
    "pref_no_startup_delay":  {"label": "Remove Startup Delay", "cat": "preference", "tip": "Removes the artificial delay before startup programs.", "danger": False,
        "fn": lambda cb: run_ps(r'$p="HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize"; If(!(Test-Path $p)){New-Item $p -Force|Out-Null}; Set-ItemProperty $p -Name StartupDelayInMSec -Value 0 -Force; Write-Host "Startup delay removed."', cb)},
    "pref_high_perf":         {"label": "High Performance Power Plan", "cat": "preference", "tip": "Best for desktops. Not recommended on battery.", "danger": False,
        "fn": lambda cb: run_cmd("powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", cb)},
}

PRESETS = {
    "Gaming PC": {"tweaks": ["disable_telemetry","end_task_rightclick","disable_fullscreen_opt","pref_no_mouse_accel","pref_no_sticky_keys","disable_bg_apps","visual_performance","pref_no_startup_delay","pref_high_perf","remove_widgets","disable_windows_ai"]},
    "Privacy":   {"tweaks": ["disable_telemetry","activity_history","consumer_features","disable_location","disable_ps7_telemetry","disable_windows_ai","remove_onedrive","disable_store_search"]},
    "Fresh Install": {"tweaks": ["pref_file_ext","pref_hidden_files","pref_dark_mode","pref_no_sticky_keys","disable_telemetry","consumer_features","pref_classic_menu","pref_no_startup_delay","end_task_rightclick","remove_widgets"]},
    "Performance": {"tweaks": ["pref_high_perf","disable_bg_apps","visual_performance","pref_no_startup_delay","disable_telemetry","services_manual","disable_storage_sense"]},
}

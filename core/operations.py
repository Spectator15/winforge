"""
WinForge core operations — all PowerShell-backed backend logic.
"""
import subprocess, threading, json, os, sys

def run_ps(script: str, cb=None) -> str:
    """Run a PowerShell script and stream output via cb(line). Returns full output."""
    try:
        proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        out = []
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                out.append(line)
                if cb: cb(line)
        proc.wait()
        return "\n".join(out)
    except Exception as e:
        msg = f"[ERROR] PowerShell error: {e}"
        if cb: cb(msg)
        return msg


# ─────────────────────────── SYSTEM INFO ────────────────────────────
def get_system_info(cb=None):
    script = r'''
$info = @{}
# OS
$os = Get-CimInstance Win32_OperatingSystem
$info["os_name"]    = $os.Caption
$info["os_version"] = $os.Version
$info["os_build"]   = $os.BuildNumber
$info["os_arch"]    = $os.OSArchitecture
$info["os_install"] = $os.InstallDate.ToString("yyyy-MM-dd")
$boot = $os.LastBootUpTime
$uptime = (Get-Date) - $boot
$info["uptime"] = "$([int]$uptime.TotalHours)h $($uptime.Minutes)m"
# CPU
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$info["cpu_name"]    = $cpu.Name.Trim()
$info["cpu_cores"]   = "$($cpu.NumberOfCores) cores / $($cpu.NumberOfLogicalProcessors) threads"
$info["cpu_clock"]   = "$([math]::Round($cpu.MaxClockSpeed/1000,1)) GHz"
# RAM
$ram = Get-CimInstance Win32_PhysicalMemory
$totalGB = [math]::Round(($ram | Measure-Object -Property Capacity -Sum).Sum / 1GB, 0)
$speed   = ($ram | Select-Object -First 1).Speed
$sticks  = $ram.Count
$type    = switch(($ram | Select-Object -First 1).SMBIOSMemoryType){
    26{"DDR4"} 34{"DDR5"} 24{"DDR3"} default{"DDR"}
}
$info["ram"] = "${totalGB}GB ${type} ${speed}MHz (${sticks} stick$(if($sticks -ne 1){'s'}))"
# GPU — use registry GUID {4d36e968-e325-11ce-bfc1-08002be10318} for real VRAM
$gpus = Get-CimInstance Win32_VideoController
$gpuList = @()
foreach ($g in $gpus) {
    $vram = $null
    try {
        $regPath = "HKLM:\SYSTEM\ControlSet001\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
        Get-ChildItem $regPath -EA SilentlyContinue | ForEach-Object {
            $desc = (Get-ItemProperty $_.PSPath -EA SilentlyContinue).DriverDesc
            if ($desc -and $desc -eq $g.Name) {
                $qw = (Get-ItemProperty $_.PSPath -EA SilentlyContinue).'HardwareInformation.qwMemorySize'
                if ($qw -and [uint64]$qw -gt 0) {
                    $vram = [math]::Round([uint64]$qw / 1GB, 0)
                }
                if (!$vram) {
                    $memBytes = (Get-ItemProperty $_.PSPath -EA SilentlyContinue).'HardwareInformation.MemorySize'
                    if ($memBytes) {
                        $bytes = [System.BitConverter]::ToUInt64([byte[]]$memBytes, 0)
                        if ($bytes -gt 0) { $vram = [math]::Round($bytes / 1GB, 0) }
                    }
                }
            }
        }
    } catch {}
    if (!$vram -or $vram -le 0) {
        $raw = $g.AdapterRAM
        if ($raw -gt 0) { $vram = [math]::Round($raw / 1GB, 0) } else { $vram = $null }
    }
    $vramStr = if ($vram -and $vram -gt 0) { "${vram}GB" } else { "Shared" }
    $gpuList += "$($g.Name) ($vramStr)"
}
$info["gpu"]        = $gpuList -join " | "
$info["gpu_driver"] = ($gpus | Select-Object -First 1).DriverVersion
# Storage
$disks = Get-CimInstance Win32_DiskDrive
$diskList = @()
foreach ($d in $disks) {
    $sizeGB = [math]::Round($d.Size/1GB,0)
    $mediaType = if($d.MediaType -match "SSD|Solid"){"SSD"}elseif($d.MediaType -match "HDD|Fixed"){"HDD"}else{"Drive"}
    $diskList += "$($d.Model) (${sizeGB}GB $mediaType)"
}
$info["disks"] = $diskList -join " | "
$vols = Get-PSDrive -PSProvider FileSystem | Where-Object {$_.Used -ne $null}
$volList = @()
foreach ($v in $vols) {
    $free = [math]::Round($v.Free/1GB,1)
    $total= [math]::Round(($v.Used+$v.Free)/1GB,1)
    $volList += "$($v.Name): ${free}GB free / ${total}GB"
}
$info["volumes"] = $volList -join " | "
# Motherboard & BIOS
$mb   = Get-CimInstance Win32_BaseBoard
$bios = Get-CimInstance Win32_BIOS
$info["motherboard"] = "$($mb.Manufacturer) $($mb.Product)"
$info["bios"]        = "$($bios.Manufacturer) $($bios.SMBIOSBIOSVersion)"
# Security
try { $sb = Confirm-SecureBootUEFI; $info["secure_boot"] = if($sb){"Enabled"}else{"Disabled"} } catch { $info["secure_boot"] = "N/A" }
try { $tpm = Get-Tpm; $info["tpm"] = if($tpm.TpmPresent){"v$($tpm.ManufacturerVersionInfo) Present"}else{"Not Present"} } catch { $info["tpm"] = "N/A" }
try {
    $def = Get-MpComputerStatus -EA SilentlyContinue
    $info["defender"] = if($def){ "$(if($def.RealTimeProtectionEnabled){'Active'}else{'Disabled'}) — Defs: $($def.AntivirusSignatureLastUpdated.ToString('yyyy-MM-dd'))" } else { "N/A" }
} catch { $info["defender"] = "N/A" }
# Network
$net = Get-CimInstance Win32_NetworkAdapterConfiguration | Where-Object {$_.IPEnabled -eq $true} | Select-Object -First 1
$info["network"] = if($net){"$($net.Description) | MAC: $($net.MACAddress)"}else{"N/A"}
# Power
try {
    $plan = powercfg /getactivescheme 2>$null
    $info["power"] = if($plan -match '\((.+)\)'){"Active: $($Matches[1])"}else{"N/A"}
} catch { $info["power"] = "N/A" }
$info | ConvertTo-Json -Compress
'''
    raw = run_ps(script, cb)
    try:
        lines = [l for l in raw.splitlines() if l.strip().startswith("{")]
        if lines:
            return json.loads(lines[-1])
    except:
        pass
    return {}


# ─────────────────────────── REPAIR ─────────────────────────────────
def run_dism(cb=None):
    return run_ps("DISM /Online /Cleanup-Image /RestoreHealth", cb)

def run_sfc(cb=None):
    return run_ps("sfc /scannow", cb)

def run_chkdsk(cb=None):
    return run_ps("chkdsk C: /f /r /x", cb)


# ─────────────────────────── CLEANUP ────────────────────────────────
def clean_temp(cb=None):
    if cb: cb("[INFO] Cleaning temp files...")
    script = r'''
$dirs = @($env:TEMP, $env:TMP, "C:\Windows\Temp", "C:\Windows\Prefetch")
$count = 0
foreach ($d in $dirs) {
    if (Test-Path $d) {
        Get-ChildItem $d -Recurse -Force -EA SilentlyContinue | Remove-Item -Recurse -Force -EA SilentlyContinue
        $count++
    }
}
Write-Host "[OK] Temp folders cleaned ($count directories)"
'''
    return run_ps(script, cb)

def clean_update_cache(cb=None):
    if cb: cb("[INFO] Cleaning Windows Update cache...")
    script = r'''
Stop-Service -Name wuauserv -Force -EA SilentlyContinue
Stop-Service -Name bits    -Force -EA SilentlyContinue
Remove-Item "C:\Windows\SoftwareDistribution\Download\*" -Recurse -Force -EA SilentlyContinue
Start-Service -Name wuauserv -EA SilentlyContinue
Start-Service -Name bits    -EA SilentlyContinue
Write-Host "[OK] Windows Update cache cleared"
'''
    return run_ps(script, cb)

def flush_dns(cb=None):
    if cb: cb("[INFO] Flushing DNS cache...")
    return run_ps('ipconfig /flushdns; Write-Host "[OK] DNS cache flushed"', cb)

def reset_network(cb=None):
    if cb: cb("[INFO] Resetting network stack...")
    script = r'''
netsh int ip reset
netsh winsock reset
netsh advfirewall reset
ipconfig /flushdns
ipconfig /release
ipconfig /renew
Write-Host "[OK] Network stack reset complete — reboot recommended"
'''
    return run_ps(script, cb)

def empty_recycle(cb=None):
    if cb: cb("[INFO] Emptying Recycle Bin...")
    script = r'''
$shell = New-Object -ComObject Shell.Application
$shell.Namespace(0xA).Items() | ForEach-Object { Remove-Item $_.Path -Recurse -Force -EA SilentlyContinue }
Write-Host "[OK] Recycle Bin emptied"
'''
    return run_ps(script, cb)

def clean_event_logs(cb=None):
    if cb: cb("[INFO] Clearing event logs...")
    script = r'''
Get-EventLog -List | ForEach-Object { Clear-EventLog -LogName $_.Log -EA SilentlyContinue }
Write-Host "[OK] Event logs cleared"
'''
    return run_ps(script, cb)


# ─────────────────────────── DEPENDENCIES ───────────────────────────
def install_dotnet(version: str, cb=None):
    if cb: cb(f"[INFO] Installing .NET {version} runtime...")
    script = f'winget install --id Microsoft.DotNet.Runtime.{version} --accept-source-agreements --accept-package-agreements -e; Write-Host "[OK] .NET {version} install complete"'
    return run_ps(script, cb)

def install_vcredist(cb=None):
    if cb: cb("[INFO] Installing VC++ Redistributables...")
    script = r'''
$ids = @(
    "Microsoft.VCRedist.2005.x86","Microsoft.VCRedist.2005.x64",
    "Microsoft.VCRedist.2008.x86","Microsoft.VCRedist.2008.x64",
    "Microsoft.VCRedist.2010.x86","Microsoft.VCRedist.2010.x64",
    "Microsoft.VCRedist.2012.x86","Microsoft.VCRedist.2012.x64",
    "Microsoft.VCRedist.2013.x86","Microsoft.VCRedist.2013.x64",
    "Microsoft.VCRedist.2015+.x86","Microsoft.VCRedist.2015+.x64"
)
foreach ($id in $ids) {
    winget install --id $id --accept-source-agreements --accept-package-agreements -e --silent 2>$null
}
Write-Host "[OK] All VC++ Redistributables installed"
'''
    return run_ps(script, cb)

def install_directx(cb=None):
    if cb: cb("[INFO] Installing DirectX...")
    script = r'winget install --id Microsoft.DirectX --accept-source-agreements --accept-package-agreements -e; Write-Host "[OK] DirectX install complete"'
    return run_ps(script, cb)

def install_webview2(cb=None):
    if cb: cb("[INFO] Installing WebView2 Runtime...")
    script = r'winget install --id Microsoft.EdgeWebView2Runtime --accept-source-agreements --accept-package-agreements -e; Write-Host "[OK] WebView2 install complete"'
    return run_ps(script, cb)

def install_xna(cb=None):
    if cb: cb("[INFO] Installing XNA Framework...")
    script = r'winget install --id Microsoft.XNAFramework --accept-source-agreements --accept-package-agreements -e; Write-Host "[OK] XNA install complete"'
    return run_ps(script, cb)


# ─────────────────────────── APP INSTALL ────────────────────────────
def install_app(app_id: str, manager: str, cb=None):
    if cb: cb(f"[INFO] Installing {app_id} via {manager}...")
    if manager == "winget":
        script = f'winget install --id "{app_id}" --accept-source-agreements --accept-package-agreements -e; Write-Host "[OK] {app_id} install complete"'
    else:
        script = f'choco install {app_id} -y; Write-Host "[OK] {app_id} install complete"'
    return run_ps(script, cb)


# ─────────────────────────── TWEAKS ─────────────────────────────────
# All verified against WinUtil (winutil.christitus.com)

def tweak_telemetry(enable=False, cb=None):
    """WinUtil: WPFTweaksTelemetry — 12 registry keys + services + scripts"""
    if cb: cb(f"[INFO] {'Disabling' if not enable else 'Enabling'} Telemetry (WinUtil-verified, 12 keys)...")
    v = "1" if enable else "0"
    v_inv = "0" if enable else "1"  # for keys that are inverted (restrict = 1 to disable)
    startup = "Automatic" if enable else "Disabled"
    consent = "1" if enable else "2"
    script = f'''
# 12 registry keys from WinUtil WPFTweaksTelemetry
$reg = @(
    @{{P="HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\AdvertisingInfo";N="Enabled";V={v}}},
    @{{P="HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Privacy";N="TailoredExperiencesWithDiagnosticDataEnabled";V={v}}},
    @{{P="HKCU:\\Software\\Microsoft\\Speech_OneCore\\Settings\\OnlineSpeechPrivacy";N="HasAccepted";V={v}}},
    @{{P="HKCU:\\Software\\Microsoft\\Input\\TIPC";N="Enabled";V={v}}},
    @{{P="HKCU:\\Software\\Microsoft\\InputPersonalization";N="RestrictImplicitInkCollection";V={v_inv}}},
    @{{P="HKCU:\\Software\\Microsoft\\InputPersonalization";N="RestrictImplicitTextCollection";V={v_inv}}},
    @{{P="HKCU:\\Software\\Microsoft\\InputPersonalization\\TrainedDataStore";N="HarvestContacts";V={v}}},
    @{{P="HKCU:\\Software\\Microsoft\\Personalization\\Settings";N="AcceptedPrivacyPolicy";V={v}}},
    @{{P="HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\DataCollection";N="AllowTelemetry";V={v}}},
    @{{P="HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced";N="Start_TrackProgs";V={v}}},
    @{{P="HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\System";N="PublishUserActivities";V={v}}},
    @{{P="HKCU:\\Software\\Microsoft\\Siuf\\Rules";N="NumberOfSIUFInPeriod";V={v}}}
)
foreach ($r in $reg) {{
    If(!(Test-Path $r.P)){{New-Item -Path $r.P -Force|Out-Null}}
    Set-ItemProperty -Path $r.P -Name $r.N -Value $r.V -Type DWord -Force -EA SilentlyContinue
}}
# Services
Set-Service -Name diagtrack -StartupType {startup} -EA SilentlyContinue
Set-Service -Name wermgr    -StartupType {startup} -EA SilentlyContinue
# Defender sample submission
Set-MpPreference -SubmitSamplesConsent {consent} -EA SilentlyContinue
# Remove SIUF PeriodInNanoSeconds if disabling
{"Remove-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Siuf\\Rules' -Name PeriodInNanoSeconds -EA SilentlyContinue" if not enable else ""}
Write-Host "[OK] Telemetry {'enabled' if enable else 'disabled'} (12 registry keys + services)"
'''
    return run_ps(script, cb)

def tweak_activity_history(enable=False, cb=None):
    """WinUtil: WPFTweaksActivity — 3 registry keys"""
    if cb: cb(f"[INFO] {'Enabling' if enable else 'Disabling'} Activity History...")
    v = "1" if enable else "0"
    script = f'''
$p = "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\System"
If(!(Test-Path $p)){{New-Item -Path $p -Force|Out-Null}}
Set-ItemProperty $p -Name EnableActivityFeed     -Value {v} -Type DWord -Force -EA SilentlyContinue
Set-ItemProperty $p -Name PublishUserActivities  -Value {v} -Type DWord -Force -EA SilentlyContinue
Set-ItemProperty $p -Name UploadUserActivities   -Value {v} -Type DWord -Force -EA SilentlyContinue
Write-Host "[OK] Activity History {'enabled' if enable else 'disabled'} (3 keys)"
'''
    return run_ps(script, cb)

def tweak_location(enable=False, cb=None):
    """WinUtil: WPFTweaksLocation — 3 registry keys + lfsvc service (exact match)"""
    if cb: cb(f"[INFO] {'Enabling' if enable else 'Disabling'} Location Tracking...")
    consent_val  = "Allow" if enable else "Deny"
    sensor_val   = "1" if enable else "0"
    maps_val     = "1" if enable else "0"
    svc_start    = "Manual" if enable else "Disabled"   # OriginalType is Manual per WinUtil
    script = f'''
# Key 1: ConsentStore — Type is String, not DWord
$p1 = "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\CapabilityAccessManager\\ConsentStore\\location"
If(!(Test-Path $p1)){{New-Item -Path $p1 -Force|Out-Null}}
Set-ItemProperty $p1 -Name Value -Value "{consent_val}" -Type String -Force -EA SilentlyContinue
# Key 2: SensorPermissionState — DWord
$p2 = "HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Sensor\\Overrides\\{{BFA794E4-F964-4FDB-90F6-51056BFE4B44}}"
If(!(Test-Path $p2)){{New-Item -Path $p2 -Force|Out-Null}}
Set-ItemProperty $p2 -Name SensorPermissionState -Value {sensor_val} -Type DWord -Force -EA SilentlyContinue
# Key 3: Maps AutoUpdate — DWord (HKLM:\SYSTEM\Maps per WinUtil)
$p3 = "HKLM:\\SYSTEM\\Maps"
If(!(Test-Path $p3)){{New-Item -Path $p3 -Force|Out-Null}}
Set-ItemProperty $p3 -Name AutoUpdateEnabled -Value {maps_val} -Type DWord -Force -EA SilentlyContinue
# Service: lfsvc — OriginalType is Manual
Set-Service -Name lfsvc -StartupType {svc_start} -EA SilentlyContinue
Write-Host "[OK] Location Tracking {'enabled' if enable else 'disabled'} (3 keys + lfsvc service)"
'''
    return run_ps(script, cb)

def tweak_consumer_features(enable=False, cb=None):
    """WinUtil: WPFTweaksConsumerFeatures — 1 registry key (exact match)"""
    if cb: cb(f"[INFO] {'Enabling' if enable else 'Disabling'} Consumer Features...")
    script = f'''
$p = "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\CloudContent"
If(!(Test-Path $p)){{New-Item -Path $p -Force|Out-Null}}
{"Remove-ItemProperty $p -Name DisableWindowsConsumerFeatures -EA SilentlyContinue" if enable else 'Set-ItemProperty $p -Name DisableWindowsConsumerFeatures -Value 1 -Type DWord -Force -EA SilentlyContinue'}
Write-Host "[OK] Consumer Features {'enabled (key removed)' if enable else 'disabled'}"
'''
    return run_ps(script, cb)

def tweak_hibernation(enable=False, cb=None):
    """WinUtil: WPFTweaksHiber — 2 registry keys + powercfg (exact match)"""
    if cb: cb(f"[INFO] {'Enabling' if enable else 'Disabling'} Hibernation...")
    hiber_val  = "1" if enable else "0"
    flyout_val = "1" if enable else "0"
    cmd        = "powercfg.exe /hibernate on" if enable else "powercfg.exe /hibernate off"
    script = f'''
# Key 1: HibernateEnabled
$p1 = "HKLM:\\System\\CurrentControlSet\\Control\\Session Manager\\Power"
Set-ItemProperty $p1 -Name HibernateEnabled -Value {hiber_val} -Type DWord -Force -EA SilentlyContinue
# Key 2: ShowHibernateOption (hide/show from power menu)
$p2 = "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FlyoutMenuSettings"
If(!(Test-Path $p2)){{New-Item -Path $p2 -Force|Out-Null}}
Set-ItemProperty $p2 -Name ShowHibernateOption -Value {flyout_val} -Type DWord -Force -EA SilentlyContinue
# InvokeScript
{cmd}
Write-Host "[OK] Hibernation {'enabled' if enable else 'disabled'} (2 registry keys + powercfg)"
'''
    return run_ps(script, cb)

def tweak_fast_startup(enable=True, cb=None):
    if cb: cb(f"[INFO] {'Enabling' if enable else 'Disabling'} Fast Startup...")
    v = "1" if enable else "0"
    script = f'''
$p = "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Power"
Set-ItemProperty $p -Name HiberbootEnabled -Value {v} -Type DWord -Force -EA SilentlyContinue
Write-Host "[OK] Fast Startup {'enabled' if enable else 'disabled'}"
'''
    return run_ps(script, cb)

def tweak_show_extensions(enable=True, cb=None):
    """WinUtil: WPFToggleShowExt — HideFileExt DWord + Explorer restart (exact match)"""
    if cb: cb(f"[INFO] {'Showing' if enable else 'Hiding'} file extensions...")
    v = "0" if enable else "1"
    script = f'''
Set-ItemProperty "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced" -Name HideFileExt -Value {v} -Type DWord -Force -EA SilentlyContinue
# WinUtil InvokeScript: restart Explorer
Stop-Process -Name explorer -Force -EA SilentlyContinue
Write-Host "[OK] File extensions {'shown' if enable else 'hidden'} (Explorer restarted)"
'''
    return run_ps(script, cb)

def tweak_show_hidden(enable=True, cb=None):
    """WinUtil: WPFToggleHiddenFiles — Hidden DWord + Explorer restart (exact match)"""
    if cb: cb(f"[INFO] {'Showing' if enable else 'Hiding'} hidden files...")
    v = "1" if enable else "0"
    script = f'''
Set-ItemProperty "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced" -Name Hidden -Value {v} -Type DWord -Force -EA SilentlyContinue
# WinUtil InvokeScript: restart Explorer
Stop-Process -Name explorer -Force -EA SilentlyContinue
Write-Host "[OK] Hidden files {'shown' if enable else 'hidden'} (Explorer restarted)"
'''
    return run_ps(script, cb)

def tweak_copilot(enable=False, cb=None):
    """WinUtil: WPFTweaksRemoveCopilot — removes Copilot AppX packages (exact match)"""
    if cb: cb(f"[INFO] {'Restoring' if enable else 'Removing'} Microsoft Copilot...")
    if not enable:
        script = r'''
# WinUtil WPFTweaksRemoveCopilot: remove Copilot AppX packages
Get-AppxPackage -AllUsers *Copilot* | Remove-AppxPackage -AllUsers -EA SilentlyContinue
Get-AppxPackage -AllUsers Microsoft.MicrosoftOfficeHub | Remove-AppxPackage -AllUsers -EA SilentlyContinue
$Appx = (Get-AppxPackage MicrosoftWindows.Client.CoreAI -EA SilentlyContinue).PackageFullName
if ($Appx) {
    $Sid = (Get-LocalUser $Env:UserName).Sid.Value
    New-Item "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\EndOfLife\$Sid\$Appx" -Force -EA SilentlyContinue
    Remove-AppxPackage $Appx -EA SilentlyContinue
}
Write-Host "[OK] Copilot removed"
'''
    else:
        # WinUtil UndoScript: reinstall via winget
        script = r'''
winget install --name Copilot --source msstore --accept-package-agreements --accept-source-agreements --silent
Write-Host "[OK] Copilot reinstalled via winget"
'''
    return run_ps(script, cb)

def tweak_widgets(remove=True, cb=None):
    """WinUtil: WPFTweaksWidget — stops Widget process first, removes both AppX packages (exact match)"""
    if cb: cb(f"[INFO] {'Removing' if remove else 'Restoring'} Widgets...")
    if remove:
        script = r'''
# WinUtil: stop process first or removal may fail
Get-Process *Widget* | Stop-Process -Force -EA SilentlyContinue
Get-AppxPackage Microsoft.WidgetsPlatformRuntime -AllUsers | Remove-AppxPackage -AllUsers -EA SilentlyContinue
Get-AppxPackage MicrosoftWindows.Client.WebExperience -AllUsers | Remove-AppxPackage -AllUsers -EA SilentlyContinue
# Restart Explorer
Stop-Process -Name explorer -Force -EA SilentlyContinue
Write-Host "[OK] Widgets removed (both AppX packages)"
'''
    else:
        script = r'''
# WinUtil UndoScript: re-register from WindowsApps directory
Add-AppxPackage -Register "C:\Program Files\WindowsApps\Microsoft.WidgetsPlatformRuntime*\AppxManifest.xml" -DisableDevelopmentMode -EA SilentlyContinue
Add-AppxPackage -Register "C:\Program Files\WindowsApps\MicrosoftWindows.Client.WebExperience*\AppxManifest.xml" -DisableDevelopmentMode -EA SilentlyContinue
Write-Host "[OK] Widgets restored (attempted re-register from WindowsApps)"
'''
    return run_ps(script, cb)

def tweak_services(optimize=True, cb=None):
    """WinUtil: WPFTweaksServices — exact 5 services + SvcHostSplitThreshold (exact match)"""
    if cb: cb("[INFO] Setting services per WinUtil (5 services + SvcHostSplitThreshold)...")
    if optimize:
        script = r'''
# WinUtil exact service list — CscService, DiagTrack, MapsBroker, StorSvc, SharedAccess
Set-Service -Name CscService    -StartupType Disabled -EA SilentlyContinue
Set-Service -Name DiagTrack     -StartupType Disabled -EA SilentlyContinue
Set-Service -Name MapsBroker    -StartupType Manual   -EA SilentlyContinue
Set-Service -Name StorSvc       -StartupType Manual   -EA SilentlyContinue
Set-Service -Name SharedAccess  -StartupType Disabled -EA SilentlyContinue
# SvcHostSplitThreshold — set to total RAM so each svchost hosts its own service
$Memory = (Get-CimInstance Win32_PhysicalMemory | Measure-Object Capacity -Sum).Sum / 1KB
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control" -Name SvcHostSplitThresholdInKB -Value $Memory -Force -EA SilentlyContinue
Write-Host "[OK] Services optimized (WinUtil: 5 services + SvcHostSplitThreshold set to ${Memory}KB)"
'''
    else:
        script = r'''
# Restore original startup types per WinUtil OriginalType values
Set-Service -Name CscService    -StartupType Manual    -EA SilentlyContinue
Set-Service -Name DiagTrack     -StartupType Automatic -EA SilentlyContinue
Set-Service -Name MapsBroker    -StartupType Automatic -EA SilentlyContinue
Set-Service -Name StorSvc       -StartupType Automatic -EA SilentlyContinue
Set-Service -Name SharedAccess  -StartupType Automatic -EA SilentlyContinue
# Restore SvcHostSplitThreshold to Windows default (380000 KB)
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control" -Name SvcHostSplitThresholdInKB -Value 380000 -Force -EA SilentlyContinue
Write-Host "[OK] Services restored to original startup types"
'''
    return run_ps(script, cb)

def tweak_num_lock(enable=True, cb=None):
    """WinUtil: WPFToggleNumLock — 2 keys (HKU\.Default + HKCU), Type=String (exact match)"""
    if cb: cb(f"[INFO] Setting NumLock on startup: {enable}...")
    v = "2" if enable else "0"
    script = f'''
# WinUtil sets both HKU\.Default (system default for new logins) and HKCU (current user)
# Type is String per WinUtil, not DWord
Set-ItemProperty "HKU:\\.Default\\Control Panel\\Keyboard" -Name InitialKeyboardIndicators -Value "{v}" -Type String -Force -EA SilentlyContinue
Set-ItemProperty "HKCU:\\Control Panel\\Keyboard" -Name InitialKeyboardIndicators -Value "{v}" -Type String -Force -EA SilentlyContinue
Write-Host "[OK] NumLock on startup {'enabled' if enable else 'disabled'} (2 keys, String type)"
'''
    return run_ps(script, cb)

def tweak_verbose_logon(enable=True, cb=None):
    if cb: cb(f"[INFO] {'Enabling' if enable else 'Disabling'} verbose logon messages...")
    v = "1" if enable else "0"
    script = f'''
$p = "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System"
Set-ItemProperty $p -Name VerboseStatus -Value {v} -Type DWord -Force -EA SilentlyContinue
Write-Host "[OK] Verbose logon {'enabled' if enable else 'disabled'}"
'''
    return run_ps(script, cb)

def tweak_dark_mode(enable=True, cb=None):
    """WinUtil: WPFToggleDarkMode — AppsUseLightTheme + SystemUsesLightTheme + Explorer restart (exact match)"""
    if cb: cb(f"[INFO] Switching to {'Dark' if enable else 'Light'} mode...")
    v = "0" if enable else "1"
    script = f'''
# WinUtil uses HKCU:\SOFTWARE (uppercase) and restarts Explorer
$p = "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize"
If(!(Test-Path $p)){{New-Item -Path $p -Force|Out-Null}}
Set-ItemProperty $p -Name AppsUseLightTheme    -Value {v} -Type DWord -Force -EA SilentlyContinue
Set-ItemProperty $p -Name SystemUsesLightTheme -Value {v} -Type DWord -Force -EA SilentlyContinue
# WinUtil InvokeScript: restart Explorer
Stop-Process -Name explorer -Force -EA SilentlyContinue
Write-Host "[OK] {'Dark' if enable else 'Light'} mode applied (Explorer restarted)"
'''
    return run_ps(script, cb)

def tweak_power_plan(plan="balanced", cb=None):
    """Power plans: Ultimate Performance uses WinUtil's exact powercfg -duplicatescheme method.
    Balanced and Power Saver use standard GUIDs (not WinUtil-sourced, our own additions)."""
    if cb: cb(f"[INFO] Setting power plan to {plan}...")
    if plan == "ultimate":
        # WinUtil: Invoke-WPFUltimatePerformance — duplicate the hidden scheme and activate it
        script = r'''
$ultimatePlan = powercfg -list | Select-String -Pattern "Ultimate Performance"
if ($ultimatePlan) {
    Write-Host "[INFO] Ultimate Performance plan already installed"
} else {
    powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61
    Write-Host "[INFO] Ultimate Performance plan installed"
}
$guid = (powercfg -list | Select-String -Pattern "Ultimate Performance" | ForEach-Object { $_ -replace '.*\(([a-f0-9-]+)\).*','$1' }).Trim()
powercfg /setactive $guid
Write-Host "[OK] Ultimate Performance power plan activated"
'''
    elif plan == "balanced":
        script = r'powercfg /setactive 381b4222-f694-41f0-9685-ff5bb260df2e; Write-Host "[OK] Balanced power plan set"'
    else:  # power_saver
        script = r'powercfg /setactive a1841308-3541-4fab-bc81-f71556f20b4a; Write-Host "[OK] Power Saver plan set"'
    return run_ps(script, cb)


# ─────────────────────────── BROWSER DEBLOAT ────────────────────────
def debloat_edge(cb=None):
    """WinUtil: WPFTweaksEdgeDebloat — all 17 verified registry entries"""
    if cb: cb("[INFO] Debloating Microsoft Edge (WinUtil-verified, 17 entries)...")
    script = r'''
$p = "HKLM:\SOFTWARE\Policies\Microsoft\Edge"
If(!(Test-Path $p)){New-Item -Path $p -Force|Out-Null}
$settings = @{
    "HideFirstRunExperience"=1;"SendSiteInfoToImproveServices"=0;
    "MetricsReportingEnabled"=1;"EdgeShoppingAssistantEnabled"=0;
    "PersonalizationReportingEnabled"=0;"ShowRecommendationsEnabled"=0;
    "EdgeCollectionsEnabled"=0;"EdgeFollowEnabled"=0;
    "NetworkPredictionOptions"=2;"SearchSuggestEnabled"=0;
    "ShowMicrosoftRewards"=0;"SpotlightExperiencesAndRecommendationsEnabled"=0;
    "TabServicesEnabled"=0;"WebWidget"=0;
    "StartupBoostEnabled"=0;"BackgroundModeEnabled"=0;
    "BrowserAddProfileEnabled"=0
}
foreach ($k in $settings.Keys) {
    Set-ItemProperty $p -Name $k -Value $settings[$k] -Type DWord -Force -EA SilentlyContinue
}
Write-Host "[OK] Edge debloated (17 entries)"
'''
    return run_ps(script, cb)

def debloat_brave(cb=None):
    """WinUtil: WPFTweaksBraveDebloat — all 12 verified registry entries"""
    if cb: cb("[INFO] Debloating Brave Browser (WinUtil-verified, 12 entries)...")
    script = r'''
$p = "HKLM:\SOFTWARE\Policies\BraveSoftware\Brave"
If(!(Test-Path $p)){New-Item -Path $p -Force|Out-Null}
$settings = @{
    "BraveRewardsDisabled"=1;"BraveWalletDisabled"=1;
    "BraveVPNDisabled"=1;"MetricsReportingEnabled"=0;
    "BraveAIChatEnabled"=0;"BraveNewsEnabled"=0;
    "BraveSearchDefaultInPrivateWindowsEnabled"=0;"BraveShieldsEnabled"=1;
    "BraveShieldsSettingsVersion"=2;"SafeBrowsingEnabled"=1;
    "PasswordManagerEnabled"=0;"AutofillCreditCardEnabled"=0
}
foreach ($k in $settings.Keys) {
    Set-ItemProperty $p -Name $k -Value $settings[$k] -Type DWord -Force -EA SilentlyContinue
}
Write-Host "[OK] Brave debloated (12 entries)"
'''
    return run_ps(script, cb)


# ─────────────────────────── APP REMOVAL ────────────────────────────
def check_app_installed(package_name: str) -> bool:
    script = f'$r = Get-AppxPackage -Name "*{package_name}*" -EA SilentlyContinue; if($r){{Write-Host "FOUND"}}else{{Write-Host "NOT_FOUND"}}'
    result = run_ps(script)
    return "FOUND" in result

def remove_app(package_name: str, display_name: str, cb=None):
    if cb: cb(f"[INFO] Checking if {display_name} is installed...")
    if not check_app_installed(package_name):
        if cb: cb(f"[INFO] {display_name} is not installed — skipping")
        return
    if cb: cb(f"[INFO] Removing {display_name}...")
    script = f'''
Get-AppxPackage -Name "*{package_name}*" | Remove-AppxPackage -EA SilentlyContinue
Get-AppxProvisionedPackage -Online | Where-Object DisplayName -like "*{package_name}*" | Remove-AppxProvisionedPackage -Online -EA SilentlyContinue
$verify = Get-AppxPackage -Name "*{package_name}*" -EA SilentlyContinue
if(!$verify){{Write-Host "[OK] {display_name} removed successfully"}}else{{Write-Host "[WARN] {display_name} may still be present"}}
'''
    return run_ps(script, cb)


# ─────────────────────────── DNS ────────────────────────────────────
DNS_PROVIDERS = {
    "Cloudflare":         (["1.1.1.1","1.0.0.1"],  ["2606:4700:4700::1111","2606:4700:4700::1001"]),
    "Google":             (["8.8.8.8","8.8.4.4"],   ["2001:4860:4860::8888","2001:4860:4860::8844"]),
    "Quad9 (Malware Block)":   (["9.9.9.9","149.112.112.112"], ["2620:fe::fe","2620:fe::9"]),
    "OpenDNS":            (["208.67.222.222","208.67.220.220"], []),
    "AdGuard":            (["94.140.14.14","94.140.15.15"], ["2a10:50c0::ad1:ff","2a10:50c0::ad2:ff"]),
    "Cloudflare Family":  (["1.1.1.3","1.0.0.3"],  ["2606:4700:4700::1113","2606:4700:4700::1003"]),
    "Automatic (DHCP)":   ([], []),
}

def set_dns(provider: str, cb=None):
    if cb: cb(f"[INFO] Setting DNS to {provider}...")
    ipv4, ipv6 = DNS_PROVIDERS.get(provider, ([], []))
    if not ipv4:
        script = r'''
$adapters = Get-NetAdapter | Where-Object {$_.Status -eq "Up"}
foreach ($a in $adapters) {
    Set-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ResetServerAddresses
}
ipconfig /flushdns
Write-Host "[OK] DNS reset to automatic (DHCP)"
'''
    else:
        primary, secondary = ipv4[0], ipv4[1] if len(ipv4) > 1 else ipv4[0]
        pv6_block = ""
        if ipv6:
            pv6_block = f'Set-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ServerAddresses ("{ipv6[0]}","{ipv6[1] if len(ipv6)>1 else ipv6[0]}")'
        script = f'''
$adapters = Get-NetAdapter | Where-Object {{$_.Status -eq "Up"}}
foreach ($a in $adapters) {{
    Set-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ServerAddresses ("{primary}","{secondary}")
}}
ipconfig /flushdns
Write-Host "[OK] DNS set to {provider} ({primary} / {secondary})"
'''
    return run_ps(script, cb)


# ─────────────────────────── WINDOWS UPDATES ────────────────────────
def set_updates_default(cb=None):
    """WinUtil: Invoke-WPFUpdatesdefault — removes all custom update policy keys"""
    if cb: cb("[INFO] Restoring Windows Update to defaults (WinUtil-verified)...")
    script = r'''
# WinUtil Invoke-WPFUpdatesdefault: remove all custom policy keys and restore services
$ErrorActionPreference = 'SilentlyContinue'
$registryPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"
$AUregistryPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"
If (Test-Path $registryPath) {
    Remove-ItemProperty -Path $registryPath -Name "ExcludeWUDriversInQualityUpdate" -EA SilentlyContinue
    Remove-ItemProperty -Path $registryPath -Name "DisableWindowsUpdateAccess"      -EA SilentlyContinue
}
If (Test-Path $AUregistryPath) {
    Remove-ItemProperty -Path $AUregistryPath -Name "NoAutoUpdate"      -EA SilentlyContinue
    Remove-ItemProperty -Path $AUregistryPath -Name "AUOptions"         -EA SilentlyContinue
    Remove-ItemProperty -Path $AUregistryPath -Name "NoAutoRebootWithLoggedOnUsers" -EA SilentlyContinue
    Remove-ItemProperty -Path $AUregistryPath -Name "ScheduledInstallDay"  -EA SilentlyContinue
    Remove-ItemProperty -Path $AUregistryPath -Name "ScheduledInstallTime" -EA SilentlyContinue
}
# Also remove DeliveryOptimization override if set by disable
$doPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\DeliveryOptimization\Config"
If (Test-Path $doPath) {
    Remove-ItemProperty -Path $doPath -Name "DODownloadMode" -EA SilentlyContinue
}
# Re-enable services disabled by WPFUpdatesdisable
Set-Service -Name BITS     -StartupType Automatic -EA SilentlyContinue
Set-Service -Name wuauserv -StartupType Automatic -EA SilentlyContinue
Set-Service -Name UsoSvc   -StartupType Automatic -EA SilentlyContinue
# Re-enable update scheduled tasks
$Tasks = '\Microsoft\Windows\InstallService\*','\Microsoft\Windows\UpdateOrchestrator\*','\Microsoft\Windows\UpdateAssistant\*','\Microsoft\Windows\WaaSMedic\*','\Microsoft\Windows\WindowsUpdate\*','\Microsoft\WindowsUpdate\*'
foreach ($Task in $Tasks) {
    Get-ScheduledTask -TaskPath $Task -EA SilentlyContinue | Enable-ScheduledTask -EA SilentlyContinue
}
Write-Host "[OK] Windows Update restored to defaults"
'''
    return run_ps(script, cb)

def set_updates_security_only(cb=None):
    """WinUtil: Invoke-WPFUpdatessecurity — defer feature updates 365 days, quality 0 days"""
    if cb: cb("[INFO] Setting Windows Update to security only (WinUtil-verified)...")
    script = r'''
$ErrorActionPreference = 'SilentlyContinue'
$registryPath    = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"
$AUregistryPath  = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"
If (!(Test-Path $registryPath)) { New-Item -Path $registryPath -Force | Out-Null }
If (!(Test-Path $AUregistryPath)) { New-Item -Path $AUregistryPath -Force | Out-Null }
# Defer feature updates by 365 days, quality updates by 0
Set-ItemProperty $registryPath -Name "DeferQualityUpdates"             -Value 1 -Type DWord -Force
Set-ItemProperty $registryPath -Name "DeferQualityUpdatesPeriodInDays" -Value 0 -Type DWord -Force
Set-ItemProperty $registryPath -Name "DeferFeatureUpdates"             -Value 1 -Type DWord -Force
Set-ItemProperty $registryPath -Name "DeferFeatureUpdatesPeriodInDays" -Value 365 -Type DWord -Force
Set-ItemProperty $registryPath -Name "ExcludeWUDriversInQualityUpdate" -Value 1 -Type DWord -Force
Set-ItemProperty $AUregistryPath -Name "NoAutoUpdate" -Value 0 -Type DWord -Force
Set-ItemProperty $AUregistryPath -Name "AUOptions"    -Value 3 -Type DWord -Force
Write-Host "[OK] Windows Update set to Security Only (feature updates deferred 365 days)"
'''
    return run_ps(script, cb)

def set_updates_disable(cb=None):
    """WinUtil: Invoke-WPFUpdatesdisable — disables BITS/wuauserv/UsoSvc, clears SoftwareDistribution, disables tasks"""
    if cb: cb("[INFO] Disabling Windows Update (WinUtil-verified)...")
    script = r'''
$ErrorActionPreference = 'SilentlyContinue'
# Registry
New-Item -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" -Force | Out-Null
Set-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" -Name "NoAutoUpdate" -Type DWord -Value 1 -Force
Set-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" -Name "AUOptions"    -Type DWord -Value 1 -Force
New-Item -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\DeliveryOptimization\Config" -Force | Out-Null
Set-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\DeliveryOptimization\Config" -Name "DODownloadMode" -Type DWord -Value 0 -Force
# Disable services
Set-Service -Name BITS     -StartupType Disabled
Set-Service -Name wuauserv -StartupType Disabled
Set-Service -Name UsoSvc   -StartupType Disabled
# Clear SoftwareDistribution cache
Remove-Item "C:\Windows\SoftwareDistribution\*" -Recurse -Force -EA SilentlyContinue
Write-Host "[INFO] Cleared SoftwareDistribution folder"
# Disable update scheduled tasks
$Tasks = '\Microsoft\Windows\InstallService\*','\Microsoft\Windows\UpdateOrchestrator\*','\Microsoft\Windows\UpdateAssistant\*','\Microsoft\Windows\WaaSMedic\*','\Microsoft\Windows\WindowsUpdate\*','\Microsoft\WindowsUpdate\*'
foreach ($Task in $Tasks) {
    Get-ScheduledTask -TaskPath $Task -EA SilentlyContinue | Disable-ScheduledTask -EA SilentlyContinue
}
Write-Host "[OK] Windows Update disabled (services + registry + tasks)"
Write-Host "[WARN] Reboot recommended for all changes to take effect"
'''
    return run_ps(script, cb)


# ─────────────────────────── REGISTRY HEALTH ────────────────────────
def scan_broken_uninstall(cb=None):
    if cb: cb("[INFO] Scanning for broken uninstall entries...")
    script = r'''
$paths = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
)
$broken = @()
foreach ($base in $paths) {
    if(!(Test-Path $base)){continue}
    Get-ChildItem $base -EA SilentlyContinue | ForEach-Object {
        $props = Get-ItemProperty $_.PSPath -EA SilentlyContinue
        $unst  = $props.UninstallString
        $name  = $props.DisplayName
        if ($name -and $unst) {
            if ($unst -match '^"?([A-Za-z]:[^"]+\.exe)"?') {
                $exe = $Matches[1]
                if (!(Test-Path $exe)) {
                    $broken += "$name | $exe"
                    Write-Host "[BROKEN] $name"
                }
            }
        }
    }
}
if($broken.Count -eq 0){Write-Host "[OK] No broken uninstall entries found"}
else{Write-Host "[WARN] Found $($broken.Count) broken entries — run clean to remove"}
'''
    return run_ps(script, cb)

def clean_broken_uninstall(cb=None):
    if cb: cb("[INFO] Cleaning broken uninstall entries (backing up first)...")
    script = r'''
$backup = "$env:USERPROFILE\Desktop\WinForge_Registry_Backup_$(Get-Date -f 'yyyyMMdd_HHmmss').reg"
reg export "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall" $backup /y | Out-Null
Write-Host "[INFO] Backup saved to $backup"
$paths = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
)
$removed = 0
foreach ($base in $paths) {
    if(!(Test-Path $base)){continue}
    Get-ChildItem $base -EA SilentlyContinue | ForEach-Object {
        $props = Get-ItemProperty $_.PSPath -EA SilentlyContinue
        $unst  = $props.UninstallString
        $name  = $props.DisplayName
        if ($name -and $unst) {
            if ($unst -match '^"?([A-Za-z]:[^"]+\.exe)"?') {
                if (!(Test-Path $Matches[1])) {
                    Remove-Item $_.PSPath -Recurse -Force -EA SilentlyContinue
                    $removed++
                    Write-Host "[OK] Removed: $name"
                }
            }
        }
    }
}
Write-Host "[OK] Cleaned $removed broken uninstall entries"
'''
    return run_ps(script, cb)


# ─────────────────────────── RESTORE POINTS ─────────────────────────
def create_restore_point(description: str = "WinForge Manual Restore Point", cb=None):
    if cb: cb(f"[INFO] Creating restore point: {description}...")
    script = f'''
Enable-ComputerRestore -Drive "C:\\" -EA SilentlyContinue
# Bypass 24h limit
$key = "HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SystemRestore"
Set-ItemProperty $key -Name SystemRestorePointCreationFrequency -Value 0 -Type DWord -Force -EA SilentlyContinue
Checkpoint-Computer -Description "{description}" -RestorePointType MODIFY_SETTINGS -EA Stop
Write-Host "[OK] Restore point created: {description}"
'''
    return run_ps(script, cb)

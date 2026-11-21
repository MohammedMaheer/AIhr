[CmdletBinding()]
param([switch]$RevokedInSmartHR)

$ErrorActionPreference = 'Stop'
if (-not $RevokedInSmartHR) { throw 'Revoke this worker in SmartHR before removing its local credentials.' }
$name = 'SmartHRManagedDesktop-' + [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $name
    Unregister-ScheduledTask -TaskName $name -Confirm:$false
}
$base = [IO.Path]::GetFullPath([Environment]::GetFolderPath('LocalApplicationData'))
$path = Join-Path $base 'SmartHRManagedDesktop'
if (Test-Path -LiteralPath $path) {
    $item = Get-Item -LiteralPath $path -Force
    if ($item.FullName -ne $path -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Unexpected worker directory; remove it through your company device administrator.'
    }
    $entries = @(Get-ChildItem -LiteralPath $path -Recurse -Force)
    foreach ($entry in $entries) {
        if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            -not $entry.FullName.StartsWith($path + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Unexpected entry inside the worker directory; remove it through your company device administrator.'
        }
    }
    Remove-Item -LiteralPath $path -Recurse -Force
}
Write-Output 'SmartHR worker removed from this account.'

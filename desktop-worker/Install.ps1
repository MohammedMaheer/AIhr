[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][uri]$Origin,
    [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'The managed installer requires Windows.' }
if ($Origin.Scheme -ne 'https' -or $Origin.UserInfo -or $Origin.Query -or $Origin.Fragment -or $Origin.AbsolutePath -ne '/') {
    throw 'Enter an HTTPS SmartHR origin without a path, query, or credentials.'
}
$node = (Get-Command node.exe -CommandType Application -TotalCount 1).Source
if ([int]((& $node --version).TrimStart('v').Split('.')[0]) -lt 22) { throw 'Node.js 22 or later is required.' }
$npm = (Get-Command npm.cmd -CommandType Application -TotalCount 1).Source
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$name = 'SmartHRManagedDesktop-' + $identity.User.Value
$target = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'SmartHRManagedDesktop'
$files = @('agent.mjs','minilm.mjs','model.mjs','package.json','package-lock.json','Run.ps1','Uninstall.ps1')
foreach ($file in $files) {
    if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot $file) -PathType Leaf)) { throw "Incomplete worker bundle: $file" }
}
if ($ValidateOnly) { Write-Output 'Worker installer prerequisites and bundle passed.'; return }
if (Test-Path -LiteralPath $target) { throw 'An installation exists. Revoke the old worker and uninstall it before reinstalling.' }
$null = New-Item -ItemType Directory -Path $target
$acl = New-Object Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true, $false)
$acl.SetOwner($identity.User)
$system = New-Object Security.Principal.SecurityIdentifier 'S-1-5-18'
foreach ($sid in @($identity.User, $system)) {
    $rule = [Security.AccessControl.FileSystemAccessRule]::new($sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $acl.AddAccessRule($rule)
}
Set-Acl -LiteralPath $target -AclObject $acl
foreach ($file in $files) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination $target }

Push-Location -LiteralPath $target
try {
    & $npm ci --ignore-scripts --omit=dev
    if ($LASTEXITCODE -ne 0) { throw 'Unable to install pinned worker dependencies.' }
    & $node agent.mjs prepare
    if ($LASTEXITCODE -ne 0) { throw 'Unable to verify the pinned model.' }
    $secure = Read-Host 'One-time SmartHR enrollment code' -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $setup = @{origin=$Origin.GetLeftPart([UriPartial]::Authority);name=$env:COMPUTERNAME;
                   enrollmentCode=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)} | ConvertTo-Json -Compress
        $details = $setup | & $node agent.mjs enroll
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        $setup = $null
        $secure.Dispose()
    }
    if ($LASTEXITCODE -ne 0 -or -not $details) { throw 'Worker enrollment failed. No task was installed.' }
    $details | ConvertTo-SecureString -AsPlainText -Force | ConvertFrom-SecureString |
        Set-Content -LiteralPath (Join-Path $target 'identity.dpapi') -Encoding ASCII
    $details = $null
    Set-Content -LiteralPath (Join-Path $target 'node.path') -Value $node -Encoding UTF8
    $systemPowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $action = New-ScheduledTaskAction -Execute $systemPowerShell -WorkingDirectory $target `
        -Argument ('-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -File "' + (Join-Path $target 'Run.ps1') + '"')
    $principal = New-ScheduledTaskPrincipal -UserId $identity.Name -LogonType Interactive -RunLevel Limited
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity.Name
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable `
        -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5) -ExecutionTimeLimit ([timespan]::Zero)
    $null = Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Principal $principal -Settings $settings
    Start-ScheduledTask -TaskName $name
    Write-Output 'SmartHR managed desktop worker installed for this account.'
} finally { Pop-Location }

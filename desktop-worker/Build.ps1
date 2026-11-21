[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$OutputDirectory)

$ErrorActionPreference = 'Stop'
$output = [IO.Path]::GetFullPath($OutputDirectory)
$null = New-Item -ItemType Directory -Path $output -Force
$bundle = Join-Path $output 'SmartHRManagedDesktop.zip'
if (Test-Path -LiteralPath $bundle) { throw 'Choose a new output directory for this bundle.' }
$names = @('Install.ps1','Run.ps1','Uninstall.ps1','agent.mjs','minilm.mjs','model.mjs','package.json','package-lock.json')
$paths = @($names | ForEach-Object { Join-Path $PSScriptRoot $_ })
Compress-Archive -LiteralPath $paths -DestinationPath $bundle -CompressionLevel Optimal
Get-FileHash -LiteralPath $bundle -Algorithm SHA256

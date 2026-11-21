$ErrorActionPreference = 'Stop'
$node = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'node.path') -Raw).Trim()
$secret = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'identity.dpapi') -Raw | ConvertTo-SecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
    [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) | & $node (Join-Path $PSScriptRoot 'agent.mjs') run
    exit $LASTEXITCODE
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    $secret.Dispose()
}

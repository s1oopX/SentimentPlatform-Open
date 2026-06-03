[CmdletBinding(SupportsShouldProcess = $true)]
param()

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Remove-IfExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LiteralPath
    )

    if (-not (Test-Path -LiteralPath $LiteralPath)) {
        return
    }

    if ($PSCmdlet.ShouldProcess($LiteralPath, 'Remove frontend local state')) {
        Remove-Item -LiteralPath $LiteralPath -Recurse -Force
    }
}

$directTargets = @(
    (Join-Path $repoRoot '.idea'),
    (Join-Path $repoRoot 'dist'),
    (Join-Path $repoRoot 'logs'),
    (Join-Path $repoRoot 'node_modules'),
    (Join-Path $repoRoot 'coverage')
)

foreach ($target in $directTargets) {
    Remove-IfExists -LiteralPath $target
}

$vscodePath = Join-Path $repoRoot '.vscode'
if (Test-Path -LiteralPath $vscodePath) {
    Get-ChildItem -LiteralPath $vscodePath -Force | Where-Object {
        $_.Name -ne 'extensions.json'
    } | ForEach-Object {
        Remove-IfExists -LiteralPath $_.FullName
    }
}

Get-ChildItem -LiteralPath $repoRoot -Filter '*.timestamp-*-*.mjs' -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-IfExists -LiteralPath $_.FullName
}

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$IncludeRuntimeOutputs
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Remove-IfExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LiteralPath,
        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    if (-not (Test-Path -LiteralPath $LiteralPath)) {
        return
    }

    if ($PSCmdlet.ShouldProcess($LiteralPath, "Remove $Description")) {
        Remove-Item -LiteralPath $LiteralPath -Recurse -Force
    }
}

function Remove-ChildItems {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LiteralPath,
        [string[]]$Exclude = @()
    )

    if (-not (Test-Path -LiteralPath $LiteralPath)) {
        return
    }

    Get-ChildItem -LiteralPath $LiteralPath -Force | Where-Object {
        $Exclude -notcontains $_.Name
    } | ForEach-Object {
        $target = $_.FullName
        if ($PSCmdlet.ShouldProcess($target, 'Remove runtime output item')) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
    }
}

$cacheTargets = @(
    @{ Path = (Join-Path $repoRoot '__pycache__'); Description = 'Python cache directory' },
    @{ Path = (Join-Path $repoRoot '.pytest_cache'); Description = 'pytest cache directory' },
    @{ Path = (Join-Path $repoRoot '.pytest_cache_compat'); Description = 'pytest compatibility cache directory' },
    @{ Path = (Join-Path $repoRoot '.pytest_tmp'); Description = 'pytest temporary directory' },
    @{ Path = (Join-Path $repoRoot '.pytest_tmp_compat'); Description = 'pytest compatibility temporary directory' },
    @{ Path = (Join-Path $repoRoot 'sentiment_platform_server.egg-info'); Description = 'package metadata directory' },
    @{ Path = (Join-Path $repoRoot '.pytest-first-fail.out'); Description = 'pytest temporary output' },
    @{ Path = (Join-Path $repoRoot '.pytest-review.out'); Description = 'pytest temporary output' }
)

foreach ($target in $cacheTargets) {
    Remove-IfExists -LiteralPath $target.Path -Description $target.Description
}

Get-ChildItem -LiteralPath $repoRoot -Force -Directory -Recurse -Filter '__pycache__' -ErrorAction SilentlyContinue |
    Where-Object { -not $_.FullName.StartsWith((Join-Path $repoRoot '.venv'), [System.StringComparison]::OrdinalIgnoreCase) } |
    ForEach-Object {
        Remove-IfExists -LiteralPath $_.FullName -Description 'Python cache directory'
    }

Get-ChildItem -LiteralPath $repoRoot -Force -Directory -Filter 'pytest-cache-files-*' -ErrorAction SilentlyContinue |
    ForEach-Object {
        Remove-IfExists -LiteralPath $_.FullName -Description 'pytest temporary cache directory'
    }

Get-ChildItem -LiteralPath $repoRoot -Force -File -Filter 'celerybeat-schedule*' -ErrorAction SilentlyContinue |
    ForEach-Object {
        Remove-IfExists -LiteralPath $_.FullName -Description 'Celery Beat runtime schedule file'
    }

if ($IncludeRuntimeOutputs) {
    Remove-ChildItems -LiteralPath (Join-Path $repoRoot 'generated_reports')
    Remove-ChildItems -LiteralPath (Join-Path $repoRoot 'logs')
    Remove-ChildItems -LiteralPath (Join-Path $repoRoot 'media')
    Remove-ChildItems -LiteralPath (Join-Path $repoRoot 'staticfiles')
    Remove-ChildItems -LiteralPath (Join-Path $repoRoot 'backups')
    Remove-ChildItems -LiteralPath (Join-Path $repoRoot 'exports')
    # Preserve the legacy JSON import source only; runtime system config now lives in MySQL.
    Remove-ChildItems -LiteralPath (Join-Path $repoRoot 'uploads') -Exclude @('system_config.json')
}

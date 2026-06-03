#Requires -Version 7.0

[CmdletBinding()]
param(
    [string]$HostAddress = '127.0.0.1',
    [ValidateRange(1, 65535)]
    [int]$BackendPort = 8000,
    [ValidateRange(1, 65535)]
    [int]$FrontendPort = 5173,
    [ValidateSet('backend', 'celery-default', 'celery-training', 'celery-beat', 'frontend')]
    [string[]]$Services = @('backend', 'celery-default', 'celery-training', 'celery-beat', 'frontend'),
    [switch]$CleanLogs
)

$ErrorActionPreference = 'Stop'

$workspaceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $workspaceRoot 'dev-services.ps1')

$stateRoot = Get-DevStateRoot
$stateFile = Get-DevStateFile
$state = Read-DevState

if ($state.ContainsKey('host')) {
    $HostAddress = [string]$state.host
}
if ($state.ContainsKey('backend_port')) {
    $BackendPort = [int]$state.backend_port
}
if ($state.ContainsKey('frontend_port')) {
    $FrontendPort = [int]$state.frontend_port
}

$serviceDefinitions = New-DevServiceDefinitions `
    -WorkspaceRoot $workspaceRoot `
    -HostAddress $HostAddress `
    -BackendPort $BackendPort `
    -FrontendPort $FrontendPort |
    Where-Object { $Services -contains $_.Name }

if ($serviceDefinitions.Count -eq 0) {
    throw 'No services selected.'
}

function Remove-StateRootWithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LiteralPath,
        [int]$Attempts = 10
    )

    $lastError = $null
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            if (-not (Test-Path -LiteralPath $LiteralPath)) {
                return $true
            }

            Remove-Item -LiteralPath $LiteralPath -Recurse -Force -ErrorAction Stop
            return $true
        } catch {
            $lastError = $_
            Start-Sleep -Milliseconds 500
        }
    }

    Write-Warning "Could not remove log directory '$LiteralPath': $($lastError.Exception.Message)"
    return $false
}

$stoppedPids = New-Object System.Collections.Generic.HashSet[int]
$protectedPids = New-Object System.Collections.Generic.HashSet[int]
$stoppedServices = @()

if ($state.ContainsKey('services')) {
    foreach ($definition in $serviceDefinitions) {
        if (-not $state.services.ContainsKey($definition.Name)) {
            continue
        }

        $serviceState = $state.services[$definition.Name]
        if ($serviceState.ContainsKey('reused') -and [bool]$serviceState.reused) {
            [void]$protectedPids.Add([int]$serviceState.pid)
        }
    }

    foreach ($definition in $serviceDefinitions) {
        if (-not $state.services.ContainsKey($definition.Name)) {
            continue
        }

        $processId = [int]$state.services[$definition.Name].pid
        if ($protectedPids.Contains($processId)) {
            continue
        }

        $process = Get-DevProcessById -ProcessId $processId
        if ($null -ne $process -and -not (Test-ProcessMatchesDefinition -Process $process -Definition $definition)) {
            Write-Warning "Ignoring stale state for service '$($definition.Name)': PID $processId no longer matches this service."
            continue
        }

        if ($stoppedPids.Add($processId)) {
            if (Stop-ProcessTreeByPid -ProcessId $processId) {
                $stoppedServices += $definition.Name
            }
        }
    }
}

foreach ($definition in $serviceDefinitions) {
    $matchedProcs = Get-ProcessesForDefinition -Definition $definition
    foreach ($match in $matchedProcs) {
        $processId = [int]$match.ProcessId
        if ($protectedPids.Contains($processId)) {
            continue
        }

        if (-not $stoppedPids.Add($processId)) {
            continue
        }
        if (Stop-ProcessTreeByPid -ProcessId $processId) {
            $stoppedServices += $definition.Name
        }
    }
}

if (Test-Path -LiteralPath $stateFile) {
    Remove-Item -LiteralPath $stateFile -Force
}

$logsRemoved = $false
if ($CleanLogs -and (Test-Path -LiteralPath $stateRoot)) {
    $logsRemoved = Remove-StateRootWithRetry -LiteralPath $stateRoot
} else {
    $logsRemoved = -not (Test-Path -LiteralPath $stateRoot)
}

Write-Host ''
Write-Host 'All services stopped.' -ForegroundColor Green
if (-not $CleanLogs -and (Test-Path -LiteralPath $stateRoot)) {
    Write-Host "  Logs retained: $stateRoot"
}
Write-Host ''

[pscustomobject]@{
    state_file_removed = -not (Test-Path -LiteralPath $stateFile)
    logs_removed = $logsRemoved
    stopped = @($stoppedServices | Select-Object -Unique)
} | ConvertTo-Json -Depth 4

#Requires -Version 7.0

[CmdletBinding()]
param(
    [string]$HostAddress = '127.0.0.1',
    [ValidateRange(1, 65535)]
    [int]$BackendPort = 8000,
    [ValidateRange(1, 65535)]
    [int]$FrontendPort = 5173,
    [ValidateSet('backend', 'celery-default', 'celery-training', 'celery-beat', 'frontend')]
    [string[]]$Services = @('backend', 'celery-default', 'celery-training', 'celery-beat', 'frontend')
)

$ErrorActionPreference = 'Stop'

$workspaceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $workspaceRoot 'dev-services.ps1')

$backendRoot = Join-Path $workspaceRoot 'sentiment_server'
$frontendRoot = Join-Path $workspaceRoot 'sentiment_webapp'
$stateRoot = Get-DevStateRoot
$stateFile = Get-DevStateFile
$backendPython = Join-Path $backendRoot '.venv\Scripts\python.exe'
$npmCmd = 'npm.cmd'

if (-not (Test-Path -LiteralPath $backendPython)) {
    throw "Backend Python not found: $backendPython"
}

$npm = Get-Command $npmCmd -ErrorAction SilentlyContinue
if ($null -eq $npm) {
    throw 'npm.cmd was not found in PATH.'
}

$envFile = Join-Path $backendRoot '.env'
if (-not (Test-Path -LiteralPath $envFile)) {
    Write-Warning "No .env file found at $envFile. Copy .env.example and configure it."
}

function Read-DotEnvFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LiteralPath
    )

    $values = @{}
    if (-not (Test-Path -LiteralPath $LiteralPath)) {
        return $values
    }

    foreach ($line in Get-Content -LiteralPath $LiteralPath -ErrorAction SilentlyContinue) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) {
            continue
        }
        $eq = $trimmed.IndexOf('=')
        if ($eq -le 0) {
            continue
        }
        $key = $trimmed.Substring(0, $eq).Trim()
        $value = $trimmed.Substring($eq + 1).Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $values[$key] = $value
    }

    return $values
}

function Test-DependencyEndpoint {
    param(
        [Parameter(Mandatory = $true)]
        [string]$EndpointHost,
        [Parameter(Mandatory = $true)]
        [int]$Port,
        [int]$TimeoutMs = 1500
    )

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $async = $client.BeginConnect($EndpointHost, $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne($TimeoutMs, $false)) {
            return $false
        }
        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Assert-RequiredDependencies {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$SelectedServices,
        [Parameter(Mandatory = $true)]
        [hashtable]$EnvValues
    )

    $needsMySql = $SelectedServices -contains 'backend'
    $needsRedis = ($SelectedServices | Where-Object { $_ -like 'celery-*' }).Count -gt 0

    $checks = @()
    if ($needsMySql) {
        $dbHost = $EnvValues['DB_HOST']
        if ([string]::IsNullOrWhiteSpace($dbHost)) { $dbHost = '127.0.0.1' }
        $dbPort = 3306
        if (-not [string]::IsNullOrWhiteSpace($EnvValues['DB_PORT'])) {
            [int]::TryParse($EnvValues['DB_PORT'], [ref]$dbPort) | Out-Null
        }
        $checks += @{
            Label = 'MySQL'
            EnvHint = 'DB_HOST/DB_PORT'
            EndpointHost = $dbHost
            Port = $dbPort
            ServiceHint = 'backend'
        }
    }
    if ($needsRedis) {
        $redisHost = $EnvValues['REDIS_HOST']
        if ([string]::IsNullOrWhiteSpace($redisHost)) { $redisHost = 'localhost' }
        $redisPort = 6379
        if (-not [string]::IsNullOrWhiteSpace($EnvValues['REDIS_PORT'])) {
            [int]::TryParse($EnvValues['REDIS_PORT'], [ref]$redisPort) | Out-Null
        }
        $checks += @{
            Label = 'Redis'
            EnvHint = 'REDIS_HOST/REDIS_PORT'
            EndpointHost = $redisHost
            Port = $redisPort
            ServiceHint = 'celery-*'
        }
    }

    foreach ($check in $checks) {
        $endpoint = "$($check.EndpointHost):$($check.Port)"
        if (-not (Test-DependencyEndpoint -EndpointHost $check.EndpointHost -Port $check.Port)) {
            throw ("$($check.Label) is not reachable at $endpoint (resolved from $($check.EnvHint) in .env). " +
                   "Start $($check.Label) before running start-dev.ps1, or skip dependent services with " +
                   "-Services excluding '$($check.ServiceHint)'.")
        }
    }
}

function Assert-RequiredEnvKeys {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$SelectedServices,
        [Parameter(Mandatory = $true)]
        [hashtable]$EnvValues,
        [Parameter(Mandatory = $true)]
        [string]$EnvFilePath
    )

    # SECRET_KEY and JWT_SIGNING_KEY are marked required=True in
    # sentiment_server/settings/base.py — Django will refuse to load when
    # either is empty. That kills both `manage.py runserver` and every
    # `celery -A sentiment_server` invocation. Detect the misconfiguration
    # here so the failure mode is a clear error instead of "All services
    # started" followed by silent crash loops.
    $needsDjango = ($SelectedServices -contains 'backend') -or
                   (($SelectedServices | Where-Object { $_ -like 'celery-*' }).Count -gt 0)
    if (-not $needsDjango) {
        return
    }

    $required = @('SECRET_KEY', 'JWT_SIGNING_KEY')
    $missing = @()
    foreach ($key in $required) {
        if ([string]::IsNullOrWhiteSpace($EnvValues[$key])) {
            $missing += $key
        }
    }

    if ($missing.Count -gt 0) {
        $joined = $missing -join ', '
        throw ("Required env keys are missing or empty in ${EnvFilePath}: $joined. " +
               "Generate values with " +
               '`.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` ' +
               "and paste them into .env before starting backend or celery services.")
    }
}

$envValues = Read-DotEnvFile -LiteralPath $envFile
Assert-RequiredEnvKeys -SelectedServices $Services -EnvValues $envValues -EnvFilePath $envFile
Assert-RequiredDependencies -SelectedServices $Services -EnvValues $envValues

New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null

$serviceDefinitions = New-DevServiceDefinitions `
    -WorkspaceRoot $workspaceRoot `
    -HostAddress $HostAddress `
    -BackendPort $BackendPort `
    -FrontendPort $FrontendPort `
    -NpmPath $npm.Source |
    Where-Object { $Services -contains $_.Name }

if ($serviceDefinitions.Count -eq 0) {
    throw 'No services selected.'
}

function Assert-ServiceCanStart {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Definition,
        [hashtable]$State
    )

    $managedPid = $null
    if ($State.ContainsKey('services') -and $State.services.ContainsKey($Definition.Name)) {
        $managedPid = $State.services[$Definition.Name].pid
    }

    if ($managedPid) {
        $managedProcess = Get-DevProcessById -ProcessId ([int]$managedPid)
        if ($null -ne $managedProcess) {
            if (Test-ProcessMatchesDefinition -Process $managedProcess -Definition $Definition) {
                return
            }

            Write-Warning "Ignoring stale state for service '$($Definition.Name)': PID $managedPid no longer matches this service."
            $State.services.Remove($Definition.Name)
        }
    }

    $matchingProcesses = Get-ProcessesForDefinition -Definition $Definition
    if ($matchingProcesses.Count -gt 0) {
        throw "Service '$($Definition.Name)' appears to be running outside start-dev.ps1. Stop it first."
    }

    if ($Definition.Port -and (Test-PortListening -Port $Definition.Port)) {
        throw "Port $($Definition.Port) is already in use by another process."
    }
}

function Invoke-FrontendWarmup {
    param(
        [string]$HostAddress,
        [int]$FrontendPort,
        [string[]]$SelectedServices
    )

    if ($SelectedServices -notcontains 'frontend') {
        return
    }

    $frontendUrl = "http://$HostAddress`:$FrontendPort/"
    try {
        Invoke-WebRequest -Uri $frontendUrl -UseBasicParsing -TimeoutSec 15 | Out-Null
        Start-Sleep -Seconds 2
    } catch {
        Write-Warning "Frontend warmup request failed for ${frontendUrl}: $($_.Exception.Message)"
    }
}

$state = Read-DevState
if (-not $state.ContainsKey('services')) {
    $state.services = @{}
}

$startedServices = @()
$reusedServices = @()
$startedPids = @()

try {
    foreach ($definition in $serviceDefinitions) {
        Assert-ServiceCanStart -Definition $definition -State $state

        $existing = Get-ProcessesForDefinition -Definition $definition
        if ($existing.Count -gt 0) {
            $process = $existing | Select-Object -First 1
            $state.services[$definition.Name] = @{
                pid = [int]$process.ProcessId
                reused = $true
                out_log = $definition.OutLog
                err_log = $definition.ErrLog
                port = $definition.Port
                working_directory = $definition.WorkingDirectory
            }
            $reusedServices += $definition.Name
            continue
        }

        $process = Start-Process -FilePath 'cmd.exe' `
            -ArgumentList @('/c', $definition.Command) `
            -WorkingDirectory $definition.WorkingDirectory `
            -RedirectStandardOutput $definition.OutLog `
            -RedirectStandardError $definition.ErrLog `
            -PassThru `
            -WindowStyle Hidden

        $startedPids += [int]$process.Id
        Start-Sleep -Seconds 2

        if ($process.HasExited) {
            throw "Service '$($definition.Name)' exited immediately. Check $($definition.ErrLog)"
        }

        if ($definition.Port) {
            Wait-PortListening -Port $definition.Port
        }

        $managedProcess = Get-ProcessesForDefinition -Definition $definition |
            Where-Object { [int]$_.ProcessId -ne [int]$process.Id } |
            Select-Object -First 1
        if ($null -eq $managedProcess) {
            $managedPid = [int]$process.Id
        } else {
            $managedPid = [int]$managedProcess.ProcessId
        }
        $startedPids += $managedPid

        $state.services[$definition.Name] = @{
            pid = $managedPid
            reused = $false
            out_log = $definition.OutLog
            err_log = $definition.ErrLog
            port = $definition.Port
            working_directory = $definition.WorkingDirectory
        }
        $startedServices += $definition.Name
    }
} catch {
    foreach ($startedPid in @($startedPids | Select-Object -Unique)) {
        Stop-ProcessTreeByPid -ProcessId $startedPid | Out-Null
    }

    throw
}

$state.workspace_root = $workspaceRoot
$state.state_root = $stateRoot
$state.started_at = (Get-Date).ToString('o')
$state.host = $HostAddress
$state.backend_port = $BackendPort
$state.frontend_port = $FrontendPort

Write-DevState -State $state
Invoke-FrontendWarmup -HostAddress $HostAddress -FrontendPort $FrontendPort -SelectedServices $Services

Write-Host ''
Write-Host 'All services started.' -ForegroundColor Green
Write-Host "  Backend:  http://$HostAddress`:$BackendPort/"
Write-Host "  Frontend: http://$HostAddress`:$FrontendPort/"
Write-Host "  API:      http://$HostAddress`:$BackendPort/api/"
Write-Host "  State:    $stateFile"
Write-Host ''

[pscustomobject]@{
    state_file = $stateFile
    state_root = $stateRoot
    started = $startedServices
    reused = $reusedServices
    backend_url = "http://$HostAddress`:$BackendPort/"
    frontend_url = "http://$HostAddress`:$FrontendPort/"
} | ConvertTo-Json -Depth 6

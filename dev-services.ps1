#Requires -Version 7.0

function Get-DevStateRoot {
    Join-Path $env:TEMP 'sentiment-platform-dev'
}

function Get-DevStateFile {
    Join-Path (Get-DevStateRoot) 'state.json'
}

function Read-DevState {
    $stateFile = Get-DevStateFile
    if (-not (Test-Path -LiteralPath $stateFile)) {
        return @{}
    }

    try {
        return Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json -AsHashtable
    } catch {
        return @{}
    }
}

function Write-DevState {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$State
    )

    $stateRoot = Get-DevStateRoot
    New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null
    ($State | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath (Get-DevStateFile) -Encoding UTF8
}

function New-DevServiceDefinitions {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkspaceRoot,
        [string]$HostAddress = '127.0.0.1',
        [ValidateRange(1, 65535)]
        [int]$BackendPort = 8000,
        [ValidateRange(1, 65535)]
        [int]$FrontendPort = 5173,
        [string]$NpmPath = 'npm.cmd'
    )

    $backendRoot = Join-Path $WorkspaceRoot 'sentiment_server'
    $frontendRoot = Join-Path $WorkspaceRoot 'sentiment_webapp'
    $stateRoot = Get-DevStateRoot
    $backendPython = Join-Path $backendRoot '.venv\Scripts\python.exe'
    $frontendArgs = "--host $HostAddress --port $FrontendPort"

    $defaultWorkerQueue = 'celery'
    # Default worker handles: reports, operation log cleanup, verification code cleanup
    $defaultWorkerMatcher = "-m celery -A sentiment_server worker -Q $defaultWorkerQueue -l info -P solo"
    # Training worker handles: model training tasks (transformer, classical, neural)
    $trainingWorkerMatcher = '-m celery -A sentiment_server worker -Q training -l info -P solo -n training@%h'
    $beatMatcher = '-m celery -A sentiment_server beat -l info'

    return @(
        @{
            Name = 'backend'
            Port = $BackendPort
            Matchers = @(
                "manage.py runserver $HostAddress`:$BackendPort --noreload",
                [Regex]::Escape($backendRoot)
            )
            OutLog = Join-Path $stateRoot "backend-$BackendPort.out.log"
            ErrLog = Join-Path $stateRoot "backend-$BackendPort.err.log"
            WorkingDirectory = $backendRoot
            Command = "set DJANGO_SETTINGS_MODULE=sentiment_server.settings.local && `"$backendPython`" manage.py runserver $HostAddress`:$BackendPort --noreload"
        }
        @{
            Name = 'celery-default'
            Port = $null
            Matchers = @(
                $defaultWorkerMatcher,
                [Regex]::Escape($backendRoot)
            )
            OutLog = Join-Path $stateRoot 'celery-default.out.log'
            ErrLog = Join-Path $stateRoot 'celery-default.err.log'
            WorkingDirectory = $backendRoot
            Command = "set DJANGO_SETTINGS_MODULE=sentiment_server.settings.local && `"$backendPython`" $defaultWorkerMatcher"
        }
        @{
            Name = 'celery-training'
            Port = $null
            Matchers = @(
                $trainingWorkerMatcher,
                [Regex]::Escape($backendRoot)
            )
            OutLog = Join-Path $stateRoot 'celery-training.out.log'
            ErrLog = Join-Path $stateRoot 'celery-training.err.log'
            WorkingDirectory = $backendRoot
            Command = "set DJANGO_SETTINGS_MODULE=sentiment_server.settings.local && `"$backendPython`" $trainingWorkerMatcher"
        }
        @{
            Name = 'celery-beat'
            Port = $null
            Matchers = @(
                $beatMatcher,
                [Regex]::Escape($backendRoot)
            )
            OutLog = Join-Path $stateRoot 'celery-beat.out.log'
            ErrLog = Join-Path $stateRoot 'celery-beat.err.log'
            WorkingDirectory = $backendRoot
            Command = "set DJANGO_SETTINGS_MODULE=sentiment_server.settings.local && `"$backendPython`" $beatMatcher"
        }
        @{
            Name = 'frontend'
            Port = $FrontendPort
            Matchers = @(
                'vite',
                [Regex]::Escape($frontendArgs),
                [Regex]::Escape($frontendRoot)
            )
            OutLog = Join-Path $stateRoot "frontend-$FrontendPort.out.log"
            ErrLog = Join-Path $stateRoot "frontend-$FrontendPort.err.log"
            WorkingDirectory = $frontendRoot
            Command = "cd /d `"$frontendRoot`" && `"$NpmPath`" run dev -- $frontendArgs"
        }
    )
}

function Test-ProcessMatchesDefinition {
    param(
        [Parameter(Mandatory = $true)]
        [CimInstance]$Process,
        [Parameter(Mandatory = $true)]
        [hashtable]$Definition
    )

    $commandLine = $Process.CommandLine
    if ([string]::IsNullOrWhiteSpace($commandLine)) {
        return $false
    }

    foreach ($matcher in $Definition.Matchers) {
        if ($commandLine -notmatch $matcher) {
            return $false
        }
    }

    return $true
}

function Get-DevProcessById {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ProcessId
    )

    try {
        Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction Stop
    } catch {
        throw "Unable to inspect process command lines. Run PowerShell as administrator or allow Win32_Process queries. $($_.Exception.Message)"
    }
}

function Get-ProcessesForDefinition {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Definition
    )

    try {
        $processes = Get-CimInstance Win32_Process -ErrorAction Stop
    } catch {
        throw "Unable to inspect process command lines. Run PowerShell as administrator or allow Win32_Process queries. $($_.Exception.Message)"
    }

    return @(
        $processes | Where-Object {
            Test-ProcessMatchesDefinition -Process $_ -Definition $Definition
        }
    )
}

function Test-PortListening {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $asyncResult = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $asyncResult.AsyncWaitHandle.WaitOne(1000, $false)) {
            return $false
        }
        $client.EndConnect($asyncResult)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Wait-PortListening {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortListening -Port $Port) {
            return
        }
        Start-Sleep -Milliseconds 500
    }

    throw "Timed out waiting for port $Port."
}

function Stop-ProcessTreeByPid {
    param(
        [Parameter(Mandatory = $true)]
        [int]$ProcessId,
        [int]$GraceSeconds = 5
    )

    $targetProcess = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($null -eq $targetProcess) {
        return $false
    }

    & cmd.exe /c "taskkill /PID $ProcessId /T >nul 2>nul" | Out-Null
    $deadline = (Get-Date).AddSeconds($GraceSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($null -eq (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) {
            return $true
        }
        Start-Sleep -Milliseconds 250
    }

    & cmd.exe /c "taskkill /PID $ProcessId /T /F >nul 2>nul" | Out-Null
    return $true
}

param(
    [ValidateSet('All', 'CloudDrive2', 'OpenList')]
    [string]$Edition = 'All'
)

$ErrorActionPreference = 'Stop'

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PyInstallerArgs = @(
    '--noconfirm'
    '--clean'
    '--onefile'
    '--windowed'
    '--collect-all', 'paramiko'
)

$BuildTargets = @()
if ($Edition -in @('All', 'CloudDrive2')) {
    $BuildTargets += [PSCustomObject]@{
        Name = 'TG115-CloudDrive2-Deployer'
        Source = 'installer_clouddrive2.py'
        AddData = @('payload_clouddrive2;payload_clouddrive2')
    }
}
if ($Edition -in @('All', 'OpenList')) {
    $BuildTargets += [PSCustomObject]@{
        Name = 'TG115-OpenList-Deployer'
        Source = 'installer_openlist.py'
        AddData = @(
            'payload_clouddrive2;payload_clouddrive2'
            'payload_openlist;payload_openlist'
        )
    }
}

function Get-Tg115IsolatedPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ToolPath
    )

    # PyInstaller resolves binary dependencies through PATH. Third-party tools
    # can expose incompatible DLLs there (for example another ICU build), which
    # are then accidentally bundled and take precedence over Windows system
    # libraries in the generated EXE.
    $entries = @(
        (Split-Path -Parent $ToolPath)
        "$env:SystemRoot\System32"
        $env:SystemRoot
        "$env:SystemRoot\System32\Wbem"
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique

    return $entries -join [System.IO.Path]::PathSeparator
}

function Invoke-Tg115PythonBuild {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExecutable
    )

    $originalPath = $env:Path
    try {
        $env:Path = Get-Tg115IsolatedPath -ToolPath $PythonExecutable
        foreach ($target in $BuildTargets) {
            Write-Host "Building $($target.Name) with PySide6..."
            & $PythonExecutable -c 'from PySide6.QtWidgets import QApplication; assert QApplication'
            if ($LASTEXITCODE -ne 0) {
                throw 'PySide6 GUI 运行时不可用，停止生成无法启动的部署器'
            }
            $targetArgs = @($PyInstallerArgs)
            foreach ($data in $target.AddData) {
                $targetArgs += @('--add-data', $data)
            }
            $targetArgs += @('--name', $target.Name, $target.Source)
            & $PythonExecutable -m PyInstaller @targetArgs
            if ($LASTEXITCODE -ne 0) {
                throw "$($target.Name) 构建失败"
            }
        }
    }
    finally {
        $env:Path = $originalPath
    }
}

function Invoke-Tg115UvBuild {
    param(
        [Parameter(Mandatory = $true)]
        [string]$UvExecutable
    )

    $originalPath = $env:Path
    try {
        $env:Path = Get-Tg115IsolatedPath -ToolPath $UvExecutable
        foreach ($target in $BuildTargets) {
            Write-Host "Building $($target.Name) with PySide6..."
            & $UvExecutable run --with-requirements requirements-build.txt `
                python -c 'from PySide6.QtWidgets import QApplication; assert QApplication'
            if ($LASTEXITCODE -ne 0) {
                throw 'PySide6 GUI 运行时不可用，停止生成无法启动的部署器'
            }
            $targetArgs = @($PyInstallerArgs)
            foreach ($data in $target.AddData) {
                $targetArgs += @('--add-data', $data)
            }
            $targetArgs += @('--name', $target.Name, $target.Source)
            & $UvExecutable run --with-requirements requirements-build.txt `
                python -m PyInstaller @targetArgs
            if ($LASTEXITCODE -ne 0) {
                throw "$($target.Name) 构建失败"
            }
        }
    }
    finally {
        $env:Path = $originalPath
    }
}

Push-Location $SourceDir
try {
    if ($Edition -eq 'All') {
        foreach ($staleName in @(
            'TG115-Deployer.exe',
            'TG115-Deployer-Modern.exe',
            'TG115-Deployer-Classic.exe'
        )) {
            $staleArtifact = Join-Path $SourceDir "dist\$staleName"
            if (Test-Path -LiteralPath $staleArtifact) {
                Remove-Item -LiteralPath $staleArtifact -Force
            }
        }
    }
    if ($env:TG115_BUILD_PYTHON) {
        & $env:TG115_BUILD_PYTHON -m pip install -r requirements-build.txt
        if ($LASTEXITCODE -ne 0) {
            throw '构建依赖安装失败'
        }
        Invoke-Tg115PythonBuild -PythonExecutable $env:TG115_BUILD_PYTHON
    }
    elseif ($uvCommand = Get-Command uv -ErrorAction SilentlyContinue) {
        Invoke-Tg115UvBuild -UvExecutable $uvCommand.Source
    }
    else {
        & python -m pip install -r requirements-build.txt
        if ($LASTEXITCODE -ne 0) {
            throw '构建依赖安装失败；请安装 uv 或提供 TG115_BUILD_PYTHON'
        }
        $pythonCommand = Get-Command python -ErrorAction Stop
        Invoke-Tg115PythonBuild -PythonExecutable $pythonCommand.Source
    }
    foreach ($target in $BuildTargets) {
        Write-Host "Build succeeded: $SourceDir\dist\$($target.Name).exe"
    }
}
finally {
    Pop-Location
}

param(
    [ValidateSet('All', 'CloudDrive2', 'OpenList')]
    [string]$Edition = 'All',
    [switch]$SkipSelfTest
)

$ErrorActionPreference = 'Stop'

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BrandIcon = Join-Path $SourceDir 'assets/brand/tg2cloud.ico'
$PyInstallerArgs = @(
    '--noconfirm'
    '--clean'
    '--onefile'
    '--windowed'
    '--collect-all', 'paramiko'
    '--icon', $BrandIcon
    '--specpath', 'build/spec'
    '--distpath', 'dist'
)

$BuildTargets = @()
if ($Edition -in @('All', 'CloudDrive2')) {
    $BuildTargets += [PSCustomObject]@{
        Key = 'clouddrive2'
        Name = 'TG2Cloud-CloudDrive2-Deployer'
        Source = 'installer_clouddrive2.py'
        VersionFile = 'packaging/windows/TG2Cloud-CloudDrive2.version.txt'
        AddData = @(
            'payload_clouddrive2;payload_clouddrive2'
            'assets/brand;assets/brand'
        )
    }
}
if ($Edition -in @('All', 'OpenList')) {
    $BuildTargets += [PSCustomObject]@{
        Key = 'openlist'
        Name = 'TG2Cloud-OpenList-Deployer'
        Source = 'installer_openlist.py'
        VersionFile = 'packaging/windows/TG2Cloud-OpenList.version.txt'
        AddData = @(
            'payload_clouddrive2;payload_clouddrive2'
            'payload_openlist;payload_openlist'
            'assets/brand;assets/brand'
        )
    }
}

function Get-Tg2CloudIsolatedPath {
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

function Invoke-Tg2CloudPythonBuild {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExecutable
    )

    $originalPath = $env:Path
    try {
        $env:Path = Get-Tg2CloudIsolatedPath -ToolPath $PythonExecutable
        foreach ($target in $BuildTargets) {
            Write-Host "Building $($target.Name) with PySide6..."
            & $PythonExecutable -c 'from PySide6.QtWidgets import QApplication; assert QApplication'
            if ($LASTEXITCODE -ne 0) {
                throw 'PySide6 GUI 运行时不可用，停止生成无法启动的部署器'
            }
            $targetArgs = @($PyInstallerArgs)
            foreach ($data in $target.AddData) {
                $parts = $data.Split(';', 2)
                $dataSource = Join-Path $SourceDir $parts[0]
                $targetArgs += @('--add-data', "$dataSource;$($parts[1])")
            }
            $targetArgs += @(
                '--version-file', (Join-Path $SourceDir $target.VersionFile)
            )
            $targetArgs += @(
                '--name', $target.Name, (Join-Path $SourceDir $target.Source)
            )
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

function Invoke-Tg2CloudUvBuild {
    param(
        [Parameter(Mandatory = $true)]
        [string]$UvExecutable
    )

    $originalPath = $env:Path
    try {
        $env:Path = Get-Tg2CloudIsolatedPath -ToolPath $UvExecutable
        foreach ($target in $BuildTargets) {
            Write-Host "Building $($target.Name) with PySide6..."
            & $UvExecutable run --with-requirements requirements-build.txt `
                python -c 'from PySide6.QtWidgets import QApplication; assert QApplication'
            if ($LASTEXITCODE -ne 0) {
                throw 'PySide6 GUI 运行时不可用，停止生成无法启动的部署器'
            }
            $targetArgs = @($PyInstallerArgs)
            foreach ($data in $target.AddData) {
                $parts = $data.Split(';', 2)
                $dataSource = Join-Path $SourceDir $parts[0]
                $targetArgs += @('--add-data', "$dataSource;$($parts[1])")
            }
            $targetArgs += @(
                '--version-file', (Join-Path $SourceDir $target.VersionFile)
            )
            $targetArgs += @(
                '--name', $target.Name, (Join-Path $SourceDir $target.Source)
            )
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

function Test-Tg2CloudBuild {
    foreach ($target in $BuildTargets) {
        $artifact = Join-Path $SourceDir "dist\$($target.Name).exe"
        if (-not (Test-Path -LiteralPath $artifact -PathType Leaf)) {
            throw "缺少构建产物：$artifact"
        }
        $resultPath = Join-Path $SourceDir "build\self-test-$($target.Key).txt"
        if (Test-Path -LiteralPath $resultPath) {
            Remove-Item -LiteralPath $resultPath -Force
        }
        $process = Start-Process `
            -FilePath $artifact `
            -ArgumentList @('--self-test', '--self-test-result', $resultPath) `
            -WindowStyle Hidden -PassThru
        if (-not $process.WaitForExit(120000)) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            throw "$($target.Name) 自检超时"
        }
        if ($process.ExitCode -ne 0) {
            throw "$($target.Name) 自检退出码为 $($process.ExitCode)"
        }
        $content = Get-Content -LiteralPath $resultPath -Raw -Encoding utf8
        foreach ($expected in @(
            "product=$($target.Key)",
            'app_version=1.0.0',
            'gui_runtime=OK',
            'backend_import=OK',
            'result=OK'
        )) {
            if ($content -notmatch [regex]::Escape($expected)) {
                throw "$($target.Name) 自检缺少：$expected"
            }
        }
        Write-Host "Self-test succeeded: $($target.Name)"
    }
}

Push-Location $SourceDir
try {
    New-Item -ItemType Directory -Force -Path 'build/spec' | Out-Null
    foreach ($required in @($BrandIcon) + @(
        $BuildTargets | ForEach-Object { Join-Path $SourceDir $_.VersionFile }
    )) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
            throw "构建资源不存在：$required"
        }
    }
    if ($Edition -eq 'All') {
        foreach ($staleName in @(
            'TG115-Deployer.exe',
            'TG115-Deployer-Modern.exe',
            'TG115-Deployer-Classic.exe',
            'TG115-CloudDrive2-Deployer.exe',
            'TG115-OpenList-Deployer.exe'
        )) {
            $staleArtifact = Join-Path $SourceDir "dist\$staleName"
            if (Test-Path -LiteralPath $staleArtifact) {
                Remove-Item -LiteralPath $staleArtifact -Force
            }
        }
    }
    if ($env:TG2CLOUD_BUILD_PYTHON) {
        & $env:TG2CLOUD_BUILD_PYTHON -m pip install -r requirements-build.txt
        if ($LASTEXITCODE -ne 0) {
            throw '构建依赖安装失败'
        }
        Invoke-Tg2CloudPythonBuild -PythonExecutable $env:TG2CLOUD_BUILD_PYTHON
    }
    elseif ($uvCommand = Get-Command uv -ErrorAction SilentlyContinue) {
        Invoke-Tg2CloudUvBuild -UvExecutable $uvCommand.Source
    }
    else {
        & python -m pip install -r requirements-build.txt
        if ($LASTEXITCODE -ne 0) {
            throw '构建依赖安装失败；请安装 uv 或提供 TG2CLOUD_BUILD_PYTHON'
        }
        $pythonCommand = Get-Command python -ErrorAction Stop
        Invoke-Tg2CloudPythonBuild -PythonExecutable $pythonCommand.Source
    }
    if (-not $SkipSelfTest) {
        Test-Tg2CloudBuild
    }
    if ($Edition -eq 'All') {
        $expectedArtifacts = @(
            $BuildTargets | ForEach-Object { "$($_.Name).exe" }
        )
        $actualArtifacts = @(
            Get-ChildItem -LiteralPath (Join-Path $SourceDir 'dist') `
                -File -Filter 'TG2Cloud-*-Deployer.exe' |
                Select-Object -ExpandProperty Name
        )
        $artifactDifference = Compare-Object $expectedArtifacts $actualArtifacts
        if ($artifactDifference) {
            throw "TG2Cloud 正式构建产物集合不正确：$($actualArtifacts -join ', ')"
        }
    }
    foreach ($target in $BuildTargets) {
        Write-Host "Build succeeded: $SourceDir\dist\$($target.Name).exe"
    }
}
finally {
    Pop-Location
}

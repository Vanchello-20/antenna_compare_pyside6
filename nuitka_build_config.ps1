# Скрипт сборки папки приложения сравнения антенн через Nuitka.
# Запускать из этой папки:
#   powershell -ExecutionPolicy Bypass -File .\nuitka_build_config.ps1

# =========================
# Настройки
# =========================

# Главный Python-файл для компиляции. Относительные пути считаются от папки этого .ps1 файла.
$MainScript = "main.py"

# Команда Python для проверки зависимостей и запуска Nuitka.
$PythonCommand = "py"

# Имя итоговой папки. Она будет создана рядом с этим .ps1 файлом.
$FinalFolderName = "Сравнение антенн"

# Имя итогового исполняемого файла внутри папки сборки.
$FinalExeName = "Сравнение антенн.exe"

# Иконка исполняемого файла. Оставьте пустым, чтобы не добавлять иконку.
$AppIconPath = "antenna_communication_icon-icons.com_67285.ico"

# Файлы, которые main.py загружает во время работы из папки приложения.
$DataFiles = @(
    "antennas.json=antennas.json",
    "antenna_communication_icon-icons.com_67285.ico=antenna_communication_icon-icons.com_67285.ico"
)

# Плагины Nuitka, которые нужно включить.
$NuitkaPlugins = @(
    "pyside6"
)

# Python-пакеты, которые нужно явно включить в сборку.
$IncludedPackages = @(
    "PySide6"
)

# Импорты, которые проверяются перед сборкой, чтобы сразу показать понятную ошибку при отсутствии зависимостей.
$RequiredImports = @(
    @{ ImportName = "PySide6"; PackageName = "PySide6" },
    @{ ImportName = "nuitka"; PackageName = "nuitka" }
)

# Дополнительные аргументы Nuitka, по одному элементу на аргумент.
$ExtraNuitkaArgs = @(
    "--windows-console-mode=disable"
)

# =========================
# Логика сборки
# =========================

$ProjectDir = $PSScriptRoot
$MainScriptPath = Join-Path $ProjectDir $MainScript
$MainScriptBaseName = [System.IO.Path]::GetFileNameWithoutExtension($MainScript)
$NuitkaDistPath = Join-Path $ProjectDir "$MainScriptBaseName.dist"
$FinalFolderPath = Join-Path $ProjectDir $FinalFolderName
$OriginalExePath = Join-Path $FinalFolderPath "$MainScriptBaseName.exe"
$FinalExePath = Join-Path $FinalFolderPath $FinalExeName

function Resolve-ProjectPath {
    param([string] $Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return ""
    }

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }

    return Join-Path $ProjectDir $Path
}

function Resolve-DataFileArg {
    param([string] $DataFile)

    $parts = $DataFile -split "=", 2
    if ($parts.Count -ne 2) {
        throw "Bad data file entry '$DataFile'. Use source=target."
    }

    $source = Resolve-ProjectPath $parts[0]
    $target = $parts[1]

    if (-not (Test-Path -LiteralPath $source)) {
        throw "Data file not found: $source"
    }

    return "$source=$target"
}

if (-not (Test-Path -LiteralPath $MainScriptPath)) {
    throw "Main script not found: $MainScriptPath"
}

foreach ($requiredImport in $RequiredImports) {
    & $PythonCommand -c "import $($requiredImport.ImportName)" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Missing Python package '$($requiredImport.PackageName)'. Install it with: py -m pip install $($requiredImport.PackageName)"
    }
}

$NuitkaArgs = @(
    "--standalone",
    "--output-dir=$ProjectDir"
)

foreach ($arg in $ExtraNuitkaArgs) {
    if (-not [string]::IsNullOrWhiteSpace($arg)) {
        $NuitkaArgs += $arg
    }
}

foreach ($plugin in $NuitkaPlugins) {
    if (-not [string]::IsNullOrWhiteSpace($plugin)) {
        $NuitkaArgs += "--enable-plugin=$plugin"
    }
}

foreach ($package in $IncludedPackages) {
    if (-not [string]::IsNullOrWhiteSpace($package)) {
        $NuitkaArgs += "--include-package=$package"
    }
}

$ResolvedAppIconPath = Resolve-ProjectPath $AppIconPath
if ($ResolvedAppIconPath) {
    if (-not (Test-Path -LiteralPath $ResolvedAppIconPath)) {
        throw "App icon not found: $ResolvedAppIconPath"
    }
    $NuitkaArgs += "--windows-icon-from-ico=$ResolvedAppIconPath"
}

foreach ($dataFile in $DataFiles) {
    if (-not [string]::IsNullOrWhiteSpace($dataFile)) {
        $NuitkaArgs += "--include-data-files=$(Resolve-DataFileArg $dataFile)"
    }
}

$NuitkaArgs += $MainScriptPath

& $PythonCommand -m nuitka @NuitkaArgs

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if (-not (Test-Path -LiteralPath $NuitkaDistPath)) {
    throw "Nuitka output folder not found: $NuitkaDistPath"
}

if (Test-Path -LiteralPath $FinalFolderPath) {
    Remove-Item -LiteralPath $FinalFolderPath -Recurse -Force
}

Move-Item -LiteralPath $NuitkaDistPath -Destination $FinalFolderPath

if ((Test-Path -LiteralPath $OriginalExePath) -and ($OriginalExePath -ne $FinalExePath)) {
    Move-Item -LiteralPath $OriginalExePath -Destination $FinalExePath -Force
}

Write-Output "Done: $FinalExePath"

# Удаление папок .build Nuitka после успешной сборки.
$BuildDirs = Get-ChildItem -Path $ProjectDir -Directory -Filter "*.build" -Recurse

foreach ($dir in $BuildDirs) {
    try {
        Remove-Item -LiteralPath $dir.FullName -Recurse -Force
        Write-Host "Removed build folder: $($dir.FullName)"
    } catch {
        Write-Host "Failed to remove: $($dir.FullName)"
    }
}

# DofusFashionistaVanced - Windows 11 launcher
# Starts the application on Windows 11, using absolute paths.

# Force UTF-8 encoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

#Requires -Version 5.0

# Prints a message with a timestamp and a color
function Write-LogMessage {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Message,
        
        [Parameter(Mandatory=$false)]
        [ValidateSet("INFO", "SUCCESS", "WARNING", "ERROR")]
        [string]$Type = "INFO"
    )
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $color = switch ($Type) {
        "INFO"    { "White" }
        "SUCCESS" { "Green" }
        "WARNING" { "Yellow" }
        "ERROR"   { "Red" }
        default   { "White" }
    }
    
    Write-Host "[$timestamp] [$Type] $Message" -ForegroundColor $color
    
    # Also append to the log file when one is set
    if ($Global:LogFile) {
        "[$timestamp] [$Type] $Message" | Out-File -FilePath $Global:LogFile -Append
    }
}

# Tells whether a command is available
function Test-CommandExists {
    param ($command)
    
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = 'stop'
    
    try {
        if (Get-Command $command) {
            return $true
        }
    }
    catch {
        return $false
    }
    finally {
        $ErrorActionPreference = $oldPreference
    }
}

# A freshly-installed Python isn't on the PATH of an already-open window until the
# session is restarted; re-read it from the registry so we find it anyway.
function Update-SessionPath {
    try {
        $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
        $user    = [Environment]::GetEnvironmentVariable('Path', 'User')
        $merged  = (@($machine, $user) | Where-Object { $_ }) -join ';'
        if ($merged) { $env:Path = $merged }
    }
    catch { }
}

function Test-PythonCandidate {
    param([string]$Exe, [string[]]$Prefix = @())
    if (-not $Exe) { return $null }
    if ($Exe -match '\\Microsoft\\WindowsApps\\') { return $null }   # Microsoft Store stub
    if (-not (Test-Path -LiteralPath $Exe)) { return $null }
    if ((Get-Item -LiteralPath $Exe).Length -le 0) { return $null }  # 0-byte alias stub
    $probe = & $Exe @Prefix -c "import sys; print('%d.%d.%d' % sys.version_info[:3])" 2>$null
    if ($LASTEXITCODE -eq 0 -and $probe) { return (@($Exe) + $Prefix) }
    return $null
}

# Returns a call prefix for a real interpreter, e.g. @('py','-3') or @('C:\...\python.exe'),
# or $null. Prefers the py launcher; falls back to PATH then well-known install dirs.
function Get-PythonCommand {
    Update-SessionPath

    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) {
        $res = Test-PythonCandidate -Exe $pyCmd.Source -Prefix @('-3')
        if ($res) { return $res }
    }

    foreach ($cmd in (Get-Command python -All -ErrorAction SilentlyContinue)) {
        $res = Test-PythonCandidate -Exe $cmd.Source
        if ($res) { return $res }
    }

    $res = Test-PythonCandidate -Exe (Join-Path $env:LOCALAPPDATA 'Programs\Python\Launcher\py.exe') -Prefix @('-3')
    if ($res) { return $res }
    $res = Test-PythonCandidate -Exe (Join-Path $env:WINDIR 'py.exe') -Prefix @('-3')
    if ($res) { return $res }
    foreach ($base in @(
            (Join-Path $env:LOCALAPPDATA 'Programs\Python'),
            (Join-Path $env:ProgramFiles 'Python'),
            (Join-Path ${env:ProgramFiles(x86)} 'Python'))) {
        if ($base -and (Test-Path -LiteralPath $base)) {
            $dirs = Get-ChildItem -LiteralPath $base -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending
            foreach ($d in $dirs) {
                $res = Test-PythonCandidate -Exe (Join-Path $d.FullName 'python.exe')
                if ($res) { return $res }
            }
        }
    }

    return $null
}

function Invoke-Python {
    $exe = $Global:PythonCmd[0]
    $prefix = @()
    if ($Global:PythonCmd.Count -gt 1) {
        $prefix = $Global:PythonCmd[1..($Global:PythonCmd.Count - 1)]
    }
    & $exe @prefix @args
}

# Checks the prerequisites
function Test-Prerequisites {
    Write-LogMessage "Checking the prerequisites..." "INFO"
    
    # A real Python interpreter, not the Microsoft Store stub
    $Global:PythonCmd = Get-PythonCommand
    if (-not $Global:PythonCmd) {
        Write-LogMessage "Python not found. The Microsoft Store aliases (python.exe/python3.exe) do not count." "ERROR"
        Write-LogMessage "Install Python 3.12+: winget install -e --id Python.Python.3.14   (or https://www.python.org/downloads/)" "ERROR"
        Write-LogMessage "Tick 'Add Python to PATH' and 'Install py launcher'. If needed, turn off the python.exe/python3.exe app execution aliases in Windows Settings." "ERROR"
        return $false
    }
    Write-LogMessage "Python interpreter: $($Global:PythonCmd -join ' ')" "SUCCESS"

    # Python version
    $pythonVersion = Invoke-Python -c "import sys; print('%d.%d.%d' % sys.version_info[:3])"
    if ($LASTEXITCODE -ne 0 -or -not $pythonVersion) {
        Write-LogMessage "Could not determine the Python version." "ERROR"
        return $false
    }
    Write-LogMessage "Python version found: $pythonVersion" "INFO"

    # pip, through the module
    Invoke-Python -m pip --version 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-LogMessage "pip is not available for this Python interpreter." "ERROR"
        Write-LogMessage "Try: $($Global:PythonCmd -join ' ') -m ensurepip --upgrade" "ERROR"
        return $false
    }
    
    # MySQL
    if (-not (Test-CommandExists mysql)) {
        Write-LogMessage "MySQL is not installed or not on the PATH." "WARNING"
        Write-LogMessage "Some features may not work correctly." "WARNING"
    } else {
        Write-LogMessage "MySQL is installed." "SUCCESS"
    }
    
    # Key folders
    if (-not (Test-Path -Path "$PSScriptRoot\fashionistapulp")) {
        Write-LogMessage "The 'fashionistapulp' folder was not found." "ERROR"
        return $false
    }
    
    if (-not (Test-Path -Path "$PSScriptRoot\fashionsite")) {
        Write-LogMessage "The 'fashionsite' folder was not found." "ERROR"
        return $false
    }
    
    if (-not (Test-Path -Path "$PSScriptRoot\fashionsite\manage.py")) {
        Write-LogMessage "manage.py was not found in the 'fashionsite' folder." "ERROR"
        return $false
    }
    
    # Missing dependencies
    Write-LogMessage "Installing the required dependencies..." "INFO"
    try {
        # Everything in requirements_win.txt
        $requirementsFile = "$PSScriptRoot\requirements_win.txt"
        if (Test-Path -Path $requirementsFile) {
            Write-LogMessage "Installing the dependencies from $requirementsFile..." "INFO"
            Invoke-Python -m pip install -r $requirementsFile --quiet 2>&1 | Out-Null
            Write-LogMessage "All dependencies installed." "SUCCESS"
        } else {
            Write-LogMessage "requirements_win.txt not found, limited install..." "WARNING"
            Invoke-Python -m pip install python-memcached 2>&1 | Out-Null
            Write-LogMessage "python-memcached installed." "SUCCESS"
        }
    }
    catch {
        Write-LogMessage "Error while installing the dependencies: $_" "WARNING"
    }
    
    return $true
}

# Sets up the Python environment
function Set-PythonEnvironment {
    Write-LogMessage "Setting up the Python environment..." "INFO"
    
    # PYTHONPATH holds only the current path
    $env:PYTHONPATH = "$PSScriptRoot\fashionistapulp"
    $env:PYTHONUNBUFFERED = "1"
    $env:PYTHONIOENCODING = "UTF-8"

    Write-LogMessage "PYTHONPATH set: $env:PYTHONPATH" "SUCCESS"
}

# Imports a MySQL/MariaDB dump into the local database
function Import-MySqlDump {
    param(
        [Parameter(Mandatory=$true)]
        [string]$SqlPath,

        [Parameter(Mandatory=$false)]
        [string]$DbName
    )

    try {
        if (-not (Test-Path -Path $SqlPath)) {
            Write-LogMessage "SQL dump not found: $SqlPath" "WARNING"
            return
        }

        # MySQL credentials from %APPDATA%\fashionista\gen_config.json
        $configDir = Join-Path $env:APPDATA 'fashionista'
        $genConfigPath = Join-Path $configDir 'gen_config.json'
        if (-not (Test-Path -Path $genConfigPath)) {
            Write-LogMessage "Configuration file not found: $genConfigPath" "WARNING"
            Write-LogMessage "SQL import skipped (MySQL credentials unknown)." "WARNING"
            return
        }

        $cfg = Get-Content -Path $genConfigPath -Raw | ConvertFrom-Json
        $dbUser = $cfg.mysql_USER
        $dbPass = $cfg.mysql_PASSWORD
        if (-not $DbName -or $DbName -eq '') {
            # Same default as Django: DB_NAME = 'fashionista'
            $DbName = if ($env:DB_NAME) { $env:DB_NAME } else { 'fashionista' }
        }

        # The mysql binary
        $mysqlCmd = 'mysql'
        if (-not (Test-CommandExists $mysqlCmd)) {
            $candidate = 'C:\\Program Files\\MariaDB 11.6\\bin\\mysql.exe'
            if (Test-Path -Path $candidate) {
                $mysqlCmd = $candidate
            } else {
                Write-LogMessage "MySQL client (mysql) not found. Add mysql to the PATH or install MariaDB/MySQL." "WARNING"
                return
            }
        }

        Write-LogMessage "Importing the SQL dump into the '$DbName' database" "INFO"

        # Create the database if needed
        $createDbOut = & $mysqlCmd -u $dbUser -p$dbPass -e "CREATE DATABASE IF NOT EXISTS `$DbName` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-LogMessage "Could not create or check the '$DbName' database." "ERROR"
            if ($createDbOut) { Write-LogMessage $createDbOut "ERROR" }
            return
        }

        # cmd /c handles the input redirection (<) reliably under PowerShell
        $quotedMysql = '"' + $mysqlCmd + '"'
        $quotedSql = '"' + $SqlPath + '"'
        $cmdLine = "$quotedMysql -u $dbUser -p$dbPass $DbName --default-character-set=utf8mb4 < $quotedSql"
        $importOut = cmd /c $cmdLine 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-LogMessage "SQL import into '$DbName' done." "SUCCESS"
        } else {
            Write-LogMessage "SQL import failed (code $LASTEXITCODE)." "ERROR"
            if ($importOut) { Write-LogMessage $importOut "ERROR" }
        }
    }
    catch {
        Write-LogMessage "Error while importing the SQL dump: $_" "ERROR"
    }
}

# Checks for the dump file, or creates it
function Ensure-DumpFile {
    Write-LogMessage "Checking the dump file..." "INFO"
    
    $dumpFilePath = "$PSScriptRoot\fashionistapulp\fashionistapulp\item_db_dumped.dump"
    $alternateDumpPath = "$PSScriptRoot\itemscraper\item_db_dumped.dump"
    
    # Main location
    if (-not (Test-Path -Path $dumpFilePath)) {
        Write-LogMessage "Dump file not found in the main location" "WARNING"
        
        # itemscraper folder
        if (Test-Path -Path $alternateDumpPath) {
            Write-LogMessage "Dump file found in the itemscraper folder, copying..." "INFO"
            
            # Make sure the destination folder exists
            $dumpFileDir = Split-Path -Path $dumpFilePath -Parent
            if (-not (Test-Path -Path $dumpFileDir)) {
                New-Item -ItemType Directory -Path $dumpFileDir -Force | Out-Null
                Write-LogMessage "Destination folder created: $dumpFileDir" "INFO"
            }
            
            # Copy the file
            Copy-Item -Path $alternateDumpPath -Destination $dumpFilePath -Force
            Write-LogMessage "Dump file copied." "SUCCESS"
            
            # Also fill the path the error names
            $wrongPathDumpDir = Join-Path $PSScriptRoot "fashionistapulp\fashionistapulp"
            if (-not (Test-Path -Path $wrongPathDumpDir)) {
                New-Item -ItemType Directory -Path $wrongPathDumpDir -Force -ErrorAction SilentlyContinue | Out-Null
                Copy-Item -Path $alternateDumpPath -Destination "$wrongPathDumpDir\item_db_dumped.dump" -Force -ErrorAction SilentlyContinue
                Write-LogMessage "Backup copy created in the alternate path." "INFO"
            }
        }
        else {
            Write-LogMessage "Dump file not found. Creating an empty file..." "WARNING"
            try {
                # Create the destination folder if needed
                $dumpFileDir = Split-Path -Path $dumpFilePath -Parent
                if (-not (Test-Path -Path $dumpFileDir)) {
                    New-Item -ItemType Directory -Path $dumpFileDir -Force | Out-Null
                }
                
                # Empty file
                "" | Out-File -FilePath $dumpFilePath -Encoding utf8
                Write-LogMessage "Empty dump file created." "SUCCESS"
                
                # Also fill the path the error names
                $wrongPathDumpDir = Join-Path $PSScriptRoot "fashionistapulp\fashionistapulp"
                if (-not (Test-Path -Path $wrongPathDumpDir)) {
                    New-Item -ItemType Directory -Path $wrongPathDumpDir -Force -ErrorAction SilentlyContinue | Out-Null 
                    "" | Out-File -FilePath "$wrongPathDumpDir\item_db_dumped.dump" -Encoding utf8 -ErrorAction SilentlyContinue
                    Write-LogMessage "Empty dump file created in the alternate path." "INFO"
                }
            }
            catch {
                Write-LogMessage "Error while creating the dump file: $_" "ERROR"
            }
        }
    }
    else {
        Write-LogMessage "Existing dump file found." "SUCCESS"
        
        # Make sure the alternate path named in the error exists too
        $wrongPathDumpDir = Join-Path $PSScriptRoot "fashionistapulp\fashionistapulp"
        $wrongPathDumpFile = "$wrongPathDumpDir\item_db_dumped.dump"
        if (-not (Test-Path -Path $wrongPathDumpFile)) {
            try {
                # Create the folder if needed
                if (-not (Test-Path -Path $wrongPathDumpDir)) {
                    New-Item -ItemType Directory -Path $wrongPathDumpDir -Force -ErrorAction SilentlyContinue | Out-Null
                }
                # Copy the existing file
                Copy-Item -Path $dumpFilePath -Destination $wrongPathDumpFile -Force -ErrorAction SilentlyContinue
                Write-LogMessage "Dump file copy created in the alternate path." "INFO"
            }
            catch {
                Write-LogMessage "Could not copy the dump file to the alternate path: $_" "WARNING"
            }
        }
    }
}

# Clears the solution cache
function Clear-SolutionCache {
    Write-LogMessage "Clearing the solution cache..." "INFO"
    
    try {
        # The dump file must exist before the cache is cleared
        Ensure-DumpFile
        
        Push-Location $PSScriptRoot
        Invoke-Python "$PSScriptRoot\wipe_solution_cache.py"
        
        if ($LASTEXITCODE -ne 0) {
            Write-LogMessage "Warning while clearing the cache." "WARNING"
        } else {
            Write-LogMessage "Cache cleared." "SUCCESS"
        }
    }
    catch {
        Write-LogMessage "Error while clearing the cache: $_" "ERROR"
    }
    finally {
        Pop-Location
    }
}

# Compiles the Django translation messages
function Invoke-DjangoCompileMessages {
    Write-LogMessage "Compiling the translation messages..." "INFO"
    
    try {
        if (Test-Path -Path "$PSScriptRoot\fashionsite") {
            Push-Location "$PSScriptRoot\fashionsite"
            
            # Is gettext installed
            $getTextInstalled = $false
            try {
                $null = & msgfmt --version
                $getTextInstalled = $true
            } catch {
                $getTextInstalled = $false
            }
            
            if ($getTextInstalled) {
                Invoke-Python -m django compilemessages
                
                if ($LASTEXITCODE -eq 0) {
                    Write-LogMessage "Messages compiled." "SUCCESS"
                } else {
                    Write-LogMessage "Problem while compiling the messages." "WARNING"
                }
            } else {
                Write-LogMessage "gettext is not installed. Skipping the translation build." "WARNING"
                Write-LogMessage "To install gettext: https://mlocati.github.io/articles/gettext-iconv-windows.html" "INFO"
            }
        } else {
            Write-LogMessage "The 'fashionsite' folder was not found." "ERROR"
        }
    }
    catch {
        Write-LogMessage "Error while compiling the messages: $_" "ERROR"
    }
    finally {
        Pop-Location
    }
}

# Points settings.py at a cache backend that works with Django 4.2+ on Windows
function Fix-DjangoSettings {
    Write-LogMessage "Adjusting the Django settings for Windows..." "INFO"
    
    $settingsPath = "$PSScriptRoot\fashionsite\fashionsite\settings.py"
    
    if (Test-Path -Path $settingsPath) {
        try {
            # Backup before any change
            $backupPath = "$settingsPath.bak"
            Copy-Item -Path $settingsPath -Destination $backupPath -Force
            Write-LogMessage "Settings backup created: $backupPath" "INFO"
            
            # pymemcache for Django 4.2+
            Invoke-Python -m pip install pymemcache 2>&1 | Out-Null
            Write-LogMessage "pymemcache installed for Django 4.2+." "SUCCESS"
            
            Write-LogMessage "Switching the cache to a local backend..." "INFO"
            
            # A Python script edits settings.py safely
            $tempScript = "$PSScriptRoot\temp_fix_django_settings.py"
@"
import re
import sys

def fix_settings(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Cache configuration to insert
    new_cache_config = """CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'fashionista-cache',
    }
}"""
    
    # Matches the whole CACHES block, nested braces included
    cache_pattern = r'CACHES\s*=\s*\{(?:[^{}]|(?:\{[^{}]*\}))*\}'
    
    # Replace the CACHES block
    if re.search(cache_pattern, content, re.DOTALL):
        modified_content = re.sub(cache_pattern, new_cache_config, content, flags=re.DOTALL)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        print("CACHES configuration updated.")
    else:
        print("CACHES block not found, checking the syntax...")
        
        # Look for an extra closing brace after the CACHES block, as fix_settings.py does
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if line.strip() == '}' and i > 0:
                prev_line = lines[i-1].strip()
                if prev_line.endswith('}'):
                    # Do the 10 previous lines contain 'CACHES'
                    prev_section = '\n'.join(lines[max(0, i-10):i])
                    if 'CACHES' in prev_section:
                        # Drop the line with the extra brace
                        lines.pop(i)
                        break
        
        # Write the fixed content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print("Syntax check and fix done.")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        fix_settings(sys.argv[1])
"@ | Out-File -FilePath $tempScript -Encoding utf8

            # Run the Python script
            Invoke-Python $tempScript $settingsPath

            # Check that the file still compiles
            $syntaxCheck = Invoke-Python -c "compile(open('$($settingsPath.Replace('\', '\\'))', 'r', encoding='utf-8').read(), '$($settingsPath.Replace('\', '\\'))', 'exec')" 2>&1
            
            if ($LASTEXITCODE -eq 0) {
                Write-LogMessage "Django settings now use the local cache." "SUCCESS"
            }
            else {
                Write-LogMessage "Syntax problem after the change. Restoring from the backup..." "WARNING"
                Copy-Item -Path $backupPath -Destination $settingsPath -Force
                
                # Run fix_settings.py when it exists
                if (Test-Path -Path "$PSScriptRoot\fix_settings.py") {
                    Invoke-Python "$PSScriptRoot\fix_settings.py"
                    Write-LogMessage "Fix applied with fix_settings.py." "INFO"
                }
            }
            
            # Remove the temporary script
            if (Test-Path -Path $tempScript) {
                Remove-Item -Path $tempScript -Force
            }
        }
        catch {
            Write-LogMessage "Error while changing the Django settings: $_" "ERROR"
        }
    } else {
        Write-LogMessage "Django settings file not found: $settingsPath" "ERROR"
    }
}

# Checks and sets up the database
function Invoke-DatabaseMigration {
    Write-LogMessage "Checking the database..." "INFO"
    
    try {
        if (Test-Path -Path "$PSScriptRoot\fashionsite\manage.py") {
            Push-Location "$PSScriptRoot\fashionsite"

            $migrateCheck = Invoke-Python manage.py migrate --noinput --check 2>&1

            if ($LASTEXITCODE -ne 0) {
                Write-LogMessage "Setting up the database..." "INFO"
                Invoke-Python manage.py migrate --noinput
                
                if ($LASTEXITCODE -eq 0) {
                    Write-LogMessage "Database set up." "SUCCESS"
                } else {
                    Write-LogMessage "Problem while setting up the database." "ERROR"
                }
            } else {
                Write-LogMessage "Database up to date." "SUCCESS"
            }
        } else {
            Write-LogMessage "manage.py was not found in the 'fashionsite' folder." "ERROR"
        }
    }
    catch {
        Write-LogMessage "Error while setting up the database: $_" "ERROR"
    }
    finally {
        Pop-Location
    }
}

# Cleans and resets the database
function Reset-Database {
    Write-LogMessage "Cleaning and resetting the database..." "INFO"
    
    try {
        # load_item_db.py resets the database
        Invoke-Python "$PSScriptRoot\load_item_db.py"
        
        if ($LASTEXITCODE -eq 0) {
            Write-LogMessage "Database reset." "SUCCESS"
            return $true
        } else {
            Write-LogMessage "Problem while resetting the database." "WARNING"
            return $false
        }
    }
    catch {
        Write-LogMessage "Error while resetting the database: $_" "ERROR"
        return $false
    }
}

# Starts the server
function Start-DjangoServer {
    Write-LogMessage "Starting the DofusFashionistaVanced server..." "INFO"
    Write-LogMessage "Open http://localhost:8000 in your browser" "INFO"
    Write-LogMessage "(Ctrl+C stops the server)" "INFO"
    
    # A stale server left on port 8000 would keep serving in place of the new one.
    $stale = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    foreach ($procId in ($stale.OwningProcess | Sort-Object -Unique)) {
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        Write-LogMessage "Stopped the old server on port 8000 (PID $procId)." "INFO"
    }

    try {
        if (Test-Path -Path "$PSScriptRoot\fashionsite\manage.py") {
            Push-Location "$PSScriptRoot\fashionsite"

            # Environment for the Python process
            $env:PYTHONPATH = "$PSScriptRoot\fashionistapulp"
            $env:PYTHONUNBUFFERED = "1"
            # The right Django settings
            $env:DJANGO_SETTINGS_MODULE = 'fashionsite.settings'
            # TCP on 127.0.0.1: on Windows 'localhost' goes through a named pipe that can reach another MySQL instance.
            $env:DB_HOST = '127.0.0.1'

            # The plain server, since the SSL server has problems with Python 3.12
            Invoke-Python -X faulthandler manage.py runserver --noreload 0.0.0.0:8000
            
            if ($LASTEXITCODE -ne 0) {
                Write-LogMessage "The server stopped with code $LASTEXITCODE" "ERROR"
                return $false
            }
        } else {
            Write-LogMessage "manage.py was not found in the 'fashionsite' folder." "ERROR"
            return $false
        }
    }
    catch {
        Write-LogMessage "Error while starting the server: $_" "ERROR"
        return $false
    }
    finally {
        Pop-Location
    }
    
    return $true
}

function Initialize-FashionistaConfig {
    Write-LogMessage "Preparing the local configuration..." "INFO"

    # settings.py reads these with json.loads / open(), which both reject a UTF-8 BOM.
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $cfgDir = Join-Path $env:APPDATA 'fashionista'
    if (-not (Test-Path -LiteralPath $cfgDir)) {
        New-Item -ItemType Directory -Force -Path $cfgDir | Out-Null
    }

    [System.IO.File]::WriteAllText((Join-Path $cfgDir 'config'),       $PSScriptRoot, $utf8NoBom)
    [System.IO.File]::WriteAllText((Join-Path $cfgDir 'debug_mode'),   'True',        $utf8NoBom)
    [System.IO.File]::WriteAllText((Join-Path $cfgDir 'serve_static'), 'True',        $utf8NoBom)

    $genPath = Join-Path $cfgDir 'gen_config.json'
    if (-not (Test-Path -LiteralPath $genPath)) {
        $buf = New-Object byte[] 48
        ([System.Security.Cryptography.RandomNumberGenerator]::Create()).GetBytes($buf)
        $secret = [Convert]::ToBase64String($buf)
        $gen = [ordered]@{
            PASSWORD_RESET_SALT              = 'local_salt'
            EMAIL_CONFIRMATION_SALT          = 'local_salt_2'
            SECRET_KEY                       = $secret
            mysql_PASSWORD                   = 'local'
            mysql_USER                       = 'root'
            EMAIL_HOST_USER                  = 'local@example.com'
            EMAIL_HOST_PASSWORD              = 'local'
            SOCIAL_AUTH_GOOGLE_OAUTH2_KEY    = $null
            SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = $null
            DBBACKUP_S3_ACCESS_KEY           = $null
            DBBACKUP_S3_SECRET_KEY           = $null
            url_captcha_secret               = $null
            char_id_SECRET_PART_1            = 'local_secret'
            char_id_SECRET_PART_2            = 'local_secret_2'
            google_analytics_id             = $null
            TESTER_USERS_EMAILS              = @('local@example.com')
            SUPER_USERS_EMAILS               = @()
            EMAIL_USE_TLS                    = $true
            EMAIL_HOST                       = 'smtp.example.com'
            EMAIL_PORT                       = 587
        }
        [System.IO.File]::WriteAllText($genPath, ($gen | ConvertTo-Json), $utf8NoBom)
        Write-LogMessage "Local configuration created: $genPath" "SUCCESS"
    }
    else {
        Write-LogMessage "Existing configuration kept: $genPath" "INFO"
    }
}

# Starts the local portable MySQL 8.0, imports the prod dump on the first run and ensures the app user.
function Ensure-LocalMysql {
    $mysqlHome  = Join-Path $env:LOCALAPPDATA 'Fashionista'
    $base       = Join-Path $mysqlHome 'mysql-8.0.46-winx64'
    $data       = Join-Path $mysqlHome 'data'
    $mysqld     = Join-Path $base 'bin\mysqld.exe'
    $mysql      = Join-Path $base 'bin\mysql.exe'
    $mysqladmin = Join-Path $base 'bin\mysqladmin.exe'
    $dump       = Join-Path $PSScriptRoot 'prod_dump.sql'

    if (-not (Test-Path -LiteralPath $mysqld)) {
        Write-LogMessage "Local MySQL 8.0 not found in $base." "ERROR"
        Write-LogMessage "Run the first-time setup: .\setup_local_mysql.ps1" "ERROR"
        return $false
    }

    if (-not (Test-Path -LiteralPath (Join-Path $data 'mysql'))) {
        Write-LogMessage "Initializing the MySQL data folder..." "INFO"
        New-Item -ItemType Directory -Force -Path $data | Out-Null
        & $mysqld --initialize-insecure "--datadir=$data" "--basedir=$base"
        if ($LASTEXITCODE -ne 0) { Write-LogMessage "MySQL initialization failed." "ERROR"; return $false }
    }

    if (-not (Get-NetTCPConnection -LocalPort 3306 -State Listen -ErrorAction SilentlyContinue)) {
        Write-LogMessage "Starting MySQL (port 3306)..." "INFO"
        Start-Process -FilePath $mysqld -ArgumentList "--datadir=$data","--basedir=$base","--port=3306","--max_allowed_packet=1G" -WindowStyle Hidden | Out-Null
        $up = $false
        foreach ($i in 1..30) {
            Start-Sleep -Milliseconds 1000
            if ((& $mysqladmin --host=127.0.0.1 --port=3306 -u root ping 2>&1) -match 'alive') { $up = $true; break }
        }
        if (-not $up) { Write-LogMessage "MySQL did not answer after 30s." "ERROR"; return $false }
    }
    Write-LogMessage "MySQL is up (port 3306)." "SUCCESS"

    $dbExists = & $mysql --host=127.0.0.1 --port=3306 -u root -N -e "SHOW DATABASES LIKE 'fashionista';" 2>$null
    if (-not $dbExists) {
        if (Test-Path -LiteralPath $dump) {
            Write-LogMessage "Importing the prod database (several minutes on the first run)..." "INFO"
            & $mysql --host=127.0.0.1 --port=3306 -u root -e "SET GLOBAL max_allowed_packet=1073741824;" 2>$null
            cmd /c "`"$mysql`" --host=127.0.0.1 --port=3306 -u root --max-allowed-packet=1G --default-character-set=utf8mb4 < `"$dump`""
            if ($LASTEXITCODE -ne 0) { Write-LogMessage "Prod database import failed." "ERROR"; return $false }
            Write-LogMessage "Prod database imported." "SUCCESS"
        }
        else {
            Write-LogMessage "No 'fashionista' database; creating an empty one (the migrations build the schema)." "WARNING"
            & $mysql --host=127.0.0.1 --port=3306 -u root -e "CREATE DATABASE IF NOT EXISTS fashionista CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" 2>$null
        }
    }

    $grant = "CREATE USER IF NOT EXISTS 'fashionista'@'%' IDENTIFIED WITH mysql_native_password BY 'fashionista';" +
             "ALTER USER 'fashionista'@'%' IDENTIFIED WITH mysql_native_password BY 'fashionista';" +
             "GRANT ALL PRIVILEGES ON fashionista.* TO 'fashionista'@'%';" +
             # manage.py test builds test_fashionista from scratch every run.
             "GRANT ALL PRIVILEGES ON ``test_fashionista``.* TO 'fashionista'@'%'; FLUSH PRIVILEGES;"
    & $mysql --host=127.0.0.1 --port=3306 -u root -e $grant 2>$null

    return $true
}

# Entry point
function Start-DofusFashionista {
    Clear-Host
    
    Write-Host "=========================================================="
    Write-Host "   DofusFashionistaVanced - Windows 11 launcher           "
    Write-Host "=========================================================="
    Write-Host ""
    
    # logs folder
    if (-not (Test-Path -Path "$PSScriptRoot\logs")) {
        New-Item -Path "$PSScriptRoot\logs" -ItemType Directory | Out-Null
    }
    
    # Log file
    $dateStr = Get-Date -Format "yyyy-MM-dd_HHmmss"
    $Global:LogFile = "$PSScriptRoot\logs\fashionista_$dateStr.log"
    
    Write-Host "Logs are in: $Global:LogFile"
    Write-Host ""
    
    # Prerequisites
    if (-not (Test-Prerequisites)) {
        Write-LogMessage "Prerequisite checks failed. Fix them before going on." "ERROR"
        Read-Host "Press Enter to exit"
        return
    }
    
    # Python environment
    Set-PythonEnvironment

    $env:DJANGO_SETTINGS_MODULE = 'fashionsite.settings'
    $env:DB_HOST = '127.0.0.1'
    $env:DB_PORT = '3306'
    $env:DB_NAME = 'fashionista'
    $env:DB_USER = 'fashionista'
    $env:DB_PASSWORD = 'fashionista'
    Write-LogMessage "Local mode: MySQL 8.0 (a copy of prod)." "INFO"

    if (-not (Ensure-LocalMysql)) {
        Read-Host "Press Enter to exit"
        return
    }

    Initialize-FashionistaConfig
    Invoke-DatabaseMigration
    Clear-SolutionCache
    Invoke-DjangoCompileMessages
    
    # Start the server, retrying on failure
    $maxRetries = 3
    $retry = 0
    $serverStarted = $false
    
    while (-not $serverStarted -and $retry -lt $maxRetries) {
        if ($retry -gt 0) {
            Write-LogMessage "Restarting the server ($retry/$maxRetries)..." "WARNING"
            Start-Sleep -Seconds 5
        }
        
        $serverStarted = Start-DjangoServer
        $retry++
    }
    
    if (-not $serverStarted) {
        Write-LogMessage "Could not start the server after $maxRetries attempts." "ERROR"
        Write-LogMessage "Check the logs for details." "ERROR"
    }
    
    Read-Host "Press Enter to exit"
}

# Run
Start-DofusFashionista
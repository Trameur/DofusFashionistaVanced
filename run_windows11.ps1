# DofusFashionistaVanced - Lanceur Windows 11
# Script PowerShell robuste pour lancer l'application sur Windows 11
# Utilise des chemins absolus et gère les erreurs de façon avancée

# Force UTF-8 encoding
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

#Requires -Version 5.0

# Fonction pour afficher les messages avec horodatage et couleur
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
    
    # Ajouter au fichier journal si on a défini un journal
    if ($Global:LogFile) {
        "[$timestamp] [$Type] $Message" | Out-File -FilePath $Global:LogFile -Append
    }
}

# Fonction pour vérifier si un programme est installé
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

# Fonction pour vérifier les prérequis
function Test-Prerequisites {
    Write-LogMessage "Vérification des prérequis..." "INFO"
    
    # Vérifier Python (un interpréteur RÉEL, pas le stub Microsoft Store)
    $Global:PythonCmd = Get-PythonCommand
    if (-not $Global:PythonCmd) {
        Write-LogMessage "Python introuvable. Les alias Microsoft Store (python.exe/python3.exe) ne comptent pas." "ERROR"
        Write-LogMessage "Installez Python 3.12+ : winget install -e --id Python.Python.3.14   (ou https://www.python.org/downloads/)" "ERROR"
        Write-LogMessage "Cochez 'Add Python to PATH' et 'Install py launcher'. Au besoin, désactivez les alias d'exécution d'application python.exe/python3.exe dans Paramètres Windows." "ERROR"
        return $false
    }
    Write-LogMessage "Interpréteur Python: $($Global:PythonCmd -join ' ')" "SUCCESS"

    # Vérifier la version de Python
    $pythonVersion = Invoke-Python -c "import sys; print('%d.%d.%d' % sys.version_info[:3])"
    if ($LASTEXITCODE -ne 0 -or -not $pythonVersion) {
        Write-LogMessage "Impossible de déterminer la version de Python." "ERROR"
        return $false
    }
    Write-LogMessage "Version Python détectée: $pythonVersion" "INFO"

    # Vérifier pip (via le module, méthode robuste)
    Invoke-Python -m pip --version 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-LogMessage "pip n'est pas disponible pour cet interpréteur Python." "ERROR"
        Write-LogMessage "Tentez : $($Global:PythonCmd -join ' ') -m ensurepip --upgrade" "ERROR"
        return $false
    }
    
    # Vérifier MySQL
    if (-not (Test-CommandExists mysql)) {
        Write-LogMessage "MySQL n'est pas installé ou n'est pas dans le PATH." "WARNING"
        Write-LogMessage "Certaines fonctionnalités pourraient ne pas fonctionner correctement." "WARNING"
    } else {
        Write-LogMessage "MySQL est installé." "SUCCESS"
    }
    
    # Vérifier si les répertoires clés existent
    if (-not (Test-Path -Path "$PSScriptRoot\fashionistapulp")) {
        Write-LogMessage "Le répertoire 'fashionistapulp' est introuvable." "ERROR"
        return $false
    }
    
    if (-not (Test-Path -Path "$PSScriptRoot\fashionsite")) {
        Write-LogMessage "Le répertoire 'fashionsite' est introuvable." "ERROR"
        return $false
    }
    
    if (-not (Test-Path -Path "$PSScriptRoot\fashionsite\manage.py")) {
        Write-LogMessage "Le fichier manage.py est introuvable dans le répertoire 'fashionsite'." "ERROR"
        return $false
    }
    
    # Installer les dépendances manquantes
    Write-LogMessage "Installation des dépendances nécessaires..." "INFO"
    try {
        # Installer toutes les dépendances depuis requirements_win.txt
        $requirementsFile = "$PSScriptRoot\requirements_win.txt"
        if (Test-Path -Path $requirementsFile) {
            Write-LogMessage "Installation des dépendances depuis $requirementsFile..." "INFO"
            Invoke-Python -m pip install -r $requirementsFile --quiet 2>&1 | Out-Null
            Write-LogMessage "Toutes les dépendances ont été installées avec succès." "SUCCESS"
        } else {
            Write-LogMessage "Fichier requirements_win.txt introuvable, installation limitée..." "WARNING"
            Invoke-Python -m pip install python-memcached 2>&1 | Out-Null
            Write-LogMessage "python-memcached installé avec succès." "SUCCESS"
        }
    }
    catch {
        Write-LogMessage "Erreur lors de l'installation des dépendances: $_" "WARNING"
    }
    
    return $true
}

# Fonction pour configurer l'environnement Python
function Set-PythonEnvironment {
    Write-LogMessage "Configuration de l'environnement Python..." "INFO"
    
    # Définition des variables d'environnement (correction du PYTHONPATH pour n'avoir que le chemin actuel)
    $env:PYTHONPATH = "$PSScriptRoot\fashionistapulp"
    $env:PYTHONUNBUFFERED = "1"
    $env:PYTHONIOENCODING = "UTF-8"

    Write-LogMessage "PYTHONPATH défini: $env:PYTHONPATH" "SUCCESS"
}

# Fonction pour importer un dump MySQL/MariaDB dans la base locale
function Import-MySqlDump {
    param(
        [Parameter(Mandatory=$true)]
        [string]$SqlPath,

        [Parameter(Mandatory=$false)]
        [string]$DbName
    )

    try {
        if (-not (Test-Path -Path $SqlPath)) {
            Write-LogMessage "Dump SQL introuvable: $SqlPath" "WARNING"
            return
        }

        # Lire les identifiants MySQL depuis %APPDATA%\fashionista\gen_config.json
        $configDir = Join-Path $env:APPDATA 'fashionista'
        $genConfigPath = Join-Path $configDir 'gen_config.json'
        if (-not (Test-Path -Path $genConfigPath)) {
            Write-LogMessage "Fichier de configuration introuvable: $genConfigPath" "WARNING"
            Write-LogMessage "Import SQL ignoré (identifiants MySQL inconnus)." "WARNING"
            return
        }

        $cfg = Get-Content -Path $genConfigPath -Raw | ConvertFrom-Json
        $dbUser = $cfg.mysql_USER
        $dbPass = $cfg.mysql_PASSWORD
        if (-not $DbName -or $DbName -eq '') {
            # Utiliser la même logique que Django: DB_NAME par défaut = 'fashionista'
            $DbName = if ($env:DB_NAME) { $env:DB_NAME } else { 'fashionista' }
        }

        # Déterminer le binaire mysql
        $mysqlCmd = 'mysql'
        if (-not (Test-CommandExists $mysqlCmd)) {
            $candidate = 'C:\\Program Files\\MariaDB 11.6\\bin\\mysql.exe'
            if (Test-Path -Path $candidate) {
                $mysqlCmd = $candidate
            } else {
                Write-LogMessage "Client MySQL introuvable (mysql). Ajoutez mysql au PATH ou installez MariaDB/MySQL." "WARNING"
                return
            }
        }

        Write-LogMessage "Import du dump SQL vers la base '$DbName'" "INFO"

        # Créer la base si nécessaire
        $createDbOut = & $mysqlCmd -u $dbUser -p$dbPass -e "CREATE DATABASE IF NOT EXISTS `$DbName` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-LogMessage "Échec lors de la création/vérification de la base '$DbName'." "ERROR"
            if ($createDbOut) { Write-LogMessage $createDbOut "ERROR" }
            return
        }

        # Importer le fichier. Utiliser cmd /c pour gérer la redirection d'entrée (<) de façon fiable sous PowerShell
        $quotedMysql = '"' + $mysqlCmd + '"'
        $quotedSql = '"' + $SqlPath + '"'
        $cmdLine = "$quotedMysql -u $dbUser -p$dbPass $DbName --default-character-set=utf8mb4 < $quotedSql"
        $importOut = cmd /c $cmdLine 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-LogMessage "Import SQL terminé avec succès dans '$DbName'." "SUCCESS"
        } else {
            Write-LogMessage "Échec de l'import SQL (code $LASTEXITCODE)." "ERROR"
            if ($importOut) { Write-LogMessage $importOut "ERROR" }
        }
    }
    catch {
        Write-LogMessage "Erreur lors de l'import du dump SQL: $_" "ERROR"
    }
}

# Fonction pour vérifier ou créer le fichier dump
function Ensure-DumpFile {
    Write-LogMessage "Vérification du fichier dump..." "INFO"
    
    $dumpFilePath = "$PSScriptRoot\fashionistapulp\fashionistapulp\item_db_dumped.dump"
    $alternateDumpPath = "$PSScriptRoot\itemscraper\item_db_dumped.dump"
    
    # Vérifier si le fichier existe dans l'emplacement principal
    if (-not (Test-Path -Path $dumpFilePath)) {
        Write-LogMessage "Fichier dump introuvable dans l'emplacement principal" "WARNING"
        
        # Vérifier s'il existe dans le dossier itemscraper
        if (Test-Path -Path $alternateDumpPath) {
            Write-LogMessage "Fichier dump trouvé dans le dossier itemscraper, copie en cours..." "INFO"
            
            # S'assurer que le chemin de destination existe
            $dumpFileDir = Split-Path -Path $dumpFilePath -Parent
            if (-not (Test-Path -Path $dumpFileDir)) {
                New-Item -ItemType Directory -Path $dumpFileDir -Force | Out-Null
                Write-LogMessage "Répertoire de destination créé: $dumpFileDir" "INFO"
            }
            
            # Copier le fichier
            Copy-Item -Path $alternateDumpPath -Destination $dumpFilePath -Force
            Write-LogMessage "Fichier dump copié avec succès." "SUCCESS"
            
            # Corriger le chemin qui contient l'erreur
            $wrongPathDumpDir = Join-Path $PSScriptRoot "fashionistapulp\fashionistapulp"
            if (-not (Test-Path -Path $wrongPathDumpDir)) {
                New-Item -ItemType Directory -Path $wrongPathDumpDir -Force -ErrorAction SilentlyContinue | Out-Null
                Copy-Item -Path $alternateDumpPath -Destination "$wrongPathDumpDir\item_db_dumped.dump" -Force -ErrorAction SilentlyContinue
                Write-LogMessage "Copie de secours créée dans le chemin alternatif." "INFO"
            }
        }
        else {
            Write-LogMessage "Fichier dump introuvable. Création d'un fichier vide..." "WARNING"
            try {
                # Créer le répertoire de destination si nécessaire
                $dumpFileDir = Split-Path -Path $dumpFilePath -Parent
                if (-not (Test-Path -Path $dumpFileDir)) {
                    New-Item -ItemType Directory -Path $dumpFileDir -Force | Out-Null
                }
                
                # Créer un fichier vide
                "" | Out-File -FilePath $dumpFilePath -Encoding utf8
                Write-LogMessage "Fichier dump vide créé." "SUCCESS"
                
                # Corriger également le chemin incorrect qui cause l'erreur
                $wrongPathDumpDir = Join-Path $PSScriptRoot "fashionistapulp\fashionistapulp"
                if (-not (Test-Path -Path $wrongPathDumpDir)) {
                    New-Item -ItemType Directory -Path $wrongPathDumpDir -Force -ErrorAction SilentlyContinue | Out-Null 
                    "" | Out-File -FilePath "$wrongPathDumpDir\item_db_dumped.dump" -Encoding utf8 -ErrorAction SilentlyContinue
                    Write-LogMessage "Fichier dump vide créé dans le chemin alternatif." "INFO"
                }
            }
            catch {
                Write-LogMessage "Erreur lors de la création du fichier dump: $_" "ERROR"
            }
        }
    }
    else {
        Write-LogMessage "Fichier dump existant trouvé." "SUCCESS"
        
        # S'assurer que le chemin alternatif mentionné dans l'erreur existe aussi
        $wrongPathDumpDir = Join-Path $PSScriptRoot "fashionistapulp\fashionistapulp"
        $wrongPathDumpFile = "$wrongPathDumpDir\item_db_dumped.dump"
        if (-not (Test-Path -Path $wrongPathDumpFile)) {
            try {
                # Créer le répertoire si nécessaire
                if (-not (Test-Path -Path $wrongPathDumpDir)) {
                    New-Item -ItemType Directory -Path $wrongPathDumpDir -Force -ErrorAction SilentlyContinue | Out-Null
                }
                # Copier le fichier existant
                Copy-Item -Path $dumpFilePath -Destination $wrongPathDumpFile -Force -ErrorAction SilentlyContinue
                Write-LogMessage "Copie du fichier dump créée dans le chemin alternatif." "INFO"
            }
            catch {
                Write-LogMessage "Impossible de créer la copie du fichier dump dans le chemin alternatif: $_" "WARNING"
            }
        }
    }
}

# Fonction pour nettoyer le cache des solutions
function Clear-SolutionCache {
    Write-LogMessage "Nettoyage du cache des solutions..." "INFO"
    
    try {
        # S'assurer que le fichier dump existe avant de nettoyer le cache
        Ensure-DumpFile
        
        Push-Location $PSScriptRoot
        Invoke-Python "$PSScriptRoot\wipe_solution_cache.py"
        
        if ($LASTEXITCODE -ne 0) {
            Write-LogMessage "Avertissement lors du nettoyage du cache." "WARNING"
        } else {
            Write-LogMessage "Cache nettoyé avec succès." "SUCCESS"
        }
    }
    catch {
        Write-LogMessage "Erreur lors du nettoyage du cache: $_" "ERROR"
    }
    finally {
        Pop-Location
    }
}

# Fonction pour compiler les messages Django
function Invoke-DjangoCompileMessages {
    Write-LogMessage "Compilation des messages de traduction..." "INFO"
    
    try {
        if (Test-Path -Path "$PSScriptRoot\fashionsite") {
            Push-Location "$PSScriptRoot\fashionsite"
            
            # Vérifier si gettext est installé
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
                    Write-LogMessage "Messages compilés avec succès." "SUCCESS"
                } else {
                    Write-LogMessage "Problème lors de la compilation des messages." "WARNING"
                }
            } else {
                Write-LogMessage "gettext n'est pas installé. Compilation des traductions ignorée." "WARNING"
                Write-LogMessage "Pour installer gettext: https://mlocati.github.io/articles/gettext-iconv-windows.html" "INFO"
            }
        } else {
            Write-LogMessage "Le répertoire 'fashionsite' est introuvable." "ERROR"
        }
    }
    catch {
        Write-LogMessage "Erreur lors de la compilation des messages: $_" "ERROR"
    }
    finally {
        Pop-Location
    }
}

# Fonction pour modifier le fichier settings.py pour utiliser un backend de cache compatible avec Django 4.2+ sur Windows
function Fix-DjangoSettings {
    Write-LogMessage "Ajustement des paramètres Django pour Windows..." "INFO"
    
    $settingsPath = "$PSScriptRoot\fashionsite\fashionsite\settings.py"
    
    if (Test-Path -Path $settingsPath) {
        try {
            # Créer une sauvegarde avant toute modification
            $backupPath = "$settingsPath.bak"
            Copy-Item -Path $settingsPath -Destination $backupPath -Force
            Write-LogMessage "Sauvegarde des paramètres créée: $backupPath" "INFO"
            
            # Installer pymemcache pour compatibilité Django 4.2+
            Invoke-Python -m pip install pymemcache 2>&1 | Out-Null
            Write-LogMessage "pymemcache installé pour compatibilité Django 4.2+." "SUCCESS"
            
            Write-LogMessage "Configuration du cache vers un backend local..." "INFO"
            
            # Utiliser un script Python pour modifier de façon sûre le fichier settings.py
            $tempScript = "$PSScriptRoot\temp_fix_django_settings.py"
@"
import re
import sys

def fix_settings(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Configuration de cache à insérer
    new_cache_config = """CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'fashionista-cache',
    }
}"""
    
    # Rechercher le bloc CACHES existant avec une regex qui gère les structures imbriquées
    # Cette regex correspond au bloc CACHES complet avec des accolades imbriquées
    cache_pattern = r'CACHES\s*=\s*\{(?:[^{}]|(?:\{[^{}]*\}))*\}'
    
    # Remplacer le bloc CACHES
    if re.search(cache_pattern, content, re.DOTALL):
        modified_content = re.sub(cache_pattern, new_cache_config, content, flags=re.DOTALL)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        print("Configuration CACHES mise à jour avec succès.")
    else:
        print("Bloc CACHES non trouvé, vérification de syntaxe...")
        
        # Vérifier s'il y a une accolade en trop à la fin du bloc CACHES
        # Cette vérification est similaire à celle dans fix_settings.py
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if line.strip() == '}' and i > 0:
                prev_line = lines[i-1].strip()
                if prev_line.endswith('}'):
                    # Rechercher si les 10 lignes précédentes contiennent 'CACHES'
                    prev_section = '\n'.join(lines[max(0, i-10):i])
                    if 'CACHES' in prev_section:
                        # Supprimer cette ligne avec l'accolade en trop
                        lines.pop(i)
                        break
        
        # Écrire le contenu corrigé
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print("Vérification et correction de syntaxe terminées.")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        fix_settings(sys.argv[1])
"@ | Out-File -FilePath $tempScript -Encoding utf8

            # Exécuter le script Python
            Invoke-Python $tempScript $settingsPath

            # Vérifier que le fichier est syntaxiquement valide
            $syntaxCheck = Invoke-Python -c "compile(open('$($settingsPath.Replace('\', '\\'))', 'r', encoding='utf-8').read(), '$($settingsPath.Replace('\', '\\'))', 'exec')" 2>&1
            
            if ($LASTEXITCODE -eq 0) {
                Write-LogMessage "Paramètres Django mis à jour pour utiliser le cache local." "SUCCESS"
            }
            else {
                Write-LogMessage "Problème de syntaxe détecté après modification. Restauration depuis la sauvegarde..." "WARNING"
                Copy-Item -Path $backupPath -Destination $settingsPath -Force
                
                # Exécuter le script fix_settings.py dédié si disponible
                if (Test-Path -Path "$PSScriptRoot\fix_settings.py") {
                    Invoke-Python "$PSScriptRoot\fix_settings.py"
                    Write-LogMessage "Correction appliquée avec fix_settings.py." "INFO"
                }
            }
            
            # Nettoyer le script temporaire
            if (Test-Path -Path $tempScript) {
                Remove-Item -Path $tempScript -Force
            }
        }
        catch {
            Write-LogMessage "Erreur lors de la modification des paramètres Django: $_" "ERROR"
        }
    } else {
        Write-LogMessage "Fichier de paramètres Django introuvable: $settingsPath" "ERROR"
    }
}

# Fonction pour vérifier et configurer la base de données
function Invoke-DatabaseMigration {
    Write-LogMessage "Vérification de la base de données..." "INFO"
    
    try {
        if (Test-Path -Path "$PSScriptRoot\fashionsite\manage.py") {
            Push-Location "$PSScriptRoot\fashionsite"

            $migrateCheck = Invoke-Python manage.py migrate --noinput --check 2>&1

            if ($LASTEXITCODE -ne 0) {
                Write-LogMessage "Configuration de la base de données..." "INFO"
                Invoke-Python manage.py migrate --noinput
                
                if ($LASTEXITCODE -eq 0) {
                    Write-LogMessage "Base de données configurée avec succès." "SUCCESS"
                } else {
                    Write-LogMessage "Problème lors de la configuration de la base de données." "ERROR"
                }
            } else {
                Write-LogMessage "Base de données à jour." "SUCCESS"
            }
        } else {
            Write-LogMessage "Le fichier manage.py est introuvable dans le répertoire 'fashionsite'." "ERROR"
        }
    }
    catch {
        Write-LogMessage "Erreur lors de la configuration de la base de données: $_" "ERROR"
    }
    finally {
        Pop-Location
    }
}

# Fonction pour nettoyer et réinitialiser la base de données
function Reset-Database {
    Write-LogMessage "Nettoyage et réinitialisation de la base de données..." "INFO"
    
    try {
        # Exécuter le script Python load_item_db.py pour réinitialiser la base de données
        Invoke-Python "$PSScriptRoot\load_item_db.py"
        
        if ($LASTEXITCODE -eq 0) {
            Write-LogMessage "Base de données réinitialisée avec succès." "SUCCESS"
            return $true
        } else {
            Write-LogMessage "Problème lors de la réinitialisation de la base de données." "WARNING"
            return $false
        }
    }
    catch {
        Write-LogMessage "Erreur lors de la réinitialisation de la base de données: $_" "ERROR"
        return $false
    }
}

# Fonction pour démarrer le serveur
function Start-DjangoServer {
    Write-LogMessage "Démarrage du serveur DofusFashionistaVanced..." "INFO"
    Write-LogMessage "Accédez à http://localhost:8000 dans votre navigateur" "INFO"
    Write-LogMessage "(Ctrl+C pour arrêter le serveur)" "INFO"
    
    try {
        if (Test-Path -Path "$PSScriptRoot\fashionsite\manage.py") {
            Push-Location "$PSScriptRoot\fashionsite"
            
            # Définir les variables d'environnement correctement pour le processus Python
            $env:PYTHONPATH = "$PSScriptRoot\fashionistapulp"
            $env:PYTHONUNBUFFERED = "1"
            # Forcer l'utilisation des bons settings Django
            $env:DJANGO_SETTINGS_MODULE = 'fashionsite.settings'
            
            # Utiliser le serveur standard au lieu du serveur SSL qui a des problèmes avec Python 3.12
            Invoke-Python -X faulthandler manage.py runserver --noreload 0.0.0.0:8000
            
            if ($LASTEXITCODE -ne 0) {
                Write-LogMessage "Le serveur s'est arrêté avec le code $LASTEXITCODE" "ERROR"
                return $false
            }
        } else {
            Write-LogMessage "Le fichier manage.py est introuvable dans le répertoire 'fashionsite'." "ERROR"
            return $false
        }
    }
    catch {
        Write-LogMessage "Erreur lors du démarrage du serveur: $_" "ERROR"
        return $false
    }
    finally {
        Pop-Location
    }
    
    return $true
}

function Initialize-FashionistaConfig {
    Write-LogMessage "Préparation de la configuration locale..." "INFO"

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
        Write-LogMessage "Configuration locale créée: $genPath" "SUCCESS"
    }
    else {
        Write-LogMessage "Configuration existante conservée: $genPath" "INFO"
    }
}

# Démarre le MySQL 8.0 local (portable, sans service), importe le dump de prod au premier
# lancement et garantit l'utilisateur applicatif. Réplique l'environnement de prod sous Windows.
function Ensure-LocalMysql {
    $mysqlHome  = Join-Path $env:LOCALAPPDATA 'Fashionista'
    $base       = Join-Path $mysqlHome 'mysql-8.0.46-winx64'
    $data       = Join-Path $mysqlHome 'data'
    $mysqld     = Join-Path $base 'bin\mysqld.exe'
    $mysql      = Join-Path $base 'bin\mysql.exe'
    $mysqladmin = Join-Path $base 'bin\mysqladmin.exe'
    $dump       = Join-Path $PSScriptRoot 'prod_dump.sql'

    if (-not (Test-Path -LiteralPath $mysqld)) {
        Write-LogMessage "MySQL 8.0 local introuvable dans $base." "ERROR"
        Write-LogMessage "Lancez l'installation initiale : .\setup_local_mysql.ps1" "ERROR"
        return $false
    }

    if (-not (Test-Path -LiteralPath (Join-Path $data 'mysql'))) {
        Write-LogMessage "Initialisation du répertoire de données MySQL..." "INFO"
        New-Item -ItemType Directory -Force -Path $data | Out-Null
        & $mysqld --initialize-insecure "--datadir=$data" "--basedir=$base"
        if ($LASTEXITCODE -ne 0) { Write-LogMessage "Échec de l'initialisation MySQL." "ERROR"; return $false }
    }

    if (-not (Get-NetTCPConnection -LocalPort 3306 -State Listen -ErrorAction SilentlyContinue)) {
        Write-LogMessage "Démarrage de MySQL (port 3306)..." "INFO"
        Start-Process -FilePath $mysqld -ArgumentList "--datadir=$data","--basedir=$base","--port=3306","--max_allowed_packet=1G" -WindowStyle Hidden | Out-Null
        $up = $false
        foreach ($i in 1..30) {
            Start-Sleep -Milliseconds 1000
            if ((& $mysqladmin --host=127.0.0.1 --port=3306 -u root ping 2>&1) -match 'alive') { $up = $true; break }
        }
        if (-not $up) { Write-LogMessage "MySQL ne répond pas après 30s." "ERROR"; return $false }
    }
    Write-LogMessage "MySQL opérationnel (port 3306)." "SUCCESS"

    $dbExists = & $mysql --host=127.0.0.1 --port=3306 -u root -N -e "SHOW DATABASES LIKE 'fashionista';" 2>$null
    if (-not $dbExists) {
        if (Test-Path -LiteralPath $dump) {
            Write-LogMessage "Import de la base de prod (plusieurs minutes au premier lancement)..." "INFO"
            & $mysql --host=127.0.0.1 --port=3306 -u root -e "SET GLOBAL max_allowed_packet=1073741824;" 2>$null
            cmd /c "`"$mysql`" --host=127.0.0.1 --port=3306 -u root --max-allowed-packet=1G --default-character-set=utf8mb4 < `"$dump`""
            if ($LASTEXITCODE -ne 0) { Write-LogMessage "Échec de l'import de la base de prod." "ERROR"; return $false }
            Write-LogMessage "Base de prod importée." "SUCCESS"
        }
        else {
            Write-LogMessage "Base 'fashionista' absente ; création vide (les migrations feront le schéma)." "WARNING"
            & $mysql --host=127.0.0.1 --port=3306 -u root -e "CREATE DATABASE IF NOT EXISTS fashionista CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" 2>$null
        }
    }

    $grant = "CREATE USER IF NOT EXISTS 'fashionista'@'%' IDENTIFIED WITH mysql_native_password BY 'fashionista';" +
             "ALTER USER 'fashionista'@'%' IDENTIFIED WITH mysql_native_password BY 'fashionista';" +
             "GRANT ALL PRIVILEGES ON fashionista.* TO 'fashionista'@'%'; FLUSH PRIVILEGES;"
    & $mysql --host=127.0.0.1 --port=3306 -u root -e $grant 2>$null

    return $true
}

# Fonction principale - point d'entrée du script
function Start-DofusFashionista {
    Clear-Host
    
    Write-Host "=========================================================="
    Write-Host "   DofusFashionistaVanced - Lanceur Robuste Windows 11    "
    Write-Host "=========================================================="
    Write-Host ""
    
    # Création du dossier logs s'il n'existe pas
    if (-not (Test-Path -Path "$PSScriptRoot\logs")) {
        New-Item -Path "$PSScriptRoot\logs" -ItemType Directory | Out-Null
    }
    
    # Définir le fichier journal
    $dateStr = Get-Date -Format "yyyy-MM-dd_HHmmss"
    $Global:LogFile = "$PSScriptRoot\logs\fashionista_$dateStr.log"
    
    Write-Host "Logs disponibles dans: $Global:LogFile"
    Write-Host ""
    
    # Vérifier les prérequis
    if (-not (Test-Prerequisites)) {
        Write-LogMessage "Échec des vérifications préalables. Correction nécessaire avant de continuer." "ERROR"
        Read-Host "Appuyez sur Entrée pour quitter"
        return
    }
    
    # Configurer l'environnement Python
    Set-PythonEnvironment

    $env:DJANGO_SETTINGS_MODULE = 'fashionsite.settings'
    $env:DB_HOST = '127.0.0.1'
    $env:DB_PORT = '3306'
    $env:DB_NAME = 'fashionista'
    $env:DB_USER = 'fashionista'
    $env:DB_PASSWORD = 'fashionista'
    Write-LogMessage "Mode local : MySQL 8.0 (réplique de la prod)." "INFO"

    if (-not (Ensure-LocalMysql)) {
        Read-Host "Appuyez sur Entrée pour quitter"
        return
    }

    Initialize-FashionistaConfig
    Invoke-DatabaseMigration
    Clear-SolutionCache
    Invoke-DjangoCompileMessages
    
    # Démarrer le serveur avec système de redémarrage automatique
    $maxRetries = 3
    $retry = 0
    $serverStarted = $false
    
    while (-not $serverStarted -and $retry -lt $maxRetries) {
        if ($retry -gt 0) {
            Write-LogMessage "Tentative de redémarrage du serveur ($retry/$maxRetries)..." "WARNING"
            Start-Sleep -Seconds 5
        }
        
        $serverStarted = Start-DjangoServer
        $retry++
    }
    
    if (-not $serverStarted) {
        Write-LogMessage "Impossible de démarrer le serveur après $maxRetries tentatives." "ERROR"
        Write-LogMessage "Vérifiez les journaux pour plus d'informations." "ERROR"
    }
    
    Read-Host "Appuyez sur Entrée pour quitter"
}

# Lancement de la fonction principale
Start-DofusFashionista
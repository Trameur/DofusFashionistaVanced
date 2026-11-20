# DofusFashionistaVanced - runs a work branch next to main, with its own folder, database and port.

param(
    [string]$Branch,
    [int]$Port = 0,
    [switch]$Refresh,
    [switch]$Remove,
    [switch]$List,
    [switch]$NoBrowser,
    [switch]$PrepareOnly
)

. (Join-Path $PSScriptRoot 'run_windows11.ps1')

$Repo        = [System.IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
$RealAppData = $env:APPDATA
$MysqlBin    = Join-Path $env:LOCALAPPDATA 'Fashionista\mysql-8.4.13-winx64\bin'
$Mysql       = Join-Path $MysqlBin 'mysql.exe'
$Mysqldump   = Join-Path $MysqlBin 'mysqldump.exe'
$StateRoot   = Join-Path $env:LOCALAPPDATA 'Fashionista\branches'
$FirstPort   = 8001
$LastPort    = 8089
$Utf8NoBom   = New-Object System.Text.UTF8Encoding($false)

function Invoke-RootSql {
    param([string]$Sql)
    & $Mysql --host=127.0.0.1 --port=3306 -u root -N -e $Sql
}

function Get-WorktreeEntries {
    $found = @()
    $entry = @{}
    $lines = @(git -C $Repo worktree list --porcelain) + @('')
    foreach ($line in $lines) {
        if ($line -eq '') {
            if ($entry.path) { $found += New-Object PSObject -Property $entry }
            $entry = @{}
        }
        elseif ($line.StartsWith('worktree ')) { $entry.path = [System.IO.Path]::GetFullPath($line.Substring(9)).TrimEnd('\') }
        elseif ($line.StartsWith('branch refs/heads/')) { $entry.branch = $line.Substring(18) }
        elseif ($line -eq 'locked' -or $line.StartsWith('locked ')) { $entry.locked = $true }
    }
    return $found
}

function Get-WorktreeEntry {
    param([string]$Path)
    $full = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    foreach ($e in (Get-WorktreeEntries)) { if ($e.path -ieq $full) { return $e } }
    return $null
}

function Get-ShortHash {
    param([string]$Text)
    $md5 = [System.Security.Cryptography.MD5]::Create()
    $bytes = $md5.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Text.ToLower()))
    return (($bytes[0..1] | ForEach-Object { $_.ToString('x2') }) -join '')
}

function Get-WorkBranches {
    $result = @()
    foreach ($w in (Get-WorktreeEntries)) {
        if (-not $w.branch -or $w.path -ieq $Repo -or $w.branch -eq 'main') { continue }
        $ahead = [int](git -C $Repo rev-list --count "main..$($w.branch)")
        if ($ahead -eq 0) { continue }
        $behind = [int](git -C $Repo rev-list --count "$($w.branch)..main")
        $info = (git -C $Repo log -1 "--format=%ct|%cd|%s" "--date=format:%d/%m/%Y" $w.branch) -split '\|', 3
        $slug = ((Split-Path $w.path -Leaf).ToLower() -replace '[^a-z0-9-]', '-')
        $result += New-Object PSObject -Property ([ordered]@{
            Branch  = $w.branch
            Source  = $w.path
            Slug    = $slug
            Tree    = $null
            Ahead   = $ahead
            Behind  = $behind
            Stamp   = [long]$info[0]
            Date    = $info[1]
            Subject = $info[2]
        })
    }
    foreach ($group in @($result | Group-Object Slug | Where-Object { $_.Count -gt 1 })) {
        $owner = Read-StateFile -State (Join-Path $StateRoot $group.Name) -Name 'tree_ready'
        foreach ($b in $group.Group) {
            $plainTree = Join-Path (Split-Path $b.Source -Parent) ("try-" + $b.Slug)
            if ($owner -and $owner -ieq $plainTree) { continue }
            $b.Slug = $b.Slug + '-' + (Get-ShortHash -Text (Split-Path $b.Source -Parent))
        }
    }
    foreach ($b in $result) { $b.Tree = Join-Path (Split-Path $b.Source -Parent) ("try-" + $b.Slug) }
    return @($result | Sort-Object Stamp -Descending)
}

function Read-StateFile {
    param([string]$State, [string]$Name)
    $file = Join-Path $State $Name
    if (Test-Path -LiteralPath $file) { return [System.IO.File]::ReadAllText($file).Trim() }
    return $null
}

function Get-LeftoverCopies {
    param($Branches)
    $slugs = @($Branches | ForEach-Object { $_.Slug })
    return @(Get-ChildItem -LiteralPath $StateRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { $slugs -notcontains $_.Name } | ForEach-Object { $_.Name })
}

function Get-LeftoverWork {
    param([string]$Name)
    $slug = $Name.ToLower()
    if ($slug -notmatch '^[a-z0-9-]+$') { return $null }
    $state = Join-Path $StateRoot $slug
    if (-not (Test-Path -LiteralPath $state)) { return $null }
    return New-Object PSObject -Property ([ordered]@{
        Branch = $slug
        Source = $null
        Slug   = $slug
        Tree   = (Read-StateFile -State $state -Name 'tree_ready')
    })
}

function Show-WorkBranches {
    param($Branches)
    Write-Host ''
    if ($Branches.Count -eq 0) { Write-Host '  No work branch ahead of main has a worktree.' }
    for ($i = 0; $i -lt $Branches.Count; $i++) {
        $b = $Branches[$i]
        Write-Host ("  {0,2}. {1}" -f ($i + 1), $b.Branch) -ForegroundColor Cyan
        Write-Host ("      {0} ahead of main, {1} behind, last commit {2}: {3}" -f $b.Ahead, $b.Behind, $b.Date, $b.Subject)
        $known = Read-StateFile -State (Join-Path $StateRoot $b.Slug) -Name 'port'
        if ($known) { Write-Host ("      http://{0}.localhost:{1}/" -f $b.Slug, $known) -ForegroundColor DarkGray }
    }
    $left = Get-LeftoverCopies -Branches $Branches
    if ($left.Count -gt 0) {
        Write-Host ''
        Write-Host '  Test copies of branches no longer listed (merged, or their worktree is gone):'
        foreach ($name in $left) { Write-Host "    $name   delete it with: .\run_branch_windows11.ps1 -Branch $name -Remove" }
    }
    Write-Host ''
}

function Select-WorkBranch {
    param($Branches, [string]$Wanted)
    if ($Wanted -match '^\d+$') {
        $n = [int]$Wanted
        if ($n -ge 1 -and $n -le $Branches.Count) { return $Branches[$n - 1] }
        return $null
    }
    foreach ($b in $Branches) {
        if ($b.Branch -ieq $Wanted -or $b.Slug -ieq $Wanted) { return $b }
    }
    return $null
}

function Get-ListeningProcessIds {
    param([int]$OnPort)
    $conns = Get-NetTCPConnection -LocalPort $OnPort -State Listen -ErrorAction SilentlyContinue
    return @($conns | ForEach-Object { $_.OwningProcess } | Sort-Object -Unique)
}

function Get-BranchPort {
    param([string]$State, [int]$Wanted)
    $taken = @{}
    foreach ($dir in @(Get-ChildItem -LiteralPath $StateRoot -Directory -ErrorAction SilentlyContinue)) {
        if ($dir.FullName -ieq $State) { continue }
        $other = Read-StateFile -State $dir.FullName -Name 'port'
        if ($other -match '^\d+$') { $taken[[int]$other] = $dir.Name }
    }
    if ($Wanted -gt 0) {
        if ($Wanted -lt $FirstPort -or $Wanted -gt $LastPort) {
            Write-LogMessage "Pick a port between $FirstPort and $LastPort; 8000 is main." "ERROR"
            return 0
        }
        if ($taken.ContainsKey($Wanted)) {
            Write-LogMessage "Port $Wanted already belongs to the test copy $($taken[$Wanted])." "ERROR"
            return 0
        }
        return $Wanted
    }
    $known = Read-StateFile -State $State -Name 'port'
    if ($known -match '^\d+$' -and -not $taken.ContainsKey([int]$known)) { return [int]$known }
    for ($p = $FirstPort; $p -le $LastPort; $p++) {
        if ($taken.ContainsKey($p)) { continue }
        if ((Get-ListeningProcessIds -OnPort $p).Count -gt 0) { continue }
        return $p
    }
    Write-LogMessage "No free port between $FirstPort and $LastPort." "ERROR"
    return 0
}

function Stop-BranchServer {
    param([int]$OnPort)
    foreach ($procId in (Get-ListeningProcessIds -OnPort $OnPort)) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue
        $line = ''
        if ($proc) { $line = [string]$proc.CommandLine }
        if ($line -match 'manage\.py' -and $line -match 'runserver' -and $line.Contains("127.0.0.1:$OnPort")) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            Write-LogMessage "Stopped the previous server of this branch (PID $procId)." "INFO"
        }
        else {
            $name = 'a program'
            if ($proc) { $name = $proc.Name }
            Write-LogMessage "Port $OnPort is used by $name (PID $procId), which this launcher did not start. Close it, or start again with -Port and a free port between $FirstPort and $LastPort." "ERROR"
            return $false
        }
    }
    Start-Sleep -Milliseconds 500
    return $true
}

function Copy-UntrackedData {
    param($Work, [string]$Tree)
    $treeData = Join-Path $Tree 'fashionistapulp\fashionistapulp'
    $tracked = @(git -C $Tree ls-files -- 'fashionistapulp/fashionistapulp/items*.db' 'fashionistapulp/fashionistapulp/item_db_dumped*.dump' |
        ForEach-Object { Split-Path $_ -Leaf })
    $seen = @{}
    foreach ($dir in @((Join-Path $Work.Source 'fashionistapulp\fashionistapulp'), (Join-Path $Repo 'fashionistapulp\fashionistapulp'))) {
        $files = @(Get-ChildItem -LiteralPath $dir -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like 'items*.db' -or $_.Name -like 'item_db_dumped*.dump' })
        foreach ($f in $files) {
            if ($seen.ContainsKey($f.Name) -or $tracked -contains $f.Name) { continue }
            $seen[$f.Name] = $true
            $dst = Join-Path $treeData $f.Name
            $old = Get-Item -LiteralPath $dst -ErrorAction SilentlyContinue
            if (-not $old -or $old.Length -ne $f.Length -or $old.LastWriteTime -ne $f.LastWriteTime) {
                Copy-Item -LiteralPath $f.FullName -Destination $dst -Force
                Write-LogMessage "Copied $($f.Name), which git does not carry, from $dir." "INFO"
            }
        }
    }
    $now = Get-Date
    foreach ($name in $tracked) {
        $db = Join-Path $treeData $name
        if ($name -like 'items*.db' -and (Test-Path -LiteralPath $db)) { (Get-Item -LiteralPath $db).LastWriteTime = $now }
    }
}

function Update-TestCopy {
    param($Work, [string]$Tree, [string]$State)
    $readyFile = Join-Path $State 'tree_ready'
    $entry = Get-WorktreeEntry -Path $Tree
    if ($entry -and $entry.branch) {
        Write-LogMessage "$Tree holds the branch $($entry.branch), so it cannot be the test copy; move it away, then start again." "ERROR"
        return $false
    }
    if (Test-Path -LiteralPath $Tree) {
        if (-not $entry) {
            Write-LogMessage "$Tree is not a git worktree; move it away, then start again." "ERROR"
            return $false
        }
        if (-not (Test-Path -LiteralPath $readyFile)) {
            if ($entry.locked) {
                Write-LogMessage "The test copy in $Tree was left half made; making it again." "WARNING"
                git -C $Repo worktree unlock $Tree | Out-Host
                git -C $Repo worktree remove --force $Tree | Out-Host
                if (Test-Path -LiteralPath $Tree) { Write-LogMessage "Remove the folder $Tree by hand, then start again." "ERROR"; return $false }
            }
            else {
                [System.IO.File]::WriteAllText($readyFile, $Tree, $Utf8NoBom)
            }
        }
    }
    elseif ($entry -and $entry.locked) {
        git -C $Repo worktree unlock $Tree | Out-Host
    }

    if (-not (Test-Path -LiteralPath $Tree)) {
        Remove-Item -LiteralPath $readyFile -Force -ErrorAction SilentlyContinue
        Write-LogMessage "Creating the test copy of $($Work.Branch) in $Tree (a few minutes the first time)..." "INFO"
        git -C $Repo worktree prune | Out-Host
        git -C $Repo worktree add --detach $Tree $Work.Branch | Out-Host
        if ($LASTEXITCODE -ne 0) { Write-LogMessage "git could not create the test copy." "ERROR"; return $false }
        [System.IO.File]::WriteAllText($readyFile, $Tree, $Utf8NoBom)
    }
    else {
        $changed = @(git -C $Tree status --porcelain --untracked-files=no)
        if ($changed.Count -gt 0) {
            Write-LogMessage "The test copy has changed files, so it stays on its current commit:" "WARNING"
            $changed | ForEach-Object { Write-LogMessage "  $_" "WARNING" }
        }
        else {
            git -C $Tree checkout --quiet --detach $Work.Branch | Out-Host
            if ($LASTEXITCODE -ne 0) { Write-LogMessage "git could not move the test copy to the latest commit." "ERROR"; return $false }
        }
    }
    $head = git -C $Tree log -1 "--format=%h %cd %s" "--date=format:%d/%m %H:%M"
    Write-LogMessage "Test copy at $head" "SUCCESS"
    Copy-UntrackedData -Work $Work -Tree $Tree
    return $true
}

function Test-DatabaseExists {
    param([string]$Name)
    $hit = Invoke-RootSql "SELECT schema_name FROM information_schema.schemata WHERE schema_name = '$Name';"
    return [bool]$hit
}

function Get-DatabaseShape {
    param([string]$Name)
    $tables = [int](Invoke-RootSql "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '$Name';")
    $chars  = [int](Invoke-RootSql "SELECT COUNT(*) FROM ``$Name``.chardata_char;")
    return New-Object PSObject -Property @{ Tables = $tables; Builds = $chars }
}

function Copy-MainDatabase {
    param([string]$Name, [string]$State)
    Write-LogMessage "Copying the local main database into $Name (a few minutes)..." "INFO"
    $dumpFile = Join-Path $State 'main_copy.sql'
    Remove-Item -LiteralPath (Join-Path $State 'db_ready') -Force -ErrorAction SilentlyContinue
    Invoke-RootSql "DROP DATABASE IF EXISTS ``$Name``; CREATE DATABASE ``$Name`` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    & $Mysqldump --host=127.0.0.1 --port=3306 -u root --single-transaction --quick --routines --triggers `
        --default-character-set=utf8mb4 --max-allowed-packet=1G "--result-file=$dumpFile" fashionista
    $ok = ($LASTEXITCODE -eq 0)
    if ($ok) {
        $source = $dumpFile.Replace('\', '/')
        & $Mysql --host=127.0.0.1 --port=3306 -u root --default-character-set=utf8mb4 --max-allowed-packet=1G `
            "--init-command=SET sql_log_bin=0" $Name -e "source $source"
        $ok = ($LASTEXITCODE -eq 0)
    }
    Remove-Item -LiteralPath $dumpFile -Force -ErrorAction SilentlyContinue
    $copy = $null
    if ($ok) {
        $main = Get-DatabaseShape -Name 'fashionista'
        $copy = Get-DatabaseShape -Name $Name
        $ok = ($copy.Tables -eq $main.Tables -and $copy.Builds -gt 0 -and $copy.Builds -le $main.Builds)
        if (-not $ok) {
            Write-LogMessage ("The copy has {0} tables and {1} builds, main {2} and {3}." -f $copy.Tables, $copy.Builds, $main.Tables, $main.Builds) "ERROR"
        }
    }
    if (-not $ok) {
        Invoke-RootSql "DROP DATABASE IF EXISTS ``$Name``;"
        Write-LogMessage "Copying the database failed; nothing was kept." "ERROR"
        return $false
    }
    [System.IO.File]::WriteAllText((Join-Path $State 'db_ready'), $Name, $Utf8NoBom)
    Write-LogMessage ("Database {0} ready: {1} tables, {2} builds." -f $Name, $copy.Tables, $copy.Builds) "SUCCESS"
    return $true
}

function Confirm-Action {
    param([string]$Question)
    $answer = Read-Host "$Question Type YES to go on"
    return ($answer -ceq 'YES')
}

function Write-PrivateConfig {
    param([string]$State, [string]$Tree)
    $realCfg = Join-Path $RealAppData 'fashionista\gen_config.json'
    if (-not (Test-Path -LiteralPath $realCfg)) {
        Write-LogMessage "No $realCfg yet: start DofusFashionista_Windows11.bat once first." "ERROR"
        return $null
    }
    $appData = Join-Path $State 'appdata'
    $cfgDir = Join-Path $appData 'fashionista'
    New-Item -ItemType Directory -Force -Path $cfgDir | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $cfgDir 'config'),       $Tree,  $Utf8NoBom)
    [System.IO.File]::WriteAllText((Join-Path $cfgDir 'debug_mode'),   'True', $Utf8NoBom)
    [System.IO.File]::WriteAllText((Join-Path $cfgDir 'serve_static'), 'True', $Utf8NoBom)
    Copy-Item -LiteralPath $realCfg -Destination (Join-Path $cfgDir 'gen_config.json') -Force
    return $appData
}

function Update-Translations {
    param([string]$Tree)
    $stale = @(Get-ChildItem -Path (Join-Path $Tree 'fashionsite') -Filter '*.po' -Recurse -File | Where-Object {
        $mo = [System.IO.Path]::ChangeExtension($_.FullName, '.mo')
        -not (Test-Path -LiteralPath $mo) -or (Get-Item -LiteralPath $mo).LastWriteTime -lt $_.LastWriteTime
    })
    if ($stale.Count -eq 0) { return $true }
    Write-LogMessage "Compiling the translations..." "INFO"
    Push-Location (Join-Path $Tree 'fashionsite')
    try { Invoke-Python -m django compilemessages | Out-Null; return ($LASTEXITCODE -eq 0) }
    finally { Pop-Location }
}

function Remove-TestCopy {
    param($Work, [string]$Tree, [string]$State, [string]$DbName, [int]$OnPort)
    $entry = $null
    if ($Tree) { $entry = Get-WorktreeEntry -Path $Tree }
    if ($entry -and $entry.branch) {
        Write-LogMessage "$Tree holds the branch $($entry.branch), not a test copy; nothing was deleted." "ERROR"
        return
    }
    $what = ''
    if ($Tree) { $what = "the test copy $Tree, " }
    if (-not (Confirm-Action "This deletes ${what}the database $DbName and $State.")) { return }
    if ($OnPort -gt 0 -and -not (Stop-BranchServer -OnPort $OnPort)) { return }
    if ($Tree -and (Test-Path -LiteralPath $Tree)) {
        if (-not $entry) { Write-LogMessage "$Tree is not a git worktree; nothing was deleted." "ERROR"; return }
        git -C $Repo worktree remove $Tree
        if ($LASTEXITCODE -ne 0) { Write-LogMessage "git kept $Tree (see above); nothing else was deleted." "ERROR"; return }
    }
    elseif ($entry) {
        if ($entry.locked) { git -C $Repo worktree unlock $Tree }
        git -C $Repo worktree prune
    }
    if (Test-DatabaseExists -Name $DbName) { Invoke-RootSql "DROP DATABASE ``$DbName``;" }
    if (Test-Path -LiteralPath $State) { Remove-Item -LiteralPath $State -Recurse -Force }
    Write-LogMessage "Test copy of $($Work.Branch) removed." "SUCCESS"
}

function Start-WorkBranch {
    New-Item -ItemType Directory -Force -Path $StateRoot | Out-Null
    $branches = @(Get-WorkBranches)
    if ($List) { Show-WorkBranches -Branches $branches; return }

    $wanted = $Branch
    if (-not $wanted) {
        Write-Host '=========================================================='
        Write-Host '   DofusFashionistaVanced - test a work branch            '
        Write-Host '=========================================================='
        Show-WorkBranches -Branches $branches
        if ($branches.Count -eq 0) { return }
        Write-Host '  Add r after the number to start again from a fresh copy of the main database (e.g. 2r).'
        $wanted = Read-Host 'Number of the branch to start (Enter to quit)'
        if (-not $wanted) { return }
        if ($wanted -match '^(\d+)\s*r$') { $wanted = $Matches[1]; $script:Refresh = $true }
    }
    $wanted = $wanted.Trim()
    $work = Select-WorkBranch -Branches $branches -Wanted $wanted
    if (-not $work -and $Remove) { $work = Get-LeftoverWork -Name $wanted }
    if (-not $work) { Write-Host "No work branch matches '$wanted'."; return }

    $state  = Join-Path $StateRoot $work.Slug
    $tree   = $work.Tree
    $dbName = 'fashionista_br_' + ($work.Slug -replace '[^a-z0-9]', '_')
    New-Item -ItemType Directory -Force -Path (Join-Path $state 'logs') | Out-Null
    $Global:LogFile = Join-Path $state ("logs\branch_{0}.log" -f (Get-Date -Format 'yyyy-MM-dd_HHmmss'))

    $lockFile = Join-Path $state 'preparing'
    $holder = Read-StateFile -State $state -Name 'preparing'
    if ($holder -match '^\d+$' -and [int]$holder -ne $PID -and
        @(Get-Process -Id ([int]$holder) -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^(powershell|pwsh)$' }).Count -gt 0) {
        Write-Host "Another window is preparing this branch (PID $holder); wait for it to finish, then start again."
        return
    }
    [System.IO.File]::WriteAllText($lockFile, [string]$PID, $Utf8NoBom)
    try {
        if (-not (Ensure-LocalMysql)) { return }

        if ($Remove) {
            $known = Read-StateFile -State $state -Name 'port'
            $onPort = 0
            if ($known -match '^\d+$') { $onPort = [int]$known }
            Remove-TestCopy -Work $work -Tree $tree -State $state -DbName $dbName -OnPort $onPort
            return
        }

        $port = Get-BranchPort -State $state -Wanted $Port
        if ($port -eq 0) { return }
        try { $Host.UI.RawUI.WindowTitle = "Fashionista - $($work.Branch) - port $port" } catch { }
        Write-LogMessage "Branch $($work.Branch), port $port, database $dbName." "INFO"

        if (-not (Stop-BranchServer -OnPort $port)) { return }
        [System.IO.File]::WriteAllText((Join-Path $state 'port'), [string]$port, $Utf8NoBom)
        if (-not (Update-TestCopy -Work $work -Tree $tree -State $state)) { return }

        $hasDb = Test-DatabaseExists -Name $dbName
        if ($hasDb -and (Read-StateFile -State $state -Name 'db_ready') -ne $dbName) {
            Write-LogMessage "The copy of the database was left half made; copying it again." "WARNING"
            $hasDb = $false
        }
        if ($hasDb -and $Refresh) {
            if (Confirm-Action "This replaces $dbName with a fresh copy of the main database; what you did on this branch is lost.") {
                $hasDb = $false
            }
        }
        if (-not $hasDb) {
            if (-not (Copy-MainDatabase -Name $dbName -State $state)) { return }
        }
        Invoke-RootSql "GRANT ALL PRIVILEGES ON ``$dbName``.* TO 'fashionista'@'%'; FLUSH PRIVILEGES;"

        $Global:PythonCmd = Get-PythonCommand
        if (-not $Global:PythonCmd) { Write-LogMessage "Python was not found." "ERROR"; return }

        $appData = Write-PrivateConfig -State $state -Tree $tree
        if (-not $appData) { return }
        if (-not $env:PYTHONUSERBASE) { $env:PYTHONUSERBASE = Join-Path $RealAppData 'Python' }
        Remove-Item Env:FASHIONISTA_CONFIG_DIR -ErrorAction SilentlyContinue
        $env:APPDATA = $appData
        $env:PYTHONPATH = Join-Path $tree 'fashionistapulp'
        $env:PYTHONUNBUFFERED = '1'
        $env:DJANGO_SETTINGS_MODULE = 'fashionsite.settings'
        $env:DB_HOST = '127.0.0.1'
        $env:DB_PORT = '3306'
        $env:DB_NAME = $dbName
        $env:DB_USER = 'fashionista'
        $env:DB_PASSWORD = 'fashionista'
        $env:FASHIONISTA_WAKFU = '1'
        $characterData = Join-Path (Split-Path $work.Source -Parent) 'character_data'
        if (-not $env:CHARACTER_DATA_ROOT -and (Test-Path -LiteralPath $characterData)) { $env:CHARACTER_DATA_ROOT = $characterData }

        if (-not (Update-Translations -Tree $tree)) { Write-LogMessage "Compiling the translations failed." "WARNING" }

        Push-Location (Join-Path $tree 'fashionsite')
        try { Invoke-Python manage.py migrate --noinput; $migrated = ($LASTEXITCODE -eq 0) }
        finally { Pop-Location }
        if (-not $migrated) {
            Write-LogMessage "The migrations failed on $dbName." "ERROR"
            Write-LogMessage "If the branch was rewritten, start it again with r after its number (or -Refresh) to get a fresh copy of the main database." "ERROR"
            return
        }

        $wipe = Join-Path $tree 'wipe_solution_cache.py'
        if (Test-Path -LiteralPath $wipe) {
            Push-Location $tree
            try { Invoke-Python $wipe | Out-Null }
            finally { Pop-Location }
        }

        $url = "http://$($work.Slug).localhost:$port/"
        if ($PrepareOnly) { Write-LogMessage "Ready; start it without -PrepareOnly to serve $url" "SUCCESS"; return }
    }
    finally {
        Remove-Item -LiteralPath $lockFile -Force -ErrorAction SilentlyContinue
    }
    if (-not $NoBrowser) {
        Start-Job -ArgumentList $url, $port -ScriptBlock {
            param($u, $p)
            for ($i = 0; $i -lt 240; $i++) {
                if (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) { Start-Process $u; return }
                Start-Sleep -Seconds 1
            }
        } | Out-Null
    }
    Write-LogMessage "Open $url (Ctrl+C stops the server)." "SUCCESS"
    Push-Location (Join-Path $tree 'fashionsite')
    try { Invoke-Python -X faulthandler manage.py runserver --noreload "127.0.0.1:$port" }
    finally { Pop-Location }
}

Start-WorkBranch
if (-not $Branch) { Read-Host 'Press Enter to close' | Out-Null }

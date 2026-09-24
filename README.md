# Prerequisites

Python 3.14.4 is recommended.

Verified locally on Windows with:
- Python 3.11.9 for the existing launcher flow
- Python 3.12.4 with `requirements_win.txt` and `python manage.py check`
- Python 3.14.4 with refreshed `.venv`, `requirements_win.txt`, and `python manage.py check`

Python 3.15+ is not verified in this repository yet.

## Python Packages

All Python packages required for this project are listed in the requirements.txt file. 
Install them with pip:  
```shell   
pip install -r requirements.txt
```

For Windows, use:
```shell
pip install -r requirements_win.txt
```

# Dofus Fashionista

For a guided data update, run `py update_all.py`.
The launcher offers the versions and the images, backs up the local state, checks
the differences and runs the tests. See [the update guide](UPDATE_DATA.md).

The Dofus Fashionista, an equipment advisor for Dofus.

This is a fork that keeps the site running and up to date. Beyond the live game, it
now supports several game versions side by side (**Dofus 3**, **Beta**, **Dofus 2**,
**Dofus Retro** and **Dofus Touch**), each with its own item, set, spell and mount
data, reachable under its own URL prefix (`/retro/`, `/touch/`, …).

# Install Fashionista:

## Windows 11 (Thanks Hoklims)

Windows 11 is fully supported with a simple install. Follow these steps to install the project:

### Simplest option: run DofusFashionista_Windows11.bat

```shell
# Clone the repository (or download the ZIP archive)
git clone https://github.com/Trameurs/DofusFashionista.git fashionista
cd fashionista

# Run the Windows 11 batch file
DofusFashionista_Windows11.bat
```

This batch file sets up and starts the application in one step.

### Other install options

#### Option 1: install with PowerShell

```shell
# Run the Windows 11 PowerShell script
powershell -ExecutionPolicy Bypass -File run_windows11.ps1
```

This PowerShell script will:
1. Check for and install every required prerequisite
2. Set up the Windows environment
3. Adjust the settings for Windows 11
4. Set up the database and run the migrations
5. Start the server and handle errors along the way

#### Option 2: classic install

```shell
# Run the install script
install_windows.bat
```

The install script will:
1. Set up the Windows environment
2. Install the required dependencies
3. Write the configuration files
4. Create and set up the database

Once the install is done, start the application with:
```shell
run_fashionista.bat
```

Then open `http://localhost:8000` in your browser.

## Unix / AWS EC2

SSH into your EC2 instance if needed

```shell 
git clone https://github.com/Trameurs/DofusFashionista.git fashionista  
echo "export PYTHONPATH=/home/<\<user\>>/fashionista/fashionistapulp" >> ~/.bashrc  
chmod 777 fashionista  
chmod 777 fashionista/fashionistapulp/fashionistapulp  
cd fashionista  
sudo python3 ./configure_fashionista_root.py -i -s -d  
```

Configure files in /etc/fashionista

```shell
python3 ./configure_fashionista.py
```

# Updating game data (scraping)

All game data (items, sets, spells, mounts and images) is refreshed with the per-version
`update_data*.py` orchestrators at the repo root. Each one runs the whole pipeline for its
version (download, transform, dump, load the DB, recipes, spells, images) and prints a
summary of warnings at the end. Run them from the repo root.

| Version      | Command                          | Data source                                        |
|--------------|----------------------------------|----------------------------------------------------|
| Dofus 3      | `python update_data.py`          | dofusdude (`api.dofusdu.de` + `dofus3-main` releases) |
| Dofus 3 Beta | `python update_data_beta.py`     | dofusdude beta release                             |
| Dofus 2      | `python update_data_dofus2.py`   | dofusdude Dofus 2 data                             |
| Dofus Retro  | `python update_data_retro.py`    | Ankama's official Retro "lang" CDN                 |
| Dofus Touch  | `python update_data_touch.py`    | the live Dofus Touch client data backend           |

Common flags: `--skip-images` / `--images-only` / `--no-resize` control the (slow) image
steps. For Dofus 3 / Beta / Dofus 2, `--version <tag>` updates the data **and** bumps the
version in `fashionista_version.py`:

```shell
python update_data.py --version 3.6.5.4        # Dofus 3
python update_data_touch.py --skip-images       # Touch, data only
```

**Dofus 3 / Beta / Dofus 2 are pinned to a data tag** (a
[`dofusdude/dofus3-main`](https://github.com/dofusdude/dofus3-main) GitHub release); pass
`--version` to move to a newer one. **Retro and Touch have no version tag**: their scrapers
always pull whatever is live right now (Ankama's Retro lang CDN / the Touch backend), so
re-running the script is how you pick up a new in-game update. Because of that, bumping
`FASHIONISTA_TOUCH_VERSION` / `FASHIONISTA_RETRO_VERSION` only makes sense right after
re-running the matching script, otherwise the label will not match the data.

The current in-game version of each variant lives in `fashionista_version.py`:

```shell
python -m fashionista_version   # prints the current Dofus 3 version
```

Each script's module docstring lists the exact per-step outputs. The standalone
`itemscraper/get_equipments*.py` scripts are the individual pipeline stages; the
`update_data*.py` wrappers call them in order, so you normally do not run them by hand.

# Run Dofus Fashionista

Running Dofus Fashionista will create/populate the database the first time you run it or recreate it if you used the Scraper.

## Unix / AWS EC2

```shell
./run_fashionista.sh
```

## Windows

```shell
run_fashionista.bat
```

## Docker (Local Development)

For Docker-based local development:

```shell
# Start services (MySQL + Django app)
./run_docker.bat

# Access app at http://localhost:8000
# Reset (with confirmation) if needed
./run_docker.bat reset CONFIRM_DELETE_DATA
```

For detailed Docker setup, see [DOCKER_SETUP.md](DOCKER_SETUP.md).

## AWS Deployment

For production deployment to AWS with RDS and ECS/Fargate:

### Quick Start
1. **Setup RDS**: Follow [AWS_MIGRATION.md](AWS_MIGRATION.md#aws-setup)
2. **Migrate Data**: Use `sync_db.py` to transfer data from local MySQL to AWS RDS
3. **Deploy App**: Follow deployment checklist in [AWS_DEPLOYMENT_CHECKLIST.md](AWS_DEPLOYMENT_CHECKLIST.md)

### Documentation
- **[AWS_MIGRATION.md](AWS_MIGRATION.md)**: Complete guide for RDS setup and data migration
- **[AWS_DEPLOYMENT_CHECKLIST.md](AWS_DEPLOYMENT_CHECKLIST.md)**: Step-by-step deployment checklist with timeline
- **[MIGRATION_EXAMPLES.md](MIGRATION_EXAMPLES.md)**: Practical examples for various migration scenarios

### Database Sync Utility

Sync local or Docker databases with AWS RDS using the reusable sync script:

```bash
# Test migration (dry-run mode)
python sync_db.py --dry-run

# Migrate local MySQL to AWS RDS
python sync_db.py \
  --source-host localhost \
  --source-port 3306 \
  --source-db fashionista_migration \
  --dest-host fashionista-mysql.xxxxx.rds.amazonaws.com \
  --dest-port 3306 \
  --dest-db fashionista

# Use environment variables
export SOURCE_DB_HOST=localhost
export DEST_DB_HOST=fashionista-mysql.xxxxx.rds.amazonaws.com
python sync_db.py
```

Features:
- Dry-run mode to test without making changes
- Automatic backup before migration
- Row-count verification after migration
- Batch processing for large datasets
- Detailed logging to `db_sync.log`
- Support for local MySQL, Docker, and AWS RDS

See [MIGRATION_EXAMPLES.md](MIGRATION_EXAMPLES.md) for more examples.

# Windows 11 troubleshooting

If the install fails on Windows 11, here are some common fixes:

1. **MySQL errors**:
   - Check that MySQL is installed and its service is running
   - Check that the MySQL user name and password are correct

2. **Dependency errors**:
   - Check that the Visual C++ Redistributable is installed
   - Check that ImageMagick is installed

3. **Port errors**:
   - If port 8000 is already in use, change the last line of run_fashionista.bat

4. **Path problems**:
   - Check that PYTHONPATH is set correctly
   - Restart your terminal after setting PYTHONPATH

# Running the tests

The Django test suite lives in `fashionsite/chardata/tests.py` and runs on an in-memory
SQLite database (it never touches your real MySQL data):

```shell
# Unix / macOS
PYTHONPATH="$PWD:$PWD/fashionistapulp" python fashionsite/manage.py test chardata --settings=fashionsite.settings_test

# Windows (PowerShell)
$env:PYTHONPATH="$PWD;$PWD/fashionistapulp"; python fashionsite/manage.py test chardata --settings=fashionsite.settings_test
```

The suite covers the solver, per-version rules (scroll caps, soft caps, stat
availability), i18n catalogues and template guards. If a run leaves
`fashionistapulp/fashionistapulp/items.db` modified, restore it with
`git checkout -- fashionistapulp/fashionistapulp/items.db`.

# Progress and Roadmap

**Current status:** the site runs all five game versions side by side, each with its own
data pipeline (see *Updating game data* above), and is mobile friendly. The live in-game
version of each variant is tracked in [fashionista_version.py](fashionista_version.py).
On top of the set optimizer it offers an inventory, a workshop, smithmagic (forgemagie),
shared builds and an encyclopedia. Original editorial `/guides/` content is published in
the five supported languages (English, French, Spanish, Portuguese, German).

- Website is fully operational
- All equipments and mounts updated to the Dofus version defined in [fashionista_version.py](fashionista_version.py)
- Sets 2.70 done
- Updated all special effects to 2.70
- Special items effects updated including Prytek
- Update UI to reflect new Dofus and Prytek
- Add Forgelance
- Update all spells to 2.70
- Update weights of special items including Dofus and Prysmaradite
- Release a beta version
- Add support for new languages
  - German
  - Italian
- Bug fixes and improvement for 3.0 release
- Windows 11 compatibility (Thanks Hoklims)
- Translate new content
  - 100% English
  - 100% French
  - 100% Spanish
  - 100% Portuguese
  - 100% German
  - 0% Italian (Ankama removed Italian language)
- Add ability to forbid prysmaradite
- Make it mobile friendly
        
- New features after 3.0 TBD
  - Shared Builds
  - Encyclopedia
  - Inventory
  - Workshop
  - Smithmagic
       
- Dofus 3 Unity
- Dofus 3 Beta
- Dofus 2
- Dofus Retro
- Dofus Touch
- Original /guides/ editorial content (5 languages)

# Reference

This is a fork of https://github.com/PiwiSlayer/DofusFashionista

Item data is sourced per game version:

- **Dofus 3 / Beta / Dofus 2**: https://github.com/dofusdude/doduapi
- **Dofus Retro**: Ankama's official Retro "lang" CDN, parsed in pure Python (see [docs/retro_data_from_ankama.md](docs/retro_data_from_ankama.md))
- **Dofus Touch**: the Touch client's own data backend, with mounts and spell data from the Touch encyclopedia/CDN (see [docs/touch_data_sources.md](docs/touch_data_sources.md))

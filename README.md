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
The Dofus Fashionista, an equipment advisor for Dofus    
This is a fork and an attempt at putting back up the website and update it to the latest version of Dofus

# Install Fashionista:

## Windows 11 (Thanks Hoklims)

Le support pour Windows 11 est maintenant pleinement fonctionnel avec une méthode d'installation simplifiée ! Suivez ces étapes pour installer le projet :

### Option la plus simple : Exécuter DofusFashionista_Windows11.bat

```shell
# Clonage du dépôt (ou téléchargez l'archive ZIP)
git clone https://github.com/Trameurs/DofusFashionista.git fashionista
cd fashionista

# Exécution du fichier batch pour Windows 11
DofusFashionista_Windows11.bat
```

Ce fichier batch va automatiquement configurer et démarrer l'application en une seule étape.

### Options alternatives d'installation

#### Option 1 : Installation avec PowerShell

```shell
# Exécution du script PowerShell amélioré pour Windows 11
powershell -ExecutionPolicy Bypass -File run_windows11.ps1
```

Ce script PowerShell robuste va :
1. Vérifier et installer tous les prérequis nécessaires
2. Configurer automatiquement l'environnement Windows
3. Optimiser les paramètres pour la compatibilité Windows 11
4. Configurer la base de données et exécuter les migrations
5. Démarrer le serveur avec gestion automatique des erreurs

#### Option 2 : Installation traditionnelle

```shell
# Exécution du script d'installation automatisé
install_windows.bat
```

Le script d'installation automatisé va:
1. Configurer l'environnement Windows correctement
2. Installer les dépendances nécessaires
3. Configurer les fichiers de configuration
4. Créer et configurer la base de données

Une fois l'installation terminée, lancez l'application avec:
```shell
run_fashionista.bat
```

Puis accédez à `http://localhost:8000` dans votre navigateur.

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

# Items scraper

The old scraper is still in the folder itemscraper, it uses the Dofus website Encyclopedia. It is veryyyy slow and the Encyclopedia is missing a lot of items, it's not viable to use it anymore. I made a new scraper that just convert the data from https://docs.dofusdu.de/ to something that store_venom.py can use.

```shell
cd itemscraper  
python3 get_equipments.py  
python3 get_equipments2.py
python3 get_equipments3.py
python3 get_equipments4.py  
python3 store_item_obtainment.py
cd ..
python3 resize_images.py
```

# Spell data & icons

Spells, damage tables, and icons all come from the data published on the [dofusdude/dofus3-main](https://github.com/dofusdude/dofus3-main) GitHub project. Everything below is scraped from those releases with the scripts in `itemscraper/`. Run the commands from the repo root.

Start by capturing the current in-game version from the centralized helper:

```powershell
$version = python -m fashionista_version
```

1. **Download the dumps**
   ```powershell
   python -m itemscraper.download_raw_data --tag $version --filter spell --filter translations --filter spell_images
   ```
   This pulls the selected release into `itemscraper/raw/<tag>/`. Set a `GITHUB_TOKEN` if GitHub rate-limits you.

2. **Transform the spells**
   ```powershell
   python -m itemscraper.get_spells --tag $version --output itemscraper/transformed_spells.json --class-output itemscraper/transformed_class_spells.json
   ```
   Generates the compact spell JSON plus the class map that mirrors the in-game spellbook.

3. **Regenerate `DAMAGE_SPELLS`**
   ```powershell
   python -m itemscraper.generate_damage_spells --class-json itemscraper/transformed_class_spells.json --spells-json itemscraper/transformed_spells.json --constants fashionistapulp/fashionistapulp/dofus_constants.py
   ```
   Fills the auto-generated block in `dofus_constants.py`.

4. **Refresh spell icons**
   ```powershell
   python -m itemscraper.download_spell_images --version $version --size 96 --scope damage --prune
   ```
   Extracts `spell_images_<size>.tar.gz`, renames each PNG with the latest English name, and copies the files to `fashionsite/chardata/static/chardata/spells` plus the mirrored `fashionsite/staticfiles/chardata/spells` directory.

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
- ✅ Dry-run mode to test without making changes
- ✅ Automatic backup before migration
- ✅ Row-count verification after migration
- ✅ Batch processing for large datasets
- ✅ Detailed logging to `db_sync.log`
- ✅ Support for local MySQL, Docker, and AWS RDS

See [MIGRATION_EXAMPLES.md](MIGRATION_EXAMPLES.md) for more examples.

# Dépannage Windows 11

Si vous rencontrez des problèmes lors de l'installation sur Windows 11, voici quelques solutions courantes:

1. **Erreurs MySQL**:
   - Vérifiez que MySQL est installé et que le service est démarré
   - Vérifiez que le nom d'utilisateur et le mot de passe MySQL sont corrects

2. **Erreurs de dépendances**:
   - Vérifiez que Visual C++ Redistributable est installé
   - Vérifiez que ImageMagick est installé

3. **Erreurs de ports**:
   - Si le port 8000 est déjà utilisé, modifiez la dernière ligne de run_fashionista.bat

4. **Problèmes de chemin**:
   - Vérifiez que PYTHONPATH est correctement défini
   - Redémarrez votre terminal après avoir défini PYTHONPATH

# Progress and Roadmap

✅ Website is fully operational     
✅ All equipments and mounts updated to the Dofus version defined in [fashionista_version.py](fashionista_version.py)      
✅ Sets 2.70 done  
✅ Updated all special effects to 2.70     
✅ Special items effects updated including Prytek         
✅ Update UI to reflect new Dofus and Prytek       
✅ Add Forgelance          
✅ Update all spells to 2.70          
✅ Update weights of special items including Dofus and Prysmaradite         
✅ Release a beta version          
✅ Add support for new languages         
       ✅ Deutsche          
       ✅ Italian          
✅ Bug fixes and improvement for 3.0 release     
✅ Windows 11 compatibility (Thanks Hoklims)         
✅ Translate new content               
       ✅ 100% English              
       ✅ 100% French               
       ✅ 100% Spanish           
       ✅ 100% Portuguese             
       ✅ 100% Deutsche              
       ❌ 0% Italian (Ankama removed Italian language)              
✅ Add ability to forbid prysmaradite       
❌ Make it mobile friendly             
        
🚧 New features after 3.0 TBD     
       ✅ Shared Builds    
       ✅ Encyclopedia     
       
✅ Dofus 3 Unity             
✅ Dofus Touch            
✅ Dofus Retro             

# Reference

This is a fork of https://github.com/PiwiSlayer/DofusFashionista      
All items data comes from https://github.com/dofusdude/doduapi

# Docker pour DofusFashionistaVanced

Ce document explique comment exécuter DofusFashionistaVanced en utilisant Docker.

## Prérequis

- Docker
- Docker Compose

## Démarrage rapide

### Pour Windows

1. Exécutez le script `run_docker.bat` en double-cliquant dessus ou à partir de la ligne de commande.

```
run_docker.bat
```

### Pour Linux/macOS

1. Rendez le script exécutable :

```bash
chmod +x run_docker.sh
```

2. Exécutez le script :

```bash
./run_docker.sh
```

## Accès à l'application

Une fois les conteneurs démarrés, l'application sera accessible à l'adresse suivante :

```
http://localhost:8000
```

## Commandes utiles

- Pour voir les logs des conteneurs :

```bash
docker-compose logs -f
```

- Pour arrêter les conteneurs :

```bash
docker-compose down
```

- Pour redémarrer les conteneurs :

```bash
docker-compose restart
```

- Pour reconstruire les images Docker (après des modifications) :

```bash
docker-compose build
```

## Structure des conteneurs

L'application utilise trois conteneurs Docker :

1. **web** - Serveur web Django avec gunicorn
2. **db** - Serveur MySQL
3. **memcached** - Serveur Memcached pour le cache

## Données persistantes

Les données de la base de données sont stockées dans un volume Docker nommé `fashionista_db_data` pour garantir la persistance entre les redémarrages.

## Aperçu du personnage

L'aperçu dessine des morceaux cuits à l'avance à partir des bundles Ankama. Les bundles (861 Mo) ne servent qu'à la cuisson et n'ont rien à faire en production ; seul le cache cuit (150 Mo) est nécessaire, dans le volume `character_cache`. Sans lui la page retombe sur l'ancien avatar, donc rien ne casse, l'aperçu est simplement absent.

Pour remplir le volume depuis une cuisson locale :

```bash
docker cp character_cache/. fashionista_web:/app/character_cache/
```

nginx sert directement les morceaux déjà présents et ne laisse passer vers Django que ceux qui restent à cuire, ce qui n'arrive qu'une fois par morceau. Après toute modification de `docker/nginx.conf`, vérifier avec `docker compose exec nginx nginx -t` avant de recharger.

## Configuration personnalisée

Pour personnaliser la configuration, vous pouvez modifier les fichiers suivants :

- `docker-compose.yml` - Configuration des services Docker
- `/etc/fashionista/gen_config.json` (dans le conteneur) - Configuration de l'application

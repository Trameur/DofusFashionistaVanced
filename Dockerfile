FROM python:3.14-slim

# Installer les dépendances système nécessaires
RUN apt-get update && apt-get install -y \
    bash \
    build-essential \
    pkg-config \
    gettext \
    mariadb-client \
    dos2unix \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Définir le répertoire de travail
WORKDIR /app

# Copier les fichiers de requirements
COPY requirements-docker.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements-docker.txt
RUN pip install --no-cache-dir gunicorn

# Copier le reste du code source
COPY . .

# Corriger les problèmes de fin de ligne CRLF sur tous les scripts
RUN find . -name "*.py" -type f -exec dos2unix {} \;
RUN find . -name "*.sh" -type f -exec dos2unix {} \;

# Rendre les scripts exécutables
RUN chmod +x *.py
RUN find . -name "*.sh" -type f -exec chmod +x {} \;

# Créer le répertoire de configuration pour Docker
RUN mkdir -p /etc/fashionista

# Créer un fichier gen_config.json pour Docker
RUN echo '{\
    "PASSWORD_RESET_SALT": "docker_salt_change_me",\
    "EMAIL_CONFIRMATION_SALT": "docker_salt_2_change_me",\
    "SECRET_KEY": "django-insecure-docker-change-me-in-production",\
    "mysql_PASSWORD": "fashionista",\
    "mysql_USER": "fashionista",\
    "EMAIL_HOST_USER": "",\
    "EMAIL_HOST_PASSWORD": "",\
    "SOCIAL_AUTH_GOOGLE_OAUTH2_KEY": null,\
    "SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET": null,\
    "SOCIAL_AUTH_FACEBOOK_KEY": null,\
    "SOCIAL_AUTH_FACEBOOK_SECRET": null,\
    "DBBACKUP_S3_ACCESS_KEY": null,\
    "DBBACKUP_S3_SECRET_KEY": null,\
    "url_captcha_secret": null,\
    "char_id_SECRET_PART_1": "docker_secret_1",\
    "char_id_SECRET_PART_2": "docker_secret_2",\
    "google_analytics_id": null,\
    "EMAIL_USE_TLS": true,\
    "EMAIL_HOST": "smtp.gmail.com",\
    "EMAIL_PORT": 587,\
    "TESTER_USERS_EMAILS": ["admin@localhost"],\
    "SUPER_USERS_EMAILS": ["admin@localhost"]\
}' > /etc/fashionista/gen_config.json

# Configurer le mode DEBUG pour Docker
RUN echo "True" > /etc/fashionista/debug_mode

# Configurer le mode serve_static pour Docker
RUN echo "True" > /etc/fashionista/serve_static

# Créer un fichier config avec le chemin du projet
RUN echo "/app" > /etc/fashionista/config

# Ajouter les répertoires au PYTHONPATH
ENV PYTHONPATH="/app:/app/fashionistapulp:/app/fashionsite"

# Copier et configurer le script d'entrée pour Docker
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN dos2unix /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Exposer le port 8000
EXPOSE 8000

# Point d'entrée: démarrer Django en développement
CMD ["python", "/app/fashionsite/manage.py", "runserver", "0.0.0.0:8000"]

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

# Copier le script de fusion de configuration
COPY merge_docker_config.py /app/merge_docker_config.py
RUN chmod +x /app/merge_docker_config.py

# Créer un fichier gen_config.json avec les valeurs par défaut en utilisant le script Python
RUN python3 /app/merge_docker_config.py

# Configurer le mode DEBUG pour Docker (production)
RUN echo "False" > /etc/fashionista/debug_mode

# Configurer le mode serve_static pour Docker
RUN echo "True" > /etc/fashionista/serve_static

# Créer un fichier config avec le chemin du projet
RUN echo "/app" > /etc/fashionista/config

# Ajouter les répertoires au PYTHONPATH
ENV PYTHONPATH="/app:/app/fashionistapulp:/app/fashionsite"

# Compiler les fichiers de traduction
RUN cd /app/fashionsite && python manage.py compilemessages

# Copier et configurer le script d'entrée pour Docker
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN dos2unix /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Exposer le port 8000
EXPOSE 8000

# Point d'entrée: démarrer Django en développement
CMD ["python", "/app/fashionsite/manage.py", "runserver", "0.0.0.0:8000"]

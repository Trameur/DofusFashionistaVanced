FROM python:3.14-slim

# System packages
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

# Working directory
WORKDIR /app

# Requirements file
COPY requirements-docker.txt .

# Python packages
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements-docker.txt

# The rest of the source code
COPY . .

# Convert CRLF line endings in every script
RUN find . -name "*.py" -type f -exec dos2unix {} \;
RUN find . -name "*.sh" -type f -exec dos2unix {} \;

# Make the scripts executable
RUN chmod +x *.py
RUN find . -name "*.sh" -type f -exec chmod +x {} \;

# Configuration folder
RUN mkdir -p /etc/fashionista

# Configuration merge script
COPY merge_docker_config.py /app/merge_docker_config.py
RUN chmod +x /app/merge_docker_config.py

# Write gen_config.json with the default values
RUN python3 /app/merge_docker_config.py

# DEBUG off for Docker (production)
RUN echo "False" > /etc/fashionista/debug_mode

# serve_static on for Docker
RUN echo "True" > /etc/fashionista/serve_static

# config file holding the project path
RUN echo "/app" > /etc/fashionista/config

# Folders on the PYTHONPATH
ENV PYTHONPATH="/app:/app/fashionistapulp:/app/fashionsite"

# Compile the translation files
RUN cd /app/fashionsite && python manage.py compilemessages

# Docker entry script
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN dos2unix /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Port 8000
EXPOSE 8000

# Default command: the Django development server
CMD ["python", "/app/fashionsite/manage.py", "runserver", "0.0.0.0:8000"]

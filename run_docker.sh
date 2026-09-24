#!/bin/bash
set -e

# Are docker and docker-compose installed
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Please install it first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose is not installed. Please install it first."
    exit 1
fi

# Configure the project for Docker
echo "Configuring the project for Docker..."
python configure_docker.py

# Build the Docker images
echo "Building the Docker images..."
docker-compose build

# Start the containers
echo "Starting the containers..."
docker-compose up -d

echo ""
echo "=================================================="
echo "DofusFashionistaVanced is now running."
echo "Open it at: http://localhost:8000"
echo "To see the logs: docker-compose logs -f"
echo "To stop: docker-compose down"
echo "=================================================="

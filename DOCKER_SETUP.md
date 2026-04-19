# Docker Setup for AWS Deployment

## Overview
Your DofusFashionistaVanced application is now configured for Docker containerization and AWS deployment.

## What Changed

### Updated Dockerfile
- **Base Image**: Changed from `python:3.9-slim` to `python:3.12-slim` (production-stable, widely AWS-compatible)
- **Removed outdated dependencies**: Removed `libdbus-1-dev`, `libdbus-glib-1-dev`, and `default-libmysqlclient-dev` (not needed with PyMySQL)
- **Added PyMySQL support**: Ensures Django can use PyMySQL for MySQL connection (already configured in `fashionsite/__init__.py`)
- **Added pymemcache**: For Django 5.1 cache compatibility
- **Pip upgrades**: Fresh setuptools and wheel for better compatibility

### Database Connectivity
- Uses **PyMySQL** (pure Python MySQL client) - works on any Linux distro, no native libs needed
- Docker entrypoint waits for MySQL service before starting Django
- Automatic migrations on container startup

### How It Works Locally
```bash
docker-compose up
```
This starts:
1. MySQL 8.0 container
2. Django app on http://localhost:8000

### Deploying to AWS

#### Option 1: AWS App Runner (Easiest)
1. Push to ECR: `docker push <account>.dkr.ecr.us-east-1.amazonaws.com/fashionista:latest`
2. Create AWS App Runner service pointing to your ECR image
3. Configure environment variables in App Runner
4. Connect RDS MySQL database (or use MySQL service in container cluster)

#### Option 2: ECS + RDS
1. Push Docker image to ECR
2. Create ECS task definition using your image
3. Create RDS MySQL database
4. Set environment variables (DB_HOST, DB_USER, DB_PASSWORD, etc.)
5. Deploy to ECS cluster

#### Option 3: EC2 with docker-compose
```bash
docker-compose up -d
```

## Key Environment Variables for AWS

```env
DB_HOST=your-rds-endpoint.amazonaws.com
DB_PORT=3306
DB_NAME=fashionista
DB_USER=fashionista
DB_PASSWORD=your-secure-password
DEBUG=False
SECRET_KEY=your-django-secret-key
```

## Production Checklist

- [ ] Update `SECRET_KEY` in settings.py (use strong random value)
- [ ] Set `DEBUG=False` in environment
- [ ] Use AWS RDS for MySQL (don't use container MySQL in production)
- [ ] Use AWS S3 for static files and media
- [ ] Configure CloudFront CDN for static content
- [ ] Set up SSL/TLS certificate (AWS Certificate Manager)
- [ ] Enable VPC security groups to restrict traffic
- [ ] Use AWS Secrets Manager for sensitive credentials
- [ ] Set up CloudWatch logging and monitoring

## Testing Locally (if Docker installed)

```bash
# Build image
docker build -t fashionista:3.12 .

# Run with docker-compose
docker-compose up

# Access app at http://localhost:8000
```

## Notes

- Your app is now **OS-independent** - runs the same on Linux (AWS), Mac, or Windows
- **No Python 3.14 issues** - Docker uses tested Python 3.12
- **All dependencies bundled** - No "works on my machine" problems
- **Gunicorn** is production web server (replaces Django dev server)
- **Automatic migrations** on startup ensure database schema is current

## Next Steps

1. Test locally with Docker (if you install Docker locally)
2. Push image to AWS ECR
3. Deploy to App Runner or ECS
4. Monitor with CloudWatch

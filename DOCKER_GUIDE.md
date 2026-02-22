# Docker Deployment Guide

Run the B2B Lead Scraper System in Docker containers for easy deployment and isolation.

## Quick Start

### 1. Build and Run (One Command)

```bash
# Build and start in foreground
docker-compose up --build

# Build and start in background (recommended)
docker-compose up -d --build
```

### 2. Check Status

```bash
# View running containers
docker-compose ps

# View logs (live tail)
docker-compose logs -f lead-scraper

# View last 100 lines
docker-compose logs --tail=100 lead-scraper
```

### 3. Stop the Container

```bash
# Graceful stop
docker-compose stop

# Stop and remove containers
docker-compose down
```

---

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB RAM available
- 10GB disk space

**Install Docker:**
- Mac: https://docs.docker.com/desktop/mac/install/
- Windows: https://docs.docker.com/desktop/windows/install/
- Linux: https://docs.docker.com/engine/install/

---

## Configuration

### Step 1: Configure .env File

```bash
# Edit .env with your API keys
nano .env

# Required:
REDDIT_API_KEYS=your_client_id:your_secret

# Recommended:
GITHUB_API_KEYS=ghp_your_token
```

### Step 2: Build the Image

```bash
docker-compose build
```

**Build options:**
```bash
# Build without cache (clean build)
docker-compose build --no-cache

# Build with specific service
docker-compose build lead-scraper
```

---

## Running the Scraper

### Background Mode (Recommended)

```bash
# Start in background
docker-compose up -d

# Monitor logs
docker-compose logs -f

# Check progress every 60 seconds
docker-compose logs -f | grep "PROGRESS REPORT"
```

### Foreground Mode (Interactive)

```bash
# Start and see output
docker-compose up

# Stop with Ctrl+C (graceful shutdown)
```

### Custom Commands

```bash
# Run tests instead of main scraper
docker-compose run lead-scraper python3 test_system.py

# Access shell inside container
docker-compose exec lead-scraper /bin/bash

# Run specific scraper (if you modified code)
docker-compose run lead-scraper python3 -c "from scrapers.hackernews_scraper import *"
```

---

## Data Persistence

All data is stored in mounted volumes:

```
./data/
├── leads.db           # SQLite database
├── exports/           # CSV exports
│   └── b2b_leads_*.csv
└── logs/              # Log files
    ├── scraper.log
    └── errors.log
```

**Volumes are persistent** - data survives container restarts and rebuilds.

---

## Database Viewer (Optional)

Access SQLite database via web interface:

### Start Database Viewer

```bash
# Start with DB viewer
docker-compose --profile debug up -d

# Access at: http://localhost:8080
```

**Features:**
- View leads in web browser
- Run SQL queries
- Export data
- Real-time updates

### Stop Database Viewer

```bash
docker-compose --profile debug down
```

---

## Monitoring

### View Progress

```bash
# Live logs
docker-compose logs -f lead-scraper

# Progress reports (every 60s)
docker-compose logs -f | grep "Total Leads"

# Error logs only
docker-compose logs -f | grep ERROR
```

### Container Stats

```bash
# CPU, Memory, Network usage
docker stats lead-scraper-system

# All containers
docker-compose stats
```

### Health Check

```bash
# Check container health
docker inspect lead-scraper-system | grep -A 10 Health
```

---

## Resource Management

### Adjust Resource Limits

Edit `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '4'      # Maximum 4 CPUs
      memory: 4G     # Maximum 4GB RAM
    reservations:
      cpus: '2'      # Minimum 2 CPUs
      memory: 2G     # Minimum 2GB RAM
```

### Reduce Resource Usage

```bash
# Lower concurrency in .env
MAX_CONCURRENT_SCRAPERS=3
CONNECTION_POOL_SIZE=50
BATCH_SIZE=50
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs lead-scraper

# Check Docker daemon
docker info

# Rebuild from scratch
docker-compose down
docker-compose build --no-cache
docker-compose up
```

### Out of Memory

```bash
# Increase memory limit in docker-compose.yml
# Or reduce in .env:
CONNECTION_POOL_SIZE=50
BATCH_SIZE=25
```

### Permission Denied on Data Folder

```bash
# Fix permissions
chmod -R 755 data/
chown -R $(whoami) data/
```

### Playwright Browser Issues

```bash
# Rebuild with Playwright
docker-compose build --no-cache lead-scraper
```

### Database Locked

```bash
# Stop all containers
docker-compose down

# Remove lock file
rm data/leads.db-wal data/leads.db-shm

# Restart
docker-compose up -d
```

---

## Production Deployment

### Using Docker Compose (Recommended)

```bash
# Production mode
docker-compose -f docker-compose.yml up -d

# With resource monitoring
docker-compose up -d && docker stats
```

### Using Docker Run

```bash
# Build image
docker build -t lead-scraper:latest .

# Run container
docker run -d \
  --name lead-scraper \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  lead-scraper:latest
```

### Environment Variables

```bash
# Pass individual variables
docker run -d \
  -e REDDIT_API_KEYS="id:secret" \
  -e GITHUB_API_KEYS="ghp_token" \
  -e MAX_LEADS_TARGET=150000 \
  lead-scraper:latest
```

---

## Automated Deployment

### With Cron (Scheduled Runs)

```bash
# Edit crontab
crontab -e

# Run daily at 2 AM
0 2 * * * cd /path/to/lead-scraper-system && docker-compose up -d

# Stop after 48 hours
0 2 */2 * * cd /path/to/lead-scraper-system && docker-compose down
```

### With CI/CD (GitHub Actions)

See `.github/workflows/docker.yml` for automated builds.

---

## Backup & Recovery

### Backup Database

```bash
# While container is running
docker-compose exec lead-scraper \
  sqlite3 /app/data/leads.db ".backup /app/data/leads_backup.db"

# Copy to host
docker cp lead-scraper-system:/app/data/leads_backup.db ./backup/
```

### Restore Database

```bash
# Stop scraper
docker-compose stop lead-scraper

# Replace database
cp backup/leads_backup.db data/leads.db

# Restart
docker-compose start lead-scraper
```

### Export Data Before Restart

```bash
# Export to CSV before rebuilding
docker-compose exec lead-scraper \
  python3 -c "from storage.export import *; asyncio.run(export_from_database(database))"
```

---

## Cleanup

### Remove Containers

```bash
# Stop and remove containers
docker-compose down

# Remove containers and volumes
docker-compose down -v

# Remove containers, volumes, and images
docker-compose down -v --rmi all
```

### Clean Docker System

```bash
# Remove unused data
docker system prune

# Remove everything (careful!)
docker system prune -a --volumes
```

### Keep Data, Remove Containers

```bash
# This preserves ./data/ folder
docker-compose down
docker-compose up -d --build
```

---

## Performance Tips

1. **Use SSD** for `./data/` folder
2. **Increase Docker RAM** to 4GB+ in Docker Desktop settings
3. **Reduce concurrency** if CPU usage is high
4. **Use host network** for better performance (remove `network_mode: bridge`)
5. **Mount tmpfs** for logs (faster writes)

---

## Security Best Practices

✅ **Don't commit .env** to version control
✅ **Use secrets** for API keys in production
✅ **Run as non-root** user (add USER directive in Dockerfile)
✅ **Scan images** for vulnerabilities: `docker scan lead-scraper:latest`
✅ **Update base images** regularly
✅ **Use specific tags** instead of `latest`

---

## Commands Cheat Sheet

```bash
# Build
docker-compose build

# Start
docker-compose up -d

# Stop
docker-compose stop

# Restart
docker-compose restart

# Logs
docker-compose logs -f

# Shell access
docker-compose exec lead-scraper bash

# Run tests
docker-compose run lead-scraper python3 test_system.py

# View stats
docker stats lead-scraper-system

# Remove everything
docker-compose down -v
```

---

## Next Steps

1. Configure `.env` with API keys
2. Build the image: `docker-compose build`
3. Start the scraper: `docker-compose up -d`
4. Monitor progress: `docker-compose logs -f`
5. Access exports: `./data/exports/`

---

**Happy Scraping! 🐳**

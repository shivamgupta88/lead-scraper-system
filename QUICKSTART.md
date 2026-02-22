# Quick Start Guide

Get the B2B Lead Scraper System up and running in 5 minutes.

## Prerequisites

- Python 3.9 or higher
- Git
- Internet connection

## Step 1: Clone and Setup

```bash
# Clone repository
git clone https://github.com/shivamgupta88/lead-scraper-system.git
cd lead-scraper-system

# Run automated setup
./setup.sh

# Or manually:
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

## Step 2: Configure API Keys

Edit `.env` file with your API credentials:

```bash
# Required for full functionality
REDDIT_API_KEYS=your_client_id:your_client_secret
GITHUB_API_KEYS=ghp_your_github_token
PRODUCTHUNT_API_KEYS=your_producthunt_token
WEBSHARE_API_KEY=your_webshare_key

# Optional: Adjust settings
MAX_LEADS_TARGET=150000
MIN_RELEVANCE_SCORE=5
```

### Getting API Keys (5 minutes each)

**Reddit:**
1. Go to https://www.reddit.com/prefs/apps
2. Click "Create App" or "Create Another App"
3. Select "script" type
4. Copy `client_id` and `client_secret`
5. Format: `client_id:client_secret`

**GitHub:**
1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes: `public_repo`, `read:user`
4. Copy token (starts with `ghp_`)

**Product Hunt:**
1. Go to https://www.producthunt.com/v2/oauth/applications
2. Create new application
3. Copy API token

**Webshare (Optional, for proxies):**
1. Sign up at https://www.webshare.io/
2. Get free tier (10 proxies)
3. Copy API key from dashboard

## Step 3: Test the System

```bash
# Activate virtual environment
source venv/bin/activate

# Run tests
python test_system.py

# Expected output: "ALL TESTS PASSED ✓"
```

## Step 4: Run the Scraper

```bash
python main.py
```

### What Happens Next

1. **Initialization** (10-30 seconds)
   - Database creation
   - Proxy pool initialization
   - API key validation
   - Rate limiter setup

2. **Scraping** (continuous)
   - All 6 sources start scraping concurrently
   - Progress updates every 60 seconds
   - Automatic checkpoint saving

3. **Processing** (real-time)
   - Email validation
   - Deduplication
   - ICP scoring (1-10 scale)
   - Database storage

4. **Completion**
   - Final statistics report
   - CSV export to `data/exports/`
   - Database saved to `data/leads.db`

## Step 5: Monitor Progress

Progress updates appear every 60 seconds:

```
╔══════════════════════════════════════════════════════════════╗
║                    SCRAPING PROGRESS REPORT                  ║
╠══════════════════════════════════════════════════════════════╣
║ Total Leads: 15,234 / 150,000 (10.2%)
║ Leads/Hour: 3,450
║ Time Elapsed: 4:24:15
║ ETA: 39:30:00
```

## Step 6: Stop Gracefully

Press `Ctrl+C` to stop:
- Saves current progress
- Completes processing queue
- Exports current data
- Creates checkpoint for resume

## Step 7: Review Results

```bash
# CSV output
ls -lh data/exports/

# View in spreadsheet
open data/exports/b2b_leads_*.csv

# Database
sqlite3 data/leads.db "SELECT COUNT(*) FROM leads;"
```

## Common Issues

### No leads being scraped
```bash
# Check API keys
grep API_KEYS .env

# Check logs
tail -f data/logs/scraper.log
```

### Rate limited
```bash
# Add more API keys or reduce rate limits in .env
RATE_LIMIT_REDDIT=30  # Reduce from 60
```

### Out of memory
```bash
# Reduce batch size in .env
BATCH_SIZE=50  # Reduce from 100
```

## Resume Interrupted Scraping

The system automatically resumes from last checkpoint:

```bash
# Just run again
python main.py

# Checkpoint data in database
sqlite3 data/leads.db "SELECT * FROM scrape_sessions;"
```

## Advanced Usage

### Export Only High-Quality Leads (Score ≥ 7)

Edit `.env`:
```bash
MIN_RELEVANCE_SCORE=7
```

### Target Specific Sources

Comment out unwanted scrapers in `core/orchestrator.py`:
```python
self.scrapers = [
    HackerNewsScraper(*scraper_args),
    # RedditScraper(*scraper_args),  # Disabled
    GitHubScraper(*scraper_args),
]
```

### Adjust Concurrency

Edit `.env`:
```bash
MAX_CONCURRENT_SCRAPERS=3  # Reduce from 6
CONNECTION_POOL_SIZE=50    # Reduce from 100
```

## Expected Results

After 48 hours of continuous scraping:

- **150,000+** total leads
- **50,000+** high-quality leads (score ≥ 7)
- **~3,000+** leads/hour average
- **CSV file** ready for import to CRM

## Support

- Documentation: [README.md](README.md)
- Issues: https://github.com/shivamgupta88/lead-scraper-system/issues
- Logs: `data/logs/scraper.log`

## Next Steps

1. Import CSV to your CRM
2. Filter by relevance_score
3. Enrich with additional data
4. Start outreach campaigns

---

**Happy Scraping! 🚀**

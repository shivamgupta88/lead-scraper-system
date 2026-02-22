# Multi-Source B2B Lead Scraper System

A production-ready lead scraping system designed to extract 150,000+ B2B SaaS leads in 48 hours from multiple free sources.

## Features

- **Multi-Source Scraping**: HackerNews, Reddit, Product Hunt, GitHub, Wellfound, TechCrunch
- **Async/Concurrent**: High-performance async scraping with connection pooling
- **Proxy Rotation**: Automatic proxy rotation with health monitoring (Webshare.io)
- **API Key Management**: Multi-key rotation per source with rate limit handling
- **Adaptive Rate Limiting**: Token bucket algorithm with automatic adjustment
- **Smart Deduplication**: Hash-based and email deduplication
- **ICP Scoring**: Relevance scoring (1-10) based on ideal customer profile
- **Data Validation**: Email validation, MX record checks, URL validation
- **Checkpoint Recovery**: Resume scraping from last checkpoint
- **CSV Export**: Streaming export for large datasets

## Architecture

```
Scrapers → scraping_queue → Processing Workers → processing_queue → Storage Workers → SQLite → CSV
```

### Tech Stack

- Python 3.9+
- asyncio, aiohttp, aiosqlite
- asyncpraw (Reddit), PyGithub, Playwright
- BeautifulSoup4, Pydantic, loguru

## Installation

1. **Clone the repository**
```bash
git clone https://github.com/shivamgupta88/lead-scraper-system.git
cd lead-scraper-system
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Install Playwright browsers** (for Wellfound scraping)
```bash
playwright install chromium
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your API keys and settings
```

## Configuration

Edit `.env` file with your API keys:

```bash
# Webshare.io Proxies
WEBSHARE_API_KEY=your_api_key_here

# API Keys (comma-separated for rotation)
REDDIT_API_KEYS=client_id1:client_secret1,client_id2:client_secret2
PRODUCTHUNT_API_KEYS=token1,token2,token3
GITHUB_API_KEYS=ghp_token1,ghp_token2,ghp_token3

# Scraping Config
MAX_LEADS_TARGET=150000
MIN_RELEVANCE_SCORE=5
```

### Getting API Keys

- **Reddit**: https://www.reddit.com/prefs/apps (create app, get client_id and client_secret)
- **Product Hunt**: https://www.producthunt.com/v2/oauth/applications
- **GitHub**: https://github.com/settings/tokens (personal access token)
- **Webshare**: https://www.webshare.io/ (proxy service)

## Usage

### Run the scraper

```bash
python main.py
```

The system will:
1. Initialize all scrapers and components
2. Start scraping from all sources concurrently
3. Process, validate, score, and deduplicate leads
4. Store in SQLite database with checkpoints
5. Export to CSV when complete

### Monitor Progress

Progress is reported every 60 seconds:
- Total leads scraped / target (%)
- Leads per hour
- ETA
- Per-source breakdown
- Component statistics

### Graceful Shutdown

Press `Ctrl+C` to gracefully shutdown:
- Stops accepting new scraping tasks
- Drains processing queues
- Flushes remaining data to database
- Saves checkpoints
- Exports current data to CSV

### Resume from Checkpoint

The system automatically resumes from the last checkpoint if interrupted. Checkpoint data is saved every 100 leads per source.

## Output

### CSV Export

Exported to `data/exports/b2b_leads_YYYYMMDD_HHMMSS.csv`

**Fields:**
- email
- name
- company
- role
- linkedin_url
- website
- location
- source
- signal_type
- date_found
- relevance_score

### Database

SQLite database at `data/leads.db` contains:
- `leads` - All scraped leads
- `scrape_sessions` - Checkpoint data
- `error_log` - Error tracking

## Relevance Scoring

Leads are scored 1-10 based on ICP matching:

1. **ICP Match (40%)**: Founder/CEO title, B2B SaaS company, 1-200 employees
2. **Hiring Signals (25%)**: Active job posts, "We're hiring", team expansion
3. **Funding Signals (20%)**: Recent funding $500K-$10M, investor-backed
4. **Engagement (10%)**: Active LinkedIn/Twitter, content creation
5. **Content Relevance (5%)**: Target keyword matches

**Export Filter**: Only leads with score ≥ 5 are exported by default.

## Source-Specific Details

### HackerNews
- Uses Algolia HN API (no auth required)
- Scrapes "Who's Hiring" threads
- Extracts emails from comments and profiles
- ~10,000+ leads potential

### Reddit
- Requires Reddit API credentials
- Subreddits: r/SaaS, r/startups, r/entrepreneur, etc.
- Searches for hiring posts and founder AMAs
- ~20,000+ leads potential

### GitHub
- Optional auth (higher rate limits with token)
- Searches for SaaS/B2B repositories
- Extracts emails from profiles and READMEs
- ~15,000+ leads potential

### Product Hunt
- Requires Product Hunt API token
- Scrapes recent SaaS/B2B launches
- Extracts maker profiles and emails
- ~5,000+ leads potential

### TechCrunch
- RSS feed scraping (no auth)
- Focuses on funding announcements
- Scrapes company websites for contact info
- ~3,000+ leads potential

### Wellfound (AngelList)
- Uses Playwright for JS rendering
- Scrapes job listings and company profiles
- ~10,000+ leads potential

## Performance

- **Target**: 150,000 leads in 48 hours
- **Expected Rate**: ~3,125 leads/hour
- **Concurrency**: 6 scrapers + 3 processors + 2 storage workers
- **Memory**: ~500MB-1GB during operation
- **Network**: Bandwidth depends on proxy usage

## Error Handling

- Automatic retry with exponential backoff
- Proxy rotation on failure
- API key rotation on rate limits
- Circuit breaker pattern (5 failures → 60s timeout)
- All errors logged to database and log files

## Troubleshooting

### "No leads being scraped"
- Check API keys in `.env`
- Verify network connectivity
- Check rate limiter settings

### "Rate limited too quickly"
- Reduce rate limits in `.env`
- Add more API keys for rotation
- Enable proxy usage

### "Database locked"
- SQLite uses WAL mode for better concurrency
- Reduce `BATCH_SIZE` if issues persist

### "Memory usage too high"
- Reduce `CONNECTION_POOL_SIZE`
- Reduce queue sizes in orchestrator
- Enable strict deduplication

## Development

### Project Structure
```
lead-scraper-system/
├── config/          # Configuration and settings
├── core/            # Core infrastructure (proxy, rate limiter, etc.)
├── scrapers/        # Source-specific scrapers
├── processors/      # Data processing (validation, scoring, dedup)
├── storage/         # Database and CSV export
├── utils/           # Utilities (logging, metrics, validators)
├── data/            # SQLite DB, exports, logs
└── main.py          # Entry point
```

### Adding a New Scraper

1. Create `scrapers/your_scraper.py`
2. Inherit from `BaseScraper`
3. Implement `scrape()` and `extract_lead_data()`
4. Add to `core/orchestrator.py`
5. Add configuration to `config/sources_config.py`

## License

MIT License - See LICENSE file for details

## Contributing

Pull requests welcome! Please ensure:
- Code follows existing patterns
- Add tests for new features
- Update documentation

## Support

For issues and questions:
- GitHub Issues: https://github.com/shivamgupta88/lead-scraper-system/issues

## Disclaimer

This tool is for educational and research purposes. Ensure compliance with:
- Website Terms of Service
- API rate limits and usage policies
- Data privacy regulations (GDPR, CCPA, etc.)
- Anti-scraping laws in your jurisdiction

Use responsibly and ethically.

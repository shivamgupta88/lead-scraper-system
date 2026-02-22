# API Keys Setup Guide

Quick reference for obtaining API keys needed for the Lead Scraper System.

## Required API Keys

### 1. Reddit API (REQUIRED for Reddit scraping)

**Time to get: 2 minutes**

**Steps:**
1. Go to https://www.reddit.com/prefs/apps
2. Scroll to bottom and click **"Create App"** or **"Create Another App"**
3. Fill in the form:
   - **name**: `Lead Scraper` (or any name)
   - **App type**: Select **"script"**
   - **description**: `B2B lead scraping` (optional)
   - **about url**: Leave blank
   - **redirect uri**: `http://localhost:8080` (required but not used)
4. Click **"Create app"**
5. Copy the credentials:
   - **client_id**: String under "personal use script" (e.g., `abc123def456`)
   - **client_secret**: String next to "secret" (e.g., `xyz789uvw012`)

**Format in .env:**
```bash
REDDIT_API_KEYS=abc123def456:xyz789uvw012
```

**For multiple keys (rotation):**
```bash
REDDIT_API_KEYS=client_id1:secret1,client_id2:secret2
```

---

## Optional API Keys (Recommended)

### 2. GitHub API (Recommended - 80x higher rate limits)

**Time to get: 1 minute**

**Without token:** 60 requests/hour
**With token:** 5,000 requests/hour

**Steps:**
1. Go to https://github.com/settings/tokens
2. Click **"Generate new token"** → **"Generate new token (classic)"**
3. Fill in the form:
   - **Note**: `Lead Scraper`
   - **Expiration**: 90 days (or custom)
   - **Scopes**: Select:
     - ✅ `public_repo`
     - ✅ `read:user`
4. Click **"Generate token"**
5. Copy the token (starts with `ghp_`)

**⚠️ Important:** Save it immediately - you won't see it again!

**Format in .env:**
```bash
GITHUB_API_KEYS=ghp_abc123def456xyz789
```

**For multiple keys:**
```bash
GITHUB_API_KEYS=ghp_token1,ghp_token2,ghp_token3
```

---

### 3. Product Hunt API (Optional)

**Time to get: 3 minutes**

**Steps:**
1. Go to https://www.producthunt.com/v2/oauth/applications
2. Sign in to Product Hunt
3. Click **"Create an application"**
4. Fill in the form:
   - **Name**: `Lead Scraper`
   - **Redirect URI**: `http://localhost:8080`
5. Click **"Create application"**
6. Copy the **API Token**

**Format in .env:**
```bash
PRODUCTHUNT_API_KEYS=your_token_here
```

**For multiple keys:**
```bash
PRODUCTHUNT_API_KEYS=token1,token2,token3
```

---

### 4. Webshare.io Proxies (Optional - prevents IP bans)

**Time to get: 3 minutes**
**Free tier:** 10 proxies, 250MB bandwidth

**Steps:**
1. Go to https://www.webshare.io/
2. Click **"Sign Up"** and create account
3. Verify email
4. Go to dashboard: https://proxy.webshare.io/
5. Navigate to **API** section
6. Copy your **API Token**

**Format in .env:**
```bash
WEBSHARE_API_KEY=your_api_key_here
PROXY_COUNT=10
```

---

## Sources That Work WITHOUT API Keys

These scrapers work out of the box:

✅ **HackerNews** - Uses public Algolia API
✅ **TechCrunch** - RSS feed scraping
✅ **Wellfound** - Web scraping (may be rate limited)

---

## Testing Your Configuration

After adding API keys to `.env`, test them:

```bash
# Test all components
python3 test_system.py

# Expected output:
# ✓ Database tests passed
# ✓ Validator tests passed
# ✓ Scorer tests passed
# ✓ Deduplicator tests passed
```

---

## Priority Setup (Minimal Configuration)

If you want to start quickly with minimal setup:

**Minimum Required:**
```bash
# Just Reddit (works alone)
REDDIT_API_KEYS=your_client_id:your_secret

# Everything else uses defaults
```

**Recommended Setup:**
```bash
# Reddit + GitHub (best coverage)
REDDIT_API_KEYS=your_client_id:your_secret
GITHUB_API_KEYS=ghp_your_token
```

**Full Setup:**
```bash
# All sources for maximum leads
REDDIT_API_KEYS=client_id:secret
GITHUB_API_KEYS=ghp_token
PRODUCTHUNT_API_KEYS=ph_token
WEBSHARE_API_KEY=webshare_key
```

---

## Rate Limit Summary

| Source | No Auth | With Auth | Multiple Keys |
|--------|---------|-----------|---------------|
| **HackerNews** | 100/min | N/A | N/A |
| **Reddit** | ❌ Required | 60/min | ✅ Rotates |
| **GitHub** | 60/hour | 5000/hour | ✅ Rotates |
| **Product Hunt** | ❌ Required | 100/hour | ✅ Rotates |
| **TechCrunch** | 30/min | N/A | N/A |
| **Wellfound** | 20/min | N/A | N/A |

---

## Troubleshooting

### "Invalid Reddit credentials"
- Double-check client_id and client_secret
- Ensure format is: `client_id:client_secret`
- No spaces around the colon

### "GitHub rate limit exceeded"
- Add GitHub token to `.env`
- Or add multiple tokens for rotation

### "Product Hunt authentication failed"
- Verify token is correct
- Check token hasn't expired
- Try regenerating the token

### "No proxies available"
- Webshare key may be invalid
- Check if you've exceeded bandwidth limit
- System works without proxies (just slower)

---

## Security Notes

⚠️ **Never commit `.env` to Git!**

The `.gitignore` already excludes it, but be careful:
- Don't share `.env` file
- Don't paste keys in public forums
- Regenerate keys if accidentally exposed
- Use separate keys for testing vs production

---

## Next Steps

1. ✅ Add API keys to `.env`
2. ✅ Run `python3 test_system.py`
3. ✅ Run `python3 main.py`
4. ✅ Monitor progress (updates every 60s)
5. ✅ Check `data/exports/` for CSV output

---

**Need help?** Check the [QUICKSTART.md](QUICKSTART.md) or [README.md](README.md)

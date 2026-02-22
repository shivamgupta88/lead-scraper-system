# CSV Output Format Specification

## Required Fields (7 Columns)

The system exports leads in CSV format with the following columns:

| # | Field Name | Description | Example | Source |
|---|------------|-------------|---------|--------|
| 1 | **Contact person name** | Full name of the lead | Archit Agarwal | Extracted from posts/profiles |
| 2 | **Contact person designation** | Job title/role | Founder & CEO | From profile or inferred |
| 3 | **Contact person email** | Email address | archit@sanfe.in | Validated email only |
| 4 | **Post content** | Relevant post/comment text | "Looking for AI automation..." | Max 1000 characters |
| 5 | **Buying intent** | Signal type or buying indicator | hiring, funding, product_launch | Auto-detected |
| 6 | **Company** | Company name | Sanfe | Extracted from post/profile |
| 7 | **Geography** | Location/country | India | Extracted if available |

---

## Post Content Requirements

**Must contain at least one ICP keyword:**

### Target Keywords (from ICP config):
- LinkedIn ghostwriting
- AI content automation
- Personal branding
- Thought leadership
- SaaS GTM
- LinkedIn marketing
- AI content marketing
- Content automation system
- SaaS LinkedIn growth
- AI growth system
- B2B content strategy
- Founder branding
- Executive branding

**Post content features:**
- Maximum length: 1000 characters (automatically truncated)
- Extracted from: Comments, posts, profiles, job descriptions
- Filtered for relevance using ICP keywords
- Only posts with relevant keywords are included

---

## Buying Intent Types

Automatically detected from context:

| Intent Type | Description | Examples |
|-------------|-------------|----------|
| **hiring** | Company is actively hiring | "We're hiring", "Join our team", Job posts |
| **funding** | Recently raised funding | "Raised $2M", "Series A", "Seed round" |
| **product_launch** | Launched new product | "We just launched", "New product" |
| **recent_launch** | Recently launched (Product Hunt) | Within 7 days of launch |
| **ama** | Founder AMA/discussion | Reddit AMA threads |
| **general** | Other buying signals | Content showing interest |

---

## Geography Detection

**Sources:**
- Reddit: User flair, post content
- LinkedIn: Profile location
- GitHub: Profile location
- Product Hunt: Inferred from timezone/content
- TechCrunch: Company location in article

**Format:** Country name or "City, Country"

---

## Sample CSV Output

```csv
Contact person name,Contact person designation,Contact person email,Post content,Buying intent,Company,Geography
Archit Agarwal,Founder,archit@sanfe.in,"Looking for AI automation and conversational commerce agencies for WhatsApp AI Agent, Instagram DM automation, and CRM integrations. Need real case studies.",hiring,Sanfe,India
Jane Smith,CEO,jane@techstartup.com,"Just raised $2M in seed funding for our B2B SaaS platform. Building LinkedIn marketing automation tools for founders.",funding,TechStartup,USA
```

---

## Data Quality Filters

### Email Validation:
✅ Valid format (RFC 5322)
✅ MX record exists (optional in strict mode)
✅ Not a placeholder (no example.com, test.com)
✅ Not noreply/no-reply addresses
✅ Corporate emails preferred

### Required Field Validation:
- All 7 fields must be present
- Name, designation, email, company cannot be "Unknown"
- Minimum 2 characters for name/company

### Relevance Scoring:
- Only leads with score ≥ 5 are exported (configurable)
- Score 1-10 based on ICP matching:
  - **ICP Match (40%)**: Title keywords, company type, size
  - **Hiring Signals (25%)**: Active job posts, team expansion
  - **Funding Signals (20%)**: Recent funding announcements
  - **Engagement (10%)**: Social media activity
  - **Content Relevance (5%)**: Target keyword matches

---

## Deduplication

Prevents duplicate leads in export:

1. **Email-based**: Same email from same source = duplicate
2. **Hash-based**: Email + Company + Name hash comparison
3. **Pair-based**: Email + Company combination

**Result:** Each unique person appears only once per source

---

## Export Configuration

### In `.env` file:

```bash
# Minimum relevance score for export (1-10)
MIN_RELEVANCE_SCORE=5

# Export path
EXPORT_PATH=./data/exports/

# Filename format (timestamp auto-added)
EXPORT_FILENAME=b2b_leads_{timestamp}.csv
```

### Export Location:
```
./data/exports/b2b_leads_YYYYMMDD_HHMMSS.csv
```

---

## Post Content Examples

### Good Examples (Will be exported):

✅ **Hiring Signal:**
```
"We're hiring for our B2B SaaS team! Looking for growth marketers
experienced in LinkedIn marketing and AI content automation."
```

✅ **Funding Signal:**
```
"Just closed our $3M seed round! Building AI-powered LinkedIn
ghostwriting platform for B2B founders. Hiring engineers."
```

✅ **Product Signal:**
```
"Launching our new personal branding platform for SaaS founders.
Helps with thought leadership content automation."
```

### Bad Examples (Will be filtered out):

❌ No relevant keywords:
```
"Great weather today! Love working from the beach."
```

❌ No buying intent:
```
"Random tech discussion without any business context."
```

---

## Comparison with Sample Data

Your sample CSV (`Warm Lead Data - Sheet1.csv`) has **2,378 leads** with this exact format.

### Matching Fields:
| Sample CSV | Our System | Status |
|------------|------------|--------|
| Name | Contact person name | ✅ Match |
| Designation | Contact person designation | ✅ Match |
| Email | Contact person email | ✅ Match |
| Post Content | Post content | ✅ Match |
| Buying Intent | Buying intent | ✅ Match |
| Company | Company | ✅ Match |
| Geography | Geography | ✅ Match |

**Note:** We removed "Sr No." as it's auto-generated during export.

---

## Integration with Scrapers

Each scraper extracts fields as follows:

| Scraper | Name Source | Designation | Email | Post Content | Geography |
|---------|-------------|-------------|-------|--------------|-----------|
| **HackerNews** | Username/Profile | From bio/context | Comments/Bio | Comment text | Profile |
| **Reddit** | Username/Post | Flair/Context | Post/Comments | Post + comments | Flair/Profile |
| **GitHub** | Profile name | Repo owner/Contributor | Public email | README | Profile |
| **Product Hunt** | Maker name | Headline | Website scrape | Product description | Inferred |
| **TechCrunch** | Article extraction | From article | Company website | Article excerpt | Article |
| **Wellfound** | Profile | Job title | Jobs page | Job description | Job location |

---

## Database Schema

SQLite table structure:

```sql
CREATE TABLE leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    name TEXT NOT NULL,
    designation TEXT NOT NULL,
    company TEXT NOT NULL,
    geography TEXT,
    post_content TEXT,
    buying_intent TEXT,
    linkedin_url TEXT,
    website TEXT,
    source TEXT NOT NULL,
    signal_type TEXT,
    date_found TEXT NOT NULL,
    relevance_score INTEGER DEFAULT 0,
    score_breakdown TEXT,
    content_hash TEXT UNIQUE NOT NULL,
    raw_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(email, source)
);
```

---

## Usage

### View CSV in Excel/Google Sheets:
1. Open `data/exports/b2b_leads_*.csv`
2. Import as CSV with UTF-8 encoding
3. Sort by any column
4. Filter as needed

### Import to CRM:
Most CRMs support CSV import with column mapping:
1. Upload CSV file
2. Map "Contact person email" → Email
3. Map "Contact person name" → Name
4. Map other fields accordingly

---

## Quality Metrics

Expected quality from 150,000 leads:

- **High Quality (Score 7-10)**: ~50,000 leads (33%)
- **Medium Quality (Score 5-6)**: ~60,000 leads (40%)
- **Filtered Out (Score <5)**: ~40,000 leads (27%)

**Exported leads:** ~110,000 with score ≥ 5

---

## Keyword Filtering

Post content MUST contain at least one keyword from ICP config for relevance.

**Example filtering:**

✅ "Looking for LinkedIn marketing automation" → Contains "LinkedIn marketing" → ✅ Exported

❌ "We sell shoes online" → No ICP keywords → ❌ Filtered out

---

Ready to scrape leads with proper CSV format! 🚀

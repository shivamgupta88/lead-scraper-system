"""ICP (Ideal Customer Profile) configuration for lead scoring"""

# Target keywords for content relevance scoring
TARGET_KEYWORDS = [
    "linkedin ghostwriting",
    "AI content automation",
    "personal branding",
    "thought leadership",
    "SaaS GTM",
    "LinkedIn marketing",
    "AI content marketing",
    "content automation system",
    "SaaS LinkedIn growth",
    "AI growth system",
    "content marketing automation",
    "B2B content strategy",
    "founder branding",
    "executive branding"
]

# Title keywords for ICP matching
TITLE_KEYWORDS = {
    "founder": 4,
    "co-founder": 4,
    "ceo": 4,
    "chief executive": 4,
    "cto": 3,
    "chief technology": 3,
    "cmo": 3,
    "chief marketing": 3,
    "vp marketing": 2,
    "head of marketing": 2,
    "marketing director": 2,
    "growth lead": 2,
    "head of growth": 2
}

# Company type keywords
COMPANY_TYPE_KEYWORDS = {
    "saas": 2,
    "b2b": 2,
    "software": 1,
    "platform": 1,
    "enterprise": 1,
    "startup": 1
}

# Company size ranges (employees)
COMPANY_SIZE_SCORES = {
    (1, 10): 2,
    (11, 50): 2,
    (51, 200): 2,
    (201, 500): 1,
    (501, 1000): 0
}

# Hiring signal keywords
HIRING_KEYWORDS = {
    "we're hiring": 2.5,
    "we are hiring": 2.5,
    "join our team": 2.5,
    "now hiring": 2.5,
    "hiring": 1.5,
    "open positions": 1.5,
    "careers": 1,
    "job opening": 1.5,
    "looking for": 1,
    "team expansion": 1,
    "growing team": 1
}

# Funding signal keywords
FUNDING_KEYWORDS = {
    "raised": 2,
    "funding": 2,
    "series a": 2,
    "series b": 2,
    "seed round": 1.5,
    "pre-seed": 1,
    "investor": 1,
    "venture backed": 1,
    "vc backed": 1,
    "bootstrapped": 0.5,
    "profitable": 0.5
}

# Engagement signal keywords
ENGAGEMENT_KEYWORDS = {
    "active linkedin": 1,
    "posting regularly": 1,
    "thought leader": 0.5,
    "speaker": 0.5,
    "podcast": 0.5,
    "newsletter": 0.5,
    "content creator": 1
}

# Scoring weights (must sum to 100)
SCORING_WEIGHTS = {
    "icp_match": 40,        # Title + Company type + Size
    "hiring_signals": 25,    # Active job posts, "We're hiring"
    "funding_signals": 20,   # Recent funding, investor-backed
    "engagement": 10,        # Social activity, content creation
    "content_relevance": 5   # Target keyword matches
}

# Minimum score thresholds
MIN_SCORE_EXPORT = 5  # Minimum score to include in export
MIN_SCORE_HIGH_QUALITY = 7  # Threshold for high-quality leads
MIN_SCORE_HOT = 9  # Threshold for hot leads


def get_company_size_score(employee_count: int) -> int:
    """Get score based on company size"""
    for (min_size, max_size), score in COMPANY_SIZE_SCORES.items():
        if min_size <= employee_count <= max_size:
            return score
    return 0


def calculate_keyword_score(text: str, keyword_dict: dict) -> float:
    """Calculate score based on keyword matches in text"""
    if not text:
        return 0.0

    text_lower = text.lower()
    total_score = 0.0

    for keyword, score in keyword_dict.items():
        if keyword.lower() in text_lower:
            total_score += score

    return total_score

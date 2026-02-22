"""Per-source configuration for rate limits and endpoints"""

SOURCE_CONFIG = {
    "hackernews": {
        "rate_limit": 100,  # requests per minute
        "endpoints": {
            "search": "http://hn.algolia.com/api/v1/search",
            "item": "https://hacker-news.firebaseio.com/v0/item/{}.json",
            "user": "https://hacker-news.firebaseio.com/v0/user/{}.json"
        },
        "search_keywords": [
            "hiring", "founder", "YC", "raised", "we're hiring",
            "SaaS", "B2B", "startup", "looking for", "join us"
        ],
        "requires_auth": False,
        "use_proxy": False
    },
    "reddit": {
        "rate_limit": 60,  # requests per minute
        "subreddits": [
            "SaaS", "startups", "entrepreneur", "marketing",
            "forhire", "startupjobs", "b2bmarketing", "digitalnomad"
        ],
        "search_keywords": [
            "hiring", "founder", "AMA", "launched", "we're hiring",
            "looking for", "join our team", "B2B SaaS"
        ],
        "requires_auth": True,
        "use_proxy": True
    },
    "producthunt": {
        "rate_limit": 100,  # requests per hour (converted to per minute)
        "endpoints": {
            "graphql": "https://www.producthunt.com/frontend/graphql"
        },
        "filters": {
            "topics": ["saas", "b2b", "marketing", "productivity"],
            "days_old": 30
        },
        "requires_auth": True,
        "use_proxy": True
    },
    "github": {
        "rate_limit": 300,  # requests per minute (5000/hour with auth)
        "search_queries": [
            "SaaS marketing automation",
            "B2B content platform",
            "LinkedIn automation",
            "AI content generation",
            "growth marketing tool"
        ],
        "filters": {
            "min_stars": 10,
            "recent_activity_days": 90,
            "has_readme": True
        },
        "requires_auth": True,
        "use_proxy": False
    },
    "wellfound": {
        "rate_limit": 20,  # requests per minute
        "base_url": "https://wellfound.com",
        "search_params": {
            "job_types": ["full-time"],
            "company_sizes": ["1-10", "11-50", "51-200"],
            "tags": ["saas", "b2b", "marketing"]
        },
        "requires_auth": False,
        "use_proxy": True,
        "use_playwright": True
    },
    "techcrunch": {
        "rate_limit": 30,  # requests per minute
        "endpoints": {
            "rss": "https://techcrunch.com/feed/",
            "category": "https://techcrunch.com/category/startups/"
        },
        "keywords": [
            "raises", "funding", "Series A", "Series B", "seed round",
            "B2B", "SaaS", "marketing platform"
        ],
        "requires_auth": False,
        "use_proxy": True
    }
}


def get_source_config(source_name: str) -> dict:
    """Get configuration for a specific source"""
    return SOURCE_CONFIG.get(source_name.lower(), {})


def get_all_sources() -> list:
    """Get list of all configured sources"""
    return list(SOURCE_CONFIG.keys())

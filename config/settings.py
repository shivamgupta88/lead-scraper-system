from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Database
    database_path: str = Field(default="./data/leads.db", env="DATABASE_PATH")

    # Webshare.io Proxies
    webshare_api_key: str = Field(default="", env="WEBSHARE_API_KEY")
    proxy_count: int = Field(default=50, env="PROXY_COUNT")

    # API Keys (comma-separated)
    reddit_api_keys: str = Field(default="", env="REDDIT_API_KEYS")
    producthunt_api_keys: str = Field(default="", env="PRODUCTHUNT_API_KEYS")
    github_api_keys: str = Field(default="", env="GITHUB_API_KEYS")

    # Rate Limits (requests per minute)
    rate_limit_hackernews: int = Field(default=100, env="RATE_LIMIT_HACKERNEWS")
    rate_limit_reddit: int = Field(default=60, env="RATE_LIMIT_REDDIT")
    rate_limit_producthunt: int = Field(default=100, env="RATE_LIMIT_PRODUCTHUNT")
    rate_limit_github: int = Field(default=300, env="RATE_LIMIT_GITHUB")
    rate_limit_wellfound: int = Field(default=20, env="RATE_LIMIT_WELLFOUND")
    rate_limit_techcrunch: int = Field(default=30, env="RATE_LIMIT_TECHCRUNCH")

    # Scraping Config
    max_concurrent_scrapers: int = Field(default=5, env="MAX_CONCURRENT_SCRAPERS")  # Updated: Reddit disabled
    batch_size: int = Field(default=100, env="BATCH_SIZE")
    max_leads_target: int = Field(default=150000, env="MAX_LEADS_TARGET")
    scrape_duration_hours: int = Field(default=48, env="SCRAPE_DURATION_HOURS")

    # Scoring
    min_relevance_score: int = Field(default=5, env="MIN_RELEVANCE_SCORE")
    icp_keywords: str = Field(
        default="linkedin ghostwriting,AI content automation,personal branding",
        env="ICP_KEYWORDS"
    )

    # Export
    export_path: str = Field(default="./data/exports/", env="EXPORT_PATH")
    export_filename: str = Field(default="b2b_leads_{timestamp}.csv", env="EXPORT_FILENAME")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: str = Field(default="./data/logs/scraper.log", env="LOG_FILE")

    # Performance
    connection_pool_size: int = Field(default=100, env="CONNECTION_POOL_SIZE")
    request_timeout: int = Field(default=120, env="REQUEST_TIMEOUT")
    max_retry_attempts: int = Field(default=3, env="MAX_RETRY_ATTEMPTS")
    retry_backoff_factor: float = Field(default=2.0, env="RETRY_BACKOFF_FACTOR")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def get_reddit_keys(self) -> List[tuple]:
        """Parse Reddit API keys into (client_id, client_secret) tuples"""
        if not self.reddit_api_keys:
            return []
        keys = []
        for pair in self.reddit_api_keys.split(','):
            if ':' in pair:
                client_id, client_secret = pair.strip().split(':', 1)
                keys.append((client_id, client_secret))
        return keys

    def get_producthunt_keys(self) -> List[str]:
        """Parse Product Hunt API keys"""
        if not self.producthunt_api_keys:
            return []
        return [k.strip() for k in self.producthunt_api_keys.split(',') if k.strip()]

    def get_github_keys(self) -> List[str]:
        """Parse GitHub API keys"""
        if not self.github_api_keys:
            return []
        return [k.strip() for k in self.github_api_keys.split(',') if k.strip()]

    def get_icp_keywords(self) -> List[str]:
        """Parse ICP keywords"""
        return [k.strip() for k in self.icp_keywords.split(',') if k.strip()]


# Global settings instance
settings = Settings()

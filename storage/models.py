"""Database models and schema definitions"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict
from datetime import datetime
import hashlib
import json


@dataclass
class Lead:
    """Lead data model"""
    # Required fields (matching CSV format)
    email: str                          # Contact person email
    name: str                           # Contact person name
    designation: str                    # Contact person designation
    company: str                        # Company
    geography: str = ""                 # Geography
    post_content: str = ""              # Post content (with keywords)
    buying_intent: str = ""             # Buying intent

    # Optional fields (for internal use)
    linkedin_url: Optional[str] = None
    website: Optional[str] = None

    # Metadata
    source: str = ""
    signal_type: str = ""
    date_found: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    relevance_score: int = 0
    score_breakdown: Dict = field(default_factory=dict)

    # Internal fields
    content_hash: str = ""
    raw_data: str = ""

    def __post_init__(self):
        """Generate content hash after initialization"""
        if not self.content_hash:
            self.content_hash = self.generate_hash()

    def generate_hash(self) -> str:
        """Generate unique hash for deduplication"""
        # Use email + company + name for hash
        content = f"{self.email.lower()}{self.company.lower()}{self.name.lower()}"
        return hashlib.sha256(content.encode()).hexdigest()

    @property
    def role(self) -> str:
        """Alias for designation (backward compatibility)"""
        return self.designation

    @property
    def location(self) -> str:
        """Alias for geography (backward compatibility)"""
        return self.geography

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        data = asdict(self)
        # Convert score_breakdown to JSON string
        if isinstance(data['score_breakdown'], dict):
            data['score_breakdown'] = json.dumps(data['score_breakdown'])
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'Lead':
        """Create Lead from dictionary"""
        # Parse score_breakdown if it's a JSON string
        if isinstance(data.get('score_breakdown'), str):
            try:
                data['score_breakdown'] = json.loads(data['score_breakdown'])
            except json.JSONDecodeError:
                data['score_breakdown'] = {}

        return cls(**data)

    def to_csv_row(self) -> dict:
        """Convert to CSV row format (matching required format)"""
        return {
            'Contact person name': self.name,
            'Contact person designation': self.designation,
            'Contact person email': self.email,
            'Post content': self.post_content,
            'Buying intent': self.buying_intent,
            'Company': self.company,
            'Geography': self.geography
        }


# Database schema SQL
SCHEMA_SQL = """
-- Leads table (updated schema matching CSV format)
CREATE TABLE IF NOT EXISTS leads (
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

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
CREATE INDEX IF NOT EXISTS idx_leads_company ON leads(company);
CREATE INDEX IF NOT EXISTS idx_leads_source ON leads(source);
CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(relevance_score);
CREATE INDEX IF NOT EXISTS idx_leads_date ON leads(date_found);
CREATE INDEX IF NOT EXISTS idx_leads_hash ON leads(content_hash);
CREATE INDEX IF NOT EXISTS idx_leads_geography ON leads(geography);
CREATE INDEX IF NOT EXISTS idx_leads_designation ON leads(designation);

-- Scrape sessions table for progress tracking
CREATE TABLE IF NOT EXISTS scrape_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    cursor TEXT,
    metadata TEXT,
    leads_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sessions_source ON scrape_sessions(source);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON scrape_sessions(status);

-- Rate limit state table
CREATE TABLE IF NOT EXISTS rate_limit_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    api_key TEXT,
    tokens_remaining REAL DEFAULT 0,
    last_request TIMESTAMP,
    reset_time TIMESTAMP,
    UNIQUE(source, api_key)
);

CREATE INDEX IF NOT EXISTS idx_ratelimit_source ON rate_limit_state(source);

-- Proxy health table
CREATE TABLE IF NOT EXISTS proxy_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proxy_url TEXT UNIQUE NOT NULL,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    last_success TIMESTAMP,
    last_failure TIMESTAMP,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_proxy_status ON proxy_health(status);

-- Error log table
CREATE TABLE IF NOT EXISTS error_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT,
    error_type TEXT,
    error_message TEXT,
    traceback TEXT,
    context TEXT,
    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_error_source ON error_log(source);
CREATE INDEX IF NOT EXISTS idx_error_type ON error_log(error_type);
CREATE INDEX IF NOT EXISTS idx_error_time ON error_log(occurred_at);
"""


def get_csv_headers() -> list:
    """Get CSV column headers (matching required format)"""
    return [
        'Contact person name',
        'Contact person designation',
        'Contact person email',
        'Post content',
        'Buying intent',
        'Company',
        'Geography'
    ]

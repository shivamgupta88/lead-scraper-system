"""Async SQLite database wrapper"""

import aiosqlite
from typing import List, Optional, Dict
from pathlib import Path
from utils.logger import log
from storage.models import Lead, SCHEMA_SQL
import json
from datetime import datetime


class Database:
    """Async SQLite database handler"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """Initialize database and create tables"""
        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Connect to database
        self.connection = await aiosqlite.connect(
            self.db_path,
            timeout=30.0
        )

        # Enable WAL mode for better concurrency
        await self.connection.execute("PRAGMA journal_mode=WAL")
        await self.connection.execute("PRAGMA synchronous=NORMAL")
        await self.connection.execute("PRAGMA cache_size=-64000")  # 64MB cache

        # Create schema
        await self.connection.executescript(SCHEMA_SQL)
        await self.connection.commit()

        log.info(f"Database initialized at {self.db_path}")

    async def close(self):
        """Close database connection"""
        if self.connection:
            await self.connection.close()
            log.info("Database connection closed")

    async def bulk_insert_leads(self, leads: List[Lead]) -> int:
        """
        Bulk insert leads into database

        Args:
            leads: List of Lead objects

        Returns:
            Number of leads successfully inserted
        """
        if not leads:
            return 0

        insert_sql = """
        INSERT OR IGNORE INTO leads (
            email, name, company, role, linkedin_url, website, location,
            source, signal_type, date_found, relevance_score, score_breakdown,
            content_hash, raw_data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        data = []
        for lead in leads:
            data.append((
                lead.email,
                lead.name,
                lead.company,
                lead.role,
                lead.linkedin_url,
                lead.website,
                lead.location,
                lead.source,
                lead.signal_type,
                lead.date_found,
                lead.relevance_score,
                json.dumps(lead.score_breakdown),
                lead.content_hash,
                lead.raw_data
            ))

        try:
            cursor = await self.connection.executemany(insert_sql, data)
            await self.connection.commit()
            inserted = cursor.rowcount
            log.debug(f"Inserted {inserted} leads into database")
            return inserted
        except Exception as e:
            log.error(f"Error bulk inserting leads: {e}")
            await self.connection.rollback()
            return 0

    async def is_duplicate(self, email: str, source: str) -> bool:
        """Check if lead already exists"""
        query = "SELECT 1 FROM leads WHERE email = ? AND source = ? LIMIT 1"

        async with self.connection.execute(query, (email, source)) as cursor:
            result = await cursor.fetchone()
            return result is not None

    async def is_duplicate_by_hash(self, content_hash: str) -> bool:
        """Check if lead exists by content hash"""
        query = "SELECT 1 FROM leads WHERE content_hash = ? LIMIT 1"

        async with self.connection.execute(query, (content_hash,)) as cursor:
            result = await cursor.fetchone()
            return result is not None

    async def get_lead_count(self) -> int:
        """Get total number of leads"""
        query = "SELECT COUNT(*) FROM leads"

        async with self.connection.execute(query) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0

    async def get_lead_count_by_source(self, source: str) -> int:
        """Get lead count for specific source"""
        query = "SELECT COUNT(*) FROM leads WHERE source = ?"

        async with self.connection.execute(query, (source,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0

    async def get_leads_for_export(
        self,
        min_score: int = 5,
        limit: int = None,
        offset: int = 0
    ) -> List[Dict]:
        """
        Get leads for CSV export

        Args:
            min_score: Minimum relevance score
            limit: Maximum number of leads to return
            offset: Number of leads to skip

        Returns:
            List of lead dictionaries
        """
        query = """
        SELECT email, name, company, role, linkedin_url, website, location,
               source, signal_type, date_found, relevance_score
        FROM leads
        WHERE relevance_score >= ?
        ORDER BY relevance_score DESC, date_found DESC
        """

        params = [min_score]

        if limit:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        async with self.connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()

            leads = []
            for row in rows:
                leads.append({
                    'email': row[0],
                    'name': row[1],
                    'company': row[2],
                    'role': row[3],
                    'linkedin_url': row[4] or '',
                    'website': row[5] or '',
                    'location': row[6] or '',
                    'source': row[7],
                    'signal_type': row[8],
                    'date_found': row[9],
                    'relevance_score': row[10]
                })

            return leads

    async def save_checkpoint(
        self,
        source: str,
        cursor: str,
        metadata: Dict = None
    ):
        """Save scraping checkpoint for resumption"""
        query = """
        INSERT INTO scrape_sessions (source, cursor, metadata, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(rowid) DO UPDATE SET
            cursor = excluded.cursor,
            metadata = excluded.metadata,
            updated_at = CURRENT_TIMESTAMP
        """

        metadata_json = json.dumps(metadata or {})
        await self.connection.execute(query, (source, cursor, metadata_json))
        await self.connection.commit()
        log.debug(f"Checkpoint saved for {source}")

    async def load_checkpoint(self, source: str) -> Optional[Dict]:
        """Load last checkpoint for a source"""
        query = """
        SELECT cursor, metadata, leads_count
        FROM scrape_sessions
        WHERE source = ? AND status = 'active'
        ORDER BY updated_at DESC
        LIMIT 1
        """

        async with self.connection.execute(query, (source,)) as cursor:
            result = await cursor.fetchone()
            if result:
                return {
                    'cursor': result[0],
                    'metadata': json.loads(result[1]) if result[1] else {},
                    'leads_count': result[2]
                }
            return None

    async def update_session_leads_count(self, source: str, count: int):
        """Update leads count for a session"""
        query = """
        UPDATE scrape_sessions
        SET leads_count = ?, updated_at = CURRENT_TIMESTAMP
        WHERE source = ? AND status = 'active'
        """
        await self.connection.execute(query, (count, source))
        await self.connection.commit()

    async def log_error(
        self,
        source: str,
        error_type: str,
        error_message: str,
        traceback: str = None,
        context: Dict = None
    ):
        """Log error to database"""
        query = """
        INSERT INTO error_log (source, error_type, error_message, traceback, context)
        VALUES (?, ?, ?, ?, ?)
        """

        context_json = json.dumps(context or {})
        await self.connection.execute(
            query,
            (source, error_type, error_message, traceback, context_json)
        )
        await self.connection.commit()

    async def get_stats(self) -> Dict:
        """Get database statistics"""
        stats = {}

        # Total leads
        stats['total_leads'] = await self.get_lead_count()

        # Leads by source
        query = "SELECT source, COUNT(*) FROM leads GROUP BY source"
        async with self.connection.execute(query) as cursor:
            stats['by_source'] = dict(await cursor.fetchall())

        # Average score
        query = "SELECT AVG(relevance_score) FROM leads"
        async with self.connection.execute(query) as cursor:
            result = await cursor.fetchone()
            stats['avg_score'] = round(result[0], 2) if result[0] else 0

        # High quality leads (score >= 7)
        query = "SELECT COUNT(*) FROM leads WHERE relevance_score >= 7"
        async with self.connection.execute(query) as cursor:
            result = await cursor.fetchone()
            stats['high_quality'] = result[0] if result else 0

        return stats

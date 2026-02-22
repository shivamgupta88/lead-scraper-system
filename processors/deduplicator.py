"""Lead deduplication using hash-based and fuzzy matching"""

from typing import Dict, Set, Optional
from utils.validators import normalize_company_name
from utils.logger import log
import hashlib


class Deduplicator:
    """Handles lead deduplication"""

    def __init__(self):
        self.seen_hashes: Set[str] = set()
        self.seen_emails: Set[str] = set()
        self.seen_email_company_pairs: Set[str] = set()

        self.dedup_stats = {
            'total_checked': 0,
            'duplicates_found': 0,
            'unique_leads': 0,
            'duplicate_by_hash': 0,
            'duplicate_by_email': 0,
            'duplicate_by_pair': 0
        }

    def is_duplicate(self, lead: Dict) -> bool:
        """
        Check if lead is a duplicate

        Args:
            lead: Lead dictionary

        Returns:
            True if duplicate, False if unique
        """
        self.dedup_stats['total_checked'] += 1

        email = lead.get('email', '').lower().strip()
        company = normalize_company_name(lead.get('company', ''))

        # Generate content hash
        content_hash = self._generate_hash(lead)

        # Check hash-based deduplication
        if content_hash in self.seen_hashes:
            self.dedup_stats['duplicates_found'] += 1
            self.dedup_stats['duplicate_by_hash'] += 1
            log.debug(f"Duplicate found (hash): {email}")
            return True

        # Check email deduplication
        if email in self.seen_emails:
            self.dedup_stats['duplicates_found'] += 1
            self.dedup_stats['duplicate_by_email'] += 1
            log.debug(f"Duplicate found (email): {email}")
            return True

        # Check email+company pair deduplication
        pair_key = f"{email}:{company}"
        if pair_key in self.seen_email_company_pairs:
            self.dedup_stats['duplicates_found'] += 1
            self.dedup_stats['duplicate_by_pair'] += 1
            log.debug(f"Duplicate found (pair): {pair_key}")
            return True

        # Not a duplicate - record it
        self.seen_hashes.add(content_hash)
        self.seen_emails.add(email)
        self.seen_email_company_pairs.add(pair_key)
        self.dedup_stats['unique_leads'] += 1

        return False

    def _generate_hash(self, lead: Dict) -> str:
        """
        Generate unique hash for lead

        Args:
            lead: Lead dictionary

        Returns:
            Hash string
        """
        # Use email + normalized company + name for hash
        email = lead.get('email', '').lower().strip()
        company = normalize_company_name(lead.get('company', ''))
        name = lead.get('name', '').lower().strip()

        content = f"{email}{company}{name}"
        return hashlib.sha256(content.encode()).hexdigest()

    def get_stats(self) -> Dict:
        """Get deduplication statistics"""
        stats = self.dedup_stats.copy()

        if stats['total_checked'] > 0:
            stats['duplicate_rate'] = (
                stats['duplicates_found'] / stats['total_checked']
            ) * 100

        return stats

    def clear_cache(self):
        """Clear deduplication cache (useful for memory management)"""
        self.seen_hashes.clear()
        self.seen_emails.clear()
        self.seen_email_company_pairs.clear()
        log.info("Deduplication cache cleared")

    def get_cache_size(self) -> int:
        """Get number of cached entries"""
        return len(self.seen_hashes)

"""Data validation for leads"""

from typing import Dict, Tuple
from utils.validators import (
    is_valid_email,
    check_mx_record,
    is_valid_url,
    is_corporate_email,
    sanitize_text
)
from utils.logger import log


class DataValidator:
    """Validates lead data quality"""

    def __init__(self, strict_mode: bool = False):
        """
        Args:
            strict_mode: If True, requires MX record validation (slower)
        """
        self.strict_mode = strict_mode
        self.validation_stats = {
            'total_validated': 0,
            'passed': 0,
            'failed': 0,
            'reasons': {}
        }

    def validate_lead(self, lead: Dict) -> Tuple[bool, str]:
        """
        Validate a lead

        Args:
            lead: Lead dictionary

        Returns:
            Tuple of (is_valid, reason)
        """
        self.validation_stats['total_validated'] += 1

        # Required fields (updated for new format)
        required_fields = ['email', 'name', 'company', 'designation']
        for field in required_fields:
            if not lead.get(field) or lead.get(field) == 'Unknown':
                reason = f"Missing or invalid {field}"
                self._record_failure(reason)
                return False, reason

        # Validate email format
        email = lead['email'].strip().lower()
        if not is_valid_email(email):
            reason = "Invalid email format"
            self._record_failure(reason)
            return False, reason

        # Check for placeholder emails
        placeholder_domains = ['example.com', 'test.com', 'fake.com', 'domain.com']
        email_domain = email.split('@')[1] if '@' in email else ''
        if any(domain in email_domain for domain in placeholder_domains):
            reason = "Placeholder email domain"
            self._record_failure(reason)
            return False, reason

        # Check for noreply emails
        if 'noreply' in email or 'no-reply' in email:
            reason = "No-reply email address"
            self._record_failure(reason)
            return False, reason

        # Strict mode: Check MX records
        if self.strict_mode:
            if not check_mx_record(email):
                reason = "No MX records for domain"
                self._record_failure(reason)
                return False, reason

        # Validate URLs if provided
        if lead.get('linkedin_url'):
            linkedin_url = lead['linkedin_url'].strip()
            if linkedin_url and not is_valid_url(linkedin_url):
                reason = "Invalid LinkedIn URL"
                self._record_failure(reason)
                return False, reason

        if lead.get('website'):
            website = lead['website'].strip()
            if website and not is_valid_url(website):
                reason = "Invalid website URL"
                self._record_failure(reason)
                return False, reason

        # Validate name length
        name = lead['name'].strip()
        if len(name) < 2 or len(name) > 100:
            reason = "Invalid name length"
            self._record_failure(reason)
            return False, reason

        # Validate company name length
        company = lead['company'].strip()
        if len(company) < 2 or len(company) > 100:
            reason = "Invalid company name length"
            self._record_failure(reason)
            return False, reason

        # All validations passed
        self.validation_stats['passed'] += 1
        return True, "Valid"

    def sanitize_lead(self, lead: Dict) -> Dict:
        """
        Sanitize lead data

        Args:
            lead: Lead dictionary

        Returns:
            Sanitized lead dictionary
        """
        sanitized = lead.copy()

        # Sanitize text fields
        text_fields = ['name', 'company', 'designation', 'geography', 'signal_type', 'buying_intent']
        for field in text_fields:
            if field in sanitized and sanitized[field]:
                sanitized[field] = sanitize_text(sanitized[field], max_length=200)

        # Sanitize post_content (longer field)
        if 'post_content' in sanitized and sanitized['post_content']:
            sanitized['post_content'] = sanitize_text(sanitized['post_content'], max_length=1000)

        # Normalize email
        if 'email' in sanitized:
            sanitized['email'] = sanitized['email'].strip().lower()

        # Normalize URLs
        for url_field in ['linkedin_url', 'website']:
            if url_field in sanitized and sanitized[url_field]:
                url = sanitized[url_field].strip()
                # Ensure URLs have protocol
                if url and not url.startswith('http'):
                    sanitized[url_field] = f"https://{url}"

        return sanitized

    def _record_failure(self, reason: str):
        """Record validation failure"""
        self.validation_stats['failed'] += 1
        if reason not in self.validation_stats['reasons']:
            self.validation_stats['reasons'][reason] = 0
        self.validation_stats['reasons'][reason] += 1

    def get_stats(self) -> Dict:
        """Get validation statistics"""
        return self.validation_stats.copy()

    def is_quality_lead(self, lead: Dict) -> bool:
        """
        Determine if lead is high quality

        Args:
            lead: Lead dictionary

        Returns:
            True if high quality
        """
        quality_score = 0

        # Corporate email (+2)
        if is_corporate_email(lead.get('email', '')):
            quality_score += 2

        # Has LinkedIn URL (+1)
        if lead.get('linkedin_url'):
            quality_score += 1

        # Has website (+1)
        if lead.get('website'):
            quality_score += 1

        # Has specific designation (not "Unknown") (+1)
        if lead.get('designation') and lead['designation'] != 'Unknown':
            quality_score += 1

        # Has geography (+0.5)
        if lead.get('geography'):
            quality_score += 0.5

        # Has post content (+1)
        if lead.get('post_content') and len(lead.get('post_content', '')) > 50:
            quality_score += 1

        # Has buying intent (+1)
        if lead.get('buying_intent'):
            quality_score += 1

        # Strong signal types (+1)
        strong_signals = ['hiring', 'funding', 'product_launch']
        if lead.get('signal_type') in strong_signals:
            quality_score += 1

        # Quality threshold: 4 or higher
        return quality_score >= 4

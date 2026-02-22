"""Data validation utilities"""

import re
from email_validator import validate_email, EmailNotValidError
import dns.resolver
from typing import Optional
import validators as val_lib


def is_valid_email(email: str) -> bool:
    """Validate email format"""
    if not email:
        return False

    try:
        # Validate email format
        validation = validate_email(email, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False


def check_mx_record(email: str) -> bool:
    """Check if email domain has MX records"""
    if not email or '@' not in email:
        return False

    try:
        domain = email.split('@')[1]
        mx_records = dns.resolver.resolve(domain, 'MX')
        return len(mx_records) > 0
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, Exception):
        return False


def is_valid_url(url: str) -> bool:
    """Validate URL format"""
    if not url:
        return False
    return val_lib.url(url) is True


def is_linkedin_url(url: str) -> bool:
    """Check if URL is a LinkedIn profile"""
    if not url:
        return False
    return 'linkedin.com/in/' in url.lower()


def extract_emails_from_text(text: str) -> list:
    """Extract email addresses from text"""
    if not text:
        return []

    # Email regex pattern
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)

    # Validate and deduplicate
    valid_emails = []
    seen = set()

    for email in emails:
        email = email.lower().strip()
        if email not in seen and is_valid_email(email):
            # Filter out common fake/placeholder emails
            if not any(x in email for x in ['example.com', 'test.com', 'fake.com', 'noreply', 'no-reply']):
                valid_emails.append(email)
                seen.add(email)

    return valid_emails


def extract_urls_from_text(text: str) -> list:
    """Extract URLs from text"""
    if not text:
        return []

    # URL regex pattern
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(url_pattern, text)

    # Validate and deduplicate
    valid_urls = []
    seen = set()

    for url in urls:
        url = url.strip()
        if url not in seen and is_valid_url(url):
            valid_urls.append(url)
            seen.add(url)

    return valid_urls


def normalize_company_name(company: str) -> str:
    """Normalize company name for deduplication"""
    if not company:
        return ""

    # Convert to lowercase
    normalized = company.lower().strip()

    # Remove common suffixes
    suffixes = [' inc', ' inc.', ' llc', ' ltd', ' ltd.', ' corp', ' corp.', ' co', ' co.']
    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)].strip()

    # Remove special characters
    normalized = re.sub(r'[^\w\s]', '', normalized)

    # Remove extra whitespace
    normalized = ' '.join(normalized.split())

    return normalized


def sanitize_text(text: str, max_length: Optional[int] = None) -> str:
    """Sanitize text by removing extra whitespace and control characters"""
    if not text:
        return ""

    # Remove control characters
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)

    # Normalize whitespace
    text = ' '.join(text.split())

    # Trim to max length
    if max_length and len(text) > max_length:
        text = text[:max_length].strip()

    return text


def is_corporate_email(email: str) -> bool:
    """Check if email is likely a corporate email (not free provider)"""
    if not email:
        return False

    free_providers = [
        'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
        'aol.com', 'icloud.com', 'mail.com', 'protonmail.com',
        'yandex.com', 'zoho.com', 'gmx.com'
    ]

    domain = email.split('@')[1].lower() if '@' in email else ''
    return domain not in free_providers


def extract_domain(url: str) -> Optional[str]:
    """Extract domain from URL"""
    if not url:
        return None

    try:
        # Remove protocol
        if '://' in url:
            url = url.split('://')[1]

        # Extract domain
        domain = url.split('/')[0].split('?')[0]

        # Remove www
        if domain.startswith('www.'):
            domain = domain[4:]

        return domain
    except Exception:
        return None

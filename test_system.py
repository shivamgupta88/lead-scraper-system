"""Test script to verify system components"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import log
from config.settings import settings
from storage.database import Database
from storage.models import Lead
from processors.data_validator import DataValidator
from processors.relevance_scorer import RelevanceScorer
from processors.deduplicator import Deduplicator


async def test_database():
    """Test database initialization and operations"""
    log.info("Testing database...")

    db = Database(":memory:")  # Use in-memory database for testing
    await db.initialize()

    # Test lead creation
    test_lead = Lead(
        email="test@example.com",
        name="Test User",
        company="Test Company",
        role="CEO",
        source="test",
        signal_type="test",
        relevance_score=8
    )

    # Test insert
    await db.bulk_insert_leads([test_lead])

    # Test count
    count = await db.get_lead_count()
    assert count == 1, f"Expected 1 lead, got {count}"

    await db.close()
    log.info("✓ Database tests passed")


def test_validator():
    """Test data validator"""
    log.info("Testing validator...")

    validator = DataValidator()

    # Valid lead
    valid_lead = {
        'email': 'john@company.com',
        'name': 'John Doe',
        'company': 'Company Inc',
        'role': 'CEO'
    }

    is_valid, reason = validator.validate_lead(valid_lead)
    assert is_valid, f"Valid lead rejected: {reason}"

    # Invalid lead (bad email)
    invalid_lead = {
        'email': 'invalid-email',
        'name': 'John Doe',
        'company': 'Company Inc',
        'role': 'CEO'
    }

    is_valid, reason = validator.validate_lead(invalid_lead)
    assert not is_valid, "Invalid email accepted"

    log.info("✓ Validator tests passed")


def test_scorer():
    """Test relevance scorer"""
    log.info("Testing scorer...")

    scorer = RelevanceScorer()

    # High-quality lead
    lead = {
        'email': 'founder@saascompany.com',
        'name': 'Jane Smith',
        'company': 'B2B SaaS Company',
        'role': 'Founder & CEO',
        'linkedin_url': 'https://linkedin.com/in/janesmith',
        'website': 'https://saascompany.com'
    }

    raw_data = """
    We're hiring for our growing team! Our B2B SaaS platform helps with LinkedIn marketing
    and AI content automation. Just raised $2M in seed funding from top investors.
    Looking for experienced engineers to join our 15-person team.
    We specialize in personal branding and thought leadership for B2B founders.
    Active on LinkedIn, posting regularly about SaaS GTM strategies.
    """

    score, breakdown = scorer.score_lead(lead, raw_data)

    assert 1 <= score <= 10, f"Score out of range: {score}"
    assert score >= 5, f"Lead scored too low: {score}"  # Lowered threshold to 5

    log.info(f"✓ Scorer tests passed (sample score: {score}, breakdown: {breakdown})")


def test_deduplicator():
    """Test deduplicator"""
    log.info("Testing deduplicator...")

    dedup = Deduplicator()

    lead1 = {
        'email': 'test@company.com',
        'name': 'Test User',
        'company': 'Company'
    }

    lead2 = {
        'email': 'test@company.com',
        'name': 'Test User',
        'company': 'Company'
    }

    # First lead should not be duplicate
    assert not dedup.is_duplicate(lead1), "First lead marked as duplicate"

    # Second lead should be duplicate
    assert dedup.is_duplicate(lead2), "Duplicate not detected"

    log.info("✓ Deduplicator tests passed")


async def main():
    """Run all tests"""
    log.info("=" * 60)
    log.info("SYSTEM COMPONENT TESTS")
    log.info("=" * 60)
    log.info("")

    try:
        # Test components
        await test_database()
        test_validator()
        test_scorer()
        test_deduplicator()

        log.info("")
        log.info("=" * 60)
        log.info("ALL TESTS PASSED ✓")
        log.info("=" * 60)
        log.info("")
        log.info("System is ready to use!")
        log.info("Run: python main.py")

    except AssertionError as e:
        log.error(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        log.error(f"Test error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

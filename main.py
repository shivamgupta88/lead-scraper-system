"""Main entry point for the lead scraper system"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.orchestrator import Orchestrator
from storage.export import stream_export_from_database
from storage.database import Database
from utils.logger import log
from utils.metrics import metrics
from config.settings import settings


async def main():
    """Main function"""
    log.info("=" * 80)
    log.info("B2B LEAD SCRAPER SYSTEM")
    log.info("=" * 80)
    log.info(f"Target: {settings.max_leads_target:,} leads")
    log.info(f"Min Relevance Score: {settings.min_relevance_score}")
    log.info(f"Duration: {settings.scrape_duration_hours} hours")
    log.info("=" * 80)

    # Create orchestrator
    orchestrator = Orchestrator()

    try:
        # Initialize
        await orchestrator.initialize()

        # Setup signal handlers
        orchestrator.setup_signal_handlers()

        # Run scraping
        log.info("Starting scraping operation...")
        await orchestrator.run()

        # Get final stats
        log.info("\n" + "=" * 80)
        log.info("SCRAPING COMPLETE")
        log.info("=" * 80)

        final_report = metrics.get_progress_report(settings.max_leads_target)
        log.info(f"\n{final_report}")

        # Print component stats
        log.info("\n" + "-" * 80)
        log.info("COMPONENT STATISTICS")
        log.info("-" * 80)
        log.info(f"Validation Stats: {orchestrator.validator.get_stats()}")
        log.info(f"Scoring Stats: {orchestrator.scorer.get_stats()}")
        log.info(f"Deduplication Stats: {orchestrator.deduplicator.get_stats()}")

        # Get database stats
        db_stats = await orchestrator.database.get_stats()
        log.info(f"\nDatabase Stats: {db_stats}")

        # Export to CSV
        log.info("\n" + "=" * 80)
        log.info("EXPORTING TO CSV")
        log.info("=" * 80)

        csv_path = await stream_export_from_database(
            orchestrator.database,
            min_score=settings.min_relevance_score
        )

        if csv_path:
            log.info(f"✓ Export complete: {csv_path}")
        else:
            log.warning("No leads to export")

        # Final summary
        log.info("\n" + "=" * 80)
        log.info("FINAL SUMMARY")
        log.info("=" * 80)
        summary = metrics.get_summary()
        log.info(f"Total Leads Scraped: {summary['total_leads']:,}")
        log.info(f"Total Processed: {summary['total_processed']:,}")
        log.info(f"Duplicates Removed: {summary['total_duplicates']:,}")
        log.info(f"Invalid Leads: {summary['total_invalid']:,}")
        log.info(f"Time Elapsed: {summary['elapsed_hours']:.2f} hours")
        log.info(f"Leads per Hour: {summary['leads_per_hour']:.0f}")
        log.info("\nSource Breakdown:")
        for source, stats in summary['sources'].items():
            log.info(f"  {source:15} | {stats['leads']:6,} leads | {stats['requests']:6,} requests | {stats['success_rate']:5.1f}% success")

        log.info("\n" + "=" * 80)
        log.info("SYSTEM SHUTDOWN COMPLETE")
        log.info("=" * 80)

    except KeyboardInterrupt:
        log.info("\nReceived keyboard interrupt, shutting down...")
        await orchestrator.shutdown()

    except Exception as e:
        log.error(f"Fatal error: {e}", exc_info=True)
        await orchestrator.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Interrupted by user")
        sys.exit(0)

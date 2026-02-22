"""Main orchestrator for coordinating all scraping and processing"""

import asyncio
from typing import List
from utils.logger import log
from utils.metrics import metrics
from config.settings import settings
from storage.database import Database
from storage.models import Lead
from core.proxy_manager import ProxyManager
from core.api_key_rotator import APIKeyRotator
from core.rate_limiter import RateLimiter
from core.session_manager import SessionManager
from processors.data_validator import DataValidator
from processors.relevance_scorer import RelevanceScorer
from processors.deduplicator import Deduplicator
from scrapers.hackernews_scraper import HackerNewsScraper
from scrapers.reddit_scraper import RedditScraper
from scrapers.github_scraper import GitHubScraper
from scrapers.producthunt_scraper import ProductHuntScraper
from scrapers.techcrunch_scraper import TechCrunchScraper
from scrapers.wellfound_scraper import WellfoundScraper
import signal
import sys


class Orchestrator:
    """Main orchestrator for the lead scraping system"""

    def __init__(self):
        # Core components
        self.database: Database = None
        self.proxy_manager: ProxyManager = None
        self.api_key_rotator: APIKeyRotator = None
        self.rate_limiter: RateLimiter = None
        self.session_manager: SessionManager = None

        # Processing components
        self.validator = DataValidator(strict_mode=False)
        self.scorer = RelevanceScorer()
        self.deduplicator = Deduplicator()

        # Scrapers
        self.scrapers = []

        # Async queues
        self.scraping_queue: asyncio.Queue = None
        self.processing_queue: asyncio.Queue = None
        self.storage_queue: asyncio.Queue = None

        # Control flags
        self.running = True
        self.shutdown_event = asyncio.Event()

        # Worker tasks
        self.worker_tasks: List[asyncio.Task] = []

    async def initialize(self):
        """Initialize all components"""
        log.info("Initializing orchestrator...")

        # Initialize database
        self.database = Database(settings.database_path)
        await self.database.initialize()

        # Initialize core components
        self.proxy_manager = ProxyManager()
        await self.proxy_manager.initialize()

        self.api_key_rotator = APIKeyRotator()
        await self.api_key_rotator.initialize()

        self.rate_limiter = RateLimiter()
        await self.rate_limiter.initialize()

        self.session_manager = SessionManager()
        await self.session_manager.initialize()

        # Create async queues
        self.scraping_queue = asyncio.Queue(maxsize=1000)
        self.processing_queue = asyncio.Queue(maxsize=500)
        self.storage_queue = asyncio.Queue(maxsize=100)

        # Initialize scrapers
        scraper_args = (
            self.proxy_manager,
            self.api_key_rotator,
            self.rate_limiter,
            self.session_manager,
            self.database
        )

        self.scrapers = [
            HackerNewsScraper(*scraper_args),
            RedditScraper(*scraper_args),
            GitHubScraper(*scraper_args),
            ProductHuntScraper(*scraper_args),
            TechCrunchScraper(*scraper_args),
            WellfoundScraper(*scraper_args)
        ]

        log.info("Orchestrator initialized successfully")

    async def scraper_worker(self, scraper):
        """Worker that runs a scraper and pushes to scraping queue"""
        log.info(f"Starting scraper worker: {scraper.source_name}")

        try:
            async for lead_data in scraper.run():
                if not self.running:
                    break

                # Push to scraping queue
                await self.scraping_queue.put(lead_data)
                metrics.record_lead(scraper.source_name)

        except Exception as e:
            log.error(f"Scraper worker {scraper.source_name} failed: {e}")
        finally:
            log.info(f"Scraper worker {scraper.source_name} finished")

    async def processing_worker(self):
        """Worker that processes leads from scraping queue"""
        log.info("Starting processing worker")

        while self.running or not self.scraping_queue.empty():
            try:
                # Get lead from queue with timeout
                try:
                    lead_data = await asyncio.wait_for(
                        self.scraping_queue.get(),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Validate lead
                is_valid, reason = self.validator.validate_lead(lead_data)
                if not is_valid:
                    log.debug(f"Lead validation failed: {reason}")
                    metrics.record_invalid()
                    continue

                # Sanitize lead
                sanitized_lead = self.validator.sanitize_lead(lead_data)

                # Check for duplicates
                if self.deduplicator.is_duplicate(sanitized_lead):
                    metrics.record_duplicate()
                    continue

                # Score lead
                raw_data = sanitized_lead.get('raw_data', '')
                score, breakdown = self.scorer.score_lead(sanitized_lead, raw_data)

                # Create Lead object
                lead = Lead(
                    email=sanitized_lead['email'],
                    name=sanitized_lead['name'],
                    designation=sanitized_lead.get('designation', ''),
                    company=sanitized_lead['company'],
                    geography=sanitized_lead.get('geography', ''),
                    post_content=sanitized_lead.get('post_content', ''),
                    buying_intent=sanitized_lead.get('buying_intent', ''),
                    linkedin_url=sanitized_lead.get('linkedin_url'),
                    website=sanitized_lead.get('website'),
                    source=sanitized_lead['source'],
                    signal_type=sanitized_lead.get('signal_type', ''),
                    relevance_score=score,
                    score_breakdown=breakdown,
                    raw_data=raw_data[:1000]
                )

                # Push to storage queue
                await self.storage_queue.put(lead)
                metrics.record_processed()

            except Exception as e:
                log.error(f"Processing worker error: {e}")
                continue

        log.info("Processing worker finished")

    async def storage_worker(self):
        """Worker that batches and stores leads to database"""
        log.info("Starting storage worker")

        batch = []
        batch_size = settings.batch_size

        while self.running or not self.storage_queue.empty():
            try:
                # Get lead from queue with timeout
                try:
                    lead = await asyncio.wait_for(
                        self.storage_queue.get(),
                        timeout=5.0
                    )
                    batch.append(lead)
                except asyncio.TimeoutError:
                    # Timeout - flush batch if not empty
                    if batch:
                        await self._flush_batch(batch)
                        batch = []
                    continue

                # Flush batch when it reaches batch_size
                if len(batch) >= batch_size:
                    await self._flush_batch(batch)
                    batch = []

            except Exception as e:
                log.error(f"Storage worker error: {e}")
                continue

        # Flush remaining leads
        if batch:
            await self._flush_batch(batch)

        log.info("Storage worker finished")

    async def _flush_batch(self, batch: List[Lead]):
        """Flush batch of leads to database"""
        try:
            inserted = await self.database.bulk_insert_leads(batch)
            log.debug(f"Flushed batch of {inserted} leads to database")
        except Exception as e:
            log.error(f"Error flushing batch to database: {e}")

    async def progress_monitor(self):
        """Monitor and report progress"""
        log.info("Starting progress monitor")

        while self.running:
            await asyncio.sleep(60)  # Report every 60 seconds

            # Print progress report
            report = metrics.get_progress_report(settings.max_leads_target)
            log.info(f"\n{report}")

            # Get component stats
            log.info(f"Validation: {self.validator.get_stats()}")
            log.info(f"Scoring: {self.scorer.get_stats()}")
            log.info(f"Deduplication: {self.deduplicator.get_stats()}")
            log.info(f"Proxy: {self.proxy_manager.get_stats()}")
            log.info(f"Rate Limiter: {self.rate_limiter.get_stats()}")

            # Check if target reached
            if metrics.total_leads >= settings.max_leads_target:
                log.info(f"Target of {settings.max_leads_target} leads reached!")
                await self.shutdown()

        log.info("Progress monitor finished")

    async def run(self):
        """Main run loop"""
        log.info("Starting orchestrator")

        # Start scraper workers
        for scraper in self.scrapers:
            task = asyncio.create_task(self.scraper_worker(scraper))
            self.worker_tasks.append(task)

        # Start processing workers (3 workers)
        for i in range(3):
            task = asyncio.create_task(self.processing_worker())
            self.worker_tasks.append(task)

        # Start storage workers (2 workers)
        for i in range(2):
            task = asyncio.create_task(self.storage_worker())
            self.worker_tasks.append(task)

        # Start progress monitor
        monitor_task = asyncio.create_task(self.progress_monitor())
        self.worker_tasks.append(monitor_task)

        # Wait for shutdown signal
        await self.shutdown_event.wait()

        # Wait for all workers to finish
        log.info("Waiting for workers to finish...")
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)

        log.info("All workers finished")

    async def shutdown(self):
        """Graceful shutdown"""
        if not self.running:
            return

        log.info("Initiating graceful shutdown...")
        self.running = False
        self.shutdown_event.set()

        # Wait a bit for queues to drain
        await asyncio.sleep(5)

        # Close connections
        await self.session_manager.close()
        await self.database.close()

        log.info("Shutdown complete")

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            log.info(f"Received signal {signum}, shutting down...")
            asyncio.create_task(self.shutdown())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

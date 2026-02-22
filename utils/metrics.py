"""Progress tracking and metrics collection"""

import time
from dataclasses import dataclass, field
from typing import Dict
from datetime import datetime, timedelta


@dataclass
class SourceMetrics:
    """Metrics for a single scraping source"""
    name: str
    leads_scraped: int = 0
    requests_made: int = 0
    errors: int = 0
    rate_limits: int = 0
    last_success: float = 0.0
    start_time: float = field(default_factory=time.time)

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.requests_made == 0:
            return 0.0
        return ((self.requests_made - self.errors) / self.requests_made) * 100

    @property
    def leads_per_hour(self) -> float:
        """Calculate leads per hour"""
        elapsed = time.time() - self.start_time
        if elapsed == 0:
            return 0.0
        hours = elapsed / 3600
        return self.leads_scraped / hours if hours > 0 else 0.0


class MetricsCollector:
    """Centralized metrics collection"""

    def __init__(self):
        self.sources: Dict[str, SourceMetrics] = {}
        self.global_start_time = time.time()
        self.total_leads = 0
        self.total_duplicates = 0
        self.total_invalid = 0
        self.total_processed = 0

    def get_source(self, name: str) -> SourceMetrics:
        """Get or create metrics for a source"""
        if name not in self.sources:
            self.sources[name] = SourceMetrics(name=name)
        return self.sources[name]

    def record_lead(self, source: str):
        """Record a successfully scraped lead"""
        self.get_source(source).leads_scraped += 1
        self.total_leads += 1

    def record_request(self, source: str):
        """Record an API request"""
        self.get_source(source).requests_made += 1

    def record_error(self, source: str):
        """Record an error"""
        self.get_source(source).errors += 1

    def record_rate_limit(self, source: str):
        """Record a rate limit hit"""
        self.get_source(source).rate_limits += 1

    def record_success(self, source: str):
        """Record a successful operation"""
        self.get_source(source).last_success = time.time()

    def record_duplicate(self):
        """Record a duplicate lead"""
        self.total_duplicates += 1

    def record_invalid(self):
        """Record an invalid lead"""
        self.total_invalid += 1

    def record_processed(self):
        """Record a processed lead"""
        self.total_processed += 1

    def get_progress_report(self, target: int = 150000) -> str:
        """Generate a progress report"""
        elapsed = time.time() - self.global_start_time
        hours_elapsed = elapsed / 3600
        progress_pct = (self.total_leads / target) * 100 if target > 0 else 0
        leads_per_hour = self.total_leads / hours_elapsed if hours_elapsed > 0 else 0

        # Calculate ETA
        if leads_per_hour > 0:
            remaining_leads = target - self.total_leads
            hours_remaining = remaining_leads / leads_per_hour
            eta = timedelta(hours=hours_remaining)
        else:
            eta = "Unknown"

        report = f"""
╔══════════════════════════════════════════════════════════════╗
║                    SCRAPING PROGRESS REPORT                  ║
╠══════════════════════════════════════════════════════════════╣
║ Total Leads: {self.total_leads:,} / {target:,} ({progress_pct:.1f}%)
║ Leads/Hour: {leads_per_hour:.0f}
║ Time Elapsed: {timedelta(seconds=int(elapsed))}
║ ETA: {eta}
║
║ Processed: {self.total_processed:,}
║ Duplicates: {self.total_duplicates:,}
║ Invalid: {self.total_invalid:,}
╠══════════════════════════════════════════════════════════════╣
║                     SOURCE BREAKDOWN                          ║
╠══════════════════════════════════════════════════════════════╣"""

        for name, metrics in sorted(self.sources.items()):
            report += f"\n║ {name.upper():15} | Leads: {metrics.leads_scraped:6,} | Req: {metrics.requests_made:6,} | Err: {metrics.errors:4} | Success: {metrics.success_rate:5.1f}%"

        report += "\n╚══════════════════════════════════════════════════════════════╝"
        return report

    def get_summary(self) -> dict:
        """Get summary statistics as dict"""
        elapsed = time.time() - self.global_start_time

        return {
            "total_leads": self.total_leads,
            "total_processed": self.total_processed,
            "total_duplicates": self.total_duplicates,
            "total_invalid": self.total_invalid,
            "elapsed_seconds": elapsed,
            "elapsed_hours": elapsed / 3600,
            "leads_per_hour": self.total_leads / (elapsed / 3600) if elapsed > 0 else 0,
            "sources": {
                name: {
                    "leads": m.leads_scraped,
                    "requests": m.requests_made,
                    "errors": m.errors,
                    "rate_limits": m.rate_limits,
                    "success_rate": m.success_rate,
                    "leads_per_hour": m.leads_per_hour
                }
                for name, m in self.sources.items()
            }
        }


# Global metrics instance
metrics = MetricsCollector()

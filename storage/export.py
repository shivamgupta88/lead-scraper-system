"""CSV export functionality"""

import csv
from pathlib import Path
from typing import List, Dict
from datetime import datetime
from utils.logger import log
from storage.models import get_csv_headers
from config.settings import settings


class CSVExporter:
    """Handles streaming CSV export"""

    def __init__(self):
        self.export_stats = {
            'total_exported': 0,
            'files_created': 0
        }

    async def export_leads(
        self,
        leads: List[Dict],
        filename: str = None,
        min_score: int = None
    ) -> str:
        """
        Export leads to CSV file

        Args:
            leads: List of lead dictionaries
            filename: Optional custom filename
            min_score: Optional minimum relevance score filter

        Returns:
            Path to exported CSV file
        """
        # Create export directory if it doesn't exist
        export_dir = Path(settings.export_path)
        export_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        if not filename:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = settings.export_filename.format(timestamp=timestamp)

        filepath = export_dir / filename

        # Filter leads by score if specified
        if min_score is not None:
            leads = [lead for lead in leads if lead.get('relevance_score', 0) >= min_score]

        # Sort by relevance score descending
        leads = sorted(leads, key=lambda x: x.get('relevance_score', 0), reverse=True)

        # Write CSV
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                headers = get_csv_headers()
                writer = csv.DictWriter(csvfile, fieldnames=headers)

                # Write header
                writer.writeheader()

                # Write rows
                for lead in leads:
                    # Ensure all required fields exist
                    row = {header: lead.get(header, '') for header in headers}
                    writer.writerow(row)

                    self.export_stats['total_exported'] += 1

            self.export_stats['files_created'] += 1

            log.info(f"Exported {len(leads)} leads to {filepath}")
            return str(filepath)

        except Exception as e:
            log.error(f"Error exporting to CSV: {e}")
            raise

    async def export_in_batches(
        self,
        leads: List[Dict],
        batch_size: int = 10000,
        min_score: int = None
    ) -> List[str]:
        """
        Export leads in multiple CSV files (for large datasets)

        Args:
            leads: List of lead dictionaries
            batch_size: Number of leads per file
            min_score: Optional minimum relevance score filter

        Returns:
            List of exported file paths
        """
        exported_files = []

        # Filter and sort
        if min_score is not None:
            leads = [lead for lead in leads if lead.get('relevance_score', 0) >= min_score]

        leads = sorted(leads, key=lambda x: x.get('relevance_score', 0), reverse=True)

        # Split into batches
        total_batches = (len(leads) + batch_size - 1) // batch_size

        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min((batch_num + 1) * batch_size, len(leads))
            batch = leads[start_idx:end_idx]

            # Generate filename for batch
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"b2b_leads_{timestamp}_batch_{batch_num + 1}.csv"

            filepath = await self.export_leads(batch, filename=filename)
            exported_files.append(filepath)

            log.info(f"Batch {batch_num + 1}/{total_batches} exported")

        return exported_files

    def get_stats(self) -> Dict:
        """Get export statistics"""
        return self.export_stats.copy()


async def export_from_database(database, min_score: int = 5) -> str:
    """
    Export leads directly from database

    Args:
        database: Database instance
        min_score: Minimum relevance score

    Returns:
        Path to exported CSV file
    """
    exporter = CSVExporter()

    # Fetch leads from database
    leads = await database.get_leads_for_export(min_score=min_score)

    log.info(f"Fetched {len(leads)} leads from database for export")

    # Export to CSV
    if leads:
        filepath = await exporter.export_leads(leads, min_score=min_score)
        return filepath
    else:
        log.warning("No leads to export")
        return ""


async def stream_export_from_database(
    database,
    min_score: int = 5,
    batch_size: int = 1000
) -> str:
    """
    Stream export leads from database (memory efficient for large datasets)

    Args:
        database: Database instance
        min_score: Minimum relevance score
        batch_size: Number of leads to fetch per batch

    Returns:
        Path to exported CSV file
    """
    from pathlib import Path
    from datetime import datetime

    # Create export directory
    export_dir = Path(settings.export_path)
    export_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    filename = f"b2b_leads_{timestamp}.csv"
    filepath = export_dir / filename

    # Get total count
    total_leads = await database.get_lead_count()
    log.info(f"Starting streaming export of {total_leads} leads")

    # Stream write CSV
    offset = 0
    total_exported = 0

    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        headers = get_csv_headers()
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()

        while True:
            # Fetch batch
            leads = await database.get_leads_for_export(
                min_score=min_score,
                limit=batch_size,
                offset=offset
            )

            if not leads:
                break

            # Write batch
            for lead in leads:
                row = {header: lead.get(header, '') for header in headers}
                writer.writerow(row)
                total_exported += 1

            offset += len(leads)
            log.info(f"Exported {total_exported} leads...")

            # Break if we got fewer leads than batch size (end of data)
            if len(leads) < batch_size:
                break

    log.info(f"Streaming export complete: {total_exported} leads exported to {filepath}")
    return str(filepath)

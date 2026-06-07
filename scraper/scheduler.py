import asyncio
import logging
from dotenv import load_dotenv
load_dotenv()
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from scraper.ncsc_scraper import NCSCScraper
from scraper.eeas_scraper import EEASScraper
from scraper.ofcom_scraper import OfcomScraper
from ingestion.chunker import RegulatoryChunker
from ingestion.vector_store import RegulatoryVectorStore
from alerting.detector import ChangeDetector
from alerting.slack_alert import send_slack_alert
from register.obligation_register import ObligationRegister
from register.linker import build_obligation_record

logger = logging.getLogger(__name__)


async def run_full_pipeline():
    """Main pipeline: scrape → detect changes → ingest → alert."""
    logger.info("=== Starting Regulatory Scanning Pipeline ===")

    scraper_classes = [NCSCScraper, EEASScraper, OfcomScraper]
    all_docs = []

    for ScraperClass in scraper_classes:
        async with ScraperClass() as scraper:
            docs = await scraper.run()
            all_docs.extend(docs)

    logger.info(f"Total documents scraped: {len(all_docs)}")

    # Detect changes
    detector = ChangeDetector()
    changes = detector.detect_changes(all_docs)
    logger.info(
        f"New: {len(changes['new'])} | Amended: {len(changes['amended'])}"
    )

    # Ingest all into vector store
    chunker = RegulatoryChunker()
    vs = RegulatoryVectorStore()
    total_chunks = 0
    for doc in all_docs:
        chunks = chunker.chunk(doc)
        vs.upsert_chunks(chunks)
        total_chunks += len(chunks)
    logger.info(f"Ingested {total_chunks} chunks into ChromaDB")

    # Populate compliance obligation register from all scraped docs
    register = ObligationRegister()
    reg_count = 0
    for doc in all_docs:
        description = doc.content[:500] if doc.content else ""
        record = build_obligation_record(
            doc=doc,
            obligation_title=doc.title,
            description=description,
            effective_date=doc.publication_date.date().isoformat() if doc.publication_date else "",
        )
        register.upsert_obligation(record)
        reg_count += 1
    logger.info(f"Upserted {reg_count} obligations into compliance register")

    # Alert on new/amended
    if changes["new"] or changes["amended"]:
        send_slack_alert(changes["new"], changes["amended"])
        logger.info("Slack alert sent")

    logger.info("=== Pipeline Complete ===")


def start_scheduler(interval_hours: int = 6):
    """Start the APScheduler to run the pipeline every N hours."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_full_pipeline, "interval", hours=interval_hours, id="reg_scan")
    scheduler.start()
    logger.info(f"Scheduler started — pipeline runs every {interval_hours} hours")
    return scheduler


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_full_pipeline())

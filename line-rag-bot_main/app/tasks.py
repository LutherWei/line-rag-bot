from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import async_session
from app.models import RawMessage
from app.services.llm_service import summarize_and_store
from sqlalchemy import select, update
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

async def scheduled_summarize():
    logger.info("Starting scheduled summarization task")
    async with async_session() as session:
        # Get distinct group_ids with unprocessed messages
        stmt = select(RawMessage.group_id).where(RawMessage.is_processed == False).distinct()
        result = await session.execute(stmt)
        group_ids = result.scalars().all()
        
        for group_id in group_ids:
            # Query messages
            msg_stmt = select(RawMessage).where(
                RawMessage.group_id == group_id,
                RawMessage.is_processed == False
            ).order_by(RawMessage.timestamp)
            msg_result = await session.execute(msg_stmt)
            messages = msg_result.scalars().all()
            
            if len(messages) >= 10:  # Threshold
                # Extract metadata
                participants = list(set([m.user_name for m in messages]))
                if messages:
                    start_date = messages[0].timestamp.strftime("%Y-%m-%d")
                    end_date = messages[-1].timestamp.strftime("%Y-%m-%d")
                    date_range = f"{start_date} to {end_date}" if start_date != end_date else start_date
                else:
                    date_range = datetime.utcnow().strftime("%Y-%m-%d")

                # Summarize and store
                await summarize_and_store(group_id, messages, participants, date_range)
                
                # Mark as processed
                msg_ids = [m.id for m in messages]
                update_stmt = update(RawMessage).where(RawMessage.id.in_(msg_ids)).values(is_processed=True)
                await session.execute(update_stmt)
                await session.commit()
                logger.info(f"Summarized and processed {len(messages)} messages for group {group_id}")

def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduled_summarize, 'cron', hour=0, minute=0) # Run at midnight daily
    # For testing, you might want an interval like minutes=1
    # scheduler.add_job(scheduled_summarize, 'interval', minutes=10)
    scheduler.start()
    logger.info("APScheduler started")

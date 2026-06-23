import httpx
import logging
from app.database import async_session
from app.models import ExtractedUrl

logger = logging.getLogger(__name__)

async def fetch_jina_reader(url: str) -> str:
    jina_url = f"https://r.jina.ai/{url}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(jina_url, timeout=30.0)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Error fetching Jina Reader for {url}: {e}")
            return ""

async def process_url(group_id: str, url: str):
    logger.info(f"Processing URL {url} for group {group_id}")
    raw_content = await fetch_jina_reader(url)
    if not raw_content:
        return
    
    # Store into relational DB
    async with async_session() as session:
        extracted = ExtractedUrl(
            group_id=group_id,
            url=url,
            raw_content=raw_content,
            is_processed=False
        )
        session.add(extracted)
        await session.commit()
        
    logger.info(f"Saved extracted content for {url} to database. Vectorizing now...")
    
    # Vectorize and store in ChromaDB
    from app.services.llm_service import chunk_text
    import google.generativeai as genai
    from app.services.vector_service import store_vectors
    import uuid
    from datetime import datetime
    from app.config import settings
    
    genai.configure(api_key=settings.google_api_key)
    chunks = chunk_text(raw_content)
    if chunks:
        try:
            embedding_model = 'models/text-embedding-004'
            embeddings = []
            for chunk in chunks:
                res = genai.embed_content(
                    model=embedding_model,
                    content=chunk,
                    task_type="retrieval_document"
                )
                embeddings.append(res['embedding'])
                
            metadatas = [
                {
                    "group_id": group_id,
                    "doc_type": "external_url",
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%d"),
                    "source_info": url
                } for _ in chunks
            ]
            
            ids = [str(uuid.uuid4()) for _ in chunks]
            store_vectors(chunks, metadatas, embeddings, ids)
            
            # Mark as processed
            from sqlalchemy import update
            async with async_session() as session:
                stmt = update(ExtractedUrl).where(ExtractedUrl.id == extracted.id).values(is_processed=True)
                await session.execute(stmt)
                await session.commit()
            logger.info(f"Successfully vectorized and processed {url}")
        except Exception as e:
            logger.error(f"Error vectorizing {url}: {e}")


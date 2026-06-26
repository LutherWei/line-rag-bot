from google import genai
from google.genai import types
from app.config import settings
from app.services.vector_service import store_vectors, query_vectors
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

client = genai.Client(api_key=settings.google_api_key)

SUMMARY_PROMPT = """You are an efficient team knowledge management expert. Below is a raw chat log from a LINE group.
Please filter out all meaningless chatter, stickers, and simple agreements (e.g., haha, +1, okay). Extract ONLY the core content that holds knowledge value (e.g., resolutions, schedule changes, equipment borrowing, important announcements, rule clarifications).

When summarizing, you MUST follow these "Information Restoration" principles:
1. Restore Pronouns: Replace "I", "he", "she", "you" with the sender's actual `user_name`.
2. Complete Time Context: If the chat mentions "tomorrow" or "next week," calculate and convert it to an absolute date based on the context (Format: YYYY-MM-DD).

Output strictly in the following Markdown format. Do not include any introductory text or explanations:

### [Summary Topic]
* Date/Range: YYYY-MM-DD
* Core Participants: [List of participant names]
* Key Content: 
  - [Key Point 1]
  - [Key Point 2]"""

RAG_PROMPT = """You are a professional, friendly, and honest LINE group assistant. Please answer the user's question based strictly on the provided [Reference Materials] below.

[Reference Materials]
{Context_with_Metadata_and_Source_Numbers}

[Strict Guidelines]
1. Your answer MUST be entirely grounded in the facts from the [Reference Materials]. If the reference materials do not contain the answer, you must reply directly: "Sorry, I cannot find relevant information from the current group logs and links." Never hallucinate or invent answers.
2. Whenever you cite a reference material in your answer, you MUST mark it at the end of the sentence or paragraph using the [Source Number].
3. At the very end of your complete answer, create a new line and clearly list all cited source details (e.g., discussion date, participants, or external URLs).

[Output Format Example]
Tomorrow's practice is confirmed for 3:00 PM! [Source 1] Also, a reminder that according to the team rules, anyone who is late must buy drinks for the whole team. [Source 2]

─── References ───
📌 Source 1: 2026-06-21 Group Chat Summary (Participants: John, Alice)
🔗 Source 2: External Link (https://example.com/rules)"""

GENERATION_MODEL = 'gemini-2.5-flash'
EMBEDDING_MODEL = 'gemini-embedding-001'

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + chunk_size])
        start += chunk_size - overlap
    return chunks

async def summarize_and_store(group_id: str, messages: list, participants: list, date_range: str) -> bool:
    log_text = "\n".join([f"[{m.timestamp}] {m.user_name}: {m.content}" for m in messages])
    
    try:
        response = client.models.generate_content(
            model=GENERATION_MODEL,
            contents=log_text,
            config=types.GenerateContentConfig(
                system_instruction=SUMMARY_PROMPT
            )
        )
        summary = response.text
        if not summary:
            logger.warning(f"Model returned empty summary for group {group_id}, skipping.")
            return False
    except Exception as e:
        logger.error(f"Error summarizing: {e}")
        return False
    
    chunks = chunk_text(summary)
    
    if not chunks:
        return False
        
    try:
        embeddings = []
        for chunk in chunks:
            res = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=chunk,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT"
                )
            )
            embeddings.append(res.embeddings[0].values)
            
        metadatas = [
            {
                "group_id": group_id,
                "doc_type": "chat_summary",
                "timestamp": date_range,
                "source_info": ", ".join(participants)
            } for _ in chunks
        ]
        
        ids = [str(uuid.uuid4()) for _ in chunks]
        
        store_vectors(chunks, metadatas, embeddings, ids)
        return True
    except Exception as e:
        logger.error(f"Error embedding/storing text: {e}")
        return False

async def process_rag_query(group_id: str, query: str, user_id: str):
    from app.services.line_service import send_push_message
    
    try:
        # 1. Generate query embedding
        res = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=query,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY"
            )
        )
        query_embedding = res.embeddings[0].values
        
        # 2. Query vectors from ChromaDB (Top-10)
        results = query_vectors(group_id, query_embedding, top_k=10)
        
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        
        if not documents:
            logger.info(f"No vector database matches found for query in group: {group_id}")
            await send_push_message(user_id, "Sorry, I cannot find relevant information from the current group logs and links.")
            return

        # 3. Format reference context
        context_parts = []
        for i, (doc, meta) in enumerate(zip(documents, metadatas), start=1):
            doc_type = meta.get("doc_type", "unknown")
            timestamp = meta.get("timestamp", "unknown")
            source_info = meta.get("source_info", "unknown")
            
            if doc_type == "chat_summary":
                source_line = f"📌 Source {i}: {timestamp} Group Chat Summary (Participants: {source_info})"
            elif doc_type == "external_url":
                source_line = f"🔗 Source {i}: External Link ({source_info})"
            elif doc_type == "chat_message":
                source_line = f"💬 Source {i}: {timestamp} Group Chat Message (Sender: {source_info})"
            elif doc_type == "historical_chat":
                source_line = f"📜 Source {i}: {timestamp} Historical Outing Chat ({source_info})"
            else:
                source_line = f"📄 Source {i}: {timestamp} ({source_info})"
                
            context_parts.append(f"[{source_line}]\n{doc}\n")
            
        context_str = "\n".join(context_parts)
        
        # 4. Fill prompt and generate response
        prompt = RAG_PROMPT.replace("{Context_with_Metadata_and_Source_Numbers}", context_str)
        
        response = client.models.generate_content(
            model=GENERATION_MODEL,
            contents=f"{prompt}\n\nUser Question: {query}"
        )
        
        await send_push_message(user_id, response.text)
    except Exception as e:
        logger.error(f"Error in ChromaDB RAG query: {e}")
        await send_push_message(user_id, "Error processing your request.")


async def vectorize_and_store_message(group_id: str, user_name: str, text: str, timestamp: datetime) -> bool:
    if not text.strip():
        return False
    
    try:
        res = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT"
            )
        )
        embedding = res.embeddings[0].values
        
        metadata = {
            "group_id": group_id,
            "doc_type": "chat_message",
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "source_info": user_name
        }
        
        doc_id = str(uuid.uuid4())
        
        store_vectors([text], [metadata], [embedding], [doc_id])
        logger.info(f"Successfully vectorized and stored real-time message for group {group_id} from {user_name}")
        return True
    except Exception as e:
        logger.error(f"Error vectorizing real-time message: {e}")
        return False




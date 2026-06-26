from google import genai
from google.genai import types
from app.config import settings
from app.services.vector_service import store_vectors, query_vectors
import uuid
import logging

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
    import os
    
    try:
        # Read the real-time TXT file
        data_dir = "data"
        file_path = os.path.join(data_dir, f"group_{group_id}.txt")
        
        chat_logs = ""
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                chat_logs += f.read()
                
        # Also include the historical file if it exists
        historical_file = "[LINE]2026 台大擊劍隊暑假社遊.txt"
        if os.path.exists(historical_file):
            with open(historical_file, "r", encoding="utf-8") as f:
                chat_logs += "\n\n--- 歷史對話 (社遊記事本) ---\n"
                chat_logs += f.read()
        
        if not chat_logs.strip():
            logger.info(f"No chat logs found for group: {group_id}")
            await send_push_message(user_id, "目前沒有任何群組對話紀錄。")
            return

        # Prepare the context
        context_str = f"[群組對話紀錄]\n{chat_logs}"
        prompt = RAG_PROMPT.replace("{Context_with_Metadata_and_Source_Numbers}", context_str)
        
        response = client.models.generate_content(
            model=GENERATION_MODEL,
            contents=f"{prompt}\n\nUser Question: {query}"
        )
        
        await send_push_message(user_id, response.text)
    except Exception as e:
        logger.error(f"Error in TXT RAG query: {e}")
        await send_push_message(user_id, "Error processing your request.")



import google.generativeai as genai
from app.config import settings
from app.services.vector_service import store_vectors, query_vectors
import uuid
import logging

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.google_api_key)

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

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + chunk_size])
        start += chunk_size - overlap
    return chunks

async def summarize_and_store(group_id: str, messages: list, participants: list, date_range: str):
    log_text = "\n".join([f"[{m.timestamp}] {m.user_name}: {m.content}" for m in messages])
    
    model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=SUMMARY_PROMPT)
    try:
        response = model.generate_content(log_text)
        summary = response.text
    except Exception as e:
        logger.error(f"Error summarizing: {e}")
        return
    
    chunks = chunk_text(summary)
    
    if not chunks:
        return
        
    try:
        embedding_model = 'models/gemini-embedding-001'
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
                "doc_type": "chat_summary",
                "timestamp": date_range,
                "source_info": ", ".join(participants)
            } for _ in chunks
        ]
        
        ids = [str(uuid.uuid4()) for _ in chunks]
        
        store_vectors(chunks, metadatas, embeddings, ids)
    except Exception as e:
        logger.error(f"Error embedding/storing text: {e}")

async def process_rag_query(group_id: str, query: str, reply_token: str):
    from app.services.line_service import send_reply
    try:
        # Using a model that is widely available in v1beta
        embedding_model = 'models/gemini-embedding-001' # Updated to gemini-embedding-001
        res = genai.embed_content(
            model=embedding_model,
            content=query,
            task_type="retrieval_query"
        )
        query_embedding = res['embedding']
        
        results = query_vectors(group_id, query_embedding)
        
        # Check if results exist and models support (fixing 404 for text-embedding-004 if needed)
        if not results['documents'] or not results['documents'][0]:
            await send_reply(reply_token, "Sorry, I cannot find relevant information from the current group logs and links.")
            return

        contexts = []
        source_idx = 1
        sources_meta = []
        for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
            context_str = f"[Source {source_idx}]\nContent: {doc}\nDoc Type: {meta.get('doc_type')}\nSource Info: {meta.get('source_info')}"
            contexts.append(context_str)
            sources_meta.append(meta)
            source_idx += 1
            
        context_joined = "\n\n".join(contexts)
        
        prompt = RAG_PROMPT.replace("{Context_with_Metadata_and_Source_Numbers}", context_joined)
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(f"{prompt}\n\nUser Question: {query}")
        
        await send_reply(reply_token, response.text)
    except Exception as e:
        logger.error(f"Error in RAG query: {e}")
        await send_reply(reply_token, "Error processing your request.")

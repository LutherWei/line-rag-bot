# LINE Group RAG Bot Development Specification (for AI Coding Agent)

This is a comprehensive system development specification. The AI Coding Agent must strictly follow the architecture, database schema, data flows, and development steps outlined below to implement a LINE Group RAG (Retrieval-Augmented Generation) system using **Python / FastAPI**. This system features an asynchronous "Chat Summarization Layer" and "Web Content Tracking."

---

## 1. Tech Stack

* **Backend Framework:** FastAPI (Fully asynchronous `async/await` architecture)
* **Relational Database:** PostgreSQL
* **DB Driver & ORM:** `asyncpg` + SQLAlchemy 2.0 (Async Engine)
* **Vector Database:** ChromaDB (Local persistent mode) or Qdrant
* **LLM Integration:** Google GenAI SDK (Use `gemini-1.5-flash` for generation and summarization; `text-embedding-004` for text embedding)
* **Background Tasks & Scheduling:** FastAPI `BackgroundTasks` (for immediate web scraping) + `APScheduler` (for scheduled chat summarization)
* **Web Content Extraction:** Jina Reader API (`https://r.jina.ai/{URL}`)
* **Environment Variable Management:** `pydantic-settings`

---

## 2. Project Directory Structure

Please initialize the project with the following structure:

```text
line-rag-bot/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI entry point & LINE Webhook routing
│   ├── config.py            # Environment variables & system settings (Pydantic Settings)
│   ├── database.py          # PostgreSQL async connection & Session management
│   ├── models.py            # SQLAlchemy 2.0 data models
│   ├── schemas.py           # Pydantic data validation schemas
│   ├── tasks.py             # APScheduler scheduled summarization tasks
│   └── services/
│       ├── __init__.py
│       ├── line_service.py  # Handle LINE Messaging API (Signature validation, Reply)
│       ├── llm_service.py   # Encapsulate Gemini generation, summarization & embedding logic
│       ├── vector_service.py# Encapsulate ChromaDB CRUD & isolated retrieval
│       └── crawler_service.py# Encapsulate Jina Reader API web scraping logic
├── .env.example
├── requirements.txt
└── README.md
3. Database Schema Design
A. Relational Database (PostgreSQL Models)
1. raw_messages (Stores raw chat logs to prevent data loss under high concurrency)
id: UUID (Primary Key, default to gen_random_uuid())

group_id: String (LINE Group ID, create an Index on this)

user_name: String (Sender's display name)

content: Text (Message text content)

timestamp: DateTime (Message sent time, timezone-aware)

is_processed: Boolean (Default False. Update to True once included in the scheduled summarization)

2. extracted_urls (Stores tracked web pages and processing status)
id: UUID (Primary Key)

group_id: String (LINE Group ID)

url: String (Original URL)

raw_content: Text (Markdown content converted via Jina Reader)

is_processed: Boolean (Default False. Update to True after vectorization and storage in ChromaDB)

created_at: DateTime (Default to current time)

B. Vector Database Design (ChromaDB Metadata)
All text chunks stored in the vector database MUST bind the following Metadata to ensure Group Permission Isolation and Source Provenance:

Collection Name: group_knowledge

Metadata Fields:

group_id: String (Mandatory for Similarity Search filtering: where={"group_id": current_group_id})

doc_type: String (Enum: "chat_summary" or "external_url")

timestamp: String (Date or time range when the data was generated, e.g., "2026-06-22")

source_info: String (Provenance explanation. For chat summaries, input the participant list like "John, Alice"; for web pages, input the original URL)

4. Core Business Logic & Pipeline
Flow 1: Webhook Message Reception & Routing (Write Flow)
When POST /webhook receives a LINE message event:

Parse Immediately: Extract group_id, user_name, text, and timestamp.

Routing Logic:

URL Detection via Regex: If text contains a URL, pass the URL to FastAPI BackgroundTasks to execute crawler_service.process_url (Do NOT block the Webhook).

Wake Word Detection: If text starts with @help (or the designated wake word), forward the request to Flow 3 (RAG Engine).

General Chat: Asynchronously insert the data into the PostgreSQL raw_messages table.

Immediate Response: Return 200 OK to the LINE server (Must be completed within 3 seconds).

Flow 2: Asynchronous Chat Summarization & Extraction (Scheduled)
Use APScheduler to set up a cron job (e.g., hourly or midnight daily):

Query all conversations from raw_messages with a specific group_id where is_processed == False, ordered by time.

If the message count exceeds the threshold (e.g., 10 messages), batch them and call gemini-1.5-flash using the "Summarization Prompt" below.

Perform Text Chunking on the LLM's structured summary output (Suggested: 500-800 tokens per chunk, 100 tokens overlap).

Call text-embedding-004 to generate vectors for the chunks.

Store the vectors along with Metadata (doc_type="chat_summary", source_info="Participant List") into ChromaDB.

Batch update the is_processed flag of these raw messages to True.

Flow 3: RAG Retrieval & Generation Engine (Read Flow)
When triggered by the wake word (e.g., @help):

Clean the query string (remove the @help tag) and call text-embedding-004 to vectorize the question.

Perform Similarity Search in ChromaDB. Mandatory filter: where={"group_id": current_group_id}.

Retrieve the Top-K (e.g., Top 3) most relevant Contexts.

Assemble the Context, relevant Metadata, and the user's question, then call gemini-1.5-flash to generate the answer.

Parse the generated answer and source citations, and send it back to the group via LINE Reply API.

5. Key Prompt Design
The Agent must encapsulate the following Prompts in llm_service.py:

A. Chat Summarization Prompt (System Prompt)
Plaintext
You are an efficient team knowledge management expert. Below is a raw chat log from a LINE group.
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
  - [Key Point 2]
B. RAG Q&A and Provenance Prompt (System Prompt)
Plaintext
You are a professional, friendly, and honest LINE group assistant. Please answer the user's question based strictly on the provided [Reference Materials] below.

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
🔗 Source 2: External Link ([https://example.com/rules](https://example.com/rules))
6. Development Milestones
The Agent must complete the following tasks sequentially and report after each stage is done:

Stage 1: Initialize the project. Write config.py and configure the PostgreSQL async connection pool using SQLAlchemy + asyncpg. Define the database tables in models.py.

Stage 2: Implement services/crawler_service.py. Use httpx to integrate the Jina Reader API. Write the FastAPI BackgroundTasks logic to ensure web pages can be successfully scraped, converted to Markdown, and saved to extracted_urls.

Stage 3: Implement the /webhook route in main.py. Integrate LINE Signature Validation (X-Line-Signature) and the message routing/database insertion logic.

Stage 4: Implement the summarization pipeline in tasks.py and services/llm_service.py. Ensure that when the scheduler triggers, unprocessed messages are correctly sent to Gemini 1.5 Flash for structured summarization, embedded, stored in ChromaDB, and their status updated.

Stage 5: Implement the RAG retrieval logic. Ensure that group_id isolation is applied during Similarity Search. Debug the final Q&A Prompt to guarantee the LINE reply accurately includes the answer and source tags.
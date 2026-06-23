import chromadb
from app.config import settings

client = chromadb.PersistentClient(path=settings.chromadb_path)
collection = client.get_or_create_collection(name="group_knowledge")

def store_vectors(texts: list[str], metadatas: list[dict], embeddings: list[list[float]], ids: list[str]):
    collection.add(
        documents=texts,
        metadatas=metadatas,
        embeddings=embeddings,
        ids=ids
    )

def query_vectors(group_id: str, query_embedding: list[float], top_k: int = 3):
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"group_id": group_id}
    )
    return results

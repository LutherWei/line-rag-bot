import os
import uuid
from google import genai
from google.genai import types
from app.config import settings
from app.services.vector_service import store_vectors
from app.services.llm_service import chunk_text, EMBEDDING_MODEL

def main():
    historical_file = "[LINE]2026 台大擊劍隊暑假社遊.txt"
    if not os.path.exists(historical_file):
        print(f"找不到檔案 {historical_file}")
        return
        
    with open(historical_file, "r", encoding="utf-8") as f:
        content = f.read()
        
    print("正在切分文字...")
    chunks = chunk_text(content, chunk_size=500, overlap=100)
    print(f"切分成 {len(chunks)} 個區塊")
    
    client = genai.Client(api_key=settings.google_api_key)
    
    group_ids = settings.allowed_group_id_list
    if not group_ids:
        print("未在 .env 設定 ALLOWED_GROUP_IDS，將使用預設的 Ce917c526c2d12ae21eb74207e7e246f7")
        group_ids = ["Ce917c526c2d12ae21eb74207e7e246f7"]
        
    for group_id in group_ids:
        print(f"正在為群組 {group_id} 向量化並儲存歷史資料...")
        embeddings = []
        for i, chunk in enumerate(chunks):
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
                "doc_type": "historical_chat",
                "timestamp": "2026-06-19 to 2026-06-25",
                "source_info": "Historical Fencing Outing Chat"
            } for _ in chunks
        ]
        ids = [str(uuid.uuid4()) for _ in chunks]
        
        from app.services.vector_service import collection
        print("Before store_vectors, collection count:", collection.count())
        store_vectors(chunks, metadatas, embeddings, ids)
        print("After store_vectors, collection count:", collection.count())
        print(f"群組 {group_id} 的歷史資料儲存完成！")

if __name__ == "__main__":
    main()

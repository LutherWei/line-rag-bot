import chromadb
from app.config import settings

def list_chroma():
    print("正在連接至 ChromaDB 向量資料庫...")
    print(f"資料庫儲存路徑: {settings.chromadb_path}")
    
    try:
        client = chromadb.PersistentClient(path=settings.chromadb_path)
        collections = client.list_collections()
        
        if not collections:
            print("目前 ChromaDB 中沒有任何集合 (Collections)。")
            return
            
        print(f"\n共找到 {len(collections)} 個集合：")
        for col in collections:
            count = col.count()
            print(f"\n📁 集合名稱: '{col.name}' (共有 {count} 筆資料)")
            print("=" * 70)
            
            if count == 0:
                print("此集合目前是空的。")
                continue
                
            # Fetch all items in the collection
            all_items = col.get()
            documents = all_items.get("documents", [])
            metadatas = all_items.get("metadatas", [])
            ids = all_items.get("ids", [])
            
            for idx, (doc_id, doc, meta) in enumerate(zip(ids, documents, metadatas), start=1):
                doc_type = meta.get("doc_type", "unknown")
                timestamp = meta.get("timestamp", "unknown")
                source_info = meta.get("source_info", "unknown")
                group_id = meta.get("group_id", "unknown")
                
                print(f"\n[{idx}] ID: {doc_id}")
                print(f"    類型 (doc_type)   : {doc_type}")
                print(f"    時間 (timestamp)  : {timestamp}")
                print(f"    來源 (source_info): {source_info}")
                print(f"    群組 (group_id)   : {group_id}")
                snippet = doc[:120].replace('\n', ' ')
                print(f"    內容 (document)   : {snippet}...")
            print("=" * 70)
            
    except Exception as e:
        print(f"讀取 ChromaDB 時發生錯誤: {e}")

if __name__ == "__main__":
    list_chroma()

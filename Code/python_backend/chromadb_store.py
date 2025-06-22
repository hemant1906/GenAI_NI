# chroma_store.py

import chromadb
from chromadb import HttpClient
from sentence_transformers import SentenceTransformer

# Use ChromaDB running in Docker (via HTTP)
chroma_client = HttpClient(host="localhost", port=8000)  # Adjust if container runs on another host/port
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

def get_or_create_collection(collection_name):
    return chroma_client.get_or_create_collection(name=collection_name)

collection = chroma_client.get_or_create_collection("diagrams_index")

def store_diagram_summary(diagram_id, diagram_name, asset_id, summary, description):
    texts = [summary, description]
    embeddings = embedding_model.encode(texts).tolist()

    collection.add(
        documents=texts,
        embeddings=embeddings,
        ids=[f"{diagram_id}_summary", f"{diagram_id}_description"],
        metadatas=[
            {"type": "summary", "diagram_id": diagram_id, "name": diagram_name, "asset_id": asset_id},
            {"type": "description", "diagram_id": diagram_id, "name": diagram_name, "asset_id": asset_id}
        ]
    )

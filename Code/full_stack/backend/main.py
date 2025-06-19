import os
import faiss
import numpy as np
import pickle
import openai
import asyncpg
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# OpenAI API Key (Replace with your key)
OPENAI_API_KEY = "your_openai_api_key"

# PostgreSQL Connection
PG_CONN = None

async def connect_db():
    global PG_CONN
    PG_CONN = await asyncpg.create_pool(
        database="architecture_db",
        user="admin",
        password="admin123",
        host="postgres_db",
        port="5432"
    )

# Neo4j Connection
NEO4J_URI = "bolt://neo4j_db:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password123"
neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# FAISS Index File Paths
FAISS_INDEX_FILE = "data/faiss_index.bin"
METADATA_FILE = "data/embedding_store.pkl"

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

# Initialize FAISS Index
dimension = 768  # Example embedding size
faiss_index = faiss.IndexFlatL2(dimension)

# Store metadata for embeddings
embedding_store = {}  # {index_id: {"diagram_id": 1, "name": "Architecture Diagram"}}

# Sentence Transformer for local embeddings
sentence_model = SentenceTransformer("all-MiniLM-L6-v2")

# Load FAISS Index & Metadata if exists
def load_faiss():
    global faiss_index, embedding_store
    if os.path.exists(FAISS_INDEX_FILE):
        faiss_index = faiss.read_index(FAISS_INDEX_FILE)
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, "rb") as f:
            embedding_store = pickle.load(f)

# Save FAISS Index & Metadata
def save_faiss():
    faiss.write_index(faiss_index, FAISS_INDEX_FILE)
    with open(METADATA_FILE, "wb") as f:
        pickle.dump(embedding_store, f)

# OpenAI Embedding Function
def get_openai_embedding(text: str):
    response = openai.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    return np.array(response.data[0].embedding).astype("float32")

# Sentence Transformer Embedding Function
def get_local_embedding(text: str):
    return np.array(sentence_model.encode(text)).astype("float32")

# Startup Event
@app.on_event("startup")
async def startup():
    print("Connecting to PostgreSQL...")
    await connect_db()
    print("Loading FAISS index and metadata...")
    load_faiss()

# Shutdown Event
@app.on_event("shutdown")
async def shutdown():
    print("Saving FAISS index and metadata...")
    save_faiss()
    print("Closing PostgreSQL connection...")
    await PG_CONN.close()
    neo4j_driver.close()

@app.post("/upload-diagram/")
async def upload_diagram(file: UploadFile = File(...), diagram_name: str = Form(...)):
    try:
        # Save the uploaded file
        file_path = f"uploads/{file.filename}"
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Convert diagram to Mermaid code using OpenAI
        openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
        prompt = f"Convert this architecture diagram to Mermaid code:\n{file.filename}"
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        mermaid_code = response.choices[0].message.content

        # Generate summary & description
        summary_prompt = f"Summarize this architecture diagram:\n{mermaid_code}"
        summary_response = openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": summary_prompt}]
        )
        summary = summary_response.choices[0].message.content

        # Store in PostgreSQL
        async with PG_CONN.acquire() as conn:
            await conn.execute(
                "INSERT INTO diagrams (name, file_path, mermaid_code, summary) VALUES ($1, $2, $3, $4)",
                diagram_name, file_path, mermaid_code, summary
            )

        return {"message": "Diagram uploaded successfully", "mermaid_code": mermaid_code, "summary": summary}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/store-nodes/")
async def store_nodes(diagram_name: str):
    try:
        async with PG_CONN.acquire() as conn:
            result = await conn.fetchrow("SELECT mermaid_code FROM diagrams WHERE name = $1", diagram_name)

        if not result:
            raise HTTPException(status_code=404, detail="Diagram not found")

        mermaid_code = result["mermaid_code"]

        # Extract nodes & relationships (Basic Parsing)
        nodes = [line.split("[")[0].strip() for line in mermaid_code.split("\n") if "-->" in line]
        relationships = [line.strip() for line in mermaid_code.split("\n") if "-->" in line]

        with neo4j_driver.session() as session:
            for node in nodes:
                session.run("MERGE (n:Node {name: $name}) RETURN n", name=node)

            for rel in relationships:
                src, dst = rel.split("-->")
                session.run("MATCH (a:Node {name: $src}), (b:Node {name: $dst}) "
                            "MERGE (a)-[:CONNECTS_TO]->(b)", src=src.strip(), dst=dst.strip())

        return {"message": "Nodes and relationships stored successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/add-diagram/")
async def add_diagram(diagram_id: int, name: str, summary: str, description: str, use_openai: bool = True):
    try:
        text = f"{summary} {description}"
        embedding = get_openai_embedding(text) if use_openai else get_local_embedding(text)

        faiss_index.add(embedding.reshape(1, -1))
        index_id = faiss_index.ntotal - 1
        embedding_store[index_id] = {"diagram_id": diagram_id, "name": name}

        save_faiss()
        return {"message": "Diagram added successfully", "index_id": index_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/semantic-search/")
async def semantic_search(query: str, use_openai: bool = True):
    try:
        query_embedding = get_openai_embedding(query) if use_openai else get_local_embedding(query)

        _, indices = faiss_index.search(query_embedding.reshape(1, -1), k=5)
        results = [embedding_store[idx] for idx in indices[0] if idx in embedding_store]

        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/")
async def status():
    return {
        "faiss_index_size": faiss_index.ntotal,
        "stored_embeddings": len(embedding_store),
        "neo4j_status": "Connected",
        "postgres_status": "Connected"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

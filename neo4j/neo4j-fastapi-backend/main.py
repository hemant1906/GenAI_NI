from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from neo4j import GraphDatabase
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite's default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Neo4j connection details
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "grAph#123"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


class QueryRequest(BaseModel):
    cypher: str


@app.post("/api/query")
async def run_cypher_query(request: QueryRequest):
    try:
        with driver.session() as session:
            result = session.run(request.cypher)
            nodes = []
            relationships = []
            node_ids = set()

            for record in result:
                for value in record.values():
                    if hasattr(value, 'labels'):
                        if value.id not in node_ids:
                            nodes.append({
                                'id': str(value.id),
                                'labels': list(value.labels),
                                'properties': dict(value.items())
                            })
                            node_ids.add(value.id)
                    elif hasattr(value, 'type'):
                        relationships.append({
                            'id': str(value.id),
                            'type': value.type,
                            'start': str(value.start_node.id),
                            'end': str(value.end_node.id),
                            'properties': dict(value.items())
                        })

            # print({"nodes": nodes, "relationships": relationships})

            return {
                "nodes": nodes,
                "relationships": relationships
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}
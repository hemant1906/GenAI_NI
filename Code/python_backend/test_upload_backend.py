from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import os
import uuid
import psycopg2
import io
from PIL import Image
from pydantic import BaseModel
from neo4j import GraphDatabase
import re
from html import unescape

# Load API Key from .env
load_dotenv()

# DB connection
conn = psycopg2.connect(
    dbname="postgres", user="postgres", password="mysecretpassword", host="localhost", port="5432"
)
cur = conn.cursor()

# FastAPI App
app = FastAPI()

# CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# Neo4j config (update with your creds)
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password123"

def get_neo4j_driver():
    try:
        return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    except Exception as e:
        print("Neo4j driver init failed:", e)
        return None

driver = get_neo4j_driver()

class MermaidInput(BaseModel):
    diagram_id: str
    mermaid_code: str

def parse_mermaid_code(code: str):
    lines = [line.strip() for line in code.strip().splitlines() if line.strip()]
    nodes = {}
    edges = []
    current_subgraph = None

    node_def_pattern = re.compile(r'^(\w+)\s*\["([^"]+)"\]')
    edge_pattern = re.compile(r'^(\w+)\s*-->\|([^|]+)\|\s*(\w+)$')

    for line in lines:
        try:
            if line.lower().startswith("subgraph"):
                match = re.search(r'"([^"]+)"', line)
                current_subgraph = match.group(1) if match else "Ungrouped"

            elif line.lower() == "end":
                current_subgraph = None

            elif node_def_pattern.match(line):
                match = node_def_pattern.match(line)
                if match and len(match.groups()) == 2:
                    node_id = match.group(1)
                    raw_label = match.group(2)
                    label = unescape(raw_label.replace("<br>", " ").strip())
                    nodes[node_id] = {
                        "id": node_id,
                        "label": label,
                        "group": current_subgraph or "Ungrouped"
                    }
                else:
                    print("!! Node match failed or malformed:", line)

            elif edge_pattern.match(line):
                match = edge_pattern.match(line)
                if match:
                    from_node, relation, to_node = match.groups()
                    edges.append({
                        "from": from_node,
                        "to": to_node,
                        "label": relation.strip()
                    })
                else:
                    print("!! Edge match failed or malformed:", line)

        except Exception as e:
            print("!! Error parsing line:", line)
            print("Exception:", str(e))

    return list(nodes.values()), edges

def store_in_neo4j(diagram_id, nodes, edges):
    with driver.session() as session:
        session.execute_write(lambda tx: _store(tx, diagram_id, nodes, edges))

def _store(tx, diagram_id, nodes, edges):
    for node in nodes:
        tx.run(
            "MERGE (n:Node {id: $id}) "
            "SET n.label = $label, n.diagram_id = $diagram_id, n.group = $group",
            id=node["id"],
            label=node["label"],
            group=node["group"],
            diagram_id=diagram_id
        )

    for edge in edges:
        rel_type = edge["label"].strip().upper()
        cypher = f"""
                MATCH (a:Node {{id: $from_id, diagram_id: $diagram_id}})
                MATCH (b:Node {{id: $to_id, diagram_id: $diagram_id}})
                MERGE (a)-[r:`{rel_type}`]->(b)
            """
        tx.run(
            cypher,
            from_id=edge["from"],
            to_id=edge["to"],
            label=edge["label"],
            diagram_id=diagram_id
        )

@app.post("/upload/")
def upload_image(image: UploadFile, diagram_name: str = Form(...), asset_id: str = Form(...)):
    try:
        diagram_id = 'DIAGRAM_ID_1'
        cur.execute("SELECT diagram_mermaid_code FROM diagrams WHERE diagram_id = %s", (diagram_id,))
        result = cur.fetchone()
        if result is None:
            raise ValueError("No diagram found.")
        mermaid_code = result[0]
        conn.commit()

        return JSONResponse({
            "status": "success",
            "diagram_id": "TEST ID",
            "mermaid_code": mermaid_code.strip(),
            "summary": "TEST SUMMARY",
            "description": "TEST DESCRIPTION"
        })

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/parse-mermaid/")
def parse_and_store_mermaid():
    try:
        diagram_id = '005ef7a9-2c5a-4efc-b2a6-ddcb36e2dd68'
        cur.execute("SELECT diagram_mermaid_code FROM diagrams WHERE diagram_id = %s", (diagram_id,))
        result = cur.fetchone()
        if result is None:
            raise ValueError("No diagram found.")
        mermaid_code = result[0]
        conn.commit()
        nodes, edges = parse_mermaid_code(mermaid_code)
        store_in_neo4j(diagram_id, nodes, edges)
        return {
            "message": "Mermaid parsed and stored in Neo4j."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
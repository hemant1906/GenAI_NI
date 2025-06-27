from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import base64
import os
import psycopg2
from uuid import uuid4
import requests
from neo4j import GraphDatabase
from final_chromadb_upload import client, store_diagram_summary, store_application, store_complexity_entry
import re
from dotenv import load_dotenv
import json
import chromadb
import google.generativeai as genai
from typing import List, Dict, Set, Tuple

# Load API Key from .env
load_dotenv()

# Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password123"
PG_CONN = psycopg2.connect(
    host="localhost", dbname="postgres", user="postgres", password="mysecretpassword"
)

# FastAPI Setup
app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# Global chat memory dictionary
chat_memory = {}  # Format: {session_id: "previous conversation text"}

# Max characters of conversation to retain per session (adjust as needed)
MAX_HISTORY_LENGTH = 4000

# --- Upload Section --- #

@app.post("/upload/")
def upload_image(image: UploadFile, diagram_name: str = Form(...), asset_id: str = Form(...)):
    try:

        # Image to base64
        img_b64 = base64.b64encode(image.file.read()).decode()
        '''
        # Structured Gemini Prompt
        prompt = """
        You are an expert Enterprise Architect. Analyze the provided system architecture diagram. From the diagram, extract the following:

1. **Mermaid** (The code must follow these specific formatting rules:
- DO NOT include word Mermaid or ```mermaid or other wrappers in the output. The code block should start with graph TD (instead of Mermaid title)
- Include a comment line with the group name before each subgraph, e.g., %% Digital Channels.
- The subgraph name itself must be in double quotes, e.g., subgraph "Digital Channels".
- Application node definitions must not have double quotes around the title, e.g., PBCP[Private Banking Client Portal].
- Include a %% Connections comment before listing the relationships.
- Relationships between systems must be represented in [Source System Code] -->|[Relationship Type]| [Target System Code] format. For example: APP001 -->|API| APP002.
- Remove any special characters like - or hyphen from the relationship type in [Source System Code] -->|[Relationship Type]| [Target System Code].
- Exclude <br> or </br> tags from the code.)
2. **Summary** (max 50 words)
3. **Description** (max 200 words)
4. **Applications List**, for each:
   - Title
   - Application node
   - Application Group/Category
   - Relationships with other components in natural language and should include source application node and target application node. 

5. **System Complexity Table** showing:
   - Component Name  
   - Complexity Score (Low/Medium/High)  
   - Reason for Complexity (e.g., Many integrations, legacy tech, critical path dependency)  

6. **Pros** of this architecture considering scalability, maintainability, security, and integration complexity. Don't include **bold** markers in the result. Output should be like:
**Pros**
- Scalability: ...
- Maintainability: ...
7. **Cons** of this architecture considering scalability, maintainability, security, and integration complexity. Don't include **bold** markers in the result. Output should be like:
**Cons**
- Scalability: ...
- Integration Complexity: ...

Format your response as:

**Mermaid**  
(The Mermaid code block should start here, without a title)
...  

**Summary**  
...  

**Description**  
...  

**Applications**  
- Title: ...  
- System Code: ...  
- Group: ...  
- Relationships:  
  - ...  

**System Complexity Table**  
| Component      | Complexity | Reason                       |  
|----------------|------------|------------------------------|  
| API Gateway    | High       | Central integration point    |  
| Identity Mgmt  | Medium     | Moderate coupling            |  

**Pros**  
- ...  

**Cons**  
- ...  

The output must contain one clearly separated block per application, using the structure shown. No additional commentary or formatting is needed beyond the required fields.
"""

        # Gemini API Call
        gemini_resp = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent",
            headers={"Content-Type": "application/json"},
            params={"key": GEMINI_API_KEY},
            json={
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": "image/png", "data": img_b64}}
                        ]
                    }
                ]
            },
        )
        
        result = gemini_resp.json()

        
        with open("test_response_genai_3.json", "w") as f:
            json.dump(gemini_resp.json(), f, indent=2)

        '''
        with open("test_response_genai_3.json", "r") as f:
            result = json.load(f)


        if "candidates" not in result:
            raise HTTPException(status_code=500, detail=result)

        output_text = result["candidates"][0]["content"]["parts"][0]["text"]

        # Example response chunks
        sections = re.split(r"\*\*(.*?)\*\*", output_text)

        # Parse Response
        mermaid = ""
        summary = ""
        description = ""
        applications = []
        complexity_table = []
        pros = []
        cons = []

        for i, section in enumerate(sections):
            if section.strip().lower() == "mermaid":
                mermaid = sections[i + 1].strip()
            elif section.strip().lower() == "summary":
                summary = sections[i + 1].strip()
            elif section.strip().lower() == "description":
                description = sections[i + 1].strip()
            elif section.strip().lower() == "applications":
                apps_text = sections[i + 1].strip()
                app_blocks = re.split(r"-\s*Title:", apps_text)

                for block in app_blocks[1:]:
                    lines = block.strip().split("\n")
                    title = lines[0].strip()
                    system_code = lines[1].replace("System Code:", "").strip()
                    group = lines[2].replace("Group:", "").strip()
                    relationships = [
                        line.strip("- ").strip()
                        for line in lines[4:]
                        if line.strip().startswith("-")
                    ]

                    applications.append({
                        "title": title,
                        "system_code": system_code,
                        "group": group,
                        "relationships": relationships
                    })
            elif "System Complexity Table" in section:
                table_text = sections[i + 1].strip()
                rows = table_text.splitlines()[2:]  # Skip header lines

                for row in rows:
                    cols = [col.strip() for col in row.split("|") if col.strip()]
                    if len(cols) == 3:
                        complexity_table.append({
                            "component": cols[0],
                            "complexity": cols[1],
                            "reason": cols[2]
                        })
            elif section.strip().lower() == "pros":
                raw_pros = sections[i + 1].strip()
                pros = [
                    line.lstrip("- ").strip()
                    for line in raw_pros.splitlines()
                    if line.strip().startswith("-")
                ]
            elif section.strip().lower() == "cons":
                raw_cons = sections[i + 1].strip()
                cons = [
                    line.lstrip("- ").strip()
                    for line in raw_cons.splitlines()
                    if line.strip().startswith("-")
                ]

        # Store Mermaid to PostgreSQL
        diagram_id = f"DIAGRAM_{str(uuid4())[:8]}"
        with PG_CONN.cursor() as cur:
            cur.execute(
                "INSERT INTO DIAGRAMS (diagram_id, diagram_mermaid_code, diagram_name) VALUES (%s, %s, %s)",
                (diagram_id, mermaid, diagram_name),
            )
            PG_CONN.commit()

            cur.execute("SELECT * FROM ASSETS WHERE asset_id = %s", (asset_id,))
            if cur.fetchone():
                cur.execute("UPDATE ASSETS SET asset_diagram_id = %s WHERE asset_id = %s", (diagram_id, asset_id))
            else:
                cur.execute(
                    "INSERT INTO ASSETS (asset_id, asset_diagram_id, asset_name, asset_description) VALUES (%s, %s, '', '')",
                    (asset_id, diagram_id),
                )
            PG_CONN.commit()

        # Store Mermaid to Neo4j
        nodes, edges = parse_mermaid(mermaid)
        with driver.session() as session:
            session.execute_write(store_graph, diagram_id, nodes, edges)

        # Store diagram-level doc
        store_diagram_summary(diagram_id, diagram_name, summary, description, pros, cons)

        # Store each application separately
        for app in applications:
            store_application({
                "title": app["title"],
                "system_code": app["system_code"],
                "group": app["group"],
                "relationships": app["relationships"],
                "diagram_id": diagram_id,
                "diagram_name": diagram_name
            })

        # Store complexity data
        for entry in complexity_table:
            store_complexity_entry(diagram_id, entry['component'], entry['complexity'], entry['reason'])

        return {
            "diagram_id": diagram_id,
            "mermaid_code": mermaid,
            "summary": summary,
            "description": description,
            "nodes": nodes,
            "edges": edges,
            "complexity_table": complexity_table,
            "pros": pros,
            "cons": cons
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Chat Section with simple RAM based chat history --- #

def infer_collection(prompt: str) -> str:
    prompt_lower = prompt.lower()

    if any(keyword in prompt_lower for keyword in ["complexity", "risk", "rationale", "complex"]):
        return "architecture_complexity"

    elif any(keyword in prompt_lower for keyword in ["application", "app", "asset", "integration", "relationship", "upstream", "downstream", "connection"]):
        return "architecture_applications"

    elif any(keyword in prompt_lower for keyword in ["diagram", "cons", "pros", "summary", "description", "architecture", "design"]):
        return "architecture_diagrams"

    else:
        return "architecture_diagrams"

# Config
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Gemini Model
model = genai.GenerativeModel("gemini-2.5-pro")

@app.post("/generate_session/")
def generate_session():
    """Generates a new session_id for chat tab."""
    session_id = str(uuid4())
    chat_memory[session_id] = ""
    return {"session_id": session_id}

@app.post("/reset_session/")
def reset_session(session_id: str = Form(...)):
    """Resets memory for the provided session_id."""
    if session_id in chat_memory:
        chat_memory[session_id] = ""
        return {"message": f"Session {session_id} has been cleared."}
    return {"error": "Session ID not found."}

@app.post("/chat/")
def chat(query: str = Form(...), session_id: str = Form(...)):
    try:
        # Validate collection input
        valid_collections = [
            "architecture_diagrams",
            "architecture_applications",
            "architecture_complexity"
        ]

        if session_id not in chat_memory:
            return {"error": "Invalid session_id. Generate one first."}

            # Auto-select collection
        collection = infer_collection(query)

        if collection not in valid_collections:
            return {"error": "Failed to infer collection."}

        # Retrieve past conversation (if any)
        context_text = chat_memory.get(session_id, "")

        coll = client.get_collection(name=collection)

        search_res = coll.query(
            query_texts=[query],
            n_results=5,
            include=["metadatas", "documents"]
        )

        results = []
        for doc, meta in zip(search_res["documents"][0], search_res["metadatas"][0]):
            results.append(f"{meta.get('source', '')}: {doc}")

        context_docs = "\n\n".join(results) if results else "No relevant documents found."

        full_prompt = f"""
You are an expert system assistant. Based on the following {collection.replace('_', ' ')} information, answer the question clearly:

**Conversation so far:**
{context_text}

**Documents:**
{context_docs}

**Question:** {query}
"""

        response = model.generate_content(full_prompt)
        answer = response.text.strip() if hasattr(response, 'text') else "Error processing response."

        # Update memory
        chat_memory[session_id] = context_text + f"\n\nQ: {query}\nA: {answer}"

        return {"response": answer}

    except Exception as e:
        return {"error": str(e)}

# --- Domain and Capabilities section --- #

def fetch_asset_ids(domain: str, capability: str) -> List[str]:
    with PG_CONN.cursor() as cur:
        cur.execute("SELECT asset_id FROM assets WHERE asset_domain = %s AND asset_capability = %s", (domain,capability))
        result = cur.fetchall()
        PG_CONN.commit()
        return [row[0] for row in result]

# Used r.interface_type instead type(r) due to sample data. May need to update with final data.
def get_interface_type_counts(asset_ids: List[str]) -> List[Dict[str, int]]:
    query = """
    MATCH (a)-[r]->(b)
    WHERE a.id IN $ids AND r.interface_type IS NOT NULL
    RETURN r.interface_type AS type, COUNT(DISTINCT a.id + '_' + b.id + '_' + r.interface_type) AS count
    """
    with driver.session() as session:
        result = session.run(query, ids=asset_ids)
        return [{record["type"]: record["count"]} for record in result]

# Used r.interface_type instead type(r) due to sample data. May need to update with final data.
def get_relationships_by_interface_type(asset_ids: List[str], interface_type: str) -> List[Dict[str, str]]:
    query = """
    MATCH (a)-[r]->(b)
    WHERE a.id IN $ids AND r.interface_type = $interface_type
    RETURN a.id AS from_node, a.name AS source_name, b.name AS target_name, b.id AS to_node, r.interface_type AS interface_type, r.protocol AS protocol
    """
    unique_edges: Set[Tuple[str, str, str, str, str, str]] = set()
    with driver.session() as session:
        result = session.run(query, ids=asset_ids, interface_type=interface_type)
        for record in result:
            edge = (
                record["from_node"],
                record["source_name"],
                record["to_node"],
                record["target_name"],
                record["interface_type"],
                record.get("protocol", "")
            )
            if edge not in unique_edges:
                unique_edges.add(edge)
    return [
        {
            "from_node": from_node,
            "source_name": source_name,
            "to_node": to_node,
            "target_name": target_name,
            "interface_type": itype,
            "protocol": protocol
        }
        for (from_node, source_name, to_node, target_name, itype, protocol) in unique_edges
    ]

# Domain partial search
@app.get("/get_domains")
def autocomplete_domain(q: str = Query(..., min_length=3)):
    with PG_CONN.cursor() as cur:
        cur.execute("SELECT DISTINCT asset_domain FROM assets WHERE asset_domain ILIKE %s", (f"{q}%",))
        rows = cur.fetchall()
        matches = [row[0] for row in rows if row[0]]
        PG_CONN.commit()
    return {"results": matches}

# Capability partial search
@app.get("/get_capabilities")
def autocomplete_capability(q: str = Query(..., min_length=3)):
    with PG_CONN.cursor() as cur:
        cur.execute("SELECT DISTINCT asset_capability FROM assets WHERE asset_capability ILIKE %s", (f"{q}%",))
        rows = cur.fetchall()
        matches = [row[0] for row in rows if row[0]]
        PG_CONN.commit()
    return {"results": matches}

# Get count per interface
@app.get("/get_interface_type_counts")
def interface_summary(domain: str, capability: str):
    try:
        if not domain or not capability:
            return {"results": []}
        asset_ids = fetch_asset_ids(domain, capability)
        if not asset_ids:
            return {"results": []}
        summary = get_interface_type_counts(asset_ids)
        return summary
    except Exception as e:
        print("[ERROR] /get_interface_type_counts:", e)
        raise HTTPException(status_code=500, detail=str(e))

# Get relationships by interface type
@app.get("/get_nodes_by_d_c_interface")
def get_nodes_by_d_c_interface(domain: str = Query(...), capability: str = Query(...), interface_type: str = Query(...)):
    try:
        asset_ids = fetch_asset_ids(domain, capability)
        if not asset_ids:
            raise HTTPException(status_code=404, detail="No assets found for given domain and capability.")
        results = get_relationships_by_interface_type(asset_ids, interface_type)
        return {"results": results}
    except Exception as e:
        print("[ERROR] /get_nodes_by_d_c_interface:", e)
        raise HTTPException(status_code=500, detail=str(e))

# --- Application connection explorer --- #

@app.get("/query")
def query_graph(node_id: str = Query(...), type: str = Query("Upstream"), depth: int = Query(1)):
    with driver.session() as session:
        if type.lower() == "upstream":
            cypher = f"""
                MATCH path = (start {{id: $node_id}})<-[*1..{depth}]-(end)
                RETURN DISTINCT path
            """
        elif type.lower() == "downstream":
            cypher = f"""
                MATCH path = (start {{id: $node_id}})-[*1..{depth}]->(end)
                RETURN DISTINCT path
            """
        elif type.lower() == "both":
            cypher = f"""
                MATCH path = (start {{id: $node_id}})-[*1..{depth}]-(end)
                RETURN DISTINCT path
            """
        else:
            return {"results": []}

        results = session.run(cypher, node_id=node_id)
        response = []
        for record in results:
            path = record["path"]
            for rel in path.relationships:
                response.append({
                    "n": dict(rel.start_node),
                    "r": [dict(rel.start_node), rel.type, dict(rel.end_node)],
                    "m": dict(rel.end_node)
                })

        return {"results": response}

@app.get("/search_assets")
def search_assets(q: str = Query(..., min_length=3)):
    with PG_CONN.cursor() as cur:
        cur.execute("SELECT asset_id, asset_domain, asset_capability FROM assets WHERE asset_id ILIKE %s", (f"{q}%",))
        result = cur.fetchall()
        matches = [{"id": row[0], "domain": row[1], "capability": row[2]} for row in result]
        PG_CONN.commit()
    return {"results": matches}

@app.get("/diagram_info")
def get_diagram_info(node_id: str = Query(...)):
    with PG_CONN.cursor() as cur:
        cur.execute("SELECT asset_diagram_id FROM assets WHERE asset_id = %s", (node_id,))
        result = cur.fetchone()
        if not result:
            return JSONResponse(status_code=404, content={"error": "No diagram found for this application"})
        diagram_id = result[0]

        cur.execute("SELECT diagram_name, diagram_mermaid_code FROM diagrams WHERE diagram_id = %s", (diagram_id,))
        result = cur.fetchone()
        if not result:
            return JSONResponse(status_code=404, content={"error": "Diagram ID not found"})

        return {
            "node_id": node_id,
            "diagram_name": result[0],
            "mermaid_code": result[1]
        }

# --- Utilities --- #

def extract_between(text, start, end):
    return text.split(start, 1)[-1].split(end, 1)[0]


import re

def parse_mermaid(mermaid_code):
    nodes = []
    edges = []
    current_group = None

    for line in mermaid_code.splitlines():
        line = line.strip()

        # Detect subgraph group
        if line.lower().startswith("subgraph"):
            match = re.match(r'subgraph\s+"?(.*?)"?$', line, re.IGNORECASE)
            if match:
                current_group = match.group(1).strip()

        # Detect node definitions
        elif "[" in line and "]" in line:
            node_match = re.match(r'(\w+)\s*\[\s*(.*?)\s*\]', line)
            if node_match:
                node_id = node_match.group(1).strip()
                label_text = node_match.group(2).strip()

                # Remove system code from label if present, extract clean name
                name = label_text.replace(node_id, "").strip()
                display_name = f"{node_id}: {label_text}"

                nodes.append({
                    "id": node_id,
                    "name": name,
                    "display_name": display_name,
                    "group": current_group or "Unknown"
                })

        # Detect edges
        elif "-->" in line:
            edge_match = re.match(r'(\w+)\s*-->\s*\|\s*(.*?)\s*\|\s*(\w+)', line)
            if edge_match:
                src = edge_match.group(1).strip()
                label = edge_match.group(2).strip()
                tgt = edge_match.group(3).strip()

                edges.append({
                    "source": src,
                    "target": tgt,
                    "label": label
                })

    return nodes, edges


def store_graph(tx, diagram_id, nodes, edges):
    for node in nodes:
        tx.run(
            """
            MERGE (n:Node {id: $id, diagram_id: $diagram_id})
            SET n.display_name = $display_name, n.name = $name, n.group = $group
            """,
            id=node["id"],
            diagram_id=diagram_id,
            display_name=node["display_name"],
            name=node.get("name", ""),
            group=node.get("group", "")
        )

    for edge in edges:
        tx.run(
            f"MATCH (a:Node {{id: $src, diagram_id: $diagram_id}}), (b:Node {{id: $tgt, diagram_id: $diagram_id}}) "
            f"MERGE (a)-[:{edge['label'].upper()}]->(b)",
            src=edge["source"], tgt=edge["target"], diagram_id=diagram_id
        )

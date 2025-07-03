# Complete AI Agent-based Refactor for Your Backend

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from uuid import uuid4
import base64, os, requests, re
from dotenv import load_dotenv
from neo4j import GraphDatabase
from final_chromadb_upload import client, store_diagram_summary, store_application, store_complexity_entry
import google.generativeai as genai
from typing import List, Dict, Set, Tuple
import psycopg2

# --- Load Config --- #
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PG_CONN = psycopg2.connect(host="localhost", dbname="postgres", user="postgres", password="mysecretpassword")
NEO4J_DRIVER = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password123"))

genai.configure(api_key=GEMINI_API_KEY)
MODEL = genai.GenerativeModel("gemini-2.5-pro")

# --- Agents --- #

class DiagramProcessingAgent:
    def __init__(self, gemini_key, pg_conn, neo4j_driver):
        self.key = gemini_key
        self.pg = pg_conn
        self.neo4j = neo4j_driver

    def process_upload(self, img_file, diagram_name, asset_id):
        img_b64 = base64.b64encode(img_file.read()).decode()
        output = self._call_gemini(img_b64)
        data = self._parse(output)

        diagram_id = f"DIAGRAM_{str(uuid4())[:8]}"
        self._store_pg(data["mermaid"], diagram_id, diagram_name, asset_id)
        self._store_neo4j(data["mermaid"], diagram_id)
        self._store_vectors(data, diagram_id, diagram_name)
        return {"diagram_id": diagram_id, **data}

    def _call_gemini(self, img_b64):
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
        resp = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent",
            headers={"Content-Type": "application/json"},
            params={"key": self.key},
            json={"contents": [{"role": "user", "parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/png", "data": img_b64}}]}]}
        )
        result = resp.json()
        if "candidates" not in result:
            raise Exception(result)
        return result["candidates"][0]["content"]["parts"][0]["text"]

    def _parse(self, text):
        sections = re.split(r"\*\*(.*?)\*\*", text)
        data = {"mermaid": "", "summary": "", "description": "", "applications": [], "complexity_table": [], "pros": [], "cons": []}
        for i, s in enumerate(sections):
            tag = s.strip().lower()
            if tag == "mermaid": data["mermaid"] = clean_mermaid_code(sections[i+1])
            elif tag == "summary": data["summary"] = sections[i+1].strip()
            elif tag == "description": data["description"] = sections[i+1].strip()
            elif tag == "applications": data["applications"] = parse_applications(sections[i+1].strip())
            elif "system complexity" in s: data["complexity_table"] = parse_complexity(sections[i+1].strip())
            elif tag == "pros": data["pros"] = parse_list(sections[i+1])
            elif tag == "cons": data["cons"] = parse_list(sections[i+1])
        return data

    def _store_pg(self, mermaid, diagram_id, name, asset_id):
        with self.pg.cursor() as cur:
            cur.execute("INSERT INTO DIAGRAMS (diagram_id, diagram_mermaid_code, diagram_name) VALUES (%s,%s,%s)", (diagram_id, mermaid, name))
            cur.execute("SELECT * FROM ASSETS WHERE asset_id=%s", (asset_id,))
            if cur.fetchone(): cur.execute("UPDATE ASSETS SET asset_diagram_id=%s WHERE asset_id=%s", (diagram_id, asset_id))
            else: cur.execute("INSERT INTO ASSETS (asset_id, asset_diagram_id) VALUES (%s,%s)", (asset_id, diagram_id))
            self.pg.commit()

    def _store_neo4j(self, mermaid, diagram_id):
        nodes, edges = parse_mermaid(mermaid)
        with self.neo4j.session() as session:
            session.execute_write(store_graph, diagram_id, nodes, edges)

    def _store_vectors(self, data, diagram_id, name):
        store_diagram_summary(diagram_id, name, data["summary"], data["description"], data["pros"], data["cons"])
        for app in data["applications"]:
            store_application({**app, "diagram_id": diagram_id, "diagram_name": name})
        for c in data["complexity_table"]:
            store_complexity_entry(diagram_id, name, c["component"], c["complexity"], c["reason"])


class ChatAgent:
    def __init__(self): self.memory = {}

    def new_session(self):
        sid = str(uuid4())
        self.memory[sid] = ""
        return sid

    def reset(self, sid):
        if sid in self.memory: self.memory[sid] = ""; return True
        return False

    def chat(self, sid, query):
        if sid not in self.memory: raise Exception("Invalid session")
        col = infer_collection(query)
        docs = client.get_collection(name=col).query(query_texts=[query], n_results=25, include=["metadatas", "documents"])
        results = []
        for doc, meta in zip(docs["documents"][0], docs["metadatas"][0]):
            results.append(f"{meta.get('source', '')}: {doc}")
        context = "\n\n".join(results) if results else "No relevant documents found."
        prompt = f"""You are an expert system assistant. Based on the following {col.replace('_', ' ')} information, answer the question clearly: \n\nConversation:\n{self.memory[sid]}\n\nDocuments:\n{context}\n\nQuestion: {query}"""
        ans = MODEL.generate_content(prompt).text.strip()
        self.memory[sid] += f"\nQ:{query}\nA:{ans}"
        return ans


class DomainCapabilityAgent:
    def fetch_assets(self, domain, cap):
        with PG_CONN.cursor() as cur:
            cur.execute("SELECT asset_id FROM assets WHERE asset_domain=%s AND asset_capability=%s", (domain, cap))
            return [r[0] for r in cur.fetchall()]

    def interface_counts(self, asset_ids):
        q = """MATCH (a)-[r]->(b) WHERE a.id IN $ids AND r.interface_type IS NOT NULL RETURN r.interface_type AS type, COUNT(DISTINCT a.id+b.id+r.interface_type) AS cnt"""
        with NEO4J_DRIVER.session() as s: return [{r["type"]: r["cnt"]} for r in s.run(q, ids=asset_ids)]

    def relationships(self, asset_ids, interface_type):
        q = """MATCH (a)-[r]->(b) WHERE a.id IN $ids AND r.interface_type=$interface RETURN a.id AS from_node, b.id AS to_node, r.interface_type AS interface_type"""
        seen, results = set(), []
        with NEO4J_DRIVER.session() as s:
            for r in s.run(q, ids=asset_ids, interface=interface_type):
                k = (r["from_node"], r["to_node"], r["interface_type"])
                if k not in seen: seen.add(k); results.append(dict(r))
        return results


class ArchitectureAgent:
    def search_names(self, q):
        with PG_CONN.cursor() as cur:
            cur.execute("SELECT DISTINCT diagram_name FROM diagrams WHERE diagram_name ILIKE %s", (f"{q}%",))
            return [r[0] for r in cur.fetchall()]

    def get_code(self, name):
        with PG_CONN.cursor() as cur:
            cur.execute("SELECT diagram_mermaid_code FROM diagrams WHERE diagram_name=%s ORDER BY UPDATED_AT DESC", (name,))
            r = cur.fetchone()
            return r[0] if r else None


class GraphExplorerAgent:
    def explore(self, node_id, direction, depth):
        dmap = {"upstream": "<-[*1..{d}]-(end)", "downstream": "-[*1..{d}]->(end)", "both": "-[*1..{d}]-(end)"}
        cypher = f"MATCH path=(start {{id:$id}}){dmap.get(direction.lower(), '')} RETURN path"
        with NEO4J_DRIVER.session() as s:
            return [dict(rel.start_node) | {"relation": rel.type} | dict(rel.end_node) for r in s.run(cypher, id=node_id) for rel in r["path"].relationships]


# --- Utilities Retained --- #
# (parse_mermaid, store_graph, clean_mermaid_code, parse_applications, parse_complexity, parse_list, infer_collection remain unchanged)

# --- FastAPI Setup with Agents --- #
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Initialize agents
diagram_agent = DiagramProcessingAgent(GEMINI_API_KEY, PG_CONN, NEO4J_DRIVER)
chat_agent = ChatAgent()
dc_agent = DomainCapabilityAgent()
arch_agent = ArchitectureAgent()
graph_agent = GraphExplorerAgent()

# Routes
@app.post("/upload/")
def upload(image: UploadFile, diagram_name: str = Form(...), asset_id: str = Form(...)):
    return diagram_agent.process_upload(image.file, diagram_name, asset_id)

@app.post("/generate_session/")
def new_session(): return {"session_id": chat_agent.new_session()}

@app.post("/reset_session/")
def reset(session_id: str = Form(...)): return {"message": "Reset"} if chat_agent.reset(session_id) else {"error": "Invalid session"}

@app.post("/chat/")
def chat(query: str = Form(...), session_id: str = Form(...)): return {"response": chat_agent.chat(session_id, query)}

@app.get("/get_domains")
def domains(q: str = Query(...)): return {"results": dc_agent.fetch_assets(q, "")}

@app.get("/get_capabilities")
def capabilities(q: str = Query(...)): return {"results": dc_agent.fetch_assets("", q)}

@app.get("/get_interface_type_counts")
def counts(domain: str, capability: str): return dc_agent.interface_counts(dc_agent.fetch_assets(domain, capability))

@app.get("/get_nodes_by_d_c_interface")
def nodes(domain: str, capability: str, interface_type: str): return dc_agent.relationships(dc_agent.fetch_assets(domain, capability), interface_type)

@app.get("/get_arch_names")
def arch_names(q: str = Query(...)): return {"results": arch_agent.search_names(q)}

@app.get("/get_arch_code")
def arch_code(arch_name: str = Query(...)): return {"arch_name": arch_name, "mermaid_code": arch_agent.get_code(arch_name)}

@app.get("/query")
def explore(node_id: str, type: str = "Upstream", depth: int = 1): return {"results": graph_agent.explore(node_id, type, depth)}

# Utility Functions Updated for AI Agent Setup

# Clean raw mermaid code block
def clean_mermaid_code(raw: str) -> str:
    lines = raw.strip().splitlines()
    if lines and lines[0].strip().startswith("```"): lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"): lines = lines[:-1]
    return "\n".join(lines).strip()

# Extract node and edge details from mermaid code
def parse_mermaid(mermaid_code):
    nodes, edges, current_group = [], [], None
    for line in mermaid_code.splitlines():
        line = line.strip()
        if line.lower().startswith("subgraph"):
            match = re.match(r'subgraph\s+"?(.*?)"?$', line, re.IGNORECASE)
            if match: current_group = match.group(1).strip()
        elif "[" in line and "]" in line:
            node_match = re.match(r'(\w+)\s*\[\s*(.*?)\s*\]', line)
            if node_match:
                node_id, label = node_match.groups()
                name = label.replace(node_id, "").strip()
                nodes.append({"id": node_id, "name": name, "display_name": f"{node_id}: {label}", "group": current_group or "Unknown"})
        elif "-->" in line:
            edge_match = re.match(r'(\w+)\s*-->\s*\|\s*(.*?)\s*\|\s*(\w+)', line)
            if edge_match:
                src, label, tgt = edge_match.groups()
                edges.append({"source": src, "target": tgt, "label": label or "UNKNOWN"})
    return nodes, edges

# Neo4j Graph Storage
def store_graph(tx, diagram_id, nodes, edges):
    for n in nodes:
        tx.run("MERGE (x:Node {id: $id, diagram_id: $d}) SET x.display_name=$disp, x.name=$name, x.group=$grp",
               id=n["id"], d=diagram_id, disp=n["display_name"], name=n.get("name", ""), grp=n.get("group", ""))
    for e in edges:
        tx.run(f"""MATCH (a:Node {{id: $src, diagram_id: $d}}), (b:Node {{id: $tgt, diagram_id: $d}}) 
                  MERGE (a)-[r:{e['label'].upper()}]->(b) SET r.interface_type=$type""",
               src=e["source"], tgt=e["target"], d=diagram_id, type=e["label"].upper())

# Parse Applications List
def parse_applications(text: str):
    apps, blocks = [], re.split(r"-\s*Title:", text)
    for b in blocks[1:]:
        lines = b.strip().split("\n")
        title, code, group = lines[0].strip(), lines[1].split(":")[1].strip(), lines[2].split(":")[1].strip()
        relations = [l.lstrip("- ").strip() for l in lines[4:] if l.strip().startswith("-")]
        apps.append({"title": title, "system_code": code, "group": group, "relationships": relations})
    return apps

# Parse Complexity Table
def parse_complexity(text: str):
    entries, rows = [], text.splitlines()[2:]
    for row in rows:
        cols = [c.strip() for c in row.split("|") if c.strip()]
        if len(cols) == 3: entries.append({"component": cols[0], "complexity": cols[1], "reason": cols[2]})
    return entries

# Parse Pros/Cons Lists
def parse_list(text: str):
    return [l.lstrip("- ").strip() for l in text.splitlines() if l.strip().startswith("-")]

# Infer Vector Collection based on Query Type
def infer_collection(prompt: str) -> str:
    p = prompt.lower()
    if any(k in p for k in ["complexity", "risk", "rationale", "complex"]): return "architecture_complexity"
    if any(k in p for k in ["application", "app", "asset", "integration", "relationship", "upstream", "downstream", "connection", "mermaid"]): return "architecture_applications"
    return "architecture_diagrams"

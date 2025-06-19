import os
import re
import uuid
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from neo4j import GraphDatabase
from qdrant_client import QdrantClient, models
from ollama import Client

# --- 1. INITIALIZATION ---

# Initialize FastAPI app
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# Environment variables for connections
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
QDRANT_HOST = os.getenv("QDRANT_HOST")
QDRANT_PORT = int(os.getenv("QDRANT_PORT"))
OLLAMA_HOST = os.getenv("OLLAMA_HOST")

# Connect to databases and LLM
try:
    neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    ollama_client = Client(host=OLLAMA_HOST)
    print("Successfully connected to databases and Ollama.")
except Exception as e:
    print(f"Error during initialization: {e}")
    neo4j_driver = qdrant_client = ollama_client = None

# Constants
QDRANT_COLLECTION_NAME = "mermaid_diagrams"
DATA_FOLDER = "/app/data_to_import"

# Ensure Qdrant collection exists
try:
    collections = qdrant_client.get_collections().collections
    if not any(c.name == QDRANT_COLLECTION_NAME for c in collections):
        qdrant_client.create_collection(
            collection_name=QDRANT_COLLECTION_NAME,
            vectors_config=models.VectorParams(size=4096, distance=models.Distance.COSINE), # Llama3 default embedding size
        )
        print(f"Created Qdrant collection: {QDRANT_COLLECTION_NAME}")
except Exception as e:
    print(f"Error checking/creating Qdrant collection: {e}")


# --- 2. DATA MODELS ---
class QueryRequest(BaseModel):
    query: str

class ImportResponse(BaseModel):
    message: str
    files_processed: int

class QueryResponse(BaseModel):
    content: str
    format: str # 'markdown', 'mermaid', or 'text'

# --- 3. HELPER & PARSING FUNCTIONS ---

def sanitize_relationship_type(label: str) -> str:
    """Sanitizes a label to be a valid Neo4j relationship type."""
    if not label:
        return "RELATES_TO" # Default type if no label
    # Keep only alphanumeric chars, replace others with underscore, and uppercase
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', label).upper()
    # Ensure it doesn't start with a number
    if sanitized and sanitized[0].isdigit():
        sanitized = '_' + sanitized
    return sanitized

def parse_mermaid(content: str):
    """Robust parser for Mermaid graph diagrams."""
    nodes = {}
    edges = []
    # Regex to find nodes with labels, e.g., B(Auth Service) or F[User Database] or just APP018
    node_pattern = re.compile(r"^\s*(\w+)(?:\[(.*?)\]|\((.*?)\)|\{(.*?)\})?")
    
    # Combined regex for various edge types, prioritizing labeled ones
    # Catches: -->|label|, -- text -->, and -->
    edge_pattern = re.compile(r"(\w+)\s*(?:-->\|(.*?)\||--\s*(.*?)\s*-->|-->)\s*(\w+)")

    for line in content.splitlines():
        line = line.strip()
        # Skip comments and directives
        if line.startswith("%%") or line.startswith("graph") or line.startswith("subgraph") or line == "end":
            continue

        edge_match = edge_pattern.search(line)
        if edge_match:
            source, label1, label2, target = edge_match.groups()
            label = label1 if label1 is not None else (label2 if label2 is not None else "")
            edges.append({"source": source, "target": target, "type": sanitize_relationship_type(label)})
            # Add nodes found in edges to the node list implicitly
            nodes[source] = nodes.get(source, source)
            nodes[target] = nodes.get(target, target)
        else:
            # Find standalone node definitions
            node_match = node_pattern.match(line)
            if node_match:
                node_id, label1, label2, label3 = node_match.groups()
                label = next((lbl for lbl in [label1, label2, label3] if lbl is not None), node_id)
                nodes[node_id] = label.strip()

    return nodes, edges


# --- 4. API ENDPOINTS ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.post("/import", response_model=ImportResponse)
async def import_data():
    files_processed = 0
    try:
        with neo4j_driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        qdrant_client.recreate_collection(
            collection_name=QDRANT_COLLECTION_NAME,
            vectors_config=models.VectorParams(size=4096, distance=models.Distance.COSINE),
        )

        points_to_upsert = []
        for filename in os.listdir(DATA_FOLDER):
            if filename.endswith(".mmd"):
                base_name = os.path.splitext(filename)[0]
                mmd_path = os.path.join(DATA_FOLDER, filename)
                txt_path = os.path.join(DATA_FOLDER, f"{base_name}.txt")

                with open(mmd_path, 'r', encoding='utf-8') as f:
                    mermaid_code = f.read()

                metadata = {}
                if os.path.exists(txt_path):
                    with open(txt_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            if ':' in line:
                                key, value = line.split(':', 1)
                                metadata[key.strip()] = value.strip()
                
                nodes, edges = parse_mermaid(mermaid_code)
                
                with neo4j_driver.session() as session:
                    # Ingest nodes
                    for node_id, label in nodes.items():
                        final_label = metadata.get(node_id, label)
                        session.run("MERGE (a:Component {id: $id}) SET a.label = $label, a.source_file = $source", id=node_id, label=final_label, source=filename)
                    
                    # Ingest relationships with dynamic types
                    for edge in edges:
                        cypher_query = f"""
                        MATCH (a:Component {{id: $source_id}})
                        MATCH (b:Component {{id: $target_id}})
                        MERGE (a)-[:{edge['type']}]->(b)
                        """
                        session.run(cypher_query, source_id=edge['source'], target_id=edge['target'])


                combined_text_for_embedding = mermaid_code + "\n" + "\n".join(f"{k}: {v}" for k, v in metadata.items())
                embedding = ollama_client.embeddings(model='llama3.1', prompt=combined_text_for_embedding)['embedding']
                
                points_to_upsert.append(models.PointStruct(id=str(uuid.uuid4()), vector=embedding, payload={"filename": filename, "mermaid_code": mermaid_code, "metadata": metadata}))
                files_processed += 1
        
        if points_to_upsert:
            qdrant_client.upsert(collection_name=QDRANT_COLLECTION_NAME, points=points_to_upsert, wait=True)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    return ImportResponse(message="Data imported successfully", files_processed=files_processed)

# --- 5. LLM and Query Logic (UPDATED) ---

def determine_query_strategy(user_query: str) -> dict:
    """Uses LLM to decide which database to query and how, with enforced JSON output."""
    system_prompt = """
    You are an expert query router. Your task is to analyze the user's query and determine the best strategy to answer it using the available tools.
    You must respond with a single, valid JSON object with two keys: "tool" and "parameters".

    Available Tools:
    1.  **NEO4J_IMPACT_ANALYSIS**: Use for queries about "impact", "dependencies", or "what is affected by". Requires 'component_name' which must be the component ID (e.g., 'APP001').
    2.  **NEO4J_PATHFINDING**: Use for queries asking for the "link", "connection", or "path" between two components. Requires 'component_a' and 'component_b', which must be the component IDs (e.g., 'APP001', 'APP002').
    3.  **QDRANT_FIND_COMPONENT**: Use for queries asking "which diagrams contain X" or "find diagrams with Y". Requires 'component_name'.
    4.  **NEO4J_FIND_BY_RELATIONSHIP_TYPE**: Use for queries like "which systems use real-time data", "show event-based interactions". Requires 'relationship_type' (e.g., 'REAL_TIME', 'EVENT', 'API', 'BATCH').
    5.  **NEO4J_COUNT_BY_RELATIONSHIP_TYPE**: Use for queries like "how many apps do event-based interactions". Requires 'relationship_type'.
    6.  **NEO4J_COUNT_INTERACTIONS**: Use for queries like "how many components are using APP040". Requires 'component_id'.
    7.  **QDRANT_SEMANTIC_SEARCH**: Use for general questions, "find diagrams about", "which diagrams have no authentication", or queries about content that is not strictly about graph paths. Requires a 'search_query' which should be the user's original query.
    8.  **GENERAL_ANSWER**: If the query is a simple greeting or doesn't fit other tools.
    """
    
    response = ollama_client.chat(model='llama3.1', format='json', messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_query}])
    try:
        return json.loads(response['message']['content'])
    except json.JSONDecodeError:
        print("Error: LLM did not return valid JSON for strategy. Falling back.")
        return {"tool": "QDRANT_SEMANTIC_SEARCH", "parameters": {"search_query": user_query}}

def execute_query(strategy: dict) -> str:
    """Executes the query based on the determined strategy."""
    tool = strategy.get("tool")
    params = strategy.get("parameters", {})
    context = ""

    if tool == "NEO4J_IMPACT_ANALYSIS":
        comp_id = params.get("component_name")
        with neo4j_driver.session() as session:
            result = session.run("MATCH (start:Component {id: $comp_id}) MATCH path = (start)-[*0..5]-(neighbor) RETURN nodes(path) as components", comp_id=comp_id)
            nodes = {node['label'] for record in result for node in record['components']}
            if nodes:
                context = f"Impact analysis for '{comp_id}' found related components: {', '.join(nodes)}"
            else:
                context = f"Could not find component with ID '{comp_id}' for impact analysis."

    elif tool == "NEO4J_PATHFINDING":
        comp_a_id, comp_b_id = params.get("component_a"), params.get("component_b")
        with neo4j_driver.session() as session:
            result = session.run("MATCH (a:Component {id: $comp_a_id}), (b:Component {id: $comp_b_id}) MATCH p = shortestPath((a)-[*]-(b)) RETURN p", comp_a_id=comp_a_id, comp_b_id=comp_b_id)
            path = result.single()
            if path:
                path_context_parts = []
                rels = path['p'].relationships
                nodes = path['p'].nodes
                for i, rel in enumerate(rels):
                    source_node = nodes[i]
                    target_node = nodes[i+1]
                    rel_type = rel.type.replace('_', ' ').title()
                    if rel_type == 'Relates To': rel_type = ''
                    path_context_parts.append(f"'{source_node['label']}' (ID: {source_node['id']}) to '{target_node['label']}' (ID: {target_node['id']}) via '{rel_type}'")
                context = "Path found:\n- " + "\n- ".join(path_context_parts)
            else:
                context = f"No path found between '{comp_a_id}' and '{comp_b_id}'."
    
    elif tool == "NEO4J_FIND_BY_RELATIONSHIP_TYPE":
        rel_type_param = params.get("relationship_type", "")
        rel_type_sanitized = sanitize_relationship_type(rel_type_param)
        with neo4j_driver.session() as session:
            cypher_query = f"MATCH (a:Component)-[r:{rel_type_sanitized}]->(b:Component) RETURN a.id AS source_id, a.label AS source_label, b.id AS target_id, b.label AS target_label"
            result = session.run(cypher_query)
            pairs = [f"'{record['source_label']}' (ID: {record['source_id']}) to '{record['target_label']}' (ID: {record['target_id']}) " for record in result]
            if pairs:
                context = f"Found the following '{rel_type_param}' interactions:\n- " + "\n- ".join(pairs)
            else:
                context = f"No interactions found with type '{rel_type_param}'."
    
    elif tool == "NEO4J_COUNT_BY_RELATIONSHIP_TYPE":
        rel_type = sanitize_relationship_type(params.get("relationship_type", ""))
        with neo4j_driver.session() as session:
            cypher_query = f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS count"
            result = session.run(cypher_query)
            count = result.single()['count']
            context = f"Found {count} interactions of type '{rel_type}'."

    elif tool == "NEO4J_COUNT_INTERACTIONS":
        comp_id = params.get("component_id")
        with neo4j_driver.session() as session:
            # Query for bidirectional relationships and return the neighbors' labels
            result = session.run(
                "MATCH (c:Component {id: $comp_id})--(neighbor:Component) RETURN neighbor.label AS neighbor_label",
                comp_id=comp_id
            )
            neighbors = [record["neighbor_label"] for record in result]
            count = len(neighbors)
            if count > 0:
                context = f"Found {count} components interacting with '{comp_id}': {', '.join(neighbors)}"
            else:
                context = f"Found no components directly interacting with '{comp_id}'."


    elif tool == "QDRANT_FIND_COMPONENT":
        comp_name = params.get("component_name")
        embedding = ollama_client.embeddings(model='llama3.1', prompt=f"diagram containing component: {comp_name}")['embedding']
        search_result = qdrant_client.search(collection_name=QDRANT_COLLECTION_NAME, query_vector=embedding, limit=10)
        
        relevant_diagrams = [f"- {hit.payload['filename']}" for hit in search_result if comp_name.lower() in hit.payload['mermaid_code'].lower()]
        
        if relevant_diagrams:
            context = f"Found diagrams containing '{comp_name}':\n" + "\n".join(relevant_diagrams)
        else:
            context = f"No diagrams found explicitly containing '{comp_name}'."

    elif tool == "QDRANT_SEMANTIC_SEARCH":
        query = params.get("search_query")
        embedding = ollama_client.embeddings(model='llama3.1', prompt=query)['embedding']
        search_result = qdrant_client.search(collection_name=QDRANT_COLLECTION_NAME, query_vector=embedding, limit=3)
        context = "Found relevant diagrams:\n" + "\n".join([f"\n--- Result {i+1} ---\nFilename: {hit.payload['filename']}\nMermaid Code:\n{hit.payload['mermaid_code']}" for i, hit in enumerate(search_result)])

    else:
        context = "This is a general query. I am an AI for architecture diagrams."

    return context

def synthesize_response(user_query: str, context: str) -> dict:
    """Synthesizes a final, formatted response using the LLM with strict rules for Mermaid generation."""
    system_prompt = """
    You are an expert system architect AI. Your task is to provide a clear and useful answer to the user's query based on the provided context, formatting it as a valid JSON object.

    You must respond with a single, valid JSON object with two keys: "format" and "content".

    **Available Formats:**
    1.  `mermaid`: Use this format if the context describes a graph structure (e.g., a list of relationships like "'Component A' (ID: APP001) to 'Component B' (ID: APP002)").
        **Mermaid Generation Rules:**
        - Always start with `graph TD;`.
        - The context provides both a label (e.g., "Online Banking Portal") and a unique ID (e.g., "APP001").
        - Use the unique, space-free ID for linking nodes.
        - Define each node using its ID and full label in quotes, like this: `APP001["Online Banking Portal"];`.
        - Create the link using the IDs.
        - If the context provides a relationship type like "... to ... via 'API'", label the link: `APP001 -->|API| APP002`. If no type is provided, use a simple arrow: `APP001 --> APP002`.
    2.  `markdown`: Use this format if the result is a list of items or needs structured text (like a table).
    3.  `text`: Use this for simple, conversational answers or when other formats don't fit.

    **Example for a path query:**
    Context: "Found the following 'API' interactions:\n- 'Online Banking Portal' (ID: APP001) to 'API Gateway' (ID: APP040)\n- 'Corporate Portal' (ID: APP002) to 'API Gateway' (ID: APP040)"
    Your JSON Response:
    {
        "format": "mermaid",
        "content": "graph TD;\\n    APP001[\\"Online Banking Portal\\"];\\n    APP040[\\"API Gateway\\"];\\n    APP002[\\"Corporate Portal\\"];\\n    APP001 -->|API| APP040;\\n    APP002 -->|API| APP040;"
    }
    """
    user_prompt = f"User's Original Query: \"{user_query}\"\n\nContext from Databases:\n---\n{context}\n---"

    response = ollama_client.chat(model='llama3.1', format='json', messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}])
    try:
        return json.loads(response['message']['content'])
    except json.JSONDecodeError:
        print("Error: LLM did not return valid JSON for synthesis. Falling back.")
        return {"format": "text", "content": "Sorry, I encountered an error while formatting the response."}

@app.post("/query")
async def handle_query(request: QueryRequest):
    try:
        strategy = determine_query_strategy(request.query)
        context = execute_query(strategy)
        final_response_obj = synthesize_response(request.query, context)
        return QueryResponse(content=final_response_obj.get("content", ""), format=final_response_obj.get("format", "text"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
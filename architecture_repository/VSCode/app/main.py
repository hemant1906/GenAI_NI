import os
import re
import uuid
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
NEO4J_PASSWORD =os.getenv("NEO4J_PASSWORD")
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
    # In a real app, you might want to handle this more gracefully
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
            vectors_config=models.VectorParams(size=4096, distance=models.Distance.COSINE), # Llama3.1 default embedding size
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
def parse_mermaid(content: str):
    """Simple parser for Mermaid graph TD diagrams."""
    nodes = {}
    edges = []
    # Regex to find nodes with labels, e.g., B(Auth Service) or F[User Database]
    node_pattern = re.compile(r"(\w+)(?:\[(.*?)\]|\((.*?)\)|\{(.*?)\})")
    
    for match in node_pattern.finditer(content):
        node_id = match.group(1)
        # Find the first non-empty label
        label = next((lbl for lbl in match.groups()[1:] if lbl is not None), node_id)
        nodes[node_id] = label.strip()
    # Regex for relationships, e.g., A --> B or B -- Valid --> D
    edge_pattern = re.compile(r"(\w+)\s*-->\s*(?:\|(.*?)\|)?\s*(\w+)")
    edge_pattern_labeled = re.compile(r"(\w+)\s*--\s*(.*?)\s*-->\s*(\w+)")
    for line in content.splitlines():
        match_labeled = edge_pattern_labeled.search(line)
        if match_labeled:
            source, label, target = match_labeled.groups()
            edges.append({"source": source.strip(), "target": target.strip(), "label": label.strip()})
        else:
            match_unlabeled = edge_pattern.search(line)
            if match_unlabeled:
                source, _, target = match_unlabeled.groups()
                edges.append({"source": source.strip(), "target": target.strip(), "label": ""})
    return nodes, edges
# --- 4. API ENDPOINTS ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())
@app.post("/import", response_model=ImportResponse)
async def import_data():
    """Endpoint to import and process all Mermaid files."""
    files_processed = 0
    try:
        # Clear existing data for a fresh import
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
                with open(mmd_path, 'r') as f:
                    mermaid_code = f.read()
                metadata = {}
                if os.path.exists(txt_path):
                    with open(txt_path, 'r') as f:
                        for line in f:
                            if ':' in line:
                                key, value = line.split(':', 1)
                                metadata[key.strip()] = value.strip()
                
                nodes, edges = parse_mermaid(mermaid_code)
                
                # Ingest into Neo4j
                with neo4j_driver.session() as session:
                    for node_id, label in nodes.items():
                        session.run(
                            "MERGE (a:Component {id: $id, label: $label, source_file: $source})",
                            id=node_id, label=label, source=filename
                        )
                    for edge in edges:
                        session.run(
                            """
                            MATCH (a:Component {id: $source})
                            MATCH (b:Component {id: $target})
                            MERGE (a)-[:RELATES_TO {label: $label}]->(b)
                            """,
                            source=edge['source'], target=edge['target'], label=edge['label']
                        )
# Prepare data for Qdrant
                # We create an embedding from the mermaid code + metadata
                combined_text_for_embedding = mermaid_code + "\n" + "\n".join(f"{k}: {v}" for k, v in metadata.items())
                embedding = ollama_client.embeddings(model='llama3.1', prompt=combined_text_for_embedding)['embedding']
                
                point_id = str(uuid.uuid4())
                points_to_upsert.append(models.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "filename": filename,
                        "mermaid_code": mermaid_code,
                        "metadata": metadata
                    }
                ))
                files_processed += 1
        
        # Batch upsert to Qdrant
        if points_to_upsert:
            qdrant_client.upsert(
                collection_name=QDRANT_COLLECTION_NAME,
                points=points_to_upsert,
                wait=True
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    return ImportResponse(message="Data imported successfully", files_processed=files_processed)
# --- LLM and Query Logic ---
def determine_query_strategy(user_query: str) -> dict:
    """Uses LLM to decide which database to query and how."""
    prompt = f"""
    Analyze the user's query and determine the best strategy to answer it using a Neo4j graph database and a Qdrant vector database.
User Query: "{user_query}"
Available Tools:
    1.  **NEO4J_IMPACT_ANALYSIS**: Use for queries about "impact", "dependencies", or "what is affected by". It finds all components connected to a given component. Requires one 'component_name'.
    2.  **NEO4J_PATHFINDING**: Use for queries asking for the "link", "connection", or "path" between two components. Requires 'component_a' and 'component_b'.
    3.  **QDRANT_SEMANTIC_SEARCH**: Use for general questions, "find diagrams about", "which diagrams have", or queries about content that is not strictly about graph paths. Requires a 'search_query' which should be the user's original query.
    4.  **GENERAL_ANSWER**: If the query seems like a simple greeting or doesn't fit other tools.
Your response must be a single JSON object with two keys: "tool" and "parameters".
    - "tool": One of ["NEO4J_IMPACT_ANALYSIS", "NEO4J_PATHFINDING", "QDRANT_SEMANTIC_SEARCH", "GENERAL_ANSWER"].
    - "parameters": A JSON object with the required parameters for the chosen tool.
Examples:
    - User Query: "What is the impact of changing the Auth Service?" -> {{"tool": "NEO4J_IMPACT_ANALYSIS", "parameters": {{"component_name": "Auth Service"}}}}
    - User Query: "show me the connection between User and Payment DB" -> {{"tool": "NEO4J_PATHFINDING", "parameters": {{"component_a": "User", "component_b": "Payment DB"}}}}
    - User Query: "find all diagrams that deal with authentication" -> {{"tool": "QDRANT_SEMANTIC_SEARCH", "parameters": {{"search_query": "diagrams that deal with authentication"}}}}
    - User Query: "hello there" -> {{"tool": "GENERAL_ANSWER", "parameters": {{}}}}
    """
    print(prompt)
    response = ollama_client.chat(
        model='llama3.1',
        messages=[{'role': 'system', 'content': prompt}],
        options={"temperature": 0.0}
    )
    print(f" response of Strategy search : {response}")
    try:
        # Clean up potential markdown code blocks
        clean_response = response['message']['content'].replace("```json", "").replace("```", "").replace("<|python_tag|>","").strip()
        return eval(clean_response) # Using eval is risky, but simplest for this demo. json.loads is safer.
    except Exception as e:
        print(f"Error parsing LLM strategy response: {e}")
        return {"tool": "QDRANT_SEMANTIC_SEARCH", "parameters": {"search_query": user_query}} # Fallback
def execute_query(strategy: dict) -> str:
    """Executes the query based on the determined strategy."""
    tool = strategy.get("tool")
    params = strategy.get("parameters", {})
    print(f"tool chosen: {tool}")
    context = ""
    if tool == "NEO4J_IMPACT_ANALYSIS":
        comp = params.get("component_name")
        with neo4j_driver.session() as session:
            result = session.run("""
                MATCH (start:Component) WHERE start.label CONTAINS $comp
                MATCH path = (start)-[*0..5]-(neighbor)
                RETURN nodes(path) as components, relationships(path) as rels
            """, comp=comp)
            # This is a simplified context, just returning the nodes found
            nodes = set()
            for record in result:
                for node in record['components']:
                    nodes.add(node['label'])
            context = f"Impact analysis for '{comp}' found the following related components: {', '.join(nodes)}"
            print(context)
    elif tool == "NEO4J_PATHFINDING":
        comp_a = params.get("component_a")
        comp_b = params.get("component_b")
        with neo4j_driver.session() as session:
            result = session.run("""
                MATCH (a:Component), (b:Component)
                WHERE a.label CONTAINS $comp_a AND b.label CONTAINS $comp_b
                MATCH p = shortestPath((a)-[:RELATES_TO*]-(b))
                RETURN p
            """, comp_a=comp_a, comp_b=comp_b)
            path = result.single()
            if path:
                # Build a context string describing the path
                path_nodes = [node['label'] for node in path['p'].nodes]
                context = f"Found a path between '{comp_a}' and '{comp_b}': {' -> '.join(path_nodes)}"
            else:
                context = f"No direct or indirect path found between '{comp_a}' and '{comp_b}'."
            print(context)
    elif tool == "QDRANT_SEMANTIC_SEARCH":
        query = params.get("search_query")
        embedding = ollama_client.embeddings(model='llama3.1', prompt=query)['embedding']
        search_result = qdrant_client.search(
            collection_name=QDRANT_COLLECTION_NAME,
            query_vector=embedding,
            limit=3
        )
        context = "Found the following relevant diagrams:\n"
        for i, hit in enumerate(search_result):
            context += f"\n--- Result {i+1} (Score: {hit.score:.2f}) ---\n"
            context += f"Filename: {hit.payload['filename']}\n"
            context += f"Mermaid Code:\n{hit.payload['mermaid_code']}\n"
    else: # GENERAL_ANSWER
        context = "This seems like a general query. I am a specialized AI for architecture diagrams."
    print(context   )
    return context
def synthesize_response(user_query: str, context: str) -> dict:
    """Uses LLM to synthesize a final, formatted response."""
    print(f" Context : {context}")
    prompt = f"""
 You are an expert system architect AI. Your task is to provide a clear and useful answer to the user's query based on the provided context.
    
    User's Original Query: "{user_query}"
    
    Context from Databases:
    ---
    {context}
    ---
Based on the query and context, determine the best output format and generate the response.
    
    Available Formats:
    1. `mermaid`: If the query asks for a connection, path, or impact, and the context describes a graph structure. Create a Mermaid `graph TD;` diagram showing the components and their links.
    2. `markdown`: If the result is a list of items or needs structured text (like a list of diagrams). Use Markdown tables for structured data.
    3. `text`: For simple, conversational answers.
Your response must be a single JSON object with two keys: "format" and "content".
    - "format": One of ["mermaid", "markdown", "text"].
    - "content": The generated response in the chosen format.
Example for a path query:
    {{"format": "mermaid", "content": "graph TD;\\n    User --> API_Gateway;\\n    API_Gateway --> Payment_Service;"}}
Example for a list query:
    {{"format": "markdown", "content": "### Relevant Diagrams\\n\\n| Filename | Score |\\n|---|---|\\n| auth_service.mmd | 0.95 |\\n| payment_service.mmd | 0.88 |"}}
    """
    print(f"prompt {prompt}")
    response = ollama_client.chat(
        model='llama3.1',
        messages=[{'role': 'system', 'content': prompt}],
        options={"temperature": 0.5}
    )
    try:
        print(f"Response content {response['message']['content']}")
        print(f"Response message {response['message']}")
        clean_response = response['message']['content'].replace("```json", "").replace("```", "").replace("<|python_tag|>","").strip()
        # A more robust way to handle potential newlines inside the JSON string content
        return eval(clean_response)
    except Exception as e:
        print(f"Error parsing final LLM response: {e}")
        return {"format": "text", "content": "Sorry, I encountered an error while formatting the response."}
@app.post("/query")
async def handle_query(request: QueryRequest):
    try:
        # 1. Determine strategy
        strategy = determine_query_strategy(request.query)
        # 2. Execute query to get context
        context = execute_query(strategy)
        # 3. Synthesize final response
        final_response_obj = synthesize_response(request.query, context)
        
        return QueryResponse(
            content=final_response_obj.get("content", "No content generated."),
            format=final_response_obj.get("format", "text")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

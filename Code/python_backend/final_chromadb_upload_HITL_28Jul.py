import chromadb
from chromadb.utils import embedding_functions
import re

client = chromadb.HttpClient(host="localhost", port=8000)
embedder = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

# Get/create collections
diagram_collection = client.get_or_create_collection(name="architecture_diagrams", embedding_function=embedder)
app_collection = client.get_or_create_collection(name="architecture_applications", embedding_function=embedder)

'''
def store_diagram_summary(diagram_id, diagram_name, summary, description, pros, cons):
    content = f"""Summary: {summary}
    Diagram Name: {diagram_name}
    Description: {description}
    Pros:
    {chr(10).join(pros)}
    
    Cons:
    {chr(10).join(cons)}
    """
    # Fetch existing metadata first (if needed)
    existing = diagram_collection.get(ids=[f"diagram_{diagram_id}"])
    existing_metadata = existing['metadatas'][0] if existing and 'metadatas' in existing else {}

    metadata = {
        "diagram_id": diagram_id,
        "diagram_name": diagram_name if diagram_name else existing_metadata.get("diagram_name", ""),
        "type": "diagram"
    }
    diagram_collection.add(
        documents=[content],
        metadatas=[metadata],
        ids=[f"diagram_{diagram_id}"]
    )
'''

def store_diagram_summary(diagram_id, diagram_name, summary, description, pros, cons):
    # Fetch existing metadata and content
    existing = diagram_collection.get(ids=[f"diagram_{diagram_id}"])
    existing_metadata = existing['metadatas'][0] if existing and 'metadatas' in existing else {}
    existing_doc = existing['documents'][0] if existing and 'documents' in existing else ""

    # Fallback: extract pros and cons from existing document if not provided
    if not pros:
        pros_match = re.search(r"Pros:\s*(.*?)\n\n", existing_doc, re.DOTALL)
        pros = [line.strip() for line in pros_match.group(1).strip().splitlines()] if pros_match else []

    if not cons:
        cons_match = re.search(r"Cons:\s*(.*)", existing_doc, re.DOTALL)
        cons = [line.strip() for line in cons_match.group(1).strip().splitlines()] if cons_match else []

    metadata = {
        "diagram_id": diagram_id,
        "diagram_name": diagram_name if diagram_name else existing_metadata.get("diagram_name", ""),
        "type": "diagram"
    }

    content = f"""Summary: {summary}
    Diagram Name: {metadata["diagram_name"]}
    Description: {description}
    Pros:
    {chr(10).join(pros)}

    Cons:
    {chr(10).join(cons)}
    """

    diagram_collection.update(
        documents=[content],
        metadatas=[metadata],
        ids=[f"diagram_{diagram_id}"]
    )

def store_application(app_data):
    content = f"""Title: {app_data['title']}
System Code: {app_data['system_code']}
Group: {app_data['group']}
Diagram Name: {app_data['diagram_name']}
Relationships:
{chr(10).join(app_data['relationships'])}"""

    metadata = {
        "diagram_id": app_data["diagram_id"],
        "diagram_name": app_data["diagram_name"],
        "system_code": app_data["system_code"],
        "group": app_data["group"],
        "type": "application"
    }

    app_collection.add(
        documents=[content],
        metadatas=[metadata],
        ids=[f"app_{app_data['system_code']}_{app_data['diagram_id']}"]
    )

def store_complexity_entry(diagram_id, diagram_name, component, complexity, reason):
    content = f"""Component: {component}
Diagram Name: {diagram_name}
Complexity: {complexity}
Reason: {reason}
"""

    metadata = {
        "diagram_id": diagram_id,
        "diagram_name": diagram_name,
        "component": component,
        "complexity": complexity,
        "type": "complexity"
    }

    complexity_collection = client.get_or_create_collection(
        name="architecture_complexity", embedding_function=embedder
    )

    complexity_collection.add(
        documents=[content],
        metadatas=[metadata],
        ids=[f"complexity_{diagram_id}_{component}"]
    )
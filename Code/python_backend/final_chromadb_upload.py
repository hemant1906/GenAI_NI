import chromadb
from chromadb.utils import embedding_functions

client = chromadb.HttpClient(host="localhost", port=8000)
embedder = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

# Get/create collections
diagram_collection = client.get_or_create_collection(name="architecture_diagrams", embedding_function=embedder)
app_collection = client.get_or_create_collection(name="architecture_applications", embedding_function=embedder)

def store_diagram_summary(diagram_id, diagram_name, summary, description, pros, cons):
    content = f"""Summary: {summary}
Description: {description}
Pros:
{chr(10).join(pros)}

Cons:
{chr(10).join(cons)}
"""

    metadata = {
        "diagram_id": diagram_id,
        "diagram_name": diagram_name,
        "type": "diagram"
    }

    diagram_collection.add(
        documents=[content],
        metadatas=[metadata],
        ids=[f"diagram_{diagram_id}"]
    )

def store_application(app_data):
    content = f"""Title: {app_data['title']}
System Code: {app_data['system_code']}
Group: {app_data['group']}
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

def store_complexity_entry(diagram_id, component, complexity, reason):
    content = f"""Component: {component}
Complexity: {complexity}
Reason: {reason}
"""

    metadata = {
        "diagram_id": diagram_id,
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
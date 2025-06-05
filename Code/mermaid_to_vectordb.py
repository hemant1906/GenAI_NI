import os
import json
import networkx as nx
import re
import chromadb
from node2vec import Node2Vec

### Configuration ###
MERMAID_FOLDER = r'C:\Users\sourav\Downloads\GenAI\architecture_repository\mermaid_code'  # Folder containing Mermaid code files (.txt)
OUTPUT_DIR = r'C:\Users\sourav\Downloads\GenAI\architecture_repository\output_data'  # Folder for saving results

### Initialize ChromaDB ###
client = chromadb.PersistentClient(path="./vector_db")
collection = client.get_or_create_collection(name="architecture_graph_store")

### Step 1: Read Mermaid Code from File ###
def read_mermaid_code(file_path):
    """Read Mermaid code from a .txt file"""
    with open(file_path, "r") as file:
        mermaid_code = file.read()
    return mermaid_code

### Step 2: Convert Mermaid Code to Graph ###
def parse_mermaid_to_graph(mermaid_code):
    """Convert Mermaid code into a graph using NetworkX"""
    graph = nx.DiGraph()
    edges = re.findall(r'(\w+)\s*--?>\s*(\w+)', mermaid_code)
    for edge in edges:
        graph.add_edge(edge[0], edge[1])
    return graph

### Step 3: Generate Graph-Based Embeddings Using Node2Vec ###
def generate_graph_embeddings(graph):
    """Generate node embeddings using Node2Vec"""
    node2vec = Node2Vec(graph, dimensions=128, walk_length=10, num_walks=50, workers=4)
    model = node2vec.fit(window=5, min_count=1, batch_words=4)
    node_embeddings = {node: model.wv[node].tolist() for node in graph.nodes()}
    return node_embeddings

### Step 4: Store Mermaid Code + Graph Embeddings in ChromaDB ###
def store_graph_embeddings(graph_embeddings, graph_metadata, mermaid_code, file_id):
    """Store graph embeddings with original Mermaid code in ChromaDB"""
    structured_json = json.dumps(graph_embeddings)
    graph_metadata_str = json.dumps(graph_metadata)  # Convert metadata to JSON string
    collection.add(
        documents=[structured_json],
        metadatas=[{"graph_metadata": graph_metadata_str, "original_mermaid_code": mermaid_code}],
        ids=[file_id]  
    )
    print("Generated Graph Embeddings:", graph_embeddings)
    print(f"Graph embeddings and Mermaid code stored for {file_id}")

### Step 4: Query ###
def query_graph_embeddings(query_text, num_results=5):
    """Query ChromaDB for relevant architecture diagrams using vector similarity"""
    results = collection.query(
        query_texts=[query_text],
        n_results=num_results
    )

    return results

### Execution Flow: Process All Mermaid Code Files from Folder ###
for idx, mermaid_file in enumerate(os.listdir(MERMAID_FOLDER)):
    file_path = os.path.join(MERMAID_FOLDER, mermaid_file)
    file_id = f"graph_{idx+1}"

    # Step 1: Read Mermaid Code
    mermaid_code = read_mermaid_code(file_path)

    # Step 2: Convert Mermaid Code to Graph
    graph_structure = parse_mermaid_to_graph(mermaid_code)
    graph_file = f"{OUTPUT_DIR}graph_{file_id}.json"
    with open(graph_file, "w") as file:
        json.dump({"nodes": list(graph_structure.nodes), "edges": [{"source": edge[0], "target": edge[1]} for edge in graph_structure.edges]}, file, indent=4)

    # Step 3: Generate Embeddings & Store in ChromaDB
    graph_metadata = json.load(open(graph_file, "r"))
    graph_embeddings = generate_graph_embeddings(graph_structure)
    store_graph_embeddings(graph_embeddings, graph_metadata, mermaid_code, file_id)

# Example Usage: Retrieve diagrams related to microservices
query_results = query_graph_embeddings("Retrieve nodes and edges for APP039", num_results=5)

# Print retrieved results
for idx, result in enumerate(query_results["documents"]):
    print(f"\nResult {idx + 1}:")
    print("Graph Embeddings:", result)
    #print("Graph Metadata:", query_results["metadatas"][idx]["graph_metadata"])
    #print("Original Mermaid Code:", query_results["metadatas"][idx]["original_mermaid_code"])
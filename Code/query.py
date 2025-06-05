import chromadb

# Initialize ChromaDB Client
client = chromadb.PersistentClient(path="./vector_db")
collection = client.get_collection(name="architecture_graph_store")


def query_graph_embeddings(query_text, num_results=5):
    """Query ChromaDB for relevant architecture diagrams using vector similarity"""
    results = collection.query(
        query_texts=[query_text],
        n_results=num_results
    )

    return results


# Example Usage: Retrieve diagrams related to microservices
query_results = query_graph_embeddings("Retrieve sources and targets for APP039", num_results=5)

# Print retrieved results
for idx, result in enumerate(query_results["documents"]):
    print(f"\nResult {idx + 1}:")
    print("Graph Embeddings:", result)
    #print("Graph Metadata:", query_results["metadatas"][idx]["graph_metadata"])
    #print("Original Mermaid Code:", query_results["metadatas"][idx]["original_mermaid_code"])

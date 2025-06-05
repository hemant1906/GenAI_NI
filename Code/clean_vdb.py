import chromadb

# Initialize ChromaDB Client
client = chromadb.PersistentClient(path="./vector_db")
collection = client.get_collection(name="architecture_graph_store")

def clear_vector_database():
    """Fetch all stored IDs and delete all entries in ChromaDB collection"""
    # Retrieve all stored IDs first
    all_entries = collection.get()
    all_ids = all_entries["ids"]

    if all_ids:
        collection.delete(ids=all_ids)  # Delete using the retrieved IDs
        print(f"Deleted {len(all_ids)} entries from ChromaDB.")
    else:
        print("No entries found in ChromaDB.")

# Example Usage: Clean the database
clear_vector_database()
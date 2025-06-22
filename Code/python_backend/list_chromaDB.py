from chromadb import HttpClient

client = HttpClient(host="localhost", port=8000)
collection = client.get_collection("diagrams_index")

data = collection.get(include=["documents", "metadatas"])

for doc, meta, doc_id in zip(data["documents"], data["metadatas"], data["ids"]):
    print(f"{doc_id} [{meta['type']}]:\n{doc}\n")

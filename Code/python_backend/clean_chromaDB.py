from chromadb import HttpClient

client = HttpClient(host="localhost", port=8000)
client.delete_collection("diagrams_index")

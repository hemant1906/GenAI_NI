from chromadb import HttpClient

client = HttpClient(host="localhost", port=8000)
client.delete_collection("architecture_applications")
client.delete_collection("architecture_diagrams")
client.delete_collection("architecture_complexity")

print("ChromaDB cleaned up")

# architecture_applications
# architecture_diagrams
# architecture_complexity
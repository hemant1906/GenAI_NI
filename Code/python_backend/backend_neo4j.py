from fastapi import FastAPI
from neo4j import GraphDatabase

# Neo4j connection details
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password123"

app = FastAPI()

class Neo4jConnector:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def get_upstream_nodes(self, node_id: str, depth: int):
        query = f"""
        MATCH path = (upstream)-[*1..{depth}]->(n {{id: $node_id}})
        RETURN nodes(path) AS upstream_nodes, relationships(path) AS upstream_relationships
        """
        with self.driver.session() as session:
            result = session.run(query, node_id=node_id)
            return [record.data() for record in result]

    def get_downstream_nodes(self, node_id: str, depth: int):
        query = f"""
        MATCH path = (n {{id: $node_id}})-[*1..{depth}]->(downstream)
        RETURN nodes(path) AS downstream_nodes, relationships(path) AS downstream_relationships
        """
        with self.driver.session() as session:
            result = session.run(query, node_id=node_id)
            return [record.data() for record in result]

    def get_allstream_nodes(self, node_id: str, depth: int):
        query = f"""
        MATCH path = (upstream)-[*1..{depth}]-(downstream {{id: $node_id}})
        RETURN nodes(path) AS allstream_nodes, relationships(path) AS allstream_relationships
        """
        with self.driver.session() as session:
            result = session.run(query, node_id=node_id)
            return [record.data() for record in result]

neo4j_connector = Neo4jConnector(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

@app.get("/query")
def query_graph(node_id: str, type: str, depth: int):
    if type.lower() == "upstream":
        result = neo4j_connector.get_upstream_nodes(node_id, depth)
    elif type.lower() == "downstream":
        result = neo4j_connector.get_downstream_nodes(node_id, depth)
    elif type.lower() == "all":
        result = neo4j_connector.get_allstream_nodes(node_id, depth)
    else:
        return {"error": "Only 'upstream, downstream or all' types are supported"}

    return {"data": result}

@app.on_event("shutdown")
def shutdown():
    neo4j_connector.close()

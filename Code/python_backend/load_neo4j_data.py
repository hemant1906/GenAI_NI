import json
from neo4j import GraphDatabase

# Neo4j connection details
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password123"

class Neo4jLoader:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def load_data(self, json_file):
        with open(json_file, "r") as file:
            data = json.load(file)

        with self.driver.session() as session:
            for graph in data:
                self._create_nodes(session, graph["nodes"])
                self._create_relationships(session, graph["relationships"])

    def _create_nodes(self, session, nodes):
        for node in nodes:
            query = """
            MERGE (n:Application {id: $id})
            SET n.name = $name
            SET n += $properties
            """
            session.run(query, id=node["id"], name=node["name"], properties=node["properties"])

    def _create_relationships(self, session, relationships):
        for rel in relationships:
            query = """
            MATCH (a:Application {id: $from_id}), (b:Application {id: $to_id})
            MERGE (a)-[r:%s]->(b)
            SET r += $properties
            """ % rel["type"]
            session.run(query, from_id=rel["from"], to_id=rel["to"], properties=rel["properties"])

if __name__ == "__main__":
    loader = Neo4jLoader(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    loader.load_data(r"C:\Users\sourav\Downloads\test_data\graph_test_data.json")
    loader.close()
    print("Neo4j database loaded successfully!")

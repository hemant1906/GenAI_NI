from neo4j import GraphDatabase

# Neo4j connection details
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password123"

class Neo4jCleaner:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def cleanup_database(self):
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")  # Deletes all nodes and relationships

if __name__ == "__main__":
    cleaner = Neo4jCleaner(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    cleaner.cleanup_database()
    cleaner.close()
    print("Neo4j database cleaned successfully!")

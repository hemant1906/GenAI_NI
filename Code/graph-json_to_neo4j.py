import json
import os
from neo4j import GraphDatabase
from typing import Dict, List, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Neo4jImporter:
    def __init__(self, uri: str, username: str, password: str):
        """Initialize Neo4j connection"""
        self.driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self):
        """Close Neo4j connection"""
        self.driver.close()

    def create_node(self, tx, node_data: Dict[str, Any]):
        """Create a node in Neo4j"""
        # Extract node properties
        node_id = node_data.get('id', node_data.get('_id', ''))
        labels = node_data.get('labels', node_data.get('label', ['Node']))
        properties = node_data.get('properties', {})

        # If labels is a string, convert to list
        if isinstance(labels, str):
            labels = [labels]

        # Escape labels that contain spaces or special characters
        escaped_labels = [f"`{label}`" if ' ' in label or not label.isalnum() else label for label in labels]
        labels_str = ':'.join(escaped_labels)

        # Prepare properties for Cypher - escape property keys if needed
        escaped_props = {}
        props_list = []
        for k, v in properties.items():
            # Escape property key if it contains spaces or special characters
            escaped_key = f"`{k}`" if ' ' in k or not k.replace('_', '').isalnum() else k
            param_key = k.replace(' ', '_').replace('-', '_')  # Safe parameter name
            props_list.append(f"{escaped_key}: ${param_key}")
            escaped_props[param_key] = v

        props_str = ', '.join(props_list)

        cypher = f"MERGE (n:{labels_str} {{id: $id}}) SET n += {{{props_str}}}" if props_str else f"MERGE (n:{labels_str} {{id: $id}})"

        # Execute query
        params = {'id': node_id, **escaped_props}
        tx.run(cypher, params)


    def create_edge(self, tx, edge_data: Dict[str, Any]):
        """Create an edge/relationship in Neo4j"""
        source = edge_data.get('source', edge_data.get('from', edge_data.get('start')))
        target = edge_data.get('target', edge_data.get('to', edge_data.get('end')))
        rel_type = edge_data.get('type', edge_data.get('relationship', edge_data.get('label', 'RELATES_TO')))
        properties = edge_data.get('properties', {})

        # Escape relationship type if it contains spaces or special characters
        escaped_rel_type = f"`{rel_type}`" if ' ' in rel_type or not rel_type.replace('_', '').isalnum() else rel_type

        # Prepare properties for Cypher - escape property keys if needed
        escaped_props = {}
        props_list = []
        for k, v in properties.items():
            # Escape property key if it contains spaces or special characters
            escaped_key = f"`{k}`" if ' ' in k or not k.replace('_', '').isalnum() else k
            param_key = k.replace(' ', '_').replace('-', '_')  # Safe parameter name
            props_list.append(f"{escaped_key}: ${param_key}")
            escaped_props[param_key] = v

        props_str = ', '.join(props_list)
        props_clause = f" {{{props_str}}}" if props_str else ""

        cypher = f"""
        MATCH (a {{id: $source}})
        MATCH (b {{id: $target}})
        MERGE (a)-[r:{escaped_rel_type}{props_clause}]->(b)
        """

        # Execute query
        params = {'source': source, 'target': target, **escaped_props}
        tx.run(cypher, params)


    def import_json_file(self, file_path: str):
        """Import data from a single JSON file"""
        logger.info(f"Processing file: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            with self.driver.session() as session:
                # Handle different JSON structures
                if isinstance(data, dict):
                    self._process_dict_format(session, data)
                elif isinstance(data, list):
                    self._process_list_format(session, data)
                else:
                    logger.warning(f"Unknown data format in {file_path}")

        except Exception as e:
            logger.error(f"Error processing {file_path}: {str(e)}")

    def _process_dict_format(self, session, data: Dict):
        """Process dictionary format JSON"""
        # Common formats:
        # {"nodes": [...], "edges": [...]}
        # {"vertices": [...], "edges": [...]}
        # {"nodes": [...], "relationships": [...]}

        nodes = data.get('nodes', data.get('vertices', []))
        edges = data.get('edges', data.get('relationships', data.get('links', [])))

        # Import nodes first
        if nodes:
            logger.info(f"Importing {len(nodes)} nodes")
            for node in nodes:
                session.execute_write(self.create_node, node)

        # Then import edges
        if edges:
            logger.info(f"Importing {len(edges)} edges")
            for edge in edges:
                session.execute_write(self.create_edge, edge)

    def _process_list_format(self, session, data: List):
        """Process list format JSON - assumes mixed nodes and edges"""
        nodes = []
        edges = []

        # Separate nodes and edges
        for item in data:
            if 'source' in item or 'target' in item or 'from' in item or 'to' in item:
                edges.append(item)
            else:
                nodes.append(item)

        # Import nodes first
        if nodes:
            logger.info(f"Importing {len(nodes)} nodes")
            for node in nodes:
                session.execute_write(self.create_node, node)

        # Then import edges
        if edges:
            logger.info(f"Importing {len(edges)} edges")
            for edge in edges:
                session.execute_write(self.create_edge, edge)

    def import_folder(self, folder_path: str):
        """Import all JSON files from a folder"""
        logger.info(f"Starting import from folder: {folder_path}")

        json_files = [f for f in os.listdir(folder_path) if f.endswith('.json')]

        if not json_files:
            logger.warning(f"No JSON files found in {folder_path}")
            return

        logger.info(f"Found {len(json_files)} JSON files")

        for filename in json_files:
            file_path = os.path.join(folder_path, filename)
            self.import_json_file(file_path)

        logger.info("Import completed successfully")


def main():
    # Configuration - Update these values for your setup
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USERNAME = "neo4j"
    NEO4J_PASSWORD = "grAph#123"  # Change this to your password
    JSON_FOLDER_PATH = r'C:\Users\sourav\Downloads\GenAI\architecture_repository\graph-converted-json'  # Change this to your folder path

    # Create importer instance
    importer = Neo4jImporter(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)

    try:
        # Import all JSON files from the folder
        importer.import_folder(JSON_FOLDER_PATH)
    except Exception as e:
        logger.error(f"Import failed: {str(e)}")
    finally:
        # Close connection
        importer.close()


if __name__ == "__main__":
    main()
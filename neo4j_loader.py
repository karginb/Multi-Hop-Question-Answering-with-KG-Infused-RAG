import json
import time
from neo4j import GraphDatabase
from tqdm import tqdm

URI = "bolt://localhost:7687"
AUTH = ("neo4j", "sifreniz123")

def create_entities_and_relations_batch(tx, nodes_batch, relations_batch):
    """Verileri tek tek değil, toplu paketler (batch) halinde yollar. Hızı 100x artırır."""
    
    # 1. Düğümleri (Nodes) Toplu Yükle
    if nodes_batch:
        node_query = """
        UNWIND $batch AS data
        MERGE (e:Entity {id: data.entity_id})
        SET e.description = data.description,
            e.aliases = data.aliases
        """
        tx.run(node_query, batch=nodes_batch)

    # 2. İlişkileri (Relations) Toplu Yükle
    if relations_batch:
        rel_query = """
        UNWIND $batch AS data
        MERGE (s:Entity {id: data.source_id})
        MERGE (t:Entity {name: data.target_name})
        MERGE (s)-[r:RELATION {type: data.relation_type}]->(t)
        """
        tx.run(rel_query, batch=relations_batch)

def load_data_to_neo4j(jsonl_file, batch_size=2500):
    print("Connecting to Neo4j...")
    driver = GraphDatabase.driver(URI, auth=AUTH)
    
    print(f"Data is starting to load from {jsonl_file} with batch size {batch_size}...")
    
    nodes_batch = []
    relations_batch = []
    
    with driver.session() as session:
        session.run("CREATE INDEX entity_id IF NOT EXISTS FOR (e:Entity) ON (e.id)")
        session.run("CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)")
        
        with open(jsonl_file, 'r', encoding='utf-8') as file:
            for count, line in tqdm(enumerate(file, 1)):
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                entity_id = data.get("entity_id", "")
                
                nodes_batch.append({
                    "entity_id": entity_id,
                    "description": data.get("entity_description", ""),
                    "aliases": data.get("entity_alias", [])
                })
                
                triples = data.get("all_one_hop_triples_str", [])
                for triple in triples:
                    if len(triple) == 2:
                        relations_batch.append({
                            "source_id": entity_id,
                            "relation_type": triple[0],
                            "target_name": triple[1]
                        })
                
                if count % batch_size == 0:
                    session.execute_write(create_entities_and_relations_batch, nodes_batch, relations_batch)
                    nodes_batch.clear()
                    relations_batch.clear()

            if nodes_batch or relations_batch:
                session.execute_write(create_entities_and_relations_batch, nodes_batch, relations_batch)

    driver.close()
    print("-" * 50)
    print("Upload Complete! All data has been ingested.")

if __name__ == "__main__":
    INPUT_FILE = "wikidata5m_kg.jsonl" 
    load_data_to_neo4j(INPUT_FILE)
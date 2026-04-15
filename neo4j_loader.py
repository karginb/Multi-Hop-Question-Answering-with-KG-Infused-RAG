import json
import time
from neo4j import GraphDatabase
from tqdm import tqdm

# Neo4j bağlantı bilgileri (Kendi şifrenle değiştir)
URI = "bolt://localhost:7687"
AUTH = ("neo4j", "sifreniz123")

def create_entity(tx, entity_id, description, aliases):
    """Sadece düğümü (Node) oluşturur."""
    query = """
    MERGE (e:Entity {id: $entity_id})
    SET e.description = $description,
        e.aliases = $aliases
    """
    tx.run(query, entity_id=entity_id, description=description, aliases=aliases)

def create_relation(tx, source_id, relation_type, target_name):
    """İlişkiyi ve (eğer yoksa) hedef düğümü oluşturur."""
    # Dikkat: Hedef düğümün ID'si her zaman elimizde olmayabilir, 
    # bazen sadece isim (örneğin "turkiye") olarak gelir.
    query = """
    MERGE (s:Entity {id: $source_id})
    MERGE (t:Entity {name: $target_name}) // Hedef düğümü ismiyle oluştur/bul
    MERGE (s)-[r:RELATION {type: $relation_type}]->(t)
    """
    tx.run(query, source_id=source_id, relation_type=relation_type, target_name=target_name)

def load_data_to_neo4j(jsonl_file):
    print("Connecting to Neo4j...")
    driver = GraphDatabase.driver(URI, auth=AUTH)
    
    print("Data is starting to load.")
    
    with driver.session() as session:
        # Önce hızlandırmak için ID ve Name üzerinde index oluşturalım
        session.run("CREATE INDEX entity_id IF NOT EXISTS FOR (e:Entity) ON (e.id)")
        session.run("CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)")
        
        with open(jsonl_file, 'r', encoding='utf-8') as file:
            for count, line in tqdm(enumerate(file, 1)):
                data = json.loads(line)
                entity_id = data.get("entity_id", "")
                description = data.get("entity_description", "")
                aliases = data.get("entity_alias", [])
                triples = data.get("all_one_hop_triples_str", [])
                
                # 1. Ana varlığı ekle
                session.execute_write(create_entity, entity_id, description, aliases)
                
                # 2. Varlığın tüm 1-hop ilişkilerini (triplets) ekle
                for triple in triples:    

                    if len(triple) == 2: # [relation, target_entity] formatında
                        relation_type = triple[0]
                        target_name = triple[1]
                        session.execute_write(create_relation, entity_id, relation_type, target_name)
                
                if count % 1000 == 0:
                    print(f"\n{count} existence and relationships were explored...")

    driver.close()
    print("-" * 50)
    print(f"Upload Complete!")

if __name__ == "__main__":
    INPUT_FILE = "wikidata5m_turkey_filtered.jsonl"
    load_data_to_neo4j(INPUT_FILE)
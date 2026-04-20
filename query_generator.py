import json
from neo4j import GraphDatabase
import ollama

URI = "bolt://localhost:7687"
AUTH = ("neo4j", "sifreniz123") # Şifreni kontrol et
MODEL_NAME = "qwen2.5"

# Domainler ve İlişkileri
DOMAINS = {
    "Turkish Football": ["member of sports team", "coach of", "home venue", "place of birth"],
    "Turkish Cinema": ["director", "cast member", "country of origin", "award received"],
    "Turkish Companies": ["founder", "headquarters location", "industry", "subsidiary"],
    "Turkish Music": ["genre", "record label", "place of birth", "award received"],
    "Turkish Academia": ["educated at", "employer", "field of work", "academic degree"]
}

# --- OPTİMİZE EDİLMİŞ CYPHER SORGULARI ---

def get_2_hop_paths(driver, relations, limit=7):
    query = """
    // 1. ÇAPA: Önce Türkiye'yi bul ve ona bağlı varlıkları al
    MATCH (tr:Entity) WHERE tr.name IN ['turkiye', 'turkey']
    MATCH (start_node:Entity)-[r_tr]->(tr)
    WHERE r_tr.type IN ['country', 'country of citizenship'] 
      AND start_node.aliases[0] IS NOT NULL
    
    // 2. Sadece bu "Türkiyeli" havuzunda istenilen ilişkiyi ara
    MATCH (start_node)-[r1]->(dummy_mid:Entity)
    WHERE r1.type IN $relations
    WITH start_node, r1, dummy_mid LIMIT 500 // RAM şişmesin diye limitliyoruz
    
    // 3. Orta ve Son Düğüm
    MATCH (mid_node:Entity)
    WHERE dummy_mid.name IN mid_node.aliases OR toLower(mid_node.aliases[0]) = toLower(dummy_mid.name)
    
    MATCH (mid_node)-[r2]->(end_node:Entity)
    WHERE end_node.name IS NOT NULL AND r2.type <> 'twinned administrative body'
    
    RETURN DISTINCT start_node.aliases[0] AS Step_0, r1.type AS Hop_1,
           mid_node.aliases[0] AS Step_1, r2.type AS Hop_2, end_node.name AS Step_2
    LIMIT $limit
    """
    with driver.session() as session:
        return [record.data() for record in session.run(query, relations=relations, limit=limit)]

def get_3_hop_paths(driver, relations, limit=3):
    query = """
    MATCH (tr:Entity) WHERE tr.name IN ['turkiye', 'turkey']
    MATCH (start_node:Entity)-[r_tr]->(tr)
    WHERE r_tr.type IN ['country', 'country of citizenship'] 
      AND start_node.aliases[0] IS NOT NULL
      
    MATCH (start_node)-[r1]->(dummy_mid1:Entity)
    WHERE r1.type IN $relations
    WITH start_node, r1, dummy_mid1 LIMIT 500
    
    MATCH (mid1:Entity) WHERE dummy_mid1.name IN mid1.aliases OR toLower(mid1.aliases[0]) = toLower(dummy_mid1.name)
    MATCH (mid1)-[r2]->(dummy_mid2:Entity)
    WITH start_node, r1, mid1, r2, dummy_mid2 LIMIT 500
    
    MATCH (mid2:Entity) WHERE dummy_mid2.name IN mid2.aliases OR toLower(mid2.aliases[0]) = toLower(dummy_mid2.name)
    MATCH (mid2)-[r3]->(end_node:Entity)
    WHERE end_node.name IS NOT NULL AND r3.type <> 'twinned administrative body'
    
    RETURN DISTINCT start_node.aliases[0] AS Step_0, r1.type AS Hop_1,
           mid1.aliases[0] AS Step_1, r2.type AS Hop_2,
           mid2.aliases[0] AS Step_2, r3.type AS Hop_3, end_node.name AS Step_3
    LIMIT $limit
    """
    with driver.session() as session:
        return [record.data() for record in session.run(query, relations=relations, limit=limit)]

def get_comparison_paths(driver, relations, limit=3):
    query = """
    // Önce Türkiyeli 2 farklı varlık bulup eşleştiriyoruz
    MATCH (tr:Entity) WHERE tr.name IN ['turkiye', 'turkey']
    MATCH (comp1:Entity)-[r_tr1]->(tr), (comp2:Entity)-[r_tr2]->(tr)
    WHERE r_tr1.type IN ['country', 'country of citizenship']
      AND r_tr2.type IN ['country', 'country of citizenship']
      AND comp1.id <> comp2.id
      AND comp1.aliases[0] IS NOT NULL AND comp2.aliases[0] IS NOT NULL
    WITH comp1, comp2 LIMIT 2000 // Kombinasyon patlamasını önleyen kilit nokta!
    
    // Şimdi bu ikisinin ortak noktasını arıyoruz
    MATCH (comp1)-[r1]->(shared_node:Entity)<-[r2]-(comp2)
    WHERE r1.type IN $relations AND r1.type = r2.type
    
    RETURN DISTINCT comp1.aliases[0] AS Comp_1, comp2.aliases[0] AS Comp_2, 
           r1.type AS Relation, shared_node.name AS Answer
    LIMIT $limit
    """
    with driver.session() as session:
        return [record.data() for record in session.run(query, relations=relations, limit=limit)]

def generate_question(path_data, q_type):
    if q_type == "2-hop":
        prompt = f"Generate a single, natural question in English using this path. Answer MUST be [{path_data['Step_2']}]. Path: [{path_data['Step_0']}] -> ({path_data['Hop_1']}) -> [{path_data['Step_1']}] -> ({path_data['Hop_2']}) -> [{path_data['Step_2']}]"
    elif q_type == "3-hop":
        prompt = f"Generate a single natural question in English using this path. Answer MUST be [{path_data['Step_3']}]. Path: [{path_data['Step_0']}] -> ({path_data['Hop_1']}) -> [{path_data['Step_1']}] -> ({path_data['Hop_2']}) -> [{path_data['Step_2']}] -> ({path_data['Hop_3']}) -> [{path_data['Step_3']}]"
    else:
        prompt = f"Generate a question asking what connects these two entities. Fact: Both [{path_data['Comp_1']}] and [{path_data['Comp_2']}] share the same ({path_data['Relation']}), which is [{path_data['Answer']}]. Answer MUST be [{path_data['Answer']}]."

    response = ollama.chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': prompt + " Only output the question text."}])
    return response['message']['content'].strip()

def create_dataset():
    driver = GraphDatabase.driver(URI, auth=AUTH)
    dataset = []
    global_id = 1
    
    print("\n[INIT] Generating Multi-Domain Dataset...")
    
    for domain_name, relations in DOMAINS.items():
        print(f"\n--- Processing Domain: {domain_name} ---")
        
        # 2-hop (6 questions)
        p2 = get_2_hop_paths(driver, relations, limit=6)
        for p in p2:
            q_text = generate_question(p, "2-hop")
            dataset.append({"question_id": f"TR_{str(global_id).zfill(3)}", "question_text": q_text, "reasoning_path": [p['Step_0'], p['Hop_1'], p['Step_1'], p['Hop_2'], p['Step_2']], "gold_answer": p['Step_2'], "difficulty": "2-hop", "domain": domain_name})
            global_id += 1
            
        # 3-hop (3 questions)
        p3 = get_3_hop_paths(driver, relations, limit=3)
        for p in p3:
            q_text = generate_question(p, "3-hop")
            dataset.append({"question_id": f"TR_{str(global_id).zfill(3)}", "question_text": q_text, "reasoning_path": [p['Step_0'], p['Hop_1'], p['Step_1'], p['Hop_2'], p['Step_2'], p['Hop_3'], p['Step_3']], "gold_answer": p['Step_3'], "difficulty": "3-hop", "domain": domain_name})
            global_id += 1
            
        # Comparison (1 question)
        pc = get_comparison_paths(driver, relations, limit=1)
        for p in pc:
            q_text = generate_question(p, "comparison")
            dataset.append({"question_id": f"TR_{str(global_id).zfill(3)}", "question_text": q_text, "reasoning_path": [p['Comp_1'], p['Comp_2'], p['Relation'], p['Answer']], "gold_answer": p['Answer'], "difficulty": "comparison", "domain": domain_name})
            global_id += 1

    driver.close()
    
    with open('turkey_qa_dataset.json', 'w', encoding='utf-8') as f:
        json.dump(dataset, f, ensure_ascii=False, indent=4)
    print(f"\nSUCCESS! Multi-domain dataset created with {len(dataset)} questions.")

if __name__ == "__main__":
    create_dataset()
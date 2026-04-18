import json
from neo4j import GraphDatabase
import ollama

# Neo4j Connection Credentials
URI = "bolt://localhost:7687"
AUTH = ("neo4j", "sifreniz123")


def get_2_hop_paths(driver, limit=30):
    query = """
    // ÇAPA: Sadece ülkesi 'turkiye' olan varlıklardan başla (5 milyonluk veride hızı 1000x artırır)
    MATCH (t:Entity {name: 'turkiye'})<-[:RELATION {type: 'country'}]-(start_node:Entity)
    
    // 1. Zıplama
    MATCH (start_node)-[r1]->(dummy_mid:Entity)
    WHERE r1.type IN ['headquarters location', 'founder', 'industry']
      AND start_node.aliases[0] IS NOT NULL
      AND NOT toLower(start_node.aliases[0]) CONTAINS 'spor'
      AND NOT toLower(start_node.aliases[0]) CONTAINS 'university'
      AND NOT toLower(start_node.aliases[0]) CONTAINS 'municipality'
    WITH start_node, r1, dummy_mid LIMIT 1000
    
    // Orta düğüm doğrulaması
    MATCH (mid_node:Entity)
    WHERE dummy_mid.name IN mid_node.aliases OR toLower(mid_node.aliases[0]) = toLower(dummy_mid.name)
    
    // 2. Zıplama
    MATCH (mid_node)-[r2]->(end_node:Entity)
    WHERE end_node.name IS NOT NULL
      AND r2.type <> 'twinned administrative body'
    
    RETURN DISTINCT
        start_node.aliases[0] AS Step_0, r1.type AS Hop_1,
        mid_node.aliases[0] AS Step_1, r2.type AS Hop_2, end_node.name AS Step_2
    LIMIT $limit
    """
    with driver.session() as session:
        return [record.data() for record in session.run(query, limit=limit)]

def get_3_hop_paths(driver, limit=15):
    query = """
    MATCH (t:Entity {name: 'turkiye'})<-[:RELATION {type: 'country'}]-(start_node:Entity)
    MATCH (start_node)-[r1]->(dummy_mid1:Entity)
    WHERE r1.type IN ['headquarters location', 'founder']
      AND start_node.aliases[0] IS NOT NULL
      AND NOT toLower(start_node.aliases[0]) CONTAINS 'spor'
      AND NOT toLower(start_node.aliases[0]) CONTAINS 'university'
      AND NOT toLower(start_node.aliases[0]) CONTAINS 'municipality'
    WITH start_node, r1, dummy_mid1 LIMIT 1000
    
    MATCH (mid1:Entity) WHERE dummy_mid1.name IN mid1.aliases OR toLower(mid1.aliases[0]) = toLower(dummy_mid1.name)
    MATCH (mid1)-[r2]->(dummy_mid2:Entity)
    WITH start_node, r1, mid1, r2, dummy_mid2 LIMIT 1000
    
    MATCH (mid2:Entity) WHERE dummy_mid2.name IN mid2.aliases OR toLower(mid2.aliases[0]) = toLower(dummy_mid2.name)
    MATCH (mid2)-[r3]->(end_node:Entity)
    WHERE end_node.name IS NOT NULL
      AND r2.type <> 'twinned administrative body' AND r3.type <> 'twinned administrative body'
    
    RETURN DISTINCT
        start_node.aliases[0] AS Step_0, r1.type AS Hop_1,
        mid1.aliases[0] AS Step_1, r2.type AS Hop_2,
        mid2.aliases[0] AS Step_2, r3.type AS Hop_3, end_node.name AS Step_3
    LIMIT $limit
    """
    with driver.session() as session:
        return [record.data() for record in session.run(query, limit=limit)]

def get_comparison_paths(driver, limit=5):
    query = """
    // Aynı merkeze veya sektöre sahip iki farklı Türkiye şirketini bul (Kesişim)
    MATCH (t:Entity {name: 'turkiye'})<-[:RELATION {type: 'country'}]-(comp1:Entity)
    MATCH (t)<-[:RELATION {type: 'country'}]-(comp2:Entity)
    
    MATCH (comp1)-[r1]->(shared_node:Entity)<-[r2]-(comp2)
    WHERE r1.type IN ['headquarters location', 'industry'] 
      AND r1.type = r2.type
      AND comp1.id <> comp2.id
      AND comp1.aliases[0] IS NOT NULL AND comp2.aliases[0] IS NOT NULL
      AND NOT toLower(comp1.aliases[0]) CONTAINS 'spor'
      AND NOT toLower(comp2.aliases[0]) CONTAINS 'spor'
      AND NOT toLower(comp1.aliases[0]) CONTAINS 'university'
      AND NOT toLower(comp2.aliases[0]) CONTAINS 'university'
    
    RETURN DISTINCT
        comp1.aliases[0] AS Comp_1, 
        comp2.aliases[0] AS Comp_2, 
        r1.type AS Relation, 
        shared_node.name AS Answer
    LIMIT $limit
    """
    with driver.session() as session:
        return [record.data() for record in session.run(query, limit=limit)]


# --- 2. LLM SORU ÜRETİCİLERİ ---

def generate_question(path_data, q_type):
    if q_type == "2-hop":
        prompt = f"""
        Generate a single, natural question in English using the following Knowledge Graph path. 
        The answer MUST be Node 3 ({path_data['Step_2']}).
        Path: [{path_data['Step_0']}] -> ({path_data['Hop_1']}) -> [{path_data['Step_1']}] -> ({path_data['Hop_2']}) -> [{path_data['Step_2']}]
        Only output the question text without quotes or explanation.
        """
    
    elif q_type == "3-hop":
        prompt = f"""
        Generate a single, complex natural question in English using the following 3-hop Knowledge Graph path. 
        The answer MUST be Node 4 ({path_data['Step_3']}).
        Path: [{path_data['Step_0']}] -> ({path_data['Hop_1']}) -> [{path_data['Step_1']}] -> ({path_data['Hop_2']}) -> [{path_data['Step_2']}] -> ({path_data['Hop_3']}) -> [{path_data['Step_3']}]
        Only output the question text without quotes or explanation.
        """
        
    elif q_type == "comparison":
        prompt = f"""
        Generate a single natural question in English asking what connects these two entities.
        Fact: Both [{path_data['Comp_1']}] and [{path_data['Comp_2']}] share the same ({path_data['Relation']}), which is [{path_data['Answer']}].
        Example: What city serves as the headquarters for both Arçelik and Vestel?
        The answer MUST be [{path_data['Answer']}].
        Only output the question text without quotes or explanation.
        """

    response = ollama.chat(model='qwen2.5', messages=[{'role': 'user', 'content': prompt}])
    return response['message']['content'].strip()


# --- 3. ANA ÇALIŞTIRICI ---

def create_dataset():
    driver = GraphDatabase.driver(URI, auth=AUTH)
    dataset = []
    global_id = 1
    
    print("\n[1/3] Fetching 2-hop paths (30 required)...")
    paths_2 = get_2_hop_paths(driver, limit=30)
    for p in paths_2:
        q_text = generate_question(p, "2-hop")
        dataset.append({
            "question_id": f"TR_COMP_{str(global_id).zfill(3)}",
            "question_text": q_text,
            "reasoning_path": [p['Step_0'], p['Hop_1'], p['Step_1'], p['Hop_2'], p['Step_2']],
            "gold_answer": p['Step_2'],
            "difficulty": "2-hop", "domain": "companies"
        })
        print(f"2-hop [{global_id}]: {q_text} -> {p['Step_2']}")
        global_id += 1

    print("\n[2/3] Fetching 3-hop paths (15 required)...")
    paths_3 = get_3_hop_paths(driver, limit=15)
    for p in paths_3:
        q_text = generate_question(p, "3-hop")
        dataset.append({
            "question_id": f"TR_COMP_{str(global_id).zfill(3)}",
            "question_text": q_text,
            "reasoning_path": [p['Step_0'], p['Hop_1'], p['Step_1'], p['Hop_2'], p['Step_2'], p['Hop_3'], p['Step_3']],
            "gold_answer": p['Step_3'],
            "difficulty": "3-hop", "domain": "companies"
        })
        print(f"3-hop [{global_id}]: {q_text} -> {p['Step_3']}")
        global_id += 1

    print("\n[3/3] Fetching Comparison paths (5 required)...")
    paths_comp = get_comparison_paths(driver, limit=5)
    for p in paths_comp:
        q_text = generate_question(p, "comparison")
        dataset.append({
            "question_id": f"TR_COMP_{str(global_id).zfill(3)}",
            "question_text": q_text,
            "reasoning_path": [p['Comp_1'], p['Comp_2'], p['Relation'], p['Answer']],
            "gold_answer": p['Answer'],
            "difficulty": "comparison", "domain": "companies"
        })
        print(f"Comp [{global_id}]: {q_text} -> {p['Answer']}")
        global_id += 1

    driver.close()
    
    with open('turkey_qa_dataset.json', 'w', encoding='utf-8') as f:
        json.dump(dataset, f, ensure_ascii=False, indent=4)
        
    print(f"\nSUCCESS! 'turkey_qa_dataset.json' created with {len(dataset)} perfectly formatted questions.")

if __name__ == "__main__":
    create_dataset()
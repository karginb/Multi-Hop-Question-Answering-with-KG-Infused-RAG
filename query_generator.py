import json
from neo4j import GraphDatabase
import ollama

# Neo4j Connection Credentials
URI = "bolt://localhost:7687"
AUTH = ("neo4j", "sifreniz123") # Kendi şifrenle değiştirmeyi unutma

def get_2_hop_paths_from_neo4j(limit=30): # Dokümana göre 2-hop soru hedefimiz 30
    driver = GraphDatabase.driver(URI, auth=AUTH)
    
    # SADECE ŞİRKETLERİ BULMAYA ZORLAYAN SORGUSU
    query = """
    // 1. Önce ülkesi kesinlikle Türkiye olan varlıkları bul
    MATCH (start_node:Entity)-[r_c:RELATION {type: 'country'}]->(t:Entity)
    WHERE toLower(t.name) = 'turkiye' OR t.id = 'Q43'
    
    // 2. Sonra bu varlıkların şirketlere özgü ilişkilere (kurucu, sektör vb.) sahip olmasını şart koş
    MATCH (start_node)-[r1]->(dummy_node:Entity)
    WHERE r1.type IN ['founder', 'industry', 'headquarters location'] 
      AND start_node.aliases[0] IS NOT NULL
    WITH start_node, r1, dummy_node LIMIT 1000
      
    // 3. Orta noktayı doğrula
    MATCH (real_mid_node:Entity)
    WHERE dummy_node.name IN real_mid_node.aliases OR toLower(real_mid_node.aliases[0]) = toLower(dummy_node.name)
    
    // 4. İkinci zıplamayı yap
    MATCH (real_mid_node)-[r2]->(end_node:Entity)
    WHERE end_node.name IS NOT NULL
    
    RETURN 
        start_node.aliases[0] AS Step_0, 
        r1.type AS Hop_1, 
        real_mid_node.aliases[0] AS Step_1, 
        r2.type AS Hop_2, 
        end_node.name AS Step_2
    LIMIT $limit
    """
    
    with driver.session() as session:
        result = session.run(query, limit=limit)
        paths = [record.data() for record in result]
        
    driver.close()
    return paths

def generate_question_with_qwen(path_data):
    # The path information provided to the LLM
    path_text = f"[{path_data['Step_0']}] -> ({path_data['Hop_1']}) -> [{path_data['Step_1']}] -> ({path_data['Hop_2']}) -> [{path_data['Step_2']}]"
    
    prompt = f"""
    You are a question generation assistant. Generate a single, natural question in English using the following Knowledge Graph path. 
    The answer to the question must be Node 3 ({path_data['Step_2']}).
    
    Path: Node 1: {path_data['Step_0']} -> Relation 1: {path_data['Hop_1']} -> Node 2: {path_data['Step_1']} -> Relation 2: {path_data['Hop_2']} -> Node 3: {path_data['Step_2']}
    
    Example Path: [Turkcell] -> (headquarters location) -> [istanbul (turkey)] -> (country) -> [turkiye]
    Example Question: What is the country of the city where Turkcell's headquarters is located?
    
    Only output the question text. Do not add any conversational filler, explanations, or quotes.
    """
    
    response = ollama.chat(model='qwen2.5-coder', messages=[
        {'role': 'user', 'content': prompt}
    ])
    
    return response['message']['content'].strip()

def create_dataset():
    paths = get_2_hop_paths_from_neo4j(limit=30) 
    dataset = []
    
    print(f"Paths successfully retrieved from Neo4j: {len(paths)} paths found.")
    if len(paths) == 0:
        print("ERROR: No paths retrieved from Neo4j! Qwen cannot generate questions.")
        return
        
    print("Qwen is generating questions, please wait (this will take a bit longer for 30 questions)...")
    
    for idx, p in enumerate(paths, 1):
        question_text = generate_question_with_qwen(p)
        reasoning_path = [p['Step_0'], p['Hop_1'], p['Step_1'], p['Hop_2'], p['Step_2']]
        
        record = {
            "question_id": f"TR_COMP_{str(idx).zfill(3)}",
            "question_text": question_text,
            "reasoning_path": reasoning_path,
            "gold_answer": p['Step_2'],
            "difficulty": "2-hop",
            "domain": "companies"
        }
        dataset.append(record)
        print(f"[{idx}/{len(paths)}] Question generated: {question_text} (Answer: {p['Step_2']})")
        
    with open('turkey_qa_dataset.json', 'w', encoding='utf-8') as f:
        json.dump(dataset, f, ensure_ascii=False, indent=4)
        
    print("\n'turkey_qa_dataset.json' has been created successfully with 30 questions!")

if __name__ == "__main__":
    create_dataset()
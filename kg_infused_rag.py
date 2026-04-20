import json
import re
from neo4j import GraphDatabase
import ollama

URI = "bolt://localhost:7687"
AUTH = ("neo4j", "sifreniz123") 
MODEL_NAME = "qwen2.5" 

# --- 1. NEO4J & BM25 HELPER FUNCTIONS ---

def setup_bm25_index(driver):
    """Veritabanında BM25 index'i yoksa otomatik olarak oluşturur."""
    print("[SYSTEM] Checking/Creating BM25 Full-Text Index...")
    query = """
    CREATE FULLTEXT INDEX entity_bm25_index IF NOT EXISTS 
    FOR (n:Entity) ON EACH [n.name, n.aliases]
    """
    try:
        with driver.session() as session:
            session.run(query)
        print("[SYSTEM] BM25 Index is ready!")
    except Exception as e:
        print(f"[WARNING] Index check failed (Maybe already exists or syntax error): {e}")

def find_seed_entity_with_bm25(driver, search_term):
    """Kullanıcının girdiği kelimeyi arar, güven skoru çok düşükse saçma sapan yerlere gitmez."""
    query = """
    CALL db.index.fulltext.queryNodes("entity_bm25_index", $search_term) YIELD node, score
    RETURN node.id AS id, node.aliases[0] AS best_name, score
    LIMIT 1
    """
    with driver.session() as session:
        # ~ ile toleranslı arama yapıyoruz
        result = session.run(query, search_term=f"{search_term}")
        record = result.single()
        
        if record:
            score = record["score"]
            best_name = record["best_name"]
            print(f"      -> [BM25 Score: {score:.2f} | Found: '{best_name}']")
            
            # Eğer skor 1.0'dan küçükse bu bir "Suam Nehri" vakasıdır, kabul etme!
            if score > 1.0: 
                return best_name
            else:
                print("      -> [WARNING] Score is too low! Index is likely still building. Falling back to exact term.")
                
        return search_term # Skor düşükse orijinal kelimeyle devam et

def get_one_hop_neighbors(driver, entity_name):
    query = """
    MATCH (n:Entity)-[r]->(target:Entity)
    WHERE toLower(n.aliases[0]) = toLower($name) OR toLower($name) IN [a IN n.aliases | toLower(a)]
    RETURN r.type AS relation, target.name AS target_name, target.aliases[0] AS target_alias
    LIMIT 150
    """
    with driver.session() as session:
        result = session.run(query, name=entity_name)
        return [record.data() for record in result]

# --- 2. LLM DECISION MECHANISM (EARLY STOPPING EKLENDİ) ---

def llm_select_relation(question, current_entity, neighbors, history):
    valid_relations = list(set([n['relation'] for n in neighbors]))
    
    relations_str = "0. [ANSWER FOUND - STOP SEARCHING]\n"
    relations_str += "\n".join([f"{i+1}. {rel}" for i, rel in enumerate(valid_relations)])
    
    if history:
        history_str = " -> ".join([f"[{t[0]}]-({t[1]})-[{t[2]}]" for t in history])
    else:
        history_str = "None (You are just starting)"
    
    # QWEN'E KESİN İTAAT KURALLARI EKLENDİ
    prompt = f"""
    You are an intelligent AI agent navigating a Knowledge Graph.
    Your goal is to answer the User Question.
    
    User Question: "{question}"
    Path traversed so far: {history_str}
    Current Node: [{current_entity}]
    
    Available Paths:
    {relations_str}
    
    INSTRUCTIONS:
    - If the "Path traversed so far" is "None", you MUST NOT output 0. You must pick a logical path to start.
    - If the "Path traversed so far" ALREADY contains the exact answer to the User Question, output ONLY the number 0.
    - Otherwise, choose the logical NEXT step to find the answer and output its corresponding number (e.g., 1, 2, 3).
    Do not write anything else.
    """
    
    response = ollama.chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': prompt}])
    llm_output = response['message']['content'].strip()
    
    try:
        match = re.search(r'\d+', llm_output)
        if match:
            choice_idx = int(match.group())
            
            # Eğer hafıza boşken 0 verirse, onu zorla 1. seçeneğe yönlendir
            if choice_idx == 0 and not history:
                return valid_relations[0]
                
            if choice_idx == 0:
                return "STOP"
                
            if 1 <= choice_idx <= len(valid_relations):
                return valid_relations[choice_idx - 1]
        return valid_relations[0]
    except Exception:
        return valid_relations[0]

# --- 3. MAIN SPREADING ACTIVATION LOOP ---

def spreading_activation(question, raw_seed_name, max_rounds=3):
    driver = GraphDatabase.driver(URI, auth=AUTH)
    
    # 1. Önce BM25 Index'in var olduğundan %100 emin ol
    setup_bm25_index(driver)
    
    # 2. BM25 ile tohumu (seed) doğrula
    print(f"\n[BM25] Analyzing seed entity '{raw_seed_name}'...")
    seed_entity_name = find_seed_entity_with_bm25(driver, raw_seed_name)
    print(f"[BM25] Snapped to exact Knowledge Graph Entity: '{seed_entity_name}'")
    
    current_entity = seed_entity_name
    collected_triplets = []
    
    for round_num in range(1, max_rounds + 1):
        print(f"\n--- Round {round_num} ---")
        
        neighbors = get_one_hop_neighbors(driver, current_entity)
        if not neighbors:
            print(f"[DEAD END] No neighbors found for '{current_entity}'. Stopping search.")
            break
            
        print("Asking Qwen for the next strategic move...")
        selected_relation = llm_select_relation(question, current_entity, neighbors, collected_triplets)
        
        # Erken Durdurma Kontrolü
        if selected_relation == "STOP":
            print(">> Qwen Agent: 'I have enough information. Stopping the search.' <<")
            break
            
        print(f"Qwen Selected Relation: >> {selected_relation} <<")
        
        next_entity = None
        for n in neighbors:
            if n['relation'] == selected_relation:
                next_entity = n.get('target_alias') or n.get('target_name')
                break
                
        if next_entity:
            triplet = (current_entity, selected_relation, next_entity)
            collected_triplets.append(triplet)
            current_entity = next_entity
            print(f"Path Traversed: {triplet}")
        else:
            print(f"[ERROR] Invalid relation chosen. Terminating path.")
            break

    driver.close()
    
    print("\n[COMPLETE] Spreading Activation finished.")
    if collected_triplets:
        summary = "Based on the Knowledge Graph:\n"
        for t in collected_triplets:
            summary += f"- {t[0]} has a relation '{t[1]}' with {t[2]}.\n"
        return summary
    else:
        return "No relevant graph paths could be traversed."

# --- Modül 2 ve 3 ---
def expand_query_with_kg(original_question, kg_summary):
    prompt = f"""
    You are an AI assistant helping to answer a question. 
    Original Question: "{original_question}"
    Knowledge Graph Context:
    {kg_summary}
    Create a combined paragraph that states the facts from the Knowledge Graph and asks the Original Question at the end.
    """
    response = ollama.chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': prompt}])
    return response['message']['content'].strip()

def generate_final_answer(expanded_query):
    prompt = f"""
    You are an expert Q&A system. Answer the question at the end of the text based strictly on the provided context.
    Keep your answer extremely brief and to the point (preferably 1-3 words).
    Context and Question:
    {expanded_query}
    Answer:
    """
    response = ollama.chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': prompt}])
    return response['message']['content'].strip()

if __name__ == "__main__":
    # Kasıtlı olarak "Turkcell" yerine yanlış/eksik yazılmış bir kelime veriyoruz
    test_question = "What is the country of the city where Turkcel's headquarters is located?"
    test_seed = "Turkcel" 
    
    print("="*50)
    print("PHASE 1: AGENTIC SPREADING ACTIVATION (with BM25)")
    print("="*50)
    kg_summary = spreading_activation(test_question, test_seed, max_rounds=3)
    
    print("\n=== Extracted Subgraph ===")
    print(kg_summary)
    
    if "No relevant graph paths" not in kg_summary:
        print("\n" + "="*50)
        print("PHASE 2 & 3: EXPANSION AND GENERATION")
        print("="*50)
        expanded_query = expand_query_with_kg(test_question, kg_summary)
        final_answer = generate_final_answer(expanded_query)
        print(f"\n>>> FINAL AI ANSWER: {final_answer} <<<")
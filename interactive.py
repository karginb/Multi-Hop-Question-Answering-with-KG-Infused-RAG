import warnings
warnings.filterwarnings('ignore')
import ollama

# BÜTÜN MOTORLARI İÇERİ AKTARIYORUZ
from no_retrieval import run_no_retrieval
from vanilla_rag import run_vanilla_rag
from vanilla_qe import run_vanilla_qe
from kg_infused_rag import spreading_activation, expand_query_with_kg, generate_final_answer

MODEL_NAME = "qwen2.5"

def extract_seeds_from_question(question):
    """
    Soruyu analiz edip, Neo4j'nin başlayacağı BÜTÜN anahtar kelimeleri çeker.
    Eğer karşılaştırma sorusuysa (örn: 2 kişi varsa) ikisini de alır.
    """
    prompt = f"""
    Identify ALL the primary entities (e.g., people, companies, movies, teams) mentioned in the question.
    If the question is comparing or asking about multiple entities, extract ALL of them.
    Output them as a simple comma-separated list. No punctuation at the end, no extra words.
    
    Example Question: "Did Emre Özkan and Oktay Derelioğlu both play for Turkey U-21?"
    Output: Emre Özkan, Oktay Derelioğlu
    
    Question: "{question}"
    Output:
    """
    response = ollama.chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': prompt}])
    return response['message']['content'].strip()

def run_interactive_demo():
    print("="*80)
    print("🚀 REAL-TIME RAG COMPARISON DEMO (MULTI-SEED EDITION)")
    print("Type 'exit' or 'quit' to stop.")
    print("="*80)

    while True:
        print("\n" + "-"*80)
        question = input("\n👤 ENTER YOUR QUESTION:\n> ").strip()
        
        if question.lower() in ['exit', 'quit', 'q']:
            print("Exiting demo. Goodbye!")
            break
            
        if not question:
            continue

        # 1. ÇOKLU TOHUM ÇIKARMA AŞAMASI
        print("\n⚙️ Extracting main entities from your question...")
        raw_seeds_str = extract_seeds_from_question(question)
        
        # Virgülle ayrılmış isimleri Python listesine çeviriyoruz
        seeds = [s.strip() for s in raw_seeds_str.split(',') if s.strip()]
        print(f"🎯 Extracted Seeds: {seeds} (Passing to Neo4j BM25...)")

        print("\n" + "="*80)
        print("🤖 GENERATING ANSWERS ACROSS 4 METHODS...")
        print("="*80)

        # --- METHOD 1: No-Retrieval ---
        print("\n[1] Baseline 1: No-Retrieval (NoR)")
        ans_m1 = run_no_retrieval(question)
        print(f"👉 AI Answer: {ans_m1}")

        # --- METHOD 2: Vanilla RAG ---
        print("\n[2] Baseline 2: Vanilla RAG (Wikipedia)")
        ans_m2, ctx_m2 = run_vanilla_rag(question)
        print(f"📄 Retrieved Context: {ctx_m2[:100]}...") 
        print(f"👉 AI Answer: {ans_m2}")

        # --- METHOD 3: Vanilla QE ---
        print("\n[3] Baseline 3: Vanilla Query Expansion (QE)")
        ans_m3, ctx_m3, exp_query = run_vanilla_qe(question)
        print(f"🔍 Expanded Query: {exp_query}")
        print(f"👉 AI Answer: {ans_m3}")

        # --- METHOD 4: KG-Infused RAG (PARALLEL SEARCH) ---
        print("\n[4] Main Method: KG-Infused RAG (Neo4j)")
        
        combined_kg_summary = ""
        
        # Kaç tane tohum (isim) bulduysa, her biri için grafikte ayrı ayrı geziyor
        for seed in seeds:
            print(f"\n   --- 🕵️‍♂️ Investigating path for: '{seed}' ---")
            summary = spreading_activation(question, seed, max_rounds=2)
            
            if "No relevant graph paths" not in summary:
                # Bulduğu yolları birleştiriyor
                combined_kg_summary += summary + "\n"

        if not combined_kg_summary.strip():
            print("\n❌ KG Context: FAILED TO FIND PATH FOR ANY SEED")
            ans_m4 = "Cannot answer without graph context."
        else:
            print(f"\n🕸️ Combined KG Subgraph:\n{combined_kg_summary.strip()}")
            expanded_query = expand_query_with_kg(question, combined_kg_summary)
            ans_m4 = generate_final_answer(expanded_query)
        
        print(f"\n👉 AI Answer: {ans_m4}")
        print("="*80)

if __name__ == "__main__":
    run_interactive_demo()
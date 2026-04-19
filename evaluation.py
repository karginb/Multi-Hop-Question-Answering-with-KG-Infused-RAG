import json
import unicodedata
import collections

# module1_spreading.py dosyamızdaki ana RAG fonksiyonlarını içeri aktarıyoruz
from spreading_module import spreading_activation, expand_query_with_kg, generate_final_answer

def normalize_turkish_text(text):
    """Türkçe karakterleri İngilizce karşılıklarına çevirir ve noktalama/boşlukları siler."""
    text = text.lower().strip()
    replacements = {'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u'}
    for turk, eng in replacements.items():
        text = text.replace(turk, eng)
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    return text

def compute_f1(a_gold, a_pred):
    """Standart QA F1-Score hesaplaması (Kelime bazlı)"""
    gold_toks = a_gold.split()
    pred_toks = a_pred.split()
    common = collections.Counter(gold_toks) & collections.Counter(pred_toks)
    num_same = sum(common.values())
    
    if len(gold_toks) == 0 or len(pred_toks) == 0:
        return int(gold_toks == pred_toks)
    if num_same == 0:
        return 0.0
    
    precision = 1.0 * num_same / len(pred_toks)
    recall = 1.0 * num_same / len(gold_toks)
    f1 = (2 * precision * recall) / (precision + recall)
    return f1

def run_evaluation(dataset_path="turkey_qa_dataset.json"):
    print("\n" + "="*50)
    print("STARTING AUTOMATED EVALUATION (ACADEMIC METRICS)")
    print("="*50)
    
    try:
        with open(dataset_path, 'r', encoding='utf-8') as f:
            dataset = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find {dataset_path}")
        return

    total_questions = len(dataset)
    
    # Metrik Sayaçları
    acc_count = 0
    em_count = 0
    f1_sum = 0.0
    retrieval_success_count = 0
    
    results_log = []

    for idx, item in enumerate(dataset, 1):
        q_id = item['question_id']
        question = item['question_text']
        gold_answer = item['gold_answer'].lower().strip()
        seed_entity = item['reasoning_path'][0] 
        
        print(f"\nEvaluating [{idx}/{total_questions}] - ID: {q_id}")
        
        # 1. Modül: Yayılma (Retrieval Aşaması)
        kg_summary = spreading_activation(question, seed_entity, max_rounds=3)
        norm_gold = normalize_turkish_text(gold_answer)
        
        # --- METRİK 4: Retrieval Recall Kontrolü ---
        if kg_summary != "No relevant graph paths could be traversed.":
            norm_summary = normalize_turkish_text(kg_summary)
            if norm_gold in norm_summary:
                retrieval_success_count += 1
                retrieval_status = "SUCCESS"
            else:
                retrieval_status = "FAIL (Answer not in subgraph)"
        else:
            retrieval_status = "FAIL (No path found)"

        # 2 ve 3. Modül: Genişletme ve Cevaplama
        if "No relevant graph paths" in kg_summary:
            final_answer = "FAILED_TO_FIND_PATH"
        else:
            expanded_query = expand_query_with_kg(question, kg_summary)
            final_answer = generate_final_answer(expanded_query).lower().strip()
            
        norm_ai = normalize_turkish_text(final_answer)
        
        print(f"Gold Answer: {gold_answer}")
        print(f"AI Answer:   {final_answer}")
        print(f"Retrieval:   {retrieval_status}")

        # --- METRİK 1: Accuracy (Yumuşak Eşleştirme) ---
        is_acc = False
        if norm_gold in norm_ai or norm_ai in norm_gold:
            is_acc = True
            acc_count += 1
            
        # --- METRİK 2: Exact Match (Birebir Eşleştirme) ---
        is_em = False
        if norm_gold == norm_ai:
            is_em = True
            em_count += 1
            
        # --- METRİK 3: F1 Score ---
        f1_score = compute_f1(norm_gold, norm_ai)
        f1_sum += f1_score
            
        # Loglama
        results_log.append({
            "question_id": q_id,
            "gold_answer": gold_answer,
            "ai_answer": final_answer,
            "metrics": {
                "accuracy": is_acc,
                "exact_match": is_em,
                "f1_score": round(f1_score, 4),
                "retrieval_success": retrieval_status == "SUCCESS"
            }
        })

    # Ortalamaları Hesapla
    accuracy_perc = (acc_count / total_questions) * 100
    em_perc = (em_count / total_questions) * 100
    f1_avg_perc = (f1_sum / total_questions) * 100
    retrieval_recall_perc = (retrieval_success_count / total_questions) * 100

    print("\n" + "="*50)
    print("FINAL EVALUATION RESULTS (ACADEMIC)")
    print("="*50)
    print(f"Total Questions:    {total_questions}")
    print(f"1. Accuracy:        {accuracy_perc:.2f}% ({acc_count}/{total_questions})")
    print(f"2. Exact Match (EM):{em_perc:.2f}% ({em_count}/{total_questions})")
    print(f"3. F1 Score:        {f1_avg_perc:.2f}%")
    print(f"4. Retrieval Recall:{retrieval_recall_perc:.2f}% ({retrieval_success_count}/{total_questions})")
    print("="*50)
    
    # Raporu Kaydet
    with open('evaluation_results.json', 'w', encoding='utf-8') as f:
        json.dump({
            "overall_metrics": {
                "accuracy_percent": round(accuracy_perc, 2),
                "exact_match_percent": round(em_perc, 2),
                "f1_score_percent": round(f1_avg_perc, 2),
                "retrieval_recall_percent": round(retrieval_recall_perc, 2),
                "total_questions": total_questions
            },
            "details": results_log
        }, f, ensure_ascii=False, indent=4)
        
    print("\nDetailed results saved to 'evaluation_results.json'")

if __name__ == "__main__":
    run_evaluation("turkey_qa_dataset.json")
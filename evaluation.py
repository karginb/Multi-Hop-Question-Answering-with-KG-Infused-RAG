import json
import unicodedata
import collections

from no_retrieval import run_no_retrieval
from vanilla_rag import run_vanilla_rag
from vanilla_qe import run_vanilla_qe
from kg_infused_rag import spreading_activation, expand_query_with_kg, generate_final_answer

def normalize_turkish_text(text):
    text = text.lower().strip()
    replacements = {'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u'}
    for turk, eng in replacements.items(): text = text.replace(turk, eng)
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    return text

def compute_f1(a_gold, a_pred):
    gold_toks = a_gold.split()
    pred_toks = a_pred.split()
    common = collections.Counter(gold_toks) & collections.Counter(pred_toks)
    num_same = sum(common.values())
    if len(gold_toks) == 0 or len(pred_toks) == 0: return int(gold_toks == pred_toks)
    if num_same == 0: return 0.0
    precision = 1.0 * num_same / len(pred_toks)
    recall = 1.0 * num_same / len(gold_toks)
    return (2 * precision * recall) / (precision + recall)

def evaluate_single_method(gold, pred, context=None):
    norm_gold = normalize_turkish_text(gold)
    norm_pred = normalize_turkish_text(pred)
    norm_context = normalize_turkish_text(context) if context else ""
    
    is_acc = norm_gold in norm_pred or norm_pred in norm_gold
    is_em = (norm_gold == norm_pred)
    f1 = compute_f1(norm_gold, norm_pred)
    
    is_recall = False
    if context and norm_gold in norm_context:
        is_recall = True
        
    return {"acc": is_acc, "em": is_em, "f1": f1, "recall": is_recall}

def run_master_evaluation(dataset_path="turkey_qa_dataset.json"):
    print("\n" + "="*80)
    print("STARTING DOMAIN-SPECIFIC MASTER EVALUATION (4 METHODS)")
    print("="*80)
    
    with open(dataset_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    total_questions = len(dataset)
    methods = ["NoR", "Vanilla_RAG", "Vanilla_QE", "KG_RAG"]
    
    # Nested Dictionary for Domain Breakdown
    # Yapı: domain_metrics[domain_name][method_name][metric]
    domain_metrics = {}
    domain_counts = {}

    results_log = []

    for idx, item in enumerate(dataset, 1):
        q_id = item['question_id']
        question = item['question_text']
        gold_answer = item['gold_answer']
        domain = item['domain']
        seed_entity = item['reasoning_path'][0] 
        
        # Domain initialization
        if domain not in domain_metrics:
            domain_metrics[domain] = {m: {"acc": 0, "em": 0, "f1": 0.0, "recall": 0} for m in methods}
            domain_counts[domain] = 0
            
        domain_counts[domain] += 1
        
        print(f"\n[{idx}/{total_questions}] Domain: {domain} | Q: {question}")
        
        ans_m1 = run_no_retrieval(question)
        eval_m1 = evaluate_single_method(gold_answer, ans_m1)
        
        ans_m2, ctx_m2 = run_vanilla_rag(question)
        eval_m2 = evaluate_single_method(gold_answer, ans_m2, ctx_m2)
        
        ans_m3, ctx_m3, _ = run_vanilla_qe(question)
        eval_m3 = evaluate_single_method(gold_answer, ans_m3, ctx_m3)
        
        kg_summary = spreading_activation(question, seed_entity, max_rounds=2)
        if "No relevant graph paths" in kg_summary:
            ans_m4 = "FAILED_TO_FIND_PATH"
        else:
            expanded_query = expand_query_with_kg(question, kg_summary)
            ans_m4 = generate_final_answer(expanded_query)
        eval_m4 = evaluate_single_method(gold_answer, ans_m4, kg_summary)
        
        # Metrikleri Domain Havuzuna Ekleme
        for m_name, eval_data in zip(methods, [eval_m1, eval_m2, eval_m3, eval_m4]):
            if eval_data["acc"]: domain_metrics[domain][m_name]["acc"] += 1
            if eval_data["em"]: domain_metrics[domain][m_name]["em"] += 1
            domain_metrics[domain][m_name]["f1"] += eval_data["f1"]
            if eval_data["recall"]: domain_metrics[domain][m_name]["recall"] += 1

        results_log.append({
            "question_id": q_id, "domain": domain, "gold_answer": gold_answer,
            "methods": {
                "No-Retrieval": {"answer": ans_m1, "metrics": eval_m1},
                "Vanilla RAG": {"answer": ans_m2, "metrics": eval_m2},
                "Vanilla QE": {"answer": ans_m3, "metrics": eval_m3},
                "KG-Infused RAG": {"answer": ans_m4, "metrics": eval_m4}
            }
        })

    # === SONUÇLARI TERMİNALE YAZDIRMA (DOMAIN BAZLI) ===
    print("\n" + "="*80)
    print("FINAL RESULTS BY DOMAIN")
    print("="*80)
    
    final_report = {}
    
    for domain, m_dict in domain_metrics.items():
        q_count = domain_counts[domain]
        print(f"\n>>> DOMAIN: {domain.upper()} ({q_count} Questions) <<<")
        print(f"{'Method':<15} | {'Acc (%)':<10} | {'EM (%)':<10} | {'F1 (%)':<10} | {'Recall (%)':<10}")
        print("-" * 75)
        
        final_report[domain] = {}
        for m_name, scores in m_dict.items():
            acc = round((scores["acc"] / q_count) * 100, 2)
            em = round((scores["em"] / q_count) * 100, 2)
            f1 = round((scores["f1"] / q_count) * 100, 2)
            rec = round((scores["recall"] / q_count) * 100, 2)
            
            final_report[domain][m_name] = {"Accuracy": acc, "Exact Match": em, "F1 Score": f1, "Retrieval Recall": rec}
            print(f"{m_name:<15} | {acc:<10} | {em:<10} | {f1:<10} | {rec:<10}")
            
    with open('results_evaluation.json', 'w', encoding='utf-8') as f:
        json.dump({"total_questions": total_questions, "domain_comparisons": final_report, "details": results_log}, f, ensure_ascii=False, indent=4)
        
    print("\nDetailed domain comparison saved to 'results_evaluation.json'")

if __name__ == "__main__":
    run_master_evaluation("turkey_qa_dataset.json")
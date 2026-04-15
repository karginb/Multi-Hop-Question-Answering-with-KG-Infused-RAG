import json
import time

def extract_turkiye_data(input_jsonl, output_jsonl):
    keywords = ["turkey", "türkiye", "turkish"]
    matched_entities_count = 0
    main_turkey_id = None
    
    print("The dataset is being scanned...")

    with open(input_jsonl, 'r', encoding='utf-8') as infile, \
         open(output_jsonl, 'w', encoding='utf-8') as outfile:
        
        for line_number, line in enumerate(infile, 1):
            try:
                data = json.loads(line)
                entity_id = data.get("entity_id", "")
                description = data.get("entity_description", "").lower()
                aliases = [alias.lower() for alias in data.get("entity_alias", [])]
                
                # 1. Ana 'Türkiye' ülkesini bulma (Q43 olması muhtemel ama script bulsun)
                if "country in eurasia" in description or "country in middle east" in description:
                    if "turkey" in aliases or "türkiye" in aliases:
                        main_turkey_id = entity_id
                        print(f"*** TTürkiye's Main Entity ID: {main_turkey_id} ***")

                # 2. Anahtar kelimeleri içeren herhangi bir entity'yi filtreleme
                is_match = False
                for kw in keywords:
                    if kw in description or any(kw in alias for alias in aliases):
                        is_match = True
                        break
                
                # Eşleşme varsa yeni dosyaya yaz
                if is_match:
                    outfile.write(line)
                    matched_entities_count += 1
                
                # Süreci takip etmek için her 500.000 satırda bir bilgi ver
                if line_number % 500000 == 0:
                    print(f"Processed line: {line_number} | Found match: {matched_entities_count}")
                    
            except json.JSONDecodeError:
                print(f"Hata: {line_number}. satır okunamadı.")
                continue

    print("-" * 50)
    print(f"A total of {matched_entities_count} entities associated with Türkiye were found.")
    print(f"The filtered data was saved to the '{output_jsonl}' file..")
    if main_turkey_id:
        print(f"The main ID for Türkiye has been identified as {main_turkey_id}.")

# Dosya yollarını kendi indirdiğin dizine göre güncelle
INPUT_FILE = 'wikidata5m_kg.jsonl'
OUTPUT_FILE = 'wikidata5m_turkey_filtered.jsonl'

if __name__ == "__main__":
    extract_turkiye_data(INPUT_FILE, OUTPUT_FILE)
import ollama

MODEL_NAME = "qwen2.5"

def run_no_retrieval(question):
    """LLM'e dışarıdan bilgi vermeden sadece kendi hafızasıyla cevaplattırır."""
    prompt = f"""
    You are an expert Q&A system. Answer the following question. 
    Rely ONLY on your internal knowledge. 
    Keep your answer extremely brief and to the point (preferably 1-3 words).
    
    Question: {question}
    Answer:
    """
    response = ollama.chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': prompt}])
    return response['message']['content'].strip()
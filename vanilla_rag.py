import ollama
import wikipedia

wikipedia.set_lang("en")
MODEL_NAME = "qwen2.5"

def run_vanilla_rag(question):
    """Soruyu Wikipedia'da aratır ve bulduğu metne göre cevaplar."""
    try:
        search_results = wikipedia.search(question, results=1)
        if not search_results:
            context = "No Wikipedia information found."
        else:
            context = wikipedia.summary(search_results[0], sentences=5)
    except wikipedia.exceptions.DisambiguationError as e:
        try: context = wikipedia.summary(e.options[0], sentences=5)
        except: context = "No specific Wikipedia information found due to ambiguity."
    except Exception:
        context = "Error retrieving from Wikipedia."

    prompt = f"""
    You are an expert Q&A system. Answer the question based STRICTLY on the provided Wikipedia Context.
    Keep your answer extremely brief and to the point (preferably 1-3 words).
    
    Wikipedia Context: {context}
    
    Question: {question}
    Answer:
    """
    response = ollama.chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': prompt}])
    return response['message']['content'].strip(), context
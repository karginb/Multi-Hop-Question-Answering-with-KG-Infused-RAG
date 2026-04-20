import ollama
import wikipedia

wikipedia.set_lang("en")
MODEL_NAME = "qwen2.5"

def expand_query_without_kg(question):
    prompt = f"""
    You are an AI search assistant. Extract and expand the key search terms from the following question to make it a better search query for Wikipedia.
    Generate a simple, space-separated string of 3-5 keywords. Do NOT write full sentences.
    
    Question: {question}
    Search Query:
    """
    response = ollama.chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': prompt}])
    return response['message']['content'].strip()

def run_vanilla_qe(question):
    """Soruyu zenginleştirip Wikipedia'da aratır ve cevaplar."""
    expanded_query = expand_query_without_kg(question)
    
    try:
        search_results = wikipedia.search(expanded_query, results=1)
        if not search_results:
            context = "No Wikipedia information found."
        else:
            context = wikipedia.summary(search_results[0], sentences=5)
    except wikipedia.exceptions.DisambiguationError as e:
        try: context = wikipedia.summary(e.options[0], sentences=5)
        except: context = "No specific Wikipedia info found."
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
    return response['message']['content'].strip(), context, expanded_query
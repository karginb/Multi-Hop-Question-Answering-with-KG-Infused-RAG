# Multi-Hop Question Answering with KG-Infused RAG: Türkiye Domain Analysis

This repository contains the implementation of the **KG-Infused RAG** framework, specifically tailored for multi-hop reasoning over Türkiye-related entities using the **Wikidata5M** knowledge graph. The project utilizes **Neo4j** as the graph backend and **Ollama (Qwen 2.5)** for agentic navigation.

## 🚀 Features

* **KG-Guided Spreading Activation:** Iterative graph traversal starting from query-relevant seed entities.
* **Neo4j Integration:** Native graph storage and BM25 full-text indexing for robust entity linking.
* **Multi-Domain Support:** Specialized reasoning paths for Turkish Football, Cinema, Companies, Music, and Academia.
* **Comparative Evaluation:** Benchmarking against No-Retrieval, Vanilla RAG, and Vanilla Query Expansion.

## 🛠️ System Architecture

The pipeline is structured into three main modular components:

1.  **Module 1 (Activation):** Navigates Neo4j to extract a relevant subgraph summary using agentic spreading activation.
2.  **Module 2 (Expansion):** Enriches the user query with structural KG facts.
3.  **Module 3 (Generation):** Generates brief, fact-grounded answers (1-3 words) strictly based on the enriched context.

## 📁 Project Structure

```bash
├── neo4j_loader.py       # Batch data ingestion to Neo4j
├── query_generator.py    # Automatic multi-hop question generation
├── kg_infused_rag.py     # Main framework (Spreading Activation & RAG)
├── evaluation.py         # Master evaluation script for all methods
├── vanilla_rag.py        # Baseline RAG implementation
├── vanilla_qe.py         # Baseline Query Expansion implementation
├── no_retrieval.py       # Parametric knowledge baseline
├── turkey_qa_dataset.json# Verified multi-hop question set
└── requirements.txt      # Project dependencies
``` 
# 📊 Experimental Results


 Our evaluation demonstrates that **KG-Infused RAG** significantly outperforms traditional baselines in structured domains by leveraging relational data.

## 🚀 Performance Metrics
The system was tested on specific datasets, yielding the following results:

| Method | Acc (%) | EM (%) | F1 (%) | Recall (%) |
| :--- | :---: | :---: | :---: | :---: |
| No-Retrieval | 2.17 | 2.17 | 6.23 | 0.0 |
| Vanilla RAG | 0.0 | 0.0 | 6.96 | 0.0 |
| Vanilla QE | 2.17 | 0.0 | 11.23 | 0.0 |
| **KG-Infused RAG** | **19.57** | **13.04** | **16.81** | **36.96** |

### Key Improvements
* **Enhanced Connectivity:** Unlike standard text-only RAG systems that often fail due to fragmented data, KG-Infused RAG consistently identifies **multi-hop relations**.
* **Structural Awareness:** The integration of Knowledge Graphs allows the model to bridge information gaps between disparate text chunks.

---

## ⚠️ Error Analysis
Based on detailed case studies, the primary causes of failure were categorized as follows:

1.  **KG Data Deficiency (45%):** Missing triples or relations within the Wikidata5M subset, leading to incomplete knowledge paths.
2.  **Alias Mismatch (30%):** Challenges in mapping entities due to high string distance or variations between Turkish and English naming conventions (BM25 limitation).
3.  **Reasoning Drift (25%):** Instances where the LLM agent selected logical but irrelevant hops during graph traversal, leading away from the ground truth.

---

## 👥 Contributors

* **Cenker Aydın** [![GitHub](https://img.shields.io/badge/GitHub-181717?style=flat&logo=github&logoColor=white)](https://github.com/cenkeraydin)
  [![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=flat&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/cenker-aydin/)

* **Berat Kargın** [![GitHub](https://img.shields.io/badge/GitHub-181717?style=flat&logo=github&logoColor=white)](https://github.com/karginb)
  [![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=flat&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/berat-kargin/)

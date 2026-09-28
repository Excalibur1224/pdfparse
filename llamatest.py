from pathlib import Path
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from langchain_ollama import OllamaEmbeddings as langembeddings
prompt = "Describe satellite from description in terms of satellite name, frequencies, Active or inactive, source or company origin, and orbit type" \
"in the order as described as structured json file"

import sys

# model, embed, parent_folder, output_folder
if len(sys.argv) < 5:
    sys.exit(1)

model = sys.argv[1]
embed = sys.argv[2]
parent_folder = sys.argv[3]
output_folder = sys.argv[4]

if(embed == 'llama'):
    embed_model = OllamaEmbedding(
        model_name="nomic-embed-text",
        request_timeout=300.0,  # Increased timeout for large documents
    )
elif(embed == 'langchain'):
    if model == "3.2":
        embed_model = langembeddings(model="llama3.2:1b")
    elif model == "3.1":
        embed_model = langembeddings(model="llama3.1:8b")
    elif model == "gemma":
        embed_model = langembeddings(model="gemma4:e2b")

if(model == "3.2"):
    llm = Ollama(
        model="llama3.2:1b",  # Confirm with `ollama list`
        request_timeout=300.0,
        temperature=0.1,          # Lower temperature for more factual responses
        )
elif(model == "3.1"):
    llm = Ollama(
        model="llama3.1:8b",  # Confirm with `ollama list`
        request_timeout=300.0,
        temperature=0.1,          # Lower temperature for more factual responses
        )
elif(model == "gemma"):
    llm = Ollama(
        model="gemma4:e2b",
        request_timeout=300.0,
        temperature=0.1,
    )

# Set global configurations
Settings.embed_model = embed_model
Settings.llm = llm

def load_and_index_documents(data_dir):
    """Load documents (json/md only) from a single folder and create vector index"""

    if not Path(data_dir).exists():
        raise FileNotFoundError(f"Data directory '{data_dir}' not found.")

    # Only json and markdown files feed the LLM workflow
    docs = SimpleDirectoryReader(data_dir, required_exts=[".json", ".md"]).load_data()

    if not docs:
        raise ValueError(f"No .json or .md documents found in {data_dir}")

    index = VectorStoreIndex.from_documents(docs, embed_model=embed_model)

    return index

def create_query_engine(index, similarity_top_k=3):
    """Create query engine with specified retrieval parameters"""

    query_engine = index.as_query_engine(
        llm=llm,
        similarity_top_k=similarity_top_k,  # Number of relevant chunks to retrieve
        response_mode="compact"             # Compact response generation
    )

    return query_engine

def run_rag_query(data_dir):
    """Run the RAG system against a single folder's documents; return LLM output only"""

    try:
        index = load_and_index_documents(data_dir)
        query_engine = create_query_engine(index)
        response = query_engine.query(prompt)
        return str(response)
    except Exception:
        return None

def run_for_all_subfolders(parent_folder, output_folder):
    """Iterate every subfolder of parent_folder; write one output file per subfolder"""

    parent = Path(parent_folder)
    if not parent.exists() or not parent.is_dir():
        return

    out_dir = Path(output_folder)
    out_dir.mkdir(parents=True, exist_ok=True)

    subfolders = sorted([f for f in parent.iterdir() if f.is_dir()])

    for subfolder in subfolders:
        has_target_files = any(
            f.suffix.lower() in {".json", ".md"} for f in subfolder.iterdir() if f.is_file()
        )
        if not has_target_files:
            continue

        response = run_rag_query(str(subfolder))
        if response is not None:
            out_file = out_dir / f"{subfolder.name}.{embed}_{model}.txt"
            out_file.write_text(response)

# Main execution
if __name__ == "__main__":
    run_for_all_subfolders(parent_folder, output_folder)
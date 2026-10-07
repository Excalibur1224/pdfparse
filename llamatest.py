from pathlib import Path
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core import SummaryIndex
from llama_index.core.embeddings import MockEmbedding
from langchain_ollama import OllamaEmbeddings as langembeddings
import traceback
prompt = "Describe satellite from description in terms of satellite name, frequencies, Active or inactive, source or company origin, and orbit type" \
"in the order as described as structured json file"

import sys
import os
# import logging
# logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
# Use the exact address that returned 200 in your test
OLLAMA_URL = "http://127.0.0.1:58715"   # replace PORT with the port you tested

# Keep local traffic away from any proxy
os.environ["NO_PROXY"] = "localhost,127.0.0.1"
os.environ["no_proxy"] = "localhost,127.0.0.1"

print("Using Ollama at:", OLLAMA_URL)


# model, embed, parent_folder, output_folder
if len(sys.argv) < 5:
    sys.exit("Usage: script.py <model> <embed> <parent_folder> <output_folder>")

model = sys.argv[1]
embed = sys.argv[2]
parent_folder = sys.argv[3]
output_folder = sys.argv[4]

# CLI key -> Ollama tag (confirm tags with `ollama list`)
LLM_TAGS = {
    "3.2": "llama3.2:1b",
    "3.1": "llama3.1:8b",
    "gemma": "gemma4:e2b",
    "gemma26": "gemma4:26b",
}

base_url = os.environ["OLLAMA_BASE_URL"]

llm = Ollama(model=model, base_url=base_url, request_timeout=1200.0,
             temperature=0.1, context_window=16384)

Settings.llm = llm
Settings.embed_model = MockEmbedding(embed_dim=8)   # placeholder, never used for real

def load_and_index_documents(data_dir):
    """Load documents (json/md only) from a single folder and create vector index"""

    if not Path(data_dir).exists():
        print(f"[LOAD FAIL] Data directory '{data_dir}' not found.")
        raise FileNotFoundError(f"Data directory '{data_dir}' not found.")

    # Only json and markdown files feed the LLM workflow
    docs = SimpleDirectoryReader(data_dir, required_exts=[".json", ".md"]).load_data()

    if not docs:
        print(f"[LOAD FAIL] No .json or .md documents found in {data_dir}")
        raise ValueError(f"No .json or .md documents found in {data_dir}")
    print(f"[LOAD OK] Loaded {len(docs)} document(s) from {data_dir}")

    try:
        index = SummaryIndex.from_documents(docs)
    except Exception:
        print(f"[INDEX FAIL] Could not build vector index for {data_dir}")
        raise
    print(f"[INDEX OK] Built vector index for {data_dir}")

    return index

def create_query_engine(index, similarity_top_k=3):
    """Create query engine with specified retrieval parameters"""
    return index.as_query_engine(llm=llm, response_mode="tree_summarize")

def run_rag_query(data_dir):
    """Run the RAG system against a single folder's documents; return LLM output only"""

    step = "load/index"
    try:
        index = load_and_index_documents(data_dir)

        step = "query engine setup"
        query_engine = create_query_engine(index)
        print(f"[ENGINE OK] Query engine ready for {data_dir}")

        step = "query"
        response = query_engine.query(prompt)
        print(f"[QUERY OK] Got response for {data_dir} ({len(str(response))} chars)")

        return str(response)
    except Exception:
        traceback.print_exc()
        return None

def run_for_all_subfolders(parent_folder, output_folder):
    """Iterate every subfolder of parent_folder; write one output file per subfolder"""
    print("in all subfolders")
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
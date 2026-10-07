import os
import sys
from pathlib import Path
from llama_index.core import SummaryIndex, SimpleDirectoryReader, Settings
from llama_index.core.embeddings import MockEmbedding
from llama_index.llms.ollama import Ollama

prompt = ("Describe one satellite from description in terms of satellite name, all frequencies, "
          "Active or inactive, source or company origin, and orbit type "
          "in the order as described as structured json file.")

model, embed, parent_folder, output_folder = sys.argv[1:5]

Settings.llm = Ollama(model=model, base_url=os.environ["OLLAMA_BASE_URL"],
                      request_timeout=1200.0, temperature=0.1, context_window=16384)
Settings.embed_model = MockEmbedding(embed_dim=8)

out_dir = Path(output_folder)
out_dir.mkdir(parents=True, exist_ok=True)

for subfolder in sorted(f for f in Path(parent_folder).iterdir() if f.is_dir()):
    docs = SimpleDirectoryReader(str(subfolder), required_exts=[".json", ".md"]).load_data()
    if not docs:
        continue
    response = SummaryIndex.from_documents(docs).as_query_engine(
        response_mode="tree_summarize").query(prompt)
    name = f"{subfolder.name}.{embed}_{model.replace(':', '_')}.txt"
    (out_dir / name).write_text(str(response))
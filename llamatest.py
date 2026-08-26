from pathlib import Path
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from langchain_ollama import OllamaEmbeddings as langembeddings

# from llama_index.readers.json import JSONReader
# from llama_index.core import VectorStoreIndex
# reader = JSONReader(clean_json=True)
# documents = reader.load_data(input_file="data.json")
# index = VectorStoreIndex.from_documents(documents)
# query_engine = index.as_query_engine()
# response = query_engine.query("What is in this JSON?")

import sys

# Ensure at least two arguments are provided
if len(sys.argv) < 3:
    print("Usage: python script.py <string1> <string2>")
    sys.exit(1)

model = sys.argv[1]
embed = sys.argv[2]

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

def load_and_index_documents(data_dir="pdfs"):
    """Load documents and create vector index"""

    # Check if data directory exists
    if not Path(data_dir).exists():
        raise FileNotFoundError(f"Data directory '{data_dir}' not found. Please create it and add your PDF files.")

    # Load documents from the data folder
    docs = SimpleDirectoryReader(data_dir).load_data()

    if not docs:
        raise ValueError(f"No documents found in {data_dir}")


    # Build vector index from documents
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

def test_rag_system():
    """Test the RAG system with sample queries"""

    try:
        # Load documents and create index
        index = load_and_index_documents()

        # Create query engine
        query_engine = create_query_engine(index)

        # Sample test queries
        test_queries = [
            # "Describe satellite in terms of ID, Name, MHz Frequency, kHz Bandwidth, Active or inactive, source, orbit type",
            "Describe satellite in terms of ID, Name, frequencies and bandwidths, Active or inactive, source or origin, orbit type",
        ]

        print("RAG System Test Results")
        print("=" * 50)

        for i, query in enumerate(test_queries, 1):
            print(f"\nTest {i}: {query}")
            print("-" * 40)

            try:
                response = query_engine.query(query)
                print(f"Response: {response}")
                print(f"Status: SUCCESS")
            except Exception as e:
                print(f"Error: {str(e)}")
                print(f"Status: FAILED")

            print("-" * 40)

        return True

    except Exception as e:
        print(f"System Error: {str(e)}")
        return False

# Main execution
if __name__ == "__main__":

    print("Starting RAG Pipeline Test...")

    # Test the complete system
    success = test_rag_system()
#!/bin/bash
llama_embed="llama"
lang_embed="langchain"
model1="3.1"
folder="results/automationTestJSON3"
base="fcc_recent_filings"

if [ ! -d "$folder" ]; then
  mkdir -p "$folder"
  echo "Directory created."
else
  echo "Directory already exists."
fi

python llamatest.py "$model1" "$llama_embed" "$base" "$folder"
python llamatest.py "$model1" "$lang_embed" "$base" "$folder"
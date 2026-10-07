#!/bin/bash
llama_embed="llama"
lang_embed="langchain"
gemma_embed="gemma"
model2="gemma26"
model1="3.1"
folder1="results/automationTestJSON_G26"
folder2="results/automationTestJSON_G12"
base="fcc_recent_filings"

if [ ! -d "$folder" ]; then
  mkdir -p "$folder"
  echo "Directory created."
else
  echo "Directory already exists."
fi

python gemmatest.py "gemma4:26b" "$gemma_embed" "$base" "$folder1"
# python gemmatest.py "gemma3:12b" "$gemma_embed" "$base" "$folder2"
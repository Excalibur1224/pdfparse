#!/bin/bash
model = $1
embed = $2
outfile = "responses"
base="fcc_recent_filings"

if [ ! -d "$folder" ]; then
  mkdir -p "$folder"
  echo "Directory created."
else
  echo "Directory already exists."
fi

python gemma_workflow.py "$model" "$embed" "$base" "$outfile"

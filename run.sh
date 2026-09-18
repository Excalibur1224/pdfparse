#!/bin/bash
llama_embed="llama"
lang_embed="langchain"
model2="3.2"
model1="3.1"
model3="gemma"
folder="results/fcc_test"

for i in {1..5}
do
    echo FORloop3 $i
    python llamatest.py $model1 $llama_embed > $folder/oll3.1:8btest$i.txt
done

for i in {1..5}
do
    echo FORloop4 $i
    python llamatest.py $model1 $lang_embed > $folder/lang3.1:8btest$i.txt
done
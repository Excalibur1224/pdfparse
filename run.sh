#!/bin/bash
llama_embed="llama"
lang_embed="langchain"
model2="3.2"
model1="3.1"
model3="gemma"
folder="jsondescriptionresults"



for i in {1..5}
do
    echo FORloop1 $i
    python llamatest.py $model2 $llama_embed > $folder/oll3.2:1btest$i.txt
done

for i in {1..5}
do
    echo FORloop2 $i
    python llamatest.py $model2 $lang_embed > $folder/lang3.2:1btest$i.txt
done

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

for i in {1..5}
do
    echo FORloop5 $i
    python llamatest.py $model3 $llama_embed > $folder/ollgem4:2btest$i.txt
done

for i in {1..5}
do
    echo FORloop6 $i
    python llamatest.py $model3 $lang_embed > $folder/langgem4:2btest$i.txt
done
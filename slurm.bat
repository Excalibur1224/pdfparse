#!/bin/bash

#SBATCH --nodes=1
#SBATCH --ntasks=10
#SBATCH --time=01:00:00
#SBATCH --partition=aa100
#SBATCH --qos=gpu-testing
#SBATCH --output=slurm.out
#SBATCH --gres=gpu:a100_3g.20gb
#SBATCH --

ml python
ml ollama
source .venv/bin/activate

PORT=$((11434 + SLURM_JOB_ID % 1000))
export OLLAMA_HOST=127.0.0.1:$PORT
export OLLAMA_BASE_URL=http://127.0.0.1:$PORT

ollama serve > ollama.log 2>&1 &
sleep 20

./run.sh

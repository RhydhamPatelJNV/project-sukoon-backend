#!/bin/bash
set -e

echo "=== Starting Project Sukoon on Hugging Face Spaces ==="

# 1. Download Model if not present (Hugging Face internal transfer is blazingly fast)
MODEL_PATH="/app/models/Qwen2.5-7B-Instruct-Q4_K_M.gguf"
if [ ! -f "$MODEL_PATH" ]; then
    echo "Downloading Qwen2.5-7B-Instruct-Q4_K_M.gguf from Hugging Face Hub..."
    mkdir -p /app/models
    curl -L "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf" -o "$MODEL_PATH"
fi

# 2. Start llama-server on localhost:8080 (Single Concurrency Slot)
echo "Starting llama-server on port 8080..."
/app/bin/llama-server \
    -m "$MODEL_PATH" \
    --host 127.0.0.1 \
    --port 8080 \
    -c 2048 \
    -t 2 &

# 3. Wait for llama-server to be ready
echo "Waiting for llama-server warmup..."
for i in {1..30}; do
    if curl -s http://127.0.0.1:8080/health > /dev/null 2>&1; then
        echo "llama-server is healthy and ready!"
        break
    fi
    sleep 2
done

# 4. Start FastAPI Backend on Hugging Face default port 7860
echo "Starting FastAPI control plane on port 7860..."
export PYTHONPATH="/app"
exec python3 -m uvicorn sukoon.api.main:app --host 0.0.0.0 --port 7860 --workers 1

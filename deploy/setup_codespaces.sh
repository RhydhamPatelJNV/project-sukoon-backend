#!/usr/bin/env bash
# ==============================================================================
# Project Sukoon — GitHub Codespaces Auto Setup Script
# Architecture: x86_64 Linux (2 vCPU, 8 GB RAM, 32 GB Storage)
# ==============================================================================

set -euo pipefail

echo "========================================================"
echo " Setting up Project Sukoon inside GitHub Codespaces     "
echo "========================================================"

# 1. Install Dependencies
echo "[1/4] Installing system & Python dependencies..."
sudo apt-get update && sudo apt-get install -y cmake build-essential curl
pip install -r requirements.txt
pip install uvicorn[standard] httpx psutil

# 2. Build x86_64 llama-server
echo "[2/4] Compiling llama-server binary..."
if [ ! -f "bin/llama-server" ]; then
    git clone --depth 1 https://github.com/ggml-org/llama.cpp.git /tmp/llama.cpp
    cmake -B /tmp/llama.cpp/build -S /tmp/llama.cpp -DGGML_BUILD_TESTS=OFF -DGGML_BUILD_EXAMPLES=OFF -DGGML_BUILD_SERVER=ON
    cmake --build /tmp/llama.cpp/build --config Release -j 2 --target llama-server
    mkdir -p bin models logs
    cp /tmp/llama.cpp/build/bin/llama-server bin/
    chmod +x bin/llama-server
fi

# 3. Download Qwen2.5-7B GGUF Model (~4.36 GB)
MODEL_FILE="models/Qwen2.5-7B-Instruct-Q4_K_M.gguf"
echo "[3/4] Downloading AI Model directly from Hugging Face..."
if [ ! -f "${MODEL_FILE}" ]; then
    curl -L "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf" \
        -o "${MODEL_FILE}"
fi

# 4. Start Background Services
echo "[4/4] Starting llama-server (port 8080) and FastAPI Backend (port 8000)..."
./bin/llama-server -m "${MODEL_FILE}" --host 127.0.0.1 --port 8080 -c 2048 -t 2 > logs/llama.log 2>&1 &
export PYTHONPATH=.
python -m uvicorn sukoon.api.main:app --host 0.0.0.0 --port 8000 > logs/backend.log 2>&1 &

echo "========================================================"
echo " Sukoon Backend is now running!                         "
echo " Go to the 'PORTS' tab at the bottom of VS Code:       "
echo " Right-click Port 8000 -> Port Visibility -> PUBLIC     "
echo "========================================================"

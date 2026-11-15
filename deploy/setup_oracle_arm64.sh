#!/usr/bin/env bash
# ==============================================================================
# Project Sukoon — Oracle Cloud Always Free Ampere A1 (ARM64) Production Setup
# Architecture: 4 OCPU, 24 GB RAM (or 12 GB budget ceiling), 200 GB Storage
# OS: Ubuntu 22.04 / 24.04 LTS (aarch64)
# ==============================================================================

set -euo pipefail

echo "=================================================================="
echo " Starting Project Sukoon Production Deployment on Oracle Cloud A1 "
echo "=================================================================="

# 1. System Updates & Core Build Tools
echo "[1/7] Updating system and installing dependencies..."
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y \
    build-essential \
    cmake \
    git \
    curl \
    wget \
    python3 \
    python3-pip \
    python3-venv \
    nginx \
    ufw \
    htop \
    jq

# 2. Fix Oracle Cloud Ubuntu Default iptables Block (Crucial for OCI)
echo "[2/7] Adjusting Oracle Cloud iptables rules to allow HTTP/HTTPS traffic..."
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT || true
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT || true
sudo netfilter-persistent save 2>/dev/null || true

# 3. Setup Project Directory Structure
APP_DIR="/opt/sukoon"
echo "[3/7] Setting up application directory at ${APP_DIR}..."
sudo mkdir -p "${APP_DIR}/models" "${APP_DIR}/bin" "${APP_DIR}/logs"
sudo chown -R "$USER:$USER" "${APP_DIR}"

# 4. Compile or Install ARM64 llama.cpp with Native Vector Optimizations
echo "[4/7] Setting up llama.cpp with ARM NEON acceleration..."
if [ ! -f "${APP_DIR}/bin/llama-server" ]; then
    cd /tmp
    rm -rf llama.cpp
    git clone --depth 1 https://github.com/ggml-org/llama.cpp.git
    cd llama.cpp
    cmake -B build -DGGML_NATIVE=ON -DGGML_BUILD_TESTS=OFF -DGGML_BUILD_EXAMPLES=OFF -DGGML_BUILD_SERVER=ON
    cmake --build build --config Release -j 4 --target llama-server
    cp build/bin/llama-server "${APP_DIR}/bin/llama-server"
    chmod +x "${APP_DIR}/bin/llama-server"
    cd "${APP_DIR}"
    echo "llama-server built successfully with native ARM optimizations."
else
    echo "llama-server binary already present in ${APP_DIR}/bin."
fi

# 5. Download Model Directly on Cloud Server (High-Speed OCI Backbone)
MODEL_FILE="${APP_DIR}/models/Qwen2.5-7B-Instruct-Q4_K_M.gguf"
echo "[5/7] Verifying AI Model file..."
if [ ! -f "${MODEL_FILE}" ]; then
    echo "Downloading Qwen2.5-7B-Instruct-Q4_K_M.gguf directly from Hugging Face (~4.36 GB)..."
    curl -L "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf" \
        -o "${MODEL_FILE}"
    echo "Model downloaded successfully."
else
    echo "Model file already exists at ${MODEL_FILE}."
fi

# 6. Python Virtual Environment Setup
echo "[6/7] Setting up Python virtual environment and dependencies..."
cd "${APP_DIR}"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
if [ -f "${APP_DIR}/requirements.txt" ]; then
    pip install -r "${APP_DIR}/requirements.txt"
fi
pip install uvicorn[standard] httpx psutil

# 7. Configure Systemd Services
echo "[7/7] Configuring systemd background services..."

# Service 1: llama.cpp server
sudo tee /etc/systemd/system/sukoon-llama.service > /dev/null <<EOF
[Unit]
Description=Project Sukoon llama.cpp Inference Runtime (Single Concurrency Slot)
After=network.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${APP_DIR}
ExecStart=${APP_DIR}/bin/llama-server -m ${MODEL_FILE} --host 127.0.0.1 --port 8080 -c 4096 -t 4
Restart=always
RestartSec=5
StandardOutput=append:${APP_DIR}/logs/llama.log
StandardError=append:${APP_DIR}/logs/llama.log

[Install]
WantedBy=multi-user.target
EOF

# Service 2: FastAPI Backend
sudo tee /etc/systemd/system/sukoon-backend.service > /dev/null <<EOF
[Unit]
Description=Project Sukoon FastAPI Telemetry and Control Plane
After=network.target sukoon-llama.service

[Service]
Type=simple
User=${USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
Environment=PYTHONPATH=${APP_DIR}
ExecStart=${APP_DIR}/venv/bin/python -m uvicorn sukoon.api.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=always
RestartSec=5
StandardOutput=append:${APP_DIR}/logs/backend.log
StandardError=append:${APP_DIR}/logs/backend.log

[Install]
WantedBy=multi-user.target
EOF

# Configure Nginx Reverse Proxy
sudo tee /etc/nginx/sites-available/sukoon > /dev/null <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/sukoon /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

# Reload and Enable Services
sudo systemctl daemon-reload
sudo systemctl enable sukoon-llama
sudo systemctl enable sukoon-backend
sudo systemctl restart sukoon-llama
sudo systemctl restart sukoon-backend

echo "=================================================================="
echo " Project Sukoon Backend Deployment Complete!                      "
echo " llama.cpp Server: systemctl status sukoon-llama                  "
echo " Sukoon Backend:   systemctl status sukoon-backend                "
echo " Nginx Proxy:      systemctl status nginx                         "
echo " Public Endpoint:  http://<YOUR_ORACLE_PUBLIC_IP>/api/v1/system/resources "
echo "=================================================================="

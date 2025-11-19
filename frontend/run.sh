#!/bin/bash

# BODA Frontend Quick Start Script
# 빠른 시작을 위한 스크립트

set -e  # Exit on error

echo "🏠 BODA Frontend Setup & Run"
echo "======================================"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Python 버전 확인
echo -e "\n${YELLOW}1. Checking Python version...${NC}"
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "   Python version: $python_version"

required_version="3.11"
if [[ $(echo -e "$python_version\n$required_version" | sort -V | head -n1) != "$required_version" ]]; then
    echo -e "${RED}   ✗ Python 3.11+ required${NC}"
    exit 1
fi
echo -e "${GREEN}   ✓ Python version OK${NC}"

# 가상 환경 확인 및 생성
echo -e "\n${YELLOW}2. Setting up virtual environment...${NC}"
if [ ! -d "venv" ]; then
    echo "   Creating virtual environment..."
    python3 -m venv venv
    echo -e "${GREEN}   ✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}   ✓ Virtual environment exists${NC}"
fi

# 가상 환경 활성화
echo "   Activating virtual environment..."
source venv/bin/activate

# 의존성 설치
echo -e "\n${YELLOW}3. Installing dependencies...${NC}"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo -e "${GREEN}   ✓ Dependencies installed${NC}"

# 환경 변수 설정 확인
echo -e "\n${YELLOW}4. Checking environment configuration...${NC}"
if [ ! -f ".env" ]; then
    echo "   Creating .env from template..."
    cp .env.example .env
    echo -e "${YELLOW}   ⚠ Please edit .env file with your settings${NC}"
else
    echo -e "${GREEN}   ✓ .env file exists${NC}"
fi

# Streamlit secrets 확인
if [ ! -f ".streamlit/secrets.toml" ]; then
    echo "   Creating secrets.toml from template..."
    cp .streamlit/secrets.toml.example .streamlit/secrets.toml
    echo -e "${YELLOW}   ⚠ Please edit .streamlit/secrets.toml if needed${NC}"
else
    echo -e "${GREEN}   ✓ secrets.toml exists${NC}"
fi

# 백엔드 연결 테스트 (선택)
echo -e "\n${YELLOW}5. Testing backend connection...${NC}"
if command -v curl &> /dev/null; then
    backend_url=$(grep BACKEND_URL .env | cut -d '=' -f2)
    backend_url=${backend_url:-http://localhost:8000}

    if curl -s -f "${backend_url}/api/v1/health" > /dev/null; then
        echo -e "${GREEN}   ✓ Backend is reachable at ${backend_url}${NC}"
    else
        echo -e "${RED}   ✗ Backend is not reachable at ${backend_url}${NC}"
        echo -e "${YELLOW}   Make sure FastAPI backend is running first!${NC}"
    fi
else
    echo -e "${YELLOW}   ⚠ curl not found, skipping backend test${NC}"
fi

# Streamlit 실행
echo -e "\n${YELLOW}6. Starting Streamlit app...${NC}"
echo "======================================"
echo -e "${GREEN}🚀 Launching BODA Chatbot...${NC}"
echo "   Access at: http://localhost:8501"
echo "   Press Ctrl+C to stop"
echo "======================================"

streamlit run app.py

FROM ghcr.io/astral-sh/uv:python3.11-bookworm

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt 먼저 복사
COPY requirements.txt ./

# 프로덕션 의존성 설치 (requirements.txt 사용)
RUN uv pip install --system -r requirements.txt --native-tls

# 애플리케이션 코드 복사 (README.md 포함)
COPY . .

# ONNX 모델 다운로드 (SSL 문제 해결)
RUN mkdir -p /app/model && \
    curl -k -L -o /app/model/all-MiniLM-L6-v2-onnx.tar.gz \
    "https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main/onnx.tar.gz" && \
    tar -xzf /app/model/all-MiniLM-L6-v2-onnx.tar.gz \
    -C /app/model && \
    rm /app/model/all-MiniLM-L6-v2-onnx.tar.gz

# 데이터 디렉토리 생성 (새로운 구조에 맞게)
RUN mkdir -p data logs config

# 스크립트 실행 권한 부여
RUN chmod +x main.py src/collect_data_now.py

# 환경 변수 설정
ENV PYTHONPATH=/app
ENV OPENSEARCH_ENDPOINT=http://opensearch:9200
ENV OPENSEARCH_USERNAME=admin
ENV OPENSEARCH_PASSWORD=admin
ENV OPENSEARCH_USE_SSL=false
ENV OPENSEARCH_VERIFY_CERTS=false
ENV OPENSEARCH_SSL_ASSERT_HOSTNAME=false
ENV OPENSEARCH_SSL_SHOW_WARN=false

# 기본 명령어 설정 (5년간 전체 데이터 수집 스케줄)
CMD ["uv", "run", "python", "main.py", "--schedule_collect"]

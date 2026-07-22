# LangGraph-Agentic-backend — PDF Agent API 이미지
# 순번 22: app/ingest 만 넣고 tests 제외 (.dockerignore)
FROM python:3.11-slim

WORKDIR /app

# gcc: 일부 wheel 컴파일 · fonts-nanum: 우화 PDF 한글 (reportlab TTF)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc fonts-nanum \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8010

# 패키지 메타 + 소스 (tests 는 .dockerignore 로 제외)
COPY pyproject.toml README.md ./
COPY app ./app
COPY ingest ./ingest

RUN pip install --upgrade pip \
    && pip install .

# 업로드·생성 tmp (런타임 볼륨 마운트 권장)
RUN mkdir -p data/uploads data/tmp/fable_pdf

EXPOSE 8010

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]

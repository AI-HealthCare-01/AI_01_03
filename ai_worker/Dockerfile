FROM python:3.13-slim

WORKDIR /app

# 1. uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 2. 의존성 패키지 관리 파일 복사
COPY pyproject.toml uv.lock ./

# 3. ai 그룹 의존성 설치
RUN uv sync --group ai --no-dev --frozen

# 4. ai_worker 소스 코드 복사 (패키지명 유지)
COPY ./ai_worker ./ai_worker

# 5. Redis 큐 기반 워커 실행
CMD ["uv", "run", "python", "-m", "ai_worker.main"]

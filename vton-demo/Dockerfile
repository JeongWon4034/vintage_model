# Playwright 공식 이미지(크로미움+의존성 내장) → 크롤러가 바로 동작
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium

COPY . .

EXPOSE 8000

# 기본: 웹 갤러리 서버. 파이프라인은 `docker compose run` 으로 실행.
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]

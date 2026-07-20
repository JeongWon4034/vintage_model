.PHONY: install sample crawl tryon demo serve inspect docker-build docker-demo docker-serve

# ---- 로컬 ----
install:            ## 의존성 설치 + 크로미움
	pip install -r requirements.txt && playwright install chromium

sample:             ## 샘플 모델 이미지 내려받기
	python scripts/fetch_sample_model.py

crawl:              ## fruitsfamily 옷 크롤링 (COUNT=5)
	python -m crawler.fruitsfamily --count $(or $(COUNT),5)

tryon:              ## 기존 옷으로 피팅만 실행
	python -m vton.pipeline $(if $(MAX),--max-pairs $(MAX),)

demo:               ## end-to-end (크롤 + 피팅), COUNT=3
	python scripts/run_demo.py --count $(or $(COUNT),3) $(if $(MAX),--max-pairs $(MAX),)

serve:              ## 결과 갤러리 웹서버
	uvicorn app.server:app --reload --port 8000

inspect:            ## IDM-VTON Space API 시그니처 확인
	python -m vton.client --inspect

# ---- Docker ----
docker-build:
	docker compose build

docker-demo:        ## 컨테이너에서 end-to-end, COUNT=3
	docker compose run --rm app python scripts/run_demo.py --count $(or $(COUNT),3)

docker-serve:       ## 컨테이너에서 웹서버
	docker compose up

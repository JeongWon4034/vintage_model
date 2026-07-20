# VTON 데모 — 빈티지 아이템 가상 피팅

fruitsfamily.com 에서 빈티지 옷 사진을 크롤링해, **오픈 diffusion VTON 모델(IDM-VTON)** 로
고정된 AI 모델에게 입혀 보는 데모입니다. 이 계열 모델이 **우리 실사용자 데이터**에서
얼마나 쓸 만한지 눈으로 검증하는 것이 목적입니다.

- 블랙박스 LLM(Gemini)이 아니라 **실제 오픈소스 diffusion 모델**을 구동합니다.
- 로컬 GPU 없이 **HF Space(`yisol/IDM-VTON`) + HF 토큰**으로 모델을 돌립니다.
- 지금은 **정면 1각도**. 360°는 `viewer.js` 의 `SpinViewer` 로 확장 가능하게 구조만 잡아뒀습니다.

```
크롤링(Playwright) → 배경제거(rembg) → IDM-VTON 피팅(gradio_client) → 웹 갤러리(FastAPI)
```

## 빠른 시작 (로컬)

```bash
cd vton-demo

# 1) 의존성
pip install -r requirements.txt
playwright install chromium

# 2) HF 토큰 설정  (https://huggingface.co/settings/tokens · read 권한이면 충분)
cp .env.example .env
#   .env 를 열어 HF_TOKEN=hf_... 채우기

# 3) end-to-end 실행 (옷 3장 크롤 → 피팅)
python scripts/run_demo.py --count 3

# 4) 결과 갤러리
uvicorn app.server:app --port 8000
#   → http://localhost:8000
```

`make` 단축키도 있습니다: `make install`, `make demo COUNT=3`, `make serve`.

## Docker

```bash
docker compose build
docker compose run --rm app python scripts/run_demo.py --count 3   # 크롤+피팅
docker compose up                                                  # http://localhost:8000
```
(`.env` 의 `HF_TOKEN` 이 컨테이너로 전달됩니다.)

## 구성 요소

| 경로 | 역할 |
|---|---|
| `crawler/fruitsfamily.py` | Playwright 로 SPA 렌더 → 상품 이미지 CDN URL 스크랩 → 다운로드 |
| `vton/client.py` | `gradio_client` 로 IDM-VTON Space 호출 (폴백 Space 재시도) |
| `vton/preprocess.py` | rembg 배경 제거 + 부적합 이미지 러프 필터 |
| `vton/pipeline.py` | (모델 × 옷) 조합 피팅 → `data/results/` + `result.json` |
| `app/server.py` + `static/` | 결과 갤러리 (FastAPI) |
| `scripts/run_demo.py` | end-to-end 러너 |
| `config.yaml` | Space·크롤·전처리·경로 설정 |

## 입력 데이터

- **모델(사람)**: `models/` 에 정면 전신 인물 이미지. 없으면 `python scripts/fetch_sample_model.py` 가 공개 예제 인물 1장을 받아 옵니다. 여러 명 넣으면 모두 사용.
- **옷**: `crawler` 가 `data/garments/` 에 채웁니다. **크롤러를 건너뛰고** 직접 이미지를 넣어도 됩니다(`--skip-crawl`).

## ⚠️ 알아둘 한계 (중요)

- **입력 사진 품질이 결과의 8할.** IDM-VTON 은 *깨끗한 정면 상품컷 + 정면 전신 인물*을 전제로 학습됐습니다.
  fruitsfamily 는 착용샷·마네킹샷·바닥 플랫레이가 섞여 있어 **유형에 따라 결과 편차가 큽니다.**
  → 이 데모의 목적은 "어떤 유형이 잘 나오고 어떤 게 깨지는지"를 확인하는 것.
- **HF Space 큐/콜드스타트**로 첫 호출이 느리거나(수십 초~분) 실패할 수 있습니다. 토큰을 넣으면 완화됩니다.
  자주 쓸 거면 Space 를 본인 계정으로 **Duplicate** 해서 전용으로 쓰는 걸 권장합니다.
- Space API 파라미터가 바뀌면: `python -m vton.client --inspect` 로 시그니처 확인 후 `vton/client.py` 조정.
- **표기 의무**: 결과에는 "AI 가상 피팅" 배지를 답니다(실제 착용 아님). 서비스 반영 시 NFR-09(AI 생성 표기) 준수.

## 다음 단계 아이디어

- 유형별 결과 비교 후 전처리 강화(착용샷→옷만 추출) 또는 모델 교체(Leffa/CatVTON).
- 360°: 같은 인물의 각도별 이미지 준비(또는 pose-transfer 합성) → 각도별 피팅 → `SpinViewer` 연결.
- 상품 카드 파이프라인과 연결: 피팅 결과 이미지를 상품 카드 `image` 필드로.

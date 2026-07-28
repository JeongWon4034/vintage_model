# VTON 데모 — 빈티지 아이템 가상 피팅

fruitsfamily.com 의 빈티지 옷을 **오픈 diffusion VTON 모델(IDM-VTON)** 로 고정 AI 모델에게
입혀 보는 데모입니다. 판매자가 적어 둔 **실측(총장)** 을 반영해 옷 길이를 제어하고,
어깨·가슴 실측을 모델 치수와 비교해 **핏(오버핏/정핏/타이트)** 까지 함께 내려줍니다.

- 로컬 GPU 없이 **HF Space + HF 토큰(무료 쿼터)** 으로 모델을 구동합니다.
- 토큰을 여러 개 넣으면 쿼터가 소진될 때마다 **자동 로테이션** 합니다.

```
크롤(Playwright) → 실측 파싱 → 모델 계측(px/cm) → 총장 마스크 → IDM-VTON → API/갤러리
```

## 빠른 시작

```bash
cd vton-demo

# 1) 의존성
pip install -r requirements.txt
playwright install chromium

# 2) HF 토큰  (https://huggingface.co/settings/tokens · read 권한이면 충분)
cp .env.example .env
#   HF_TOKEN=hf_...              단일 토큰
#   HF_TOKENS=hf_a,hf_b,hf_c     (선택) 쿼터 소진 시 자동 전환

# 3) API 서버
uvicorn app.server:app --reload --port 8000
#   → http://localhost:8000        데모 갤러리
#   → http://localhost:8000/docs   Swagger
```

`make install`, `make demo COUNT=3`, `make serve` 단축키도 있습니다.

## 프론트엔드 연동

CORS 는 열려 있어 별도 포트(Vite 5173 / Next 3000 등)에서 바로 호출할 수 있습니다.
**저장소만 클론해도** `data/samples/` 의 경량 이미지로 화면을 붙일 수 있습니다
(원본 고해상도 결과는 용량 때문에 git 에서 제외).

| 엔드포인트 | 설명 |
|---|---|
| `GET /api/health` | 상태 + 피팅 건수 |
| `GET /api/model` | 고정 모델 스펙(키/어깨/가슴) + 360° 프레임 |
| `GET /api/fittings` | **메인.** 피팅 결과 + 옷 실측 + 핏 판정 |
| `GET /api/fittings/{garment_key}` | 단건 조회 |
| `GET /api/length-series` | 같은 옷 총장별 비교 세트 |
| `GET /api/garment-specs` | 옷 실측 원본(크롤/추정 구분) |
| `GET /img/{kind}/{name}` | 이미지. kind = `model` \| `angle` \| `garment` \| `result` \| `sample` |

`/api/fittings` 응답 예시:

```jsonc
{
  "model": { "name": "female_hf_01.png", "height_cm": 168, "shoulder_cm": 38, "chest_cm": 84 },
  "count": 7,
  "items": [{
    "garment_key": "K_footwork_tee",
    "applied_length_cm": 75,              // 이 총장으로 마스크를 만들어 렌더함
    "spec": {
      "label": "퍼블릭포제션 Footwork 반팔티 (L)",
      "length_cm": 75, "shoulder_cm": 54, "chest_cm": 57,
      "source": "crawled",                // crawled = 판매자 실측, manual_estimate = 추정치
      "source_url": "https://fruitsfamily.com/product/..."
    },
    "fit": {
      "label": "오버핏",
      "length_note": "롱 — 엉덩이 덮음",
      "reasons": ["어깨 +16.0cm · 어깨가 많이 떨어짐", "가슴둘레 +30.0cm · 품이 매우 넉넉"]
    },
    "images": {
      "garment": "/img/garment/K_footwork_tee.jpg",       // 원본(로컬 생성 시)
      "result":  "/img/result/measured_footwork_75.png",
      "garment_sample": "/img/sample/K_footwork_tee__garment.jpg",  // 저장소 포함(권장)
      "result_sample":  "/img/sample/K_footwork_tee__result.jpg"
    }
  }]
}
```

> **UI 주의**: `spec.source` 가 `manual_estimate` 인 항목은 실측이 아니라 추정치이므로,
> 화면에서 "추정" 표기를 함께 노출해야 합니다. 결과 이미지에는 **"AI 가상 피팅"** 배지 필수(NFR-09).

## 실측 기반 피팅 실행

```bash
# 모델 계측 (px/cm 산출 · 검증 오버레이 저장)
python -m vton.metrics --model female_hf_01.png --height 168 --debug debug.jpg

# 총장(cm)을 지정해 피팅
python scripts/fit_measured.py --model female_hf_01.png \
  --garment data/garments/E_red_suede.jpg --length 58 \
  --out measured_redsuede_58.png --des "a red suede trucker jacket"

# 결과 인덱스 + 프론트 샘플 재생성
python scripts/build_index.py
```

주요 옵션: `--length`(총장cm) `--widen`(오버핏 여유) `--neck-drop` `--no-arms` `--steps` `--seed`

## 구성 요소

| 경로 | 역할 |
|---|---|
| `crawler/fruitsfamily.py` | 상품 이미지 스크랩 |
| `crawler/linked.py` | **상품 링크 + 이미지 + 실측**을 한 세트로 수집 |
| `crawler/product_detail.py` | 상세 본문에서 총장/어깨/가슴 파싱 |
| `vton/metrics.py` | 모델 사진 계측 → `px_per_cm` 환산 |
| `vton/masking.py` | 총장(cm) → 마스크 생성 |
| `vton/fitlabel.py` | 실측 vs 모델 치수 → 핏 라벨 |
| `vton/client.py` | IDM-VTON Space 호출(폴백·토큰 로테이션) |
| `scripts/fit_measured.py` | 실측 기반 피팅 러너 |
| `scripts/ab_engines.py` | 엔진 A/B (IDM-VTON·OOTD·Leffa·CatVTON) |
| `scripts/build_index.py` | `result.json` + 프론트 샘플 생성 |
| `app/server.py` | API + 갤러리 (FastAPI) |

## ⚠️ 검증으로 확인된 한계

성능 자체보다 **어떤 옷에서 쓸 만한지**가 이 데모의 결론입니다.

| 옷 유형 | 결과 |
|---|---|
| 솔리드 질감 (스웨이드·무통·플리츠·누빔·워시드) | ✅ 아주 좋음 |
| 전면 반복 패턴 (체크·스트라이프·니트 골) | 🔸 무난 |
| 크고 단순한 아웃라인 그래픽 | 🔸 형태는 유지 |
| 국소 프린트·로고·**잔글씨** | ❌ 재창작되어 깨짐 |

- **잔글씨는 어떤 파라미터로도 못 살립니다.** diffusion 이 옷을 다시 그리는 방식이라 원본 픽셀이 보존되지 않습니다.
  엔진 A/B 결과 프린트 보존은 `OOTDiffusion > Leffa > IDM-VTON` 이지만, OOTD 는 해상도·얼굴·소매가 망가져
  상품컷으로 쓰기 어렵습니다. 프린트가 중요하면 상용 API 검토가 필요합니다.
- **실측 기재율이 낮습니다.** 표본 45건 중 숫자 검출 11건(24%), 총장+어깨+가슴 3종 완비는 3건(7%).
  판매자 자유 입력이라, 서비스화하려면 *사용자 직접 입력* 또는 *카테고리 표준 치수 폴백*이 필요합니다.
- **상품 이미지는 620px 고정.** CDN 이 `resized@width620` 외 요청을 403 으로 막습니다(원본 경로도 차단).
- 검색 파라미터 `?q=` 는 실제 키워드 필터가 아닙니다(인기 피드 반환). 카테고리 필터(`subcategoryIds`)를 써야 합니다.
- **핏 판정은 참고용**입니다. 길이는 실측으로 제어되지만, 원단이 눌리고 당겨지는 *물리 시뮬레이션은 아닙니다*
  (그건 3D 의류 시뮬레이터 영역).
- Space API 파라미터가 바뀌면 `python -m vton.client --inspect` 로 시그니처 확인 후 조정.

## 다음 단계

- 모델 3명 확장: `models/` 에 체형별 컷 추가 + `config.yaml` 의 `model_spec.height_cm` 지정 → 같은 옷을 체형별 비교.
- 실측 없는 상품용 폴백(카테고리 표준 치수 / 사용자 입력).
- 상품 카드 파이프라인 연결: 피팅 결과를 상품 카드 이미지로.

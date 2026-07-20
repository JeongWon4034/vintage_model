# 고정 모델 이미지 (무신사 룩북 스타일)

옷을 입힐 **고정 모델(사람) 이미지** 폴더. 파일명 컨벤션으로 성별·사이즈를 표현합니다.

## 파일명 컨벤션

```
{gender}_{size}_{번호}.jpg

gender : male | female
size   : s | avg | l          # 키·몸무게 기준 3단계 (데모는 avg 만)
번호    : 01, 02, ...          # 같은 조건의 다른 모델/포즈
```

예) `female_avg_01.jpg`, `male_avg_01.jpg`, `male_l_01.jpg`

- 파이프라인은 이 폴더의 **모든 이미지**를 모델로 사용합니다.
- 목표 구성: 남/여 × S/AVG/L = 6명. **현재 데모는 평균(avg) 남녀 2명**이면 충분.

## 이미지 요구 사항 (품질이 결과의 절반)

| 항목 | 기준 |
| --- | --- |
| 해상도 | **768×1024 이상** (VTON 출력이 이 해상도라, 입력이 낮으면 결과도 뭉개짐) |
| 구도 | **정면 전신 or 무릎 위**, 무신사 룩북처럼 얼굴 비중 낮아도 OK (단, **어깨~골반은 완전히** 보여야 함) |
| 배경 | 스튜디오 무지 배경(회색/베이지) 권장 |
| 옷 | 몸에 붙는 단색 기본템 (오버핏 입으면 그 실루엣이 결과에 남음) |
| 포즈 | 팔이 몸통을 가리지 않는 자연스러운 차렷/살짝 벌림 |

⚠️ 무신사처럼 **머리를 아예 잘라낸** 컷은 인체 파싱이 불안정해질 수 있음.
→ 얼굴 비중을 줄이려면 "턱 아래부터"가 아니라 **얼굴이 작게 나오는 전신 컷**을 쓰고,
갤러리에서 위를 살짝 크롭해 보여주는 방식을 권장.

## 모델 이미지 만드는 법 (권장 순서)

1. **AI 이미지 생성** (Midjourney/DALL-E/Stable Diffusion 등) — 아래 프롬프트 참고
2. 실제 촬영 (스튜디오/무지벽 + 스마트폰도 OK, 세로 3:4)
3. 데모 임시: 공개 데이터셋 예제 (현 `female_avg_01.jpg` 가 VITON-HD 예제)

### 생성 프롬프트 예시 (avg 남성)

```
full body fashion lookbook photo of a Korean male model, 175cm average build,
standing front view, arms relaxed at sides, plain fitted white t-shirt and
slim gray pants, neutral gray studio background, soft even lighting,
e-commerce catalog style, photorealistic, 4k, 3:4 portrait
```

sizes 는 `slim build 170cm` / `average build 175cm` / `tall muscular 183cm` 식으로 변형.
**같은 시드/모델 얼굴로 시리즈를 뽑아야** 사이즈별 일관성이 생깁니다.

## 360° 확장 시

같은 인물의 각도별 이미지를 `female_avg_01_a00.jpg`, `_a45.jpg` … 식으로 준비하면
`app/static/viewer.js` 의 `SpinViewer` 로 드래그 회전 뷰를 만들 수 있습니다.

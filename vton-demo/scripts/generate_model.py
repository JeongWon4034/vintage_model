"""무신사/29cm 룩북 스타일 고정 모델 이미지 생성 (FLUX.1-schnell).

HF Inference Providers 경유로 오픈소스 diffusion 모델을 호출한다 (HF_TOKEN 필요).
후보를 여러 장 생성해 models/_candidates/ 에 저장 → 사람이 보고 베스트를
models/{gender}_{size}_01.jpg 로 채택하는 흐름.

사용:
    python scripts/generate_model.py --gender female --n 2
    python scripts/generate_model.py --gender male --n 2 --size avg
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import settings  # noqa: E402

MODEL_ID = "black-forest-labs/FLUX.1-schnell"

# 무신사 룩북 톤: 정면 전신, 무지 스튜디오 배경, 얼굴 비중 작은 전신 프레이밍,
# VTON 베이스로 쓰기 좋게 '몸에 붙는 기본템' 착용을 명시한다.
PROMPTS = {
    ("female", "avg"): (
        "Korean fashion e-commerce lookbook photo, full body shot of a Korean female model, "
        "average build, 163cm, standing straight facing camera, arms relaxed at her sides, "
        "wearing a plain fitted white crew-neck t-shirt tucked into straight-leg blue jeans, "
        "plain light gray studio background, soft even studio lighting, natural skin texture, "
        "minimal makeup, hair tied back, head fully visible but small in frame, "
        "photorealistic, 4k quality, sharp focus, muji minimal catalog style"
    ),
    ("male", "avg"): (
        "Korean fashion e-commerce lookbook photo, full body shot of a Korean male model, "
        "average build, 175cm, standing straight facing camera, arms relaxed at his sides, "
        "wearing a plain fitted white crew-neck t-shirt and straight-leg blue jeans, "
        "plain light gray studio background, soft even studio lighting, natural skin texture, "
        "short neat black hair, head fully visible but small in frame, "
        "photorealistic, 4k quality, sharp focus, muji minimal catalog style"
    ),
}
# 사이즈 변형 (s/l 은 문구 치환으로 파생)
SIZE_PHRASES = {
    "s": "slim build, 160cm" if True else "",
    "avg": None,  # 기본 프롬프트 그대로
    "l": "tall athletic build, 178cm",
}


def build_prompt(gender: str, size: str) -> str:
    base = PROMPTS[(gender, "avg")]
    if size == "avg":
        return base
    phrase = SIZE_PHRASES[size]
    return base.replace(
        "average build, 163cm" if gender == "female" else "average build, 175cm", phrase
    )


def generate(gender: str, size: str, n: int) -> list[Path]:
    from huggingface_hub import InferenceClient

    if not settings.HF_TOKEN:
        raise SystemExit("HF_TOKEN 이 필요합니다 (.env)")
    out_dir = settings.MODELS_DIR / "_candidates"
    out_dir.mkdir(parents=True, exist_ok=True)

    client = InferenceClient(api_key=settings.HF_TOKEN)
    prompt = build_prompt(gender, size)
    print(f"[gen] {MODEL_ID} · {gender}/{size} × {n}")
    saved = []
    for i in range(1, n + 1):
        img = client.text_to_image(
            prompt,
            model=MODEL_ID,
            width=768,
            height=1024,
            # schnell 은 4 스텝 증류 모델 — 스텝 수 낮아도 품질 유지
            num_inference_steps=4,
            seed=1000 + i,  # 재현 가능하게 시드 고정
        )
        out = out_dir / f"{gender}_{size}_cand{i:02d}.jpg"
        img.convert("RGB").save(out, "JPEG", quality=95)
        saved.append(out)
        print(f"[gen]   저장 {out.name}  ({img.width}x{img.height})")
    return saved


def main() -> None:
    ap = argparse.ArgumentParser(description="룩북 모델 이미지 생성")
    ap.add_argument("--gender", choices=["female", "male"], required=True)
    ap.add_argument("--size", choices=["s", "avg", "l"], default="avg")
    ap.add_argument("--n", type=int, default=2, help="후보 수")
    args = ap.parse_args()
    generate(args.gender, args.size, args.n)


if __name__ == "__main__":
    main()

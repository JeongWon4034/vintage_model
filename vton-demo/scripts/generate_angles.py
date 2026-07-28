"""고정 모델의 다각도(유사 360°) 프레임 생성 (FLUX.1-Kontext-dev).

채택된 정면 모델 이미지를 입력으로, 이미지 편집 모델이 **동일 인물·의상·배경을
유지한 채** 카메라 각도만 바꾼 프레임을 생성한다.
결과는 models/angles/{모델stem}_a{각도:03d}.jpg 로 저장되며,
갤러리의 SpinViewer 가 드래그 회전 뷰로 보여준다.

사용:
    python scripts/generate_angles.py --model female_avg_01
    python scripts/generate_angles.py --model male_avg_01 --angles 45 90 180 270 315
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import settings  # noqa: E402

EDIT_MODEL = "black-forest-labs/FLUX.1-Kontext-dev"   # Inference Providers 경로 (크레딧 필요)
EDIT_SPACE = "black-forest-labs/FLUX.1-Kontext-Dev"   # ZeroGPU Space 경로 (기본, 무료 쿼터)

# 각도별 편집 지시. '동일 인물/의상/배경 유지'를 반복 강조해야 일관성이 산다.
ANGLE_PROMPTS = {
    45: "Rotate the camera 45 degrees to the left around the model. Same person, same face, "
        "same clothes, same plain gray studio background, full body, three-quarter view.",
    90: "Rotate the camera to show the model's left side profile, 90 degrees. Same person, "
        "same clothes, same plain gray studio background, full body side view.",
    180: "Show the same model from directly behind, back view. Same person, same hair, "
         "same clothes, same plain gray studio background, full body.",
    270: "Rotate the camera to show the model's right side profile, 90 degrees. Same person, "
         "same clothes, same plain gray studio background, full body side view.",
    315: "Rotate the camera 45 degrees to the right around the model. Same person, same face, "
         "same clothes, same plain gray studio background, full body, three-quarter view.",
}


def _edit_via_space(src: Path, prompt: str) -> Path:
    """ZeroGPU Space(무료 쿼터)로 Kontext 편집. 결과 이미지 로컬 경로 반환.

    토큰이 여러 개면(.env 의 HF_TOKENS) 무료 쿼터가 소진될 때마다 다음 토큰으로 넘어간다.
    """
    from gradio_client import Client, handle_file

    tokens = settings.HF_TOKENS or [settings.HF_TOKEN]
    last: Exception | None = None
    for ti, tok in enumerate(tokens, 1):
        try:
            client = Client(EDIT_SPACE, token=tok, verbose=False)
            result, _seed = client.predict(
                handle_file(str(src)),
                prompt,
                0,      # seed
                False,  # randomize_seed — 재현성 위해 고정
                2.5,    # guidance_scale
                28,     # steps
                api_name="/infer",
            )
            path = result["path"] if isinstance(result, dict) else result
            return Path(path)
        except Exception as e:  # noqa: BLE001
            last = e
            low = str(e).lower()
            if ("acceleratorerror" in low or "quota" in low
                    or "zerogpu" in low or "exceeded" in low or "no gpu" in low):
                print(f"[angles]   토큰#{ti} 쿼터소진 → 다음 토큰")
                continue
            raise
    raise RuntimeError(f"모든 토큰 실패: {last}")


def _edit_via_providers(src: Path, prompt: str):
    """Inference Providers 경로 (월 크레딧 소모, --providers 옵션용)."""
    from huggingface_hub import InferenceClient

    client = InferenceClient(api_key=settings.HF_TOKEN)
    return client.image_to_image(src.read_bytes(), prompt=prompt, model=EDIT_MODEL)


def generate(model_stem: str, angles: list[int], use_providers: bool = False) -> list[Path]:
    if not settings.HF_TOKEN:
        raise SystemExit("HF_TOKEN 이 필요합니다 (.env)")
    # 모델 파일은 .jpg 뿐 아니라 .png 로도 들어온다 (힉스필드 생성컷 등)
    src = next((settings.MODELS_DIR / f"{model_stem}{e}"
                for e in (".jpg", ".png", ".jpeg", ".webp")
                if (settings.MODELS_DIR / f"{model_stem}{e}").exists()), None)
    if src is None:
        raise SystemExit(f"모델 이미지가 없습니다: {settings.MODELS_DIR / model_stem}.*")

    out_dir = settings.MODELS_DIR / "angles"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 0도(정면)는 원본 복사
    front = out_dir / f"{model_stem}_a000.jpg"
    if not front.exists():
        shutil.copyfile(src, front)
        print(f"[angles] a000 = 원본 복사")

    saved = [front]
    for deg in angles:
        prompt = ANGLE_PROMPTS.get(deg)
        if not prompt:
            print(f"[angles] {deg}° 프롬프트 없음 — 건너뜀")
            continue
        out = out_dir / f"{model_stem}_a{deg:03d}.jpg"
        if out.exists():
            print(f"[angles] {deg}° 이미 존재 — 건너뜀")
            saved.append(out)
            continue
        print(f"[angles] {deg}° 생성 중…")
        try:
            if use_providers:
                img = _edit_via_providers(src, prompt)
                img.convert("RGB").save(out, "JPEG", quality=95)
            else:
                produced = _edit_via_space(src, prompt)
                from PIL import Image
                Image.open(produced).convert("RGB").save(out, "JPEG", quality=95)
            saved.append(out)
            print(f"[angles]   저장 {out.name}")
        except Exception as e:  # noqa: BLE001
            print(f"[angles]   ✗ {deg}° 실패: {e}")
    return saved


def main() -> None:
    ap = argparse.ArgumentParser(description="모델 다각도 프레임 생성")
    ap.add_argument("--model", required=True, help="models/ 의 파일 stem (예: female_avg_01)")
    ap.add_argument("--angles", type=int, nargs="*", default=[45, 90, 180, 270, 315])
    ap.add_argument("--providers", action="store_true",
                    help="Inference Providers 경로 사용 (월 크레딧 소모, 기본은 ZeroGPU Space)")
    args = ap.parse_args()
    generate(args.model, args.angles, use_providers=args.providers)


if __name__ == "__main__":
    main()

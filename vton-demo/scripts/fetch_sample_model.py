"""데모용 샘플 모델(정면 전신 인물) 이미지 1장을 내려받아 models/ 에 넣는다.

이미지를 직접 생성할 수 없으므로, 공개된 VTON 예제 인물 이미지를 재사용한다.
자체 AI 모델을 쓰려면 models/ 에 정면 전신 인물 이미지를 넣으면 된다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
import settings  # noqa: E402

# 공개 VTON 예제 인물 이미지 후보 (앞에서부터 성공하는 것 사용)
CANDIDATES = [
    "https://huggingface.co/spaces/yisol/IDM-VTON/resolve/main/example/human/00034_00.jpg",
    "https://huggingface.co/spaces/yisol/IDM-VTON/resolve/main/example/human/00035_00.jpg",
    "https://huggingface.co/spaces/yisol/IDM-VTON/resolve/main/example/human/Jensen.jpeg",
    "https://huggingface.co/spaces/yisol/IDM-VTON/resolve/main/example/human/will1.png",
]


def main() -> None:
    settings.ensure_dirs()
    if settings.list_images(settings.MODELS_DIR):
        print(f"[model] 이미 모델 이미지가 있습니다: {settings.MODELS_DIR}")
        return
    out = settings.MODELS_DIR / "model_01.jpg"
    headers = {"User-Agent": "Mozilla/5.0"}
    if settings.HF_TOKEN:
        headers["Authorization"] = f"Bearer {settings.HF_TOKEN}"
    with httpx.Client(headers=headers, timeout=30, follow_redirects=True) as c:
        for url in CANDIDATES:
            try:
                r = c.get(url)
                r.raise_for_status()
                out.write_bytes(r.content)
                print(f"[model] 저장: {out}  (from {url})")
                return
            except Exception as e:  # noqa: BLE001
                print(f"[model] skip ({e}): {url}")
    print(
        "[model] ⚠️ 샘플 모델 다운로드 실패.\n"
        f"  models/ 에 정면 전신 인물 이미지를 직접 넣어주세요: {settings.MODELS_DIR}"
    )


if __name__ == "__main__":
    main()

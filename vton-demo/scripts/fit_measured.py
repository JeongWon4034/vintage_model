"""실측(총장) 기반 피팅 — auto-mask 대신 cm 로 계산한 수동 마스크를 넣는다.

    python scripts/fit_measured.py --model female_hf_01.png \
        --garment data/garments/I_carhartt_denim.jpg --length 62 \
        --out fit_carhartt_62.png --des "a washed denim work jacket"
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import settings
from gradio_client import handle_file
from vton import client, masking, metrics

MASK_DIR = settings.ROOT / "data" / "masks"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="female_hf_01.png")
    ap.add_argument("--garment", required=True)
    ap.add_argument("--length", type=float, required=True, help="옷 총장(cm)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--des", default="a jacket")
    ap.add_argument("--height", type=float, default=None, help="모델 키(cm). 기본은 config")
    ap.add_argument("--steps", type=int, default=40)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-arms", action="store_true", help="팔 영역 제외(민소매/베스트)")
    ap.add_argument("--no-crop", action="store_true",
                    help="is_checked_crop 끄기. 수동 마스크에서 얼굴/배경이 바뀔 때 사용")
    ap.add_argument("--widen", type=float, default=0.06, help="실루엣 대비 좌우 여유(오버핏)")
    ap.add_argument("--neck-drop", type=float, default=3.0, help="어깨선 위 여유(cm)")
    a = ap.parse_args()

    model_path = settings.MODELS_DIR / a.model
    garment = Path(a.garment)
    height_cm = a.height or settings.MODEL_SPEC.get("height_cm", 168.0)

    m, fg = metrics.analyze(model_path, height_cm)
    mask = masking.build_mask(fg, m, a.length, include_arms=not a.no_arms,
                              widen_ratio=a.widen, neck_drop_cm=a.neck_drop)
    stem = f"{model_path.stem}__{garment.stem}__{int(a.length)}cm"
    layer = masking.save_layer(mask, MASK_DIR / f"{stem}_layer.png")
    masking.save_preview(model_path, mask, MASK_DIR / f"{stem}_preview.jpg")

    print(f"[measured] 모델 {height_cm:.0f}cm | {m.px_per_cm:.2f}px/cm | "
          f"어깨 y={m.shoulder_y} → 총장 {a.length}cm = {m.cm_to_px(a.length)}px")
    print(f"[measured] mask -> {layer.name}")

    human = {
        "background": handle_file(str(model_path)),
        "layers": [handle_file(str(layer))],
        "composite": handle_file(str(model_path)),
    }

    tokens = settings.HF_TOKENS or [settings.HF_TOKEN]
    out = settings.RESULTS_DIR / a.out
    t0 = time.time()
    for ti, tok in enumerate(tokens, 1):
        try:
            cli = client.get_client(settings.VTON["space"], token=tok)
        except Exception as e:  # noqa: BLE001
            print(f"[measured] 토큰#{ti} 연결실패 {str(e)[:60]}")
            continue
        try:
            res = cli.predict(
                human, handle_file(str(garment)), a.des,
                False,              # is_checked = auto-mask 끄기 → layers 의 마스크 사용
                not a.no_crop,      # is_checked_crop
                a.steps, a.seed,
                api_name=settings.VTON["api_name"],
            )
            produced = Path(res[0] if isinstance(res, (list, tuple)) else res)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(produced, out)
            print(f"[measured] ✓ {time.time()-t0:.1f}s (토큰#{ti}) -> {out}")
            return
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            low = msg.lower()
            # 쿼터/GPU 소진은 메시지가 여러 형태로 온다 → 전부 다음 토큰으로 전환
            if ("AcceleratorError" in msg or "quota" in low
                    or "zerogpu" in low or "exceeded" in low or "no gpu" in low):
                print(f"[measured] 토큰#{ti} 쿼터소진 → 다음 토큰")
                continue
            print(f"[measured] ✗ {msg[:120]}")
            return
    print("[measured] 모든 토큰 실패")


if __name__ == "__main__":
    main()

"""결과 인덱스 + 프론트 배포용 샘플 생성.

무거운 원본(1536x2048 PNG, 장당 ~2MB)은 git 에서 제외되므로,
프론트가 저장소만 받아도 바로 붙일 수 있도록 축소 JPEG 샘플을 함께 만든다.

    python scripts/build_index.py
      → data/results/result.json      (피팅 인덱스)
      → data/samples/*.jpg + index.json (프론트 개발용 경량 샘플)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import settings
from vton.fitlabel import Garment, judge

MODEL = "female_hf_01.png"

# (옷 key, 결과 파일, 적용한 총장cm | None=자동 마스크, 소요초)
FITTINGS = [
    ("K_footwork_tee", "measured_footwork_75.png", 75, 51.7),
    ("E_red_suede", "measured_redsuede_58.png", 58, 44.2),
    ("I_carhartt_denim", "measured_carhartt_62_fix.png", 62, 42.6),
    ("G_suede_shearling", "female_hf_01__G_suede_shearling.png", None, 28.7),
    ("H_pleated_olive", "female_hf_01__H_pleated_olive.png", None, 27.9),
    ("F_puffer_vest", "female_hf_01__F_puffer.png", None, 39.0),
    ("D_plaid_flannel", "female_hf_01__D_plaid.png", None, 34.9),
]

# 같은 옷에 총장만 바꿔 넣은 비교 세트
LENGTH_SERIES = {
    "garment": "E_red_suede",
    "frames": [(58, "len_redsuede_58.png"), (70, "len_redsuede_70.png"), (85, "len_redsuede_85.png")],
}

SAMPLES_DIR = settings.ROOT / "data" / "samples"
SPEC_PATH = settings.ROOT / "data" / "garment_specs.json"


def garment_file(key: str) -> Path | None:
    for ext in (".jpg", ".png", ".jpeg", ".webp"):
        p = settings.GARMENTS_DIR / f"{key}{ext}"
        if p.exists():
            return p
    return None


def shrink(src: Path, dst: Path, max_h: int, q: int = 85) -> tuple[int, int]:
    im = Image.open(src).convert("RGB")
    w, h = im.size
    if h > max_h:
        im = im.resize((round(w * max_h / h), max_h), Image.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, "JPEG", quality=q, optimize=True)
    return im.size


def main() -> None:
    specs = json.loads(SPEC_PATH.read_text(encoding="utf-8"))["garments"]
    ms = settings.MODEL_SPEC
    items, samples = [], []

    for key, result_name, applied, secs in FITTINGS:
        gp, rp = garment_file(key), settings.RESULTS_DIR / result_name
        if gp is None or not rp.exists():
            print(f"[index] skip {key} (파일 없음)")
            continue
        s = specs.get(key, {})
        g = Garment(key, s.get("length_cm"), s.get("shoulder_cm"),
                    s.get("chest_cm"), s.get("source", "manual_estimate"))
        v = judge(g, ms["shoulder_cm"], ms["chest_cm"])

        items.append({
            "model": MODEL,
            "garment": gp.name,
            "garment_key": key,
            "result": result_name,
            "ok": True,
            "error": None,
            "seconds": secs,
            "applied_length_cm": applied,
            "spec": {
                "label": s.get("label", key),
                "length_cm": s.get("length_cm"),
                "shoulder_cm": s.get("shoulder_cm"),
                "chest_cm": s.get("chest_cm"),
                "source": s.get("source", "manual_estimate"),
                "source_url": s.get("source_url"),
            },
            "fit": {
                "label": v["label"],
                "length_note": v["length_note"],
                "reasons": v["reasons"],
            },
        })

        gs = shrink(gp, SAMPLES_DIR / f"{key}__garment.jpg", 620, 82)
        rs = shrink(rp, SAMPLES_DIR / f"{key}__result.jpg", 1280, 84)
        samples.append({
            "garment_key": key,
            "garment": f"{key}__garment.jpg",
            "result": f"{key}__result.jpg",
            "garment_size": list(gs),
            "result_size": list(rs),
        })

    series = []
    for L, fn in LENGTH_SERIES["frames"]:
        p = settings.RESULTS_DIR / fn
        if not p.exists():
            continue
        shrink(p, SAMPLES_DIR / f"length_{L}.jpg", 1280, 84)
        series.append({"length_cm": L, "result": fn, "sample": f"length_{L}.jpg"})

    model_path = settings.MODELS_DIR / MODEL
    if model_path.exists():
        shrink(model_path, SAMPLES_DIR / "model.jpg", 1280, 86)

    payload = {
        "generated_at": time.time(),
        "space": settings.VTON["space"],
        "model": {
            "name": MODEL,
            "height_cm": ms.get("height_cm"),
            "shoulder_cm": ms.get("shoulder_cm"),
            "chest_cm": ms.get("chest_cm"),
        },
        "items": items,
        "length_series": {"garment_key": LENGTH_SERIES["garment"], "frames": series},
    }
    settings.RESULT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    (SAMPLES_DIR / "index.json").write_text(json.dumps({
        "note": "프론트 개발용 축소 샘플. 원본은 data/results (git 제외).",
        "model": "model.jpg",
        "items": samples,
        "length_series": series,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    total = sum(p.stat().st_size for p in SAMPLES_DIR.glob("*.jpg"))
    print(f"[index] result.json ← {len(items)}건, 길이시리즈 {len(series)}컷")
    print(f"[index] samples → {SAMPLES_DIR} ({total/1024/1024:.1f}MB)")


if __name__ == "__main__":
    main()

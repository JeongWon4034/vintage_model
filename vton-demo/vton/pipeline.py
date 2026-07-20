"""VTON 파이프라인.

models/ 의 고정 모델(정면) × data/garments/ 의 옷 → 각 조합을 IDM-VTON 으로 피팅하고
결과 이미지 + result.json 을 data/results/ 에 저장한다.

사용:
    python -m vton.pipeline                 # 모든 모델 × 모든 옷
    python -m vton.pipeline --max-pairs 3   # 최대 3조합만 (빠른 확인)
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import settings
from vton import client, preprocess


def _result_name(model: Path, garment: Path) -> str:
    return f"{model.stem}__{garment.stem}.png"


def _load_previous() -> dict[tuple[str, str], dict]:
    """이전 manifest 에서 성공한 항목을 (model, garment) 키로 로드."""
    if not settings.RESULT_JSON.exists():
        return {}
    try:
        prev = json.loads(settings.RESULT_JSON.read_text(encoding="utf-8"))
        return {
            (i["model"], i["garment"]): i
            for i in prev.get("items", [])
            if i.get("ok") and (settings.RESULTS_DIR / i["result"]).exists()
        }
    except Exception:  # noqa: BLE001
        return {}


def run(max_pairs: int | None = None, skip_filter: bool = False, force: bool = False) -> dict:
    settings.ensure_dirs()
    work_dir = settings.RESULTS_DIR / "_work"
    work_dir.mkdir(parents=True, exist_ok=True)
    previous = {} if force else _load_previous()

    models = settings.list_images(settings.MODELS_DIR)
    garments_all = settings.list_images(settings.GARMENTS_DIR)

    if not models:
        raise SystemExit(
            f"[pipeline] 모델 이미지가 없습니다: {settings.MODELS_DIR}\n"
            "  정면 전신 인물 이미지를 넣거나 `python scripts/fetch_sample_model.py` 를 실행하세요."
        )
    if not garments_all:
        raise SystemExit(
            f"[pipeline] 옷 이미지가 없습니다: {settings.GARMENTS_DIR}\n"
            "  `python -m crawler.fruitsfamily --count 5` 로 크롤링하거나 직접 넣으세요."
        )

    # 러프 필터로 명백히 부적합한 이미지 제거
    if skip_filter:
        garments = garments_all
    else:
        garments = [g for g in garments_all if preprocess.looks_like_garment(g)]
        dropped = len(garments_all) - len(garments)
        if dropped:
            print(f"[pipeline] 필터로 {dropped}장 제외(디테일컷/극단비율 추정)")

    pairs = [(m, g) for m in models for g in garments]
    if max_pairs:
        pairs = pairs[:max_pairs]

    print(f"[pipeline] 모델 {len(models)} × 옷 {len(garments)} → {len(pairs)}조합 처리")

    items: list[dict] = []
    # 옷 전처리는 조합마다 반복하지 않도록 캐시
    clean_cache: dict[Path, Path] = {}

    for model, garment in pairs:
        # 이미 성공한 조합은 GPU 할당량 절약을 위해 건너뜀 (--force 로 재생성)
        prev = previous.get((model.name, garment.name))
        if prev:
            print(f"[pipeline]   ↷ 스킵(기존 성공): {model.name} × {garment.name}")
            items.append(prev)
            continue
        if garment not in clean_cache:
            clean_cache[garment] = preprocess.prepare_garment(garment, work_dir)
        garment_clean = clean_cache[garment]

        out = settings.RESULTS_DIR / _result_name(model, garment)
        entry = {
            "model": model.name,
            "garment": garment.name,
            "result": out.name,
            "ok": False,
            "error": None,
            "seconds": None,
        }
        t0 = time.time()
        try:
            client.tryon(model, garment_clean, out)
            entry["ok"] = True
        except Exception as e:  # noqa: BLE001
            entry["error"] = str(e)
            print(f"[pipeline]   ✗ 실패: {e}")
        entry["seconds"] = round(time.time() - t0, 1)
        items.append(entry)

    manifest = {
        "generated_at": time.time(),
        "space": settings.VTON["space"],
        "items": items,
    }
    settings.RESULT_JSON.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ok = sum(1 for i in items if i["ok"])
    print(f"[pipeline] 완료 · 성공 {ok}/{len(items)} · manifest → {settings.RESULT_JSON}")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description="VTON 파이프라인")
    ap.add_argument("--max-pairs", type=int, default=None, help="최대 조합 수")
    ap.add_argument("--skip-filter", action="store_true", help="옷 이미지 러프 필터 끄기")
    ap.add_argument("--force", action="store_true", help="기존 성공 결과도 다시 생성")
    args = ap.parse_args()
    run(max_pairs=args.max_pairs, skip_filter=args.skip_filter, force=args.force)


if __name__ == "__main__":
    main()

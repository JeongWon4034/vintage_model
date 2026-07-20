"""End-to-end 데모 러너.

  1) (모델 없으면) 샘플 모델 이미지 확보
  2) fruitsfamily 에서 옷 N장 크롤링
  3) 고정 모델 × 옷 조합을 IDM-VTON 으로 피팅
  4) 결과 경로 안내

사용:
    python scripts/run_demo.py --count 3
    python scripts/run_demo.py --count 5 --max-pairs 3
    python scripts/run_demo.py --skip-crawl        # 크롤 건너뛰고 기존 옷으로만
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import settings  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="VTON 데모 end-to-end 실행")
    ap.add_argument("--count", type=int, default=3, help="크롤링할 옷 이미지 수")
    ap.add_argument("--max-pairs", type=int, default=None, help="최대 (모델×옷) 조합 수")
    ap.add_argument("--skip-crawl", action="store_true", help="크롤링 건너뛰기")
    ap.add_argument("--skip-filter", action="store_true", help="옷 러프 필터 끄기")
    args = ap.parse_args()

    settings.ensure_dirs()

    # 1) 모델 확보
    if not settings.list_images(settings.MODELS_DIR):
        print("[demo] 모델 이미지가 없어 샘플을 내려받습니다…")
        from scripts import fetch_sample_model  # noqa
        fetch_sample_model.main()

    # 2) 크롤링
    if not args.skip_crawl:
        from crawler.fruitsfamily import crawl
        crawl(count=args.count)
    else:
        print("[demo] 크롤 건너뜀 — 기존 data/garments/ 사용")

    # 3) 피팅
    if not settings.HF_TOKEN:
        print("[demo] ⚠️ HF_TOKEN 이 없습니다. .env 에 설정하면 큐 대기가 크게 줄어듭니다.")
    from vton.pipeline import run
    run(max_pairs=args.max_pairs, skip_filter=args.skip_filter)

    # 4) 안내
    print(
        "\n[demo] 완료! 결과 보기:\n"
        "  uvicorn app.server:app --port 8000\n"
        "  → http://localhost:8000\n"
    )


if __name__ == "__main__":
    main()

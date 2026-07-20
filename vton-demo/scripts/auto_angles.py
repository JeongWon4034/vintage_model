"""ZeroGPU 무료 쿼터가 회복될 때까지 자동 재시도하며 360° 각도를 완성한다.

generate_angles.py 를 반복 호출한다. 이미 만들어진 각도 프레임은 건너뛰므로
쿼터가 부분적으로 열려도 조금씩 채워지고, 전부 채워지면 종료한다.

사용:
    python scripts/auto_angles.py --model female_avg_01
    python scripts/auto_angles.py --model female_avg_01 --interval 1200 --max-tries 48
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANGLES = [45, 90, 180, 270, 315]


def existing_frames(model_stem: str) -> set[int]:
    d = ROOT / "models" / "angles"
    if not d.exists():
        return set()
    got = set()
    for f in d.glob(f"{model_stem}_a*.jpg"):
        try:
            got.add(int(f.stem.split("_a")[-1]))
        except ValueError:
            pass
    return got


def run_once(model_stem: str) -> str:
    """generate_angles 1회 실행. 표준출력을 반환."""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_angles.py"),
         "--model", model_stem, "--angles", *map(str, ANGLES)],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    return proc.stdout + proc.stderr


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--interval", type=int, default=1200, help="재시도 간격(초), 기본 20분")
    ap.add_argument("--max-tries", type=int, default=72, help="최대 시도 횟수 (기본 72 ≈ 24h)")
    args = ap.parse_args()

    target = set(ANGLES) | {0}  # 0도(정면)는 원본 복사로 항상 생김
    for attempt in range(1, args.max_tries + 1):
        have = existing_frames(args.model) | {0}
        missing = sorted(target - have)
        if not missing:
            print(f"[auto] ✅ 360° 완성 — 모든 각도 존재: {sorted(have)}")
            return
        print(f"[auto] 시도 {attempt}/{args.max_tries} · 남은 각도 {missing}", flush=True)
        out = run_once(args.model)
        # 성공/실패 라인만 요약 출력
        for line in out.splitlines():
            if "저장" in line or "실패" in line or "✅" in line:
                print("[auto]  " + line.strip(), flush=True)

        have = existing_frames(args.model) | {0}
        if not (target - have):
            print(f"[auto] ✅ 360° 완성", flush=True)
            return
        if "quota" in out.lower() or "쿼터" in out:
            print(f"[auto] 쿼터 소진 — {args.interval//60}분 후 재시도", flush=True)
        else:
            print(f"[auto] 일부 실패 — {args.interval//60}분 후 재시도", flush=True)
        if attempt < args.max_tries:
            time.sleep(args.interval)

    print(f"[auto] ⛔ 최대 시도 도달. 남은 각도: {sorted(target - (existing_frames(args.model) | {0}))}")


if __name__ == "__main__":
    main()

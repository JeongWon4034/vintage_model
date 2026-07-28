"""파라미터 튜닝 피팅 러너 — description/denoise_steps/seed/crop 를 직접 지정해 호출."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import settings
from vton import client
from gradio_client import handle_file


def predict(cli, model_path: Path, garment_path: Path, des: str, steps: int, seed: int, crop: bool):
    human = {"background": handle_file(str(model_path)), "layers": [], "composite": None}
    res = cli.predict(
        human,
        handle_file(str(garment_path)),
        des,
        settings.VTON["auto_mask"],
        crop,
        steps,
        seed,
        api_name=settings.VTON["api_name"],
    )
    return Path(res[0] if isinstance(res, (list, tuple)) else res)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="female_avg_01.jpg")
    ap.add_argument("--garment", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--des", default="a white short-sleeve t-shirt with a large black circular graphic print on the front")
    ap.add_argument("--steps", type=int, default=40)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--crop", action="store_true")
    a = ap.parse_args()

    model = settings.MODELS_DIR / a.model
    garment = Path(a.garment)
    out = settings.RESULTS_DIR / a.out
    print(f"[tuned] {model.name} × {garment.name} | steps={a.steps} seed={a.seed} crop={a.crop}")
    print(f"[tuned] des='{a.des}'")

    tokens = settings.HF_TOKENS or [settings.HF_TOKEN]
    print(f"[tuned] 토큰 {len(tokens)}개 로테이션 (무료 쿼터만 사용)")
    space = settings.VTON["space"]
    t0 = time.time()
    produced = None
    last_err = None
    # 각 토큰마다: 연결 후 최대 3회 시도. AcceleratorError(무료 쿼터 소진) 나면 다음 토큰으로.
    for ti, tok in enumerate(tokens, 1):
        try:
            cli = client.get_client(space, token=tok)
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"[tuned] 토큰#{ti} 연결 실패: {str(e)[:80]} → 다음 토큰")
            continue
        accel_hit = False
        for attempt in range(1, 4):
            try:
                produced = predict(cli, model, garment, a.des, a.steps, a.seed, a.crop)
                print(f"[tuned] 토큰#{ti}로 성공 (시도 {attempt})")
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
                msg = str(e)
                low = msg.lower()
                if ("AcceleratorError" in msg or "quota" in low
                        or "zerogpu" in low or "exceeded" in low or "no gpu" in low):
                    print(f"[tuned] 토큰#{ti} 무료 쿼터 소진 → 다음 토큰")
                    accel_hit = True
                    break
                if "500" in msg or "502" in msg or "timed out" in msg.lower():
                    print(f"[tuned] 토큰#{ti} 일시오류 시도 {attempt}/3: {msg[:60]}")
                    time.sleep(15)
                    continue
                print(f"[tuned] 토큰#{ti} 실패: {msg[:80]} → 다음 토큰")
                break
        if produced is not None:
            break
        if not accel_hit:
            continue
    if produced is None:
        raise RuntimeError(f"모든 토큰({len(tokens)}개) 무료 쿼터 소진/실패. 마지막: {str(last_err)[:120]}")
    import shutil
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(produced, out)
    secs = round(time.time() - t0, 1)
    print(f"[tuned] ✓ {secs}s -> {out}")


if __name__ == "__main__":
    main()

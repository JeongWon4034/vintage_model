"""엔진 A/B — 동일 (모델 × 옷)을 여러 VTON Space 에 돌려 프린트 보존력을 비교한다.

사용:
    python scripts/ab_engines.py --model female_hf_01.png --garment data/garments/B_photogrid_tee.jpg
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import settings
from gradio_client import Client, handle_file


def _client(space: str, token: str) -> Client:
    return Client(space, token=token, verbose=False)


def _pick(res):
    """반환값에서 결과 이미지 경로를 뽑는다 (튜플/갤러리/딕트 대응)."""
    if isinstance(res, (list, tuple)):
        first = res[0]
        if isinstance(first, dict):
            return first.get("image") or first.get("path")
        return first
    if isinstance(res, dict):
        return res.get("image") or res.get("path")
    return res


def run_idm(cli, model: Path, garment: Path, seed: int):
    human = {"background": handle_file(str(model)), "layers": [], "composite": None}
    return _pick(cli.predict(
        human, handle_file(str(garment)),
        "a t-shirt with a graphic print on the front",
        True, True, 40, seed, api_name="/tryon",
    ))


def run_catvton(cli, model: Path, garment: Path, seed: int):
    # ImageEditor 는 composite 까지 채워줘야 내부에서 인덱싱 에러가 안 난다
    f = handle_file(str(model))
    person = {"background": f, "layers": [], "composite": f}
    return _pick(cli.predict(
        person, handle_file(str(garment)),
        "upper", 50, 2.5, seed, "result only",
        api_name="/submit_function",
    ))


def run_leffa(cli, model: Path, garment: Path, seed: int):
    # ref_acceleration / vt_repaint 은 문자열이 아니라 파이썬 bool 이어야 한다
    return _pick(cli.predict(
        handle_file(str(model)), handle_file(str(garment)),
        False, 30, 2.5, seed, "viton_hd", "upper_body", False,
        api_name="/leffa_predict_vt",
    ))


def run_ootd(cli, model: Path, garment: Path, seed: int):
    return _pick(cli.predict(
        handle_file(str(model)), handle_file(str(garment)),
        1, 20, 2.0, seed, api_name="/process_hd",
    ))


ENGINES = [
    ("idm",     "yisol/IDM-VTON",        run_idm),
    ("catvton", "zhengchong/CatVTON",    run_catvton),
    ("leffa",   "franciszzj/Leffa",      run_leffa),
    ("ootd",    "levihsu/OOTDiffusion",  run_ootd),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="female_hf_01.png")
    ap.add_argument("--garment", required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--tag", default="ab")
    a = ap.parse_args()

    model = settings.MODELS_DIR / a.model
    garment = Path(a.garment)
    tokens = settings.HF_TOKENS or [settings.HF_TOKEN]
    settings.ensure_dirs()
    print(f"[ab] {model.name} × {garment.name} | 엔진 {len(ENGINES)}개 | 토큰 {len(tokens)}개 로테이션\n")

    for name, space, fn in ENGINES:
        out = settings.RESULTS_DIR / f"{a.tag}_{name}.png"
        done = False
        t0 = time.time()
        for ti, tok in enumerate(tokens, 1):
            try:
                cli = _client(space, tok)
            except Exception as e:  # noqa: BLE001
                print(f"[ab] {name}: 토큰#{ti} 연결실패 {str(e)[:60]}")
                continue
            try:
                produced = fn(cli, model, garment, a.seed)
                p = Path(produced)
                if not p.exists():
                    raise RuntimeError(f"결과 파일 없음: {p}")
                shutil.copyfile(p, out)
                print(f"[ab] {name}: ✓ {time.time()-t0:.1f}s (토큰#{ti}) -> {out.name}")
                done = True
                break
            except Exception as e:  # noqa: BLE001
                msg = str(e)
                if "AcceleratorError" in msg or "quota" in msg.lower():
                    print(f"[ab] {name}: 토큰#{ti} 쿼터소진 → 다음 토큰")
                    continue
                print(f"[ab] {name}: ✗ {msg[:110]}")
                break
        if not done:
            print(f"[ab] {name}: 실패 (스킵)")
    print("\n[ab] 완료")


if __name__ == "__main__":
    main()

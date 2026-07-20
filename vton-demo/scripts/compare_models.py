"""VTON 모델 A/B 비교: 같은 (모델 × 옷) 을 여러 Space 로 돌려 나란히 저장.

목적: IDM-VTON(현재) vs Leffa(Meta SOTA) vs Kolors 중 품질 최고를 눈으로 선정.
결과는 data/compare/{garment}__{model_key}.png 로 저장되고,
compare_sheet.jpg 컨택트 시트도 생성한다.

사용:
    python scripts/compare_models.py --garments garment_02 garment_05
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import settings  # noqa: E402

MODEL_IMG = settings.MODELS_DIR / "female_avg_01.jpg"
OUT_DIR = settings.ROOT / "data" / "compare"


def _conn(space: str, tries: int = 6):
    from gradio_client import Client
    last = None
    for _ in range(tries):
        try:
            return Client(space, token=settings.HF_TOKEN, verbose=False)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(4)
    raise RuntimeError(f"연결 실패: {last}")


def _retry(fn, tries: int = 4):
    """일시 500/503 재시도 래퍼."""
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            msg = str(e)
            if "quota" in msg.lower() or "No GPU" in msg:
                raise
            if any(c in msg for c in ("500", "502", "503", "timed out")) and i < tries - 1:
                time.sleep(6)
                continue
            raise
    raise last


def run_idm(model: Path, garment: Path) -> Path:
    from gradio_client import handle_file
    c = _conn(settings.VTON["space"])
    def call():
        human = {"background": handle_file(str(model)), "layers": [], "composite": None}
        r = c.predict(human, handle_file(str(garment)), "a photo of the clothing item",
                      True, False, 30, 42, api_name="/tryon")
        return Path(r[0] if isinstance(r, (list, tuple)) else r)
    return _retry(call)


def run_leffa(model: Path, garment: Path, garment_type: str = "upper_body") -> Path:
    from gradio_client import handle_file
    c = _conn("franciszzj/Leffa")
    def call():
        r = c.predict(
            handle_file(str(model)),     # src (사람)
            handle_file(str(garment)),   # ref (옷)
            False,                       # ref_acceleration (bool)
            30, 2.5, 42,
            "viton_hd", garment_type, False,  # vt_repaint (bool)
            api_name="/leffa_predict_vt")
        img = r[0]
        return Path(img["path"] if isinstance(img, dict) else img)
    return _retry(call)


def run_kolors(model: Path, garment: Path) -> Path:
    """Kolors 는 이름 없는 엔드포인트 → REST /call 로 시도 (best-effort)."""
    from gradio_client import handle_file
    c = _conn("Kwai-Kolors/Kolors-Virtual-Try-On")
    def call():
        # 여러 호출 방식 순차 시도
        for kwargs in ({"api_name": "/tryon"}, {"fn_index": 2}, {"fn_index": 3}):
            try:
                r = c.predict(handle_file(str(model)), handle_file(str(garment)), 0, True, **kwargs)
                img = r[0] if isinstance(r, (list, tuple)) else r
                return Path(img["path"] if isinstance(img, dict) else img)
            except Exception:  # noqa: BLE001
                continue
        raise RuntimeError("Kolors 호출 방식 모두 실패")
    return _retry(call, tries=2)


ENGINES = {
    "idm": ("IDM-VTON", run_idm),
    "leffa": ("Leffa", run_leffa),
    "kolors": ("Kolors", run_kolors),
}


def main() -> None:
    import shutil

    ap = argparse.ArgumentParser()
    ap.add_argument("--garments", nargs="+", required=True, help="예: garment_02 garment_05")
    ap.add_argument("--engines", nargs="+", default=["idm", "leffa", "kolors"])
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    for gstem in args.garments:
        gpath = settings.GARMENTS_DIR / f"{gstem}.jpg"
        if not gpath.exists():
            print(f"[compare] 옷 없음: {gpath}")
            continue
        for key in args.engines:
            name, fn = ENGINES[key]
            print(f"[compare] {name} · {gstem} 실행…", flush=True)
            t0 = time.time()
            try:
                produced = fn(MODEL_IMG, gpath)
                out = OUT_DIR / f"{gstem}__{key}.png"
                shutil.copyfile(produced, out)
                dt = time.time() - t0
                results[(gstem, key)] = out
                print(f"[compare]   ✓ {name} → {out.name} ({dt:.1f}s)", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[compare]   ✗ {name} 실패: {str(e)[:120]}", flush=True)

    # 컨택트 시트
    _build_sheet(args.garments, args.engines)


def _build_sheet(garments: list[str], engines: list[str]) -> None:
    from PIL import Image, ImageDraw

    cw, ch = 260, 360
    cols = len(engines) + 1  # 원본 옷 + 엔진들
    rows = len(garments)
    sheet = Image.new("RGB", (cw * cols, ch * rows + 30), "#0b0d11")
    d = ImageDraw.Draw(sheet)
    heads = ["원본 옷"] + [ENGINES[e][0] for e in engines]
    for j, hname in enumerate(heads):
        d.text((j * cw + 10, 8), hname, fill="#e8ecf3")

    def fit(p):
        im = Image.open(p).convert("RGB"); im.thumbnail((cw - 16, ch - 16)); return im

    for i, g in enumerate(garments):
        y = 30 + i * ch
        gp = settings.GARMENTS_DIR / f"{g}.jpg"
        if gp.exists():
            sheet.paste(fit(gp), (8, y + 8))
        for j, e in enumerate(engines):
            out = OUT_DIR / f"{g}__{e}.png"
            x = (j + 1) * cw
            if out.exists():
                sheet.paste(fit(out), (x + 8, y + 8))
            else:
                d.rectangle([x + 8, y + 8, x + cw - 8, y + ch - 8], outline="#e0555a")
                d.text((x + 20, y + ch // 2), "FAIL", fill="#e0555a")
    path = OUT_DIR / "compare_sheet.jpg"
    sheet.save(path, quality=92)
    print(f"[compare] 컨택트 시트 → {path}")


if __name__ == "__main__":
    main()

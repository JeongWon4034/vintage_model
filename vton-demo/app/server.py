"""결과 갤러리 웹서버 (FastAPI).

data/results/result.json 을 읽어 모델 × 옷 → 피팅 결과를 나란히 보여준다.
이미지는 models/ , data/garments/ , data/results/ 에서 직접 서빙.

실행:
    uvicorn app.server:app --reload --port 8000
    → http://localhost:8000
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

import settings

app = FastAPI(title="VTON Demo")

STATIC_DIR = Path(__file__).resolve().parent / "static"

_DIRS = {
    "model": settings.MODELS_DIR,
    "angle": settings.MODELS_DIR / "angles",
    "garment": settings.GARMENTS_DIR,
    "result": settings.RESULTS_DIR,
}


@app.get("/api/models")
def api_models() -> dict:
    """고정 모델 목록 + 각 모델의 각도 프레임(360° 스핀용)."""
    angles_dir = settings.MODELS_DIR / "angles"
    models = []
    for m in settings.list_images(settings.MODELS_DIR):
        frames = sorted(angles_dir.glob(f"{m.stem}_a*.jpg")) if angles_dir.exists() else []
        models.append({
            "name": m.name,
            "stem": m.stem,
            "frames": [f.name for f in frames],  # a000(정면)부터 각도순
        })
    return {"models": models}


@app.get("/api/masters")
def api_masters() -> dict:
    """정면 마스터 컷(고정 모델) + 메타데이터. 승인 리뷰용."""
    from PIL import Image

    angles_dir = settings.MODELS_DIR / "angles"
    out = []
    for m in settings.list_images(settings.MODELS_DIR):
        try:
            w, h = Image.open(m).size
        except Exception:  # noqa: BLE001
            w = h = 0
        frames = sorted(angles_dir.glob(f"{m.stem}_a*.jpg")) if angles_dir.exists() else []
        out.append({
            "name": m.name,
            "stem": m.stem,
            "width": w,
            "height": h,
            "angle_count": len(frames),
        })
    return {"masters": out}


@app.get("/api/results")
def api_results() -> dict:
    """result.json 을 그대로 반환 (없으면 빈 목록)."""
    if not settings.RESULT_JSON.exists():
        return {"generated_at": None, "space": settings.VTON["space"], "items": []}
    return json.loads(settings.RESULT_JSON.read_text(encoding="utf-8"))


@app.get("/img/{kind}/{name}")
def img(kind: str, name: str) -> FileResponse:
    """kind = model | garment | result 의 이미지 파일 서빙."""
    base = _DIRS.get(kind)
    if base is None:
        raise HTTPException(404, "unknown kind")
    # 경로 탈출 방지
    path = (base / name).resolve()
    if base.resolve() not in path.parents or not path.exists():
        raise HTTPException(404, "not found")
    return FileResponse(path)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/review", response_class=HTMLResponse)
def review() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "review.html").read_text(encoding="utf-8"))


# viewer.js 등 정적 자원
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

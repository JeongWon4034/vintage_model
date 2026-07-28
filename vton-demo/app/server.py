"""VTON 데모 API 서버 (FastAPI).

프론트엔드는 아래 엔드포인트만 알면 된다.

    GET /api/health                  상태 확인
    GET /api/model                   고정 모델 스펙(키/어깨/가슴) + 360° 프레임
    GET /api/models                  (레거시) 모델 목록 + 각도 프레임
    GET /api/masters                 정면 마스터 컷 + 메타 (승인 리뷰용)
    GET /api/fittings                피팅 결과 + 옷 실측 + 핏 판정  ← 메인
    GET /api/fittings/{garment_key}  단건 조회
    GET /api/length-series           같은 옷 총장별 비교 세트
    GET /api/results                 (레거시) result.json 원본

    GET /img/{kind}/{name}           kind = model | angle | garment | result | sample

실행:
    uvicorn app.server:app --reload --port 8000
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

import settings

app = FastAPI(title="VTON Demo API", version="1.0")

# 프론트엔드가 별도 포트(Vite 5173 / Next 3000 등)에서 뜨므로 CORS 허용.
# 배포 시에는 allow_origins 를 실제 도메인으로 좁힐 것.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
SAMPLES_DIR = settings.ROOT / "data" / "samples"
SPEC_PATH = settings.ROOT / "data" / "garment_specs.json"

_DIRS = {
    "model": settings.MODELS_DIR,
    "angle": settings.MODELS_DIR / "angles",
    "garment": settings.GARMENTS_DIR,
    "result": settings.RESULTS_DIR,
    "sample": SAMPLES_DIR,
}


def _load_result() -> dict:
    if not settings.RESULT_JSON.exists():
        return {"generated_at": None, "space": settings.VTON["space"], "items": []}
    return json.loads(settings.RESULT_JSON.read_text(encoding="utf-8"))


def _angle_frames(stem: str) -> list[str]:
    d = settings.MODELS_DIR / "angles"
    return [f.name for f in sorted(d.glob(f"{stem}_a*.jpg"))] if d.exists() else []


@app.get("/api/health")
def health() -> dict:
    data = _load_result()
    return {
        "ok": True,
        "space": settings.VTON["space"],
        "fittings": len(data.get("items", [])),
        "has_samples": SAMPLES_DIR.exists(),
    }


@app.get("/api/model")
def api_model() -> dict:
    """고정 모델 스펙 + 360° 스핀 프레임. 실측→px 환산의 기준이 되는 키를 포함."""
    data = _load_result()
    m = data.get("model") or {}
    name = m.get("name") or "female_hf_01.png"
    stem = Path(name).stem
    ms = settings.MODEL_SPEC
    frames = _angle_frames(stem)

    # 360° 프레임이 이 모델에 아직 없으면, 프레임을 가진 다른 모델을 알려준다
    # (프론트가 스핀 뷰어를 어떤 모델로 돌릴지 판단할 수 있게).
    spin_stem, spin_frames = (stem, frames) if frames else (None, [])
    if not frames:
        for other in settings.list_images(settings.MODELS_DIR):
            f = _angle_frames(other.stem)
            if f:
                spin_stem, spin_frames = other.stem, f
                break

    return {
        "name": name,
        "stem": stem,
        "height_cm": m.get("height_cm", ms.get("height_cm")),
        "shoulder_cm": m.get("shoulder_cm", ms.get("shoulder_cm")),
        "chest_cm": m.get("chest_cm", ms.get("chest_cm")),
        "image": f"/img/model/{name}",
        "frames": [f"/img/angle/{f}" for f in frames],
        "spin": {
            "stem": spin_stem,
            "same_as_fitting_model": bool(frames),
            "frames": [f"/img/angle/{f}" for f in spin_frames],
        },
    }


@app.get("/api/models")
def api_models() -> dict:
    """(레거시) 고정 모델 목록 + 각 모델의 각도 프레임. viewer.js 가 사용."""
    models = []
    for m in settings.list_images(settings.MODELS_DIR):
        models.append({
            "name": m.name,
            "stem": m.stem,
            "frames": _angle_frames(m.stem),   # a000(정면)부터 각도순
        })
    return {"models": models}


@app.get("/api/masters")
def api_masters() -> dict:
    """정면 마스터 컷(고정 모델) + 메타데이터. 승인 리뷰용."""
    from PIL import Image

    out = []
    for m in settings.list_images(settings.MODELS_DIR):
        try:
            w, h = Image.open(m).size
        except Exception:  # noqa: BLE001
            w = h = 0
        out.append({
            "name": m.name, "stem": m.stem, "width": w, "height": h,
            "angle_count": len(_angle_frames(m.stem)),
        })
    return {"masters": out}


def _decorate(it: dict) -> dict:
    """프론트가 그대로 렌더할 수 있게 이미지 URL 을 붙인다."""
    key = it.get("garment_key", "")
    out = dict(it)
    out["images"] = {
        "garment": f"/img/garment/{it['garment']}",
        "result": f"/img/result/{it['result']}",
        # 저장소만 받아도 보이는 경량 샘플 (원본은 git 제외)
        "garment_sample": f"/img/sample/{key}__garment.jpg",
        "result_sample": f"/img/sample/{key}__result.jpg",
    }
    return out


@app.get("/api/fittings")
def api_fittings() -> dict:
    """피팅 결과 + 옷 실측 + 핏 판정. 프론트 메인 엔드포인트."""
    data = _load_result()
    return {
        "generated_at": data.get("generated_at"),
        "space": data.get("space"),
        "model": data.get("model"),
        "count": len(data.get("items", [])),
        "items": [_decorate(i) for i in data.get("items", [])],
    }


@app.get("/api/fittings/{garment_key}")
def api_fitting_one(garment_key: str) -> dict:
    for it in _load_result().get("items", []):
        if it.get("garment_key") == garment_key:
            return _decorate(it)
    raise HTTPException(404, f"unknown garment_key: {garment_key}")


@app.get("/api/length-series")
def api_length_series() -> dict:
    """같은 옷에 총장(cm)만 바꿔 넣은 비교 세트."""
    ls = _load_result().get("length_series") or {"garment_key": None, "frames": []}
    frames = [{
        "length_cm": f["length_cm"],
        "image": f"/img/result/{f['result']}",
        "sample": f"/img/sample/{f['sample']}",
    } for f in ls.get("frames", [])]
    return {"garment_key": ls.get("garment_key"), "frames": frames}


@app.get("/api/garment-specs")
def api_garment_specs() -> dict:
    """옷 실측 원본(크롤/추정 구분 포함)."""
    if not SPEC_PATH.exists():
        return {"garments": {}}
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


@app.get("/api/results")
def api_results() -> dict:
    """(레거시) result.json 을 그대로 반환."""
    return _load_result()


@app.get("/img/{kind}/{name}")
def img(kind: str, name: str) -> FileResponse:
    """kind = model | angle | garment | result | sample 의 이미지 파일 서빙."""
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

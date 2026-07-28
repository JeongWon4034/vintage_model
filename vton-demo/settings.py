"""공통 설정 로더.

config.yaml + .env 를 읽어 프로젝트 전역에서 쓰는 경로/옵션을 노출한다.
모든 스크립트는 프로젝트 루트에서 실행된다고 가정한다 (settings.ROOT 기준 절대경로 사용).
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent

# .env 로드 (있으면)
load_dotenv(ROOT / ".env")

with open(ROOT / "config.yaml", "r", encoding="utf-8") as f:
    CONFIG: dict = yaml.safe_load(f)

# --- 자주 쓰는 값 단축 접근 ---
HF_TOKEN: str | None = os.environ.get("HF_TOKEN") or None

# 여러 토큰 로테이션용 (HF_TOKENS=tok1,tok2,...). 없으면 HF_TOKEN 하나만.
def _parse_tokens() -> list[str]:
    raw = os.environ.get("HF_TOKENS", "") or ""
    toks = [t.strip() for t in raw.split(",") if t.strip()]
    if HF_TOKEN and HF_TOKEN not in toks:
        toks.insert(0, HF_TOKEN)
    return toks

HF_TOKENS: list[str] = _parse_tokens()

VTON = CONFIG["vton"]
MODEL_SPEC = CONFIG.get("model_spec", {"height_cm": 168})
CRAWLER = CONFIG["crawler"]
PREPROCESS = CONFIG["preprocess"]

_paths = CONFIG["paths"]
MODELS_DIR = ROOT / _paths["models_dir"]
GARMENTS_DIR = ROOT / _paths["garments_dir"]
RESULTS_DIR = ROOT / _paths["results_dir"]

RESULT_JSON = RESULTS_DIR / "result.json"

# 이미지 확장자 화이트리스트
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def ensure_dirs() -> None:
    """데이터 디렉터리들을 생성한다."""
    for d in (MODELS_DIR, GARMENTS_DIR, RESULTS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def list_images(directory: Path) -> list[Path]:
    """디렉터리 내 이미지 파일을 정렬해서 반환."""
    if not directory.exists():
        return []
    return sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )

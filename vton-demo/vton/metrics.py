"""모델 사진 계측 — 실루엣에서 머리/발/어깨 위치와 px_per_cm 를 구한다.

실측(cm) 기반으로 마스크 길이를 만들려면, 사진 속 1cm 가 몇 px 인지 알아야 한다.
모델의 실제 키(cm)를 알고 있으면  px_per_cm = (발 y − 머리 y) / 키  로 환산된다.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path

import cv2
import numpy as np


@dataclass
class ModelMetrics:
    width: int
    height: int
    head_y: int          # 머리 최상단 y
    feet_y: int          # 발 최하단 y
    shoulder_y: int      # 어깨선 y (옷 길이 측정 기준점)
    person_px: int       # 머리~발 픽셀 높이
    height_cm: float     # 실제 키
    px_per_cm: float

    def cm_to_px(self, cm: float) -> int:
        return int(round(cm * self.px_per_cm))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["px_per_cm"] = round(self.px_per_cm, 3)
        return d


def person_mask(img_bgr: np.ndarray) -> np.ndarray:
    """GrabCut 으로 인물 전경 마스크(0/255)를 뽑는다. 배경이 단색 스튜디오라 잘 동작."""
    h, w = img_bgr.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    # 인물이 중앙에 세로로 서 있다고 가정한 초기 사각형
    rect = (int(w * 0.18), int(h * 0.01), int(w * 0.64), int(h * 0.98))
    cv2.grabCut(img_bgr, mask, rect, bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype("uint8")
    # 잡음 제거 + 구멍 메우기
    k = np.ones((7, 7), np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, k, iterations=2)
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, k, iterations=3)
    # 가장 큰 연결요소만 남김 (그림자/잡티 제거)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fg, 8)
    if n > 1:
        big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        fg = np.where(lab == big, 255, 0).astype("uint8")
    return fg


def row_widths(fg: np.ndarray) -> np.ndarray:
    """행마다 전경 픽셀 폭(가장 왼쪽~오른쪽)을 계산."""
    out = np.zeros(fg.shape[0], np.int32)
    for y in range(fg.shape[0]):
        xs = np.flatnonzero(fg[y])
        if xs.size:
            out[y] = xs[-1] - xs[0] + 1
    return out


def analyze(image_path: Path, height_cm: float = 168.0) -> tuple[ModelMetrics, np.ndarray]:
    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(image_path)
    h, w = img.shape[:2]
    fg = person_mask(img)
    widths = row_widths(fg)
    rows = np.flatnonzero(widths > 0)
    if rows.size == 0:
        raise RuntimeError("인물 실루엣을 찾지 못했습니다")
    head_y, feet_y = int(rows[0]), int(rows[-1])
    person_px = feet_y - head_y

    # 어깨선: 머리 구간의 최대 폭 대비 폭이 급증하는 첫 지점
    head_band = widths[head_y: head_y + max(1, int(person_px * 0.10))]
    head_w = int(head_band.max()) if head_band.size else 1
    shoulder_y = head_y + int(person_px * 0.16)  # 기본값(대략 어깨 위치)
    for y in range(head_y + int(person_px * 0.06), head_y + int(person_px * 0.30)):
        if widths[y] > head_w * 1.55:
            shoulder_y = y
            break

    m = ModelMetrics(
        width=w, height=h, head_y=head_y, feet_y=feet_y, shoulder_y=shoulder_y,
        person_px=person_px, height_cm=height_cm, px_per_cm=person_px / height_cm,
    )
    return m, fg


def debug_overlay(image_path: Path, m: ModelMetrics, fg: np.ndarray, out: Path) -> None:
    """계측 결과를 선으로 그려 검증용 이미지를 저장."""
    img = cv2.imread(str(image_path))
    tint = img.copy()
    tint[fg > 0] = (0.65 * tint[fg > 0] + 0.35 * np.array([0, 180, 255])).astype("uint8")
    img = tint
    for y, color, label in [
        (m.head_y, (0, 0, 255), "head"),
        (m.shoulder_y, (0, 255, 0), "shoulder"),
        (m.feet_y, (255, 0, 0), "feet"),
    ]:
        cv2.line(img, (0, y), (m.width, y), color, 5)
        cv2.putText(img, label, (12, max(30, y - 12)), cv2.FONT_HERSHEY_SIMPLEX, 1.4, color, 4)
    cv2.putText(img, f"{m.px_per_cm:.2f} px/cm  ({m.height_cm:.0f}cm)",
                (12, m.height - 24), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (30, 30, 30), 4)
    cv2.imwrite(str(out), img)


if __name__ == "__main__":
    import argparse
    import json
    import settings

    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="female_hf_01.png")
    ap.add_argument("--height", type=float, default=168.0)
    ap.add_argument("--debug", default=None, help="검증 오버레이 저장 경로")
    a = ap.parse_args()

    p = settings.MODELS_DIR / a.model
    m, fg = analyze(p, a.height)
    print(json.dumps(m.to_dict(), ensure_ascii=False, indent=2))
    print(f"  → 총장 68cm = {m.cm_to_px(68)}px,  55cm = {m.cm_to_px(55)}px")
    if a.debug:
        debug_overlay(p, m, fg, Path(a.debug))
        print(f"  debug -> {a.debug}")

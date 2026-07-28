"""실측(총장) 기반 수동 마스크 생성.

IDM-VTON 은 auto-mask 를 끄면(is_checked=False) ImageEditor 의 layers[0] 알파를
"옷을 그려 넣을 영역"으로 쓴다. 그래서 어깨선부터 총장(cm)만큼 내려오는 영역을
직접 칠해서 넘기면, 원본 모델이 입고 있던 옷의 밑단과 무관하게 길이를 제어할 수 있다.
(기존 auto-mask 는 원본 티셔츠 밑단=허리선에서 잘려서 늘 "바지에 넣은" 것처럼 보였다.)
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .metrics import ModelMetrics


def build_mask(
    fg: np.ndarray,
    m: ModelMetrics,
    length_cm: float,
    *,
    include_arms: bool = True,
    widen_ratio: float = 0.06,
    neck_drop_cm: float = 3.0,
) -> np.ndarray:
    """어깨선 아래 length_cm 까지 덮는 이진 마스크(0/255)를 만든다.

    widen_ratio: 몸 실루엣보다 좌우로 얼마나 더 넓게 잡을지(오버핏 여유).
    neck_drop_cm: 목/카라가 그려질 여유로 어깨선보다 살짝 위에서 시작.
    """
    h, w = fg.shape[:2]
    top = max(0, m.shoulder_y - m.cm_to_px(neck_drop_cm))
    bottom = min(h - 1, m.shoulder_y + m.cm_to_px(length_cm))

    mask = np.zeros((h, w), np.uint8)
    body_w = 0
    for y in range(top, bottom + 1):
        xs = np.flatnonzero(fg[y])
        if xs.size == 0:
            continue
        x0, x1 = int(xs[0]), int(xs[-1])
        body_w = max(body_w, x1 - x0)
        pad = int((x1 - x0) * widen_ratio)
        mask[y, max(0, x0 - pad): min(w, x1 + pad + 1)] = 255

    if not include_arms:
        # 몸통 중앙 60% 만 남겨 팔을 제외
        cx = w // 2
        half = int(body_w * 0.30)
        side = np.zeros_like(mask)
        side[:, max(0, cx - half): min(w, cx + half)] = 255
        mask = cv2.bitwise_and(mask, side)

    # 경계 살짝 매끄럽게
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=2)
    return mask


def save_layer(mask: np.ndarray, out: Path) -> Path:
    """IDM-VTON 이 읽는 마스크 레이어로 저장.

    주의: Space 쪽 pil_to_binary_mask() 는 RGBA 를 "L"(그레이스케일)로 변환하며
    알파 채널을 버린다. 따라서 마스크는 반드시 **RGB 채널**에 담아야 한다.
    (알파에만 넣으면 RGB 가 전부 흰색으로 읽혀 화면 전체가 마스크가 된다.)
    """
    h, w = mask.shape[:2]
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., 0] = mask           # B
    rgba[..., 1] = mask           # G
    rgba[..., 2] = mask           # R  → 칠한 곳만 흰색, 나머지 검정
    rgba[..., 3] = 255            # 알파는 불투명 고정
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), rgba)
    return out


def save_preview(image_path: Path, mask: np.ndarray, out: Path) -> Path:
    """원본 위에 마스크를 반투명으로 얹은 검증용 이미지."""
    img = cv2.imread(str(image_path))
    overlay = img.copy()
    overlay[mask > 0] = (0.45 * overlay[mask > 0] + 0.55 * np.array([255, 0, 200])).astype("uint8")
    cv2.imwrite(str(out), overlay)
    return out

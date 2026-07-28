"""핏 판정 — 옷 실측 vs 모델 치수를 비교해 오버핏/정핏/타이트 라벨을 만든다.

판정 기준(여성 상의 기준, 어깨/가슴 여유율):
  어깨 여유 = 옷어깨 − 모델어깨
  가슴 여유 = 옷가슴(반폭×2) − 모델가슴둘레
둘 중 더 강한 신호를 채택한다.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Garment:
    name: str
    length_cm: float | None = None      # 총장
    shoulder_cm: float | None = None    # 어깨 단면
    chest_cm: float | None = None       # 가슴 단면(반폭)
    source: str = "manual"              # manual | crawled

    @property
    def chest_round_cm(self) -> float | None:
        """가슴 단면(반폭) → 둘레 환산."""
        return self.chest_cm * 2 if self.chest_cm is not None else None


# 어깨 여유(cm) 기준
SHOULDER_BANDS = [
    (-99, -1.5, "타이트", "어깨가 끼는 편"),
    (-1.5, 2.5, "정핏", "어깨가 맞음"),
    (2.5, 6.0, "세미오버", "어깨가 살짝 여유"),
    (6.0, 99, "오버핏", "어깨가 많이 떨어짐"),
]

# 가슴 둘레 여유(cm) 기준
CHEST_BANDS = [
    (-99, 2, "타이트", "품이 붙음"),
    (2, 12, "정핏", "품이 적당"),
    (12, 24, "세미오버", "품에 여유"),
    (24, 99, "오버핏", "품이 매우 넉넉"),
]

RANK = {"타이트": 0, "정핏": 1, "세미오버": 2, "오버핏": 3}


def _band(value: float, bands) -> tuple[str, str]:
    for lo, hi, label, note in bands:
        if lo <= value < hi:
            return label, note
    return "정핏", ""


def judge(g: Garment, model_shoulder_cm: float, model_chest_cm: float) -> dict:
    """핏 라벨 + 근거를 반환. 실측이 없으면 label=None."""
    signals: list[tuple[str, str, float]] = []

    if g.shoulder_cm is not None:
        d = g.shoulder_cm - model_shoulder_cm
        label, note = _band(d, SHOULDER_BANDS)
        signals.append((label, f"어깨 {d:+.1f}cm · {note}", d))

    if g.chest_round_cm is not None:
        d = g.chest_round_cm - model_chest_cm
        label, note = _band(d, CHEST_BANDS)
        signals.append((label, f"가슴둘레 {d:+.1f}cm · {note}", d))

    if not signals:
        return {"label": None, "reasons": [], "length_note": _length_note(g)}

    # 더 극단적인(랭크가 중앙에서 먼) 신호를 채택
    label = max(signals, key=lambda s: abs(RANK[s[0]] - 1))[0]
    return {
        "label": label,
        "reasons": [s[1] for s in signals],
        "length_note": _length_note(g),
        "source": g.source,
    }


def _length_note(g: Garment) -> str | None:
    """총장으로 착장 위치를 설명 (168cm 여성 기준 대략적)."""
    if g.length_cm is None:
        return None
    L = g.length_cm
    if L < 50:
        return "크롭 — 허리 위"
    if L < 60:
        return "숏 — 허리선"
    if L < 68:
        return "베이직 — 골반 위"
    if L < 78:
        return "롱 — 엉덩이 덮음"
    return "맥시 — 허벅지까지"

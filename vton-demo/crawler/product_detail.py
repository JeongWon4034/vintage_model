"""상품 상세페이지에서 실측(총장/어깨/가슴/소매)을 긁어온다.

fruitsfamily 는 SPA 라 Playwright 로 렌더 후 본문 텍스트를 뽑고,
판매자가 자유 서술한 실측 표기를 정규식으로 파싱한다.

    python -m crawler.product_detail --id 4619406 --dump
    python -m crawler.product_detail --id 4619406 --key E_red_suede
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import settings

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

URL_PATTERNS = [
    "https://fruitsfamily.com/product/{id}",
    "https://fruitsfamily.com/products/{id}",
    "https://fruitsfamily.com/item/{id}",
]

# 판매자 표기 흔들림 흡수: "총장 68", "총장:68cm", "기장 68 cm", "총 장 68"
_NUM = r"(\d{1,3}(?:\.\d)?)"
FIELDS = {
    "length_cm":   [r"총\s*장", r"기\s*장", r"총장\(길이\)"],
    "shoulder_cm": [r"어\s*깨", r"견\s*장", r"어깨\s*단면"],
    "chest_cm":    [r"가\s*슴", r"품", r"가슴\s*단면", r"흉\s*위"],
    "sleeve_cm":   [r"소\s*매", r"암\s*홀\s*소매", r"소매\s*길이"],
}


def fetch_text(pid: str, headful: bool = False) -> tuple[str, str]:
    """상품 페이지를 렌더해 (사용된 URL, 본문 텍스트) 반환."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headful)
        ctx = browser.new_context(user_agent=UA, viewport={"width": 1400, "height": 1200})
        page = ctx.new_page()
        for pat in URL_PATTERNS:
            url = pat.format(id=pid)
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
            except Exception:
                continue
            time.sleep(3)
            # 더보기/펼치기 버튼이 있으면 눌러 본문 확장
            for sel in ["text=더보기", "text=더 보기", "button:has-text('더보기')"]:
                try:
                    page.click(sel, timeout=1200)
                    time.sleep(1)
                except Exception:
                    pass
            page.mouse.wheel(0, 3000)
            time.sleep(1.5)
            text = page.evaluate("() => document.body.innerText")
            status = resp.status if resp else 0
            if text and len(text) > 200 and status < 400:
                browser.close()
                return url, text
        browser.close()
    return "", ""


# 항목별 상식 범위 (cm). 신발사이즈·가격·연도 같은 숫자 오탐을 막는다.
RANGES = {
    "length_cm": (35, 130),
    "shoulder_cm": (28, 70),
    "chest_cm": (30, 80),
    "sleeve_cm": (25, 80),
}


def parse_measurements(text: str) -> dict:
    """본문에서 실측 숫자를 뽑는다. 못 찾은 항목은 None.

    오탐 방지:
      - 항목별 상식 범위를 벗어난 값은 버린다
      - 키워드와 숫자가 멀리 떨어진 경우는 무시 (사이 15자 이내)
      - 'cm' 단위가 붙은 매치를 우선 채택
    """
    out: dict[str, float | None] = {}
    flat = re.sub(r"[ \t]+", " ", text)
    lo_hi = RANGES
    for field, keys in FIELDS.items():
        with_unit: float | None = None
        without_unit: float | None = None
        for k in keys:
            for m in re.finditer(
                rf"{k}[^0-9\n]{{0,15}}?{_NUM}\s*(cm|CM|센치|센티)?", flat
            ):
                try:
                    v = float(m.group(1))
                except ValueError:
                    continue
                lo, hi = lo_hi[field]
                if not (lo <= v <= hi):
                    continue
                if m.group(2):
                    with_unit = v
                    break
                if without_unit is None:
                    without_unit = v
            if with_unit is not None:
                break
        out[field] = with_unit if with_unit is not None else without_unit
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="상품 ID")
    ap.add_argument("--key", default=None, help="garment_specs.json 에 저장할 키")
    ap.add_argument("--label", default=None)
    ap.add_argument("--dump", action="store_true", help="본문 텍스트 출력(파싱 디버깅)")
    ap.add_argument("--headful", action="store_true")
    a = ap.parse_args()

    url, text = fetch_text(a.id, a.headful)
    if not text:
        print(f"[detail] ✗ 상세페이지를 열지 못했습니다 (id={a.id}). URL 패턴이 바뀌었을 수 있음")
        return
    print(f"[detail] URL: {url}  (본문 {len(text)}자)")

    if a.dump:
        print("-" * 60)
        print(text[:3000])
        print("-" * 60)

    meas = parse_measurements(text)
    print("[detail] 파싱 결과:", json.dumps(meas, ensure_ascii=False))

    if a.key:
        p = settings.ROOT / "data/garment_specs.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        entry = data["garments"].get(a.key, {})
        for k, v in meas.items():
            if v is not None:
                entry[k] = v
        if a.label:
            entry["label"] = a.label
        entry["source"] = "crawled" if any(v is not None for v in meas.values()) else entry.get("source", "manual_estimate")
        entry["source_url"] = url
        data["garments"][a.key] = entry
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[detail] ✓ garment_specs.json 갱신 → {a.key} ({entry['source']})")


if __name__ == "__main__":
    main()

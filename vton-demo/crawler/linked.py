"""상품 링크 + 이미지 + 실측을 한 세트로 크롤한다.

fruitsfamily 상품 카드는 <a href> 가 아니라 JS 라우팅이라, 카드를 클릭해 상세 URL 로
이동한 뒤 본문에서 실측을 파싱하고 뒤로 돌아오는 방식을 쓴다.

이미지 CDN 은 경로에 resized@width620 이 박혀 있는데, 이 숫자를 키우면
더 큰 원본을 받을 수 있다 (VTON 입력 디테일이 좋아진다).

    python -m crawler.linked --q "스웨이드 자켓" --count 8 --width 1200
"""
from __future__ import annotations

import argparse
import io
import json
import re
import time
from pathlib import Path
from urllib.parse import quote

import httpx
from PIL import Image

import settings
from crawler.product_detail import parse_measurements

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

OUT_DIR = settings.ROOT / "data" / "linked"
SPEC_PATH = settings.ROOT / "data" / "garment_specs.json"


def upscale_url(url: str, width: int) -> str:
    """resized@width620 → resized@width{width} 로 교체 (인코딩 형태 모두 대응)."""
    url = re.sub(r"resized%40width\d+", f"resized%40width{width}", url)
    url = re.sub(r"resized@width\d+", f"resized@width{width}", url)
    return url


def crawl(keyword: str, count: int, width: int, headful: bool = False,
          keyword_filter: str = "") -> list[dict]:
    from playwright.sync_api import sync_playwright

    search = f"https://fruitsfamily.com/search?q={quote(keyword)}"
    results: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headful)
        ctx = browser.new_context(user_agent=UA, viewport={"width": 1400, "height": 1100})
        page = ctx.new_page()
        print(f"[linked] 검색: {search}")
        page.goto(search, wait_until="domcontentloaded", timeout=60000)
        time.sleep(4)
        for _ in range(3):
            page.mouse.wheel(0, 2500)
            time.sleep(1.2)

        # 상품 카드는 a.ProductPreview 앵커. href 를 직접 뽑아 상세로 이동한다.
        cards = page.evaluate("""() => Array.from(document.querySelectorAll('a.ProductPreview'))
            .map(a => {
                const img = a.querySelector('img');
                return {href: a.getAttribute('href'),
                        title: (img && img.alt) || '',
                        img: (img && img.src) || ''};
            }).filter(c => c.href && c.img)""")
        print(f"[linked] 카드 {len(cards)}개 발견")

        if keyword_filter:
            kws = [k for k in keyword_filter.split() if k]
            cards = [c for c in cards if any(k in c["title"] for k in kws)]
            print(f"[linked] 제목 필터('{keyword_filter}') 적용 후 {len(cards)}개")

        for i, card in enumerate(cards[:count], 1):
            url = card["href"]
            if url.startswith("/"):
                url = "https://fruitsfamily.com" + url
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(2.5)
                for sel in ["text=더보기", "button:has-text('더보기')"]:
                    try:
                        page.click(sel, timeout=1000); time.sleep(0.8)
                    except Exception:
                        pass
                page.mouse.wheel(0, 2200); time.sleep(1.2)
                text = page.evaluate("() => document.body.innerText")
                meas = parse_measurements(text)
                results.append({
                    "url": url, "title": card["title"].strip(),
                    "image": upscale_url(card["img"], width),
                    "measurements": meas,
                    "text_len": len(text),
                })
                got = {k: v for k, v in meas.items() if v}
                print(f"[linked] {i}. {card['title'][:32]:<32} {got if got else '실측 없음'}")
            except Exception as e:  # noqa: BLE001
                print(f"[linked] {i}. 실패: {str(e)[:70]}")
            time.sleep(settings.CRAWLER.get("request_delay_sec", 1.0))
        browser.close()
    return results


def download(items: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": UA, "Referer": "https://fruitsfamily.com/"}
    with httpx.Client(headers=headers, timeout=30, follow_redirects=True) as c:
        for i, it in enumerate(items, 1):
            try:
                r = c.get(it["image"]); r.raise_for_status()
                im = Image.open(io.BytesIO(r.content)).convert("RGB")
                p = OUT_DIR / f"linked_{i:02d}.jpg"
                im.save(p, "JPEG", quality=94)
                it["file"] = str(p.relative_to(settings.ROOT))
                it["size"] = list(im.size)
                print(f"[linked]   ↓ {p.name} {im.size}")
            except Exception as e:  # noqa: BLE001
                print(f"[linked]   ↓ 실패: {str(e)[:60]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", required=True, help="검색 키워드")
    ap.add_argument("--count", type=int, default=8)
    ap.add_argument("--width", type=int, default=620,
                    help="CDN 이미지 요청 폭. 620 외 값은 403 이므로 사실상 620 고정")
    ap.add_argument("--filter", default="", help="상품 제목에 포함돼야 하는 단어(공백 구분, OR)")
    ap.add_argument("--headful", action="store_true")
    a = ap.parse_args()

    items = crawl(a.q, a.count, a.width, a.headful, a.filter)
    download(items)
    out = OUT_DIR / "linked.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for i in items if any(v for v in i["measurements"].values()))
    print(f"\n[linked] 완료 · {len(items)}개 중 실측 파싱 성공 {ok}개 → {out}")


if __name__ == "__main__":
    main()

"""fruitsfamily.com 상품 이미지 크롤러.

fruitsfamily 는 React SPA (Apollo GraphQL) 이고 상품 API 는 인증이 필요하다.
따라서 정적 HTML 파싱 대신 **Playwright 로 페이지를 렌더링**한 뒤,
DOM 에 실제로 로드된 image.production.fruitsfamily.com 이미지 URL 을 긁어온다.

robots.txt 확인: User-agent: * / Disallow: (전체 허용). 그래도 예의상 rate-limit 을 둔다.

사용:
    python -m crawler.fruitsfamily --count 5
    python -m crawler.fruitsfamily --url "https://fruitsfamily.com/search?q=..." --count 10
    python -m crawler.fruitsfamily --headful      # 브라우저 창 띄워서 디버깅

크롤러 없이 쓰고 싶으면: data/garments/ 에 직접 옷 이미지를 넣으면 파이프라인이 그대로 사용한다.
"""
from __future__ import annotations

import argparse
import io
import time
from pathlib import Path
from urllib.parse import urlparse, urljoin

import httpx
from PIL import Image

import settings

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)


def _collect_image_urls(page, image_host: str) -> list[dict]:
    """렌더된 DOM 에서 상품 이미지 CDN URL 을 크기와 함께 수집한다."""
    items: list[dict] = page.evaluate(
        """(host) => {
            const out = new Map();
            const add = (u, w, h) => {
                if (!u || !u.includes(host)) return;
                if (!out.has(u)) out.set(u, {url: u, w: w || 0, h: h || 0});
            };
            document.querySelectorAll('img').forEach(img => {
                add(img.src, img.naturalWidth, img.naturalHeight);
                if (img.srcset) {
                    const cands = img.srcset.split(',')
                        .map(s => s.trim().split(' ')[0]).filter(u => u.includes(host));
                    if (cands.length) add(cands[cands.length - 1], img.naturalWidth, img.naturalHeight);
                }
            });
            document.querySelectorAll('*').forEach(el => {
                const bg = getComputedStyle(el).backgroundImage;
                if (bg && bg.includes(host)) {
                    const m = bg.match(/url\\(["']?(.*?)["']?\\)/);
                    if (m && m[1]) add(m[1], 0, 0);
                }
            });
            return Array.from(out.values());
        }""",
        image_host,
    )
    return items


def _filter_items(items: list[dict], cfg: dict) -> list[dict]:
    """경로 포함/제외 규칙과 세로형 우선 규칙을 적용한다."""
    include = cfg.get("image_path_include")
    if isinstance(include, str):
        include = [include]
    exclude = cfg.get("image_path_exclude", [])
    out = []
    for it in items:
        path = urlparse(it["url"]).path
        if include and not any(inc in path for inc in include):
            continue
        if any(x in path for x in exclude):
            continue
        out.append(it)
    if cfg.get("prefer_portrait"):
        # 세로형(상품컷)을 앞으로 정렬 (크기 정보 없는 것은 중립)
        out.sort(key=lambda i: 0 if (i["h"] and i["w"] and i["h"] >= i["w"]) else 1)
    return out


def _dedupe(items: list[dict]) -> list[dict]:
    """쿼리스트링을 무시하고 경로 기준으로 중복 제거 (같은 상품의 리사이즈 변형 제거)."""
    seen: set[str] = set()
    result: list[dict] = []
    for it in items:
        key = urlparse(it["url"]).path
        if key not in seen:
            seen.add(key)
            result.append(it)
    return result


def _scroll_to_load(page, rounds: int = 6, delay: float = 1.0) -> None:
    """lazy-load 이미지를 트리거하기 위해 스크롤을 반복한다."""
    for _ in range(rounds):
        page.mouse.wheel(0, 4000)
        time.sleep(delay)


def crawl(count: int | None = None, url: str | None = None, headful: bool = False) -> list[Path]:
    from playwright.sync_api import sync_playwright  # 지연 import (미설치 시 에러 메시지 명확)

    settings.ensure_dirs()
    cfg = settings.CRAWLER
    count = count or cfg["default_count"]
    start_urls = [url] if url else cfg["start_urls"]
    image_host = cfg["image_host"]
    min_width = cfg["min_width"]
    delay = cfg["request_delay_sec"]

    print(f"[crawl] 시작 · 목표 {count}장 · 대상 {start_urls}")

    collected: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headful)
        ctx = browser.new_context(user_agent=UA, viewport={"width": 1400, "height": 1000})
        page = ctx.new_page()
        for start in start_urls:
            print(f"[crawl] 렌더링: {start}")
            try:
                # networkidle 은 SPA 에서 잘 안 걸리므로 domcontentloaded 후 수동 대기
                page.goto(start, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                print(f"[crawl] goto 경고({start}): {e} — 계속 진행")
            time.sleep(3)
            _scroll_to_load(page, rounds=8, delay=delay)
            items = _collect_image_urls(page, image_host)
            print(f"[crawl]   → {len(items)}개 이미지 URL 발견")
            collected.extend(items)
        browser.close()

    items = _filter_items(_dedupe(collected), cfg)
    print(f"[crawl] 필터+dedupe 후 {len(items)}개. 다운로드 시작 (min_width={min_width}px)")

    saved: list[Path] = []
    headers = {"User-Agent": UA, "Referer": "https://fruitsfamily.com/"}
    with httpx.Client(headers=headers, timeout=30, follow_redirects=True) as client:
        for it in items:
            u = it["url"]
            if len(saved) >= count:
                break
            try:
                r = client.get(u)
                r.raise_for_status()
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
            except Exception as e:
                print(f"[crawl]   skip ({e}): {u[:80]}")
                continue
            if img.width < min_width:
                continue  # 썸네일/아이콘 제외
            if cfg.get("garment_only"):
                from vton.preprocess import has_person
                if has_person(img):
                    print(f"[crawl]   skip (착용샷): {u[:70]}")
                    continue
            idx = len(saved) + 1
            out = settings.GARMENTS_DIR / f"garment_{idx:02d}.jpg"
            img.save(out, "JPEG", quality=92)
            saved.append(out)
            print(f"[crawl]   저장 {out.name}  ({img.width}x{img.height})")
            time.sleep(delay)

    if not saved:
        print(
            "[crawl] ⚠️  다운로드된 이미지가 없습니다.\n"
            "  - 사이트 구조가 바뀌었거나 렌더링이 덜 됐을 수 있습니다. --headful 로 확인해보세요.\n"
            "  - 또는 data/garments/ 에 옷 이미지를 직접 넣고 파이프라인만 돌려도 됩니다."
        )
    else:
        print(f"[crawl] 완료 · {len(saved)}장 저장 → {settings.GARMENTS_DIR}")
    return saved


def main() -> None:
    ap = argparse.ArgumentParser(description="fruitsfamily 상품 이미지 크롤러")
    ap.add_argument("--count", type=int, default=None, help="다운로드할 이미지 수")
    ap.add_argument("--url", type=str, default=None, help="크롤 시작 URL 오버라이드")
    ap.add_argument("--headful", action="store_true", help="브라우저 창 표시(디버깅)")
    args = ap.parse_args()
    crawl(count=args.count, url=args.url, headful=args.headful)


if __name__ == "__main__":
    main()

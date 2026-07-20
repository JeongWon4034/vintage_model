"""IDM-VTON HF Space 클라이언트.

gradio_client 로 오픈 diffusion VTON 모델(IDM-VTON)을 호출한다.
로컬 GPU 없이 HF 인프라에서 '실제 모델'을 구동하는 방식.

Space API 가 바뀌었는지 확인하려면:
    python -m vton.client --inspect
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import settings


def get_client(space: str, conn_retries: int = 6, wait: float = 5.0):
    """Space 연결. config-fetch 가 자주 실패해서(슬립/재시작) 재시도한다."""
    import time

    from gradio_client import Client

    last = None
    for i in range(conn_retries):
        try:
            # gradio_client >= 2.x 는 token 인자 사용 (구버전 hf_token 아님)
            return Client(space, token=settings.HF_TOKEN, verbose=False)
        except Exception as e:  # noqa: BLE001
            last = e
            if i < conn_retries - 1:
                time.sleep(wait)
    raise RuntimeError(f"연결 실패({conn_retries}회): {last}")


def _predict_idm(client, model_path: Path, garment_path: Path):
    """IDM-VTON(yisol) 계열 /tryon 시그니처로 호출.

    시그니처: start_tryon(dict, garm_img, garment_des, is_checked,
                          is_checked_crop, denoise_steps, seed)
    반환: (결과이미지경로, 마스크이미지경로)
    """
    from gradio_client import handle_file

    v = settings.VTON
    human = {"background": handle_file(str(model_path)), "layers": [], "composite": None}
    result = client.predict(
        human,
        handle_file(str(garment_path)),
        "a photo of the clothing item",   # garment_des
        v["auto_mask"],                    # is_checked (auto masking)
        v["crop"],                         # is_checked_crop
        v["denoise_steps"],                # denoise_steps
        v["seed"],                         # seed
        api_name=v["api_name"],
    )
    # result 는 (output_path, masked_path) 튜플 또는 단일 경로
    if isinstance(result, (list, tuple)):
        return result[0]
    return result


def tryon(model_path: Path, garment_path: Path, out_path: Path) -> Path:
    """모델 이미지에 옷을 입혀 out_path 로 저장. 성공 시 out_path 반환, 실패 시 예외."""
    import time

    spaces = [settings.VTON["space"], *settings.VTON.get("fallbacks", [])]
    predict_retries = 4          # ZeroGPU 파일 프록시 500 등 일시 오류 재시도
    last_err: Exception | None = None
    for space in spaces:
        try:
            print(f"[vton] {space} 호출: {model_path.name} × {garment_path.name}")
            client = get_client(space)
        except Exception as e:  # noqa: BLE001 — 연결 실패 시 다음 Space
            last_err = e
            print(f"[vton]   ✗ {space} 연결 실패: {str(e)[:120]}")
            continue

        for attempt in range(1, predict_retries + 1):
            try:
                produced = Path(_predict_idm(client, model_path, garment_path))
                if not produced.exists():
                    raise RuntimeError(f"결과 파일 없음: {produced}")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(produced, out_path)
                print(f"[vton]   ✓ 저장 → {out_path.name}")
                return out_path
            except Exception as e:  # noqa: BLE001
                last_err = e
                msg = str(e)
                # 쿼터 소진은 재시도 무의미 → 즉시 다음 Space
                if "quota" in msg.lower() or "No GPU" in msg:
                    print(f"[vton]   ✗ {space} 쿼터/GPU 소진: {msg[:100]}")
                    break
                # 일시 오류(500, 연결 등)는 재시도
                transient = "500" in msg or "502" in msg or "503" in msg or "timed out" in msg.lower()
                print(f"[vton]   ⚠ {space} 시도 {attempt}/{predict_retries} 실패: {msg[:100]}")
                if transient and attempt < predict_retries:
                    time.sleep(6)
                    continue
                break
        # 이 Space 는 실패 → 다음 Space 로 (for-else 없이 자연 진행)
        msg = str(last_err)
        if "No GPU" in msg or "quota" in msg.lower():
            if not settings.HF_TOKEN:
                print(
                    "[vton]   💡 무료 GPU 큐 소진. .env 에 HF_TOKEN 을 넣으면 할당량이 늘어납니다.\n"
                    "         (huggingface.co/settings/tokens → New token(read) → .env 의 HF_TOKEN=hf_...)"
                )
            else:
                print(
                    "[vton]   💡 토큰 할당량도 소진. 몇 분 후 재시도하거나,\n"
                    "         Space 를 본인 계정으로 Duplicate(유료 GPU)하는 것을 권장합니다."
                )
    raise RuntimeError(f"모든 Space 실패. 마지막 에러: {last_err}")


def inspect() -> None:
    """1순위 Space 의 API 시그니처를 출력 (파라미터가 바뀌었는지 확인용)."""
    space = settings.VTON["space"]
    print(f"[inspect] {space} API:")
    if not settings.HF_TOKEN:
        print("  (HF_TOKEN 없음 — public 접근으로 시도)")
    client = get_client(space)
    client.view_api()


def main() -> None:
    ap = argparse.ArgumentParser(description="IDM-VTON HF Space 클라이언트")
    ap.add_argument("--inspect", action="store_true", help="Space API 시그니처 출력")
    args = ap.parse_args()
    if args.inspect:
        inspect()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()

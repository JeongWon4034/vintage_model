"""옷 이미지 전처리.

IDM-VTON 은 '깨끗한 흰 배경의 정면 상품컷'을 전제로 학습됐다.
fruitsfamily 는 착용샷/마네킹샷/바닥 플랫레이가 섞여 있으므로,
배경을 제거해 흰 배경으로 정규화하면 결과 품질이 올라간다.

- remove_background: rembg(U2-Net)로 배경 제거 후 흰 배경 합성
- looks_like_garment: 디테일컷/극단 비율 이미지를 러프하게 걸러내는 휴리스틱
  (완벽한 분류는 범위 밖 — 명백한 케이스만 제거)
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

import settings

_session = None  # rembg 세션 캐시
_face_det = None  # YuNet 얼굴 검출기 캐시


def _get_face_detector():
    """YuNet 얼굴 검출기 (OpenCV 5 는 Haar cascade 제거됨 → DNN 사용)."""
    global _face_det
    if _face_det is None:
        import cv2
        model = settings.ROOT / "assets" / "yunet.onnx"
        _face_det = cv2.FaceDetectorYN.create(str(model), "", (320, 320), 0.6)
    return _face_det


def has_face(img) -> bool:
    """PIL 이미지에 얼굴이 있는지 검출 (YuNet)."""
    import cv2
    import numpy as np

    det = _get_face_detector()
    arr = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    h, w = arr.shape[:2]
    det.setInputSize((w, h))
    _, faces = det.detect(arr)
    return faces is not None and len(faces) > 0


_pose_lm = None  # MediaPipe PoseLandmarker 캐시

# 몸통 랜드마크 인덱스: 어깨(11,12) 팔꿈치(13,14) 손목(15,16) 엉덩이(23,24)
_BODY_LM = (11, 12, 13, 14, 15, 16, 23, 24)


def _get_pose_landmarker():
    global _pose_lm
    if _pose_lm is None:
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
        opts = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(
                model_asset_path=str(settings.ROOT / "assets" / "pose_landmarker_lite.task")),
            running_mode=vision.RunningMode.IMAGE)
        _pose_lm = vision.PoseLandmarker.create_from_options(opts)
    return _pose_lm


def body_landmark_count(img) -> int:
    """보이는 몸통 랜드마크 수(0~8). 머리 잘린 착용샷도 몸으로 감지된다."""
    import mediapipe as mp
    import numpy as np

    lm = _get_pose_landmarker()
    arr = np.array(img.convert("RGB"))
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=arr)
    res = lm.detect(mp_img)
    if not res.pose_landmarks:
        return 0
    marks = res.pose_landmarks[0]
    return sum(1 for i in _BODY_LM if marks[i].visibility > 0.5)


def has_person(img) -> bool:
    """착용샷 판별: 얼굴 검출 OR 몸통 랜드마크 4개 이상.

    - 얼굴만 있는 컷, 머리 잘린 착용샷 모두 잡는다.
    - 한계: 행거에 걸린 옷을 몸통으로 오인하는 경우가 드물게 있음
      (좋은 사진을 스킵하는 방향의 오류라 안전).
    """
    if has_face(img):
        return True
    return body_landmark_count(img) >= 4


def looks_like_garment(path: Path) -> bool:
    """상품 피팅에 부적합해 보이는 이미지를 러프하게 걸러낸다."""
    try:
        img = Image.open(path)
    except Exception:
        return False
    w, h = img.size
    if w < 300 or h < 300:
        return False  # 너무 작음(썸네일/아이콘)
    ar = w / h
    if ar > 2.2 or ar < 0.45:
        return False  # 극단적 가로/세로 비율(배너·디테일 크롭 가능성)
    return True


def _get_session():
    global _session
    if _session is None:
        from rembg import new_session
        _session = new_session("u2net")
    return _session


def remove_background(in_path: Path, out_path: Path, bg_color=(255, 255, 255)) -> Path:
    """rembg 로 배경 제거 후 지정 배경색으로 합성해 저장."""
    from rembg import remove

    img = Image.open(in_path).convert("RGBA")
    cut = remove(img, session=_get_session())          # RGBA (배경 투명)
    bg = Image.new("RGBA", cut.size, (*bg_color, 255))
    composed = Image.alpha_composite(bg, cut).convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    composed.save(out_path, "JPEG", quality=92)
    return out_path


def prepare_garment(in_path: Path, work_dir: Path) -> Path:
    """설정에 따라 옷 이미지를 전처리하고, 사용할 최종 경로를 반환한다."""
    if not settings.PREPROCESS.get("remove_background", False):
        return in_path
    out_path = work_dir / f"{in_path.stem}_clean.jpg"
    bg = tuple(settings.PREPROCESS.get("bg_color", [255, 255, 255]))
    try:
        return remove_background(in_path, out_path, bg_color=bg)
    except Exception as e:  # noqa: BLE001
        print(f"[preprocess] 배경 제거 실패({e}) — 원본 사용: {in_path.name}")
        return in_path

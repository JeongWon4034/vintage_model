/*
 * 360° 스핀 뷰어 (스텁 / 확장용).
 *
 * 지금은 정면 1각도만 생성하므로 갤러리는 단일 이미지를 쓴다.
 * 나중에 모델별 다각도 프레임(정면/45°/측면/…)을 만들면,
 * 아래 SpinViewer 에 프레임 URL 배열만 넘기면 드래그로 회전하는 유사 360° 뷰가 된다.
 *
 * 사용 예 (확장 시):
 *   const el = document.querySelector('#spin');
 *   new SpinViewer(el, [
 *     '/img/result/model_01__garment_01__a00.png',
 *     '/img/result/model_01__garment_01__a45.png',
 *     '/img/result/model_01__garment_01__a90.png',
 *     ...
 *   ]);
 */
class SpinViewer {
  constructor(container, frameUrls) {
    this.container = container;
    this.frames = frameUrls;
    this.index = 0;
    this.dragging = false;
    this.lastX = 0;

    this.img = document.createElement('img');
    this.img.style.width = '100%';
    this.img.style.userSelect = 'none';
    this.img.draggable = false;
    this.img.src = this.frames[0];
    container.appendChild(this.img);

    // 프레임 프리로드
    this.frames.forEach(u => { const i = new Image(); i.src = u; });

    container.addEventListener('pointerdown', e => this._down(e));
    window.addEventListener('pointermove', e => this._move(e));
    window.addEventListener('pointerup', () => { this.dragging = false; });
  }

  _down(e) { this.dragging = true; this.lastX = e.clientX; }

  _move(e) {
    if (!this.dragging) return;
    const dx = e.clientX - this.lastX;
    if (Math.abs(dx) < 8) return;           // 감도
    const dir = dx > 0 ? 1 : -1;
    this.index = (this.index + dir + this.frames.length) % this.frames.length;
    this.img.src = this.frames[this.index];
    this.lastX = e.clientX;
  }
}

// 전역 노출(확장 시 index.html 에서 사용)
window.SpinViewer = SpinViewer;

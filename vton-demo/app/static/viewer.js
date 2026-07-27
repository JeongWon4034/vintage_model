/*
 * 360° 스핀 뷰어.
 *
 * 프레임 URL 배열(회전 순서: 정면→45→90→180→270→315→loop)을 받아
 *  - 로드 시 자동 회전(오토플레이) → "돌아간다"는 게 바로 보임
 *  - 마우스 드래그 / 터치로 수동 스크럽
 *  - 좌우 버튼으로 한 프레임씩
 * 을 제공하는 유사 360° 뷰.
 *
 * 사용:
 *   const sv = new SpinViewer(holder, frameUrls);
 *   sv.img  // 스타일 조정용 <img> 참조
 */
class SpinViewer {
  constructor(container, frameUrls) {
    this.container = container;
    this.frames = frameUrls;
    this.index = 0;
    this.dragging = false;
    this.lastX = 0;
    this.userInteracted = false;

    container.style.position = 'relative';
    container.style.touchAction = 'pan-y';

    // 메인 이미지
    this.img = document.createElement('img');
    this.img.style.width = '100%';
    this.img.style.userSelect = 'none';
    this.img.draggable = false;
    this.img.src = this.frames[0];
    container.appendChild(this.img);

    // 프레임 프리로드 (끊김 방지)
    this._loaded = 0;
    this.frames.forEach(u => {
      const im = new Image();
      im.onload = () => { this._loaded++; };
      im.src = u;
    });

    // 오버레이: 힌트 + 프레임 인디케이터
    if (this.frames.length > 1) {
      this.hint = document.createElement('div');
      this.hint.textContent = '↔ 드래그로 360° 회전';
      Object.assign(this.hint.style, {
        position: 'absolute', bottom: '10px', left: '50%', transform: 'translateX(-50%)',
        background: 'rgba(0,0,0,0.6)', color: '#fff', fontSize: '12px',
        padding: '5px 12px', borderRadius: '999px', pointerEvents: 'none',
        whiteSpace: 'nowrap', transition: 'opacity 0.4s', zIndex: 3,
      });
      container.appendChild(this.hint);

      this.dots = document.createElement('div');
      Object.assign(this.dots.style, {
        position: 'absolute', top: '10px', right: '12px',
        background: 'rgba(0,0,0,0.55)', color: '#fff', fontSize: '11px',
        padding: '3px 9px', borderRadius: '999px', pointerEvents: 'none', zIndex: 3,
      });
      container.appendChild(this.dots);
      this._updateDots();

      this._addButtons();

      // 이벤트
      container.addEventListener('pointerdown', e => this._down(e));
      window.addEventListener('pointermove', e => this._move(e));
      window.addEventListener('pointerup', () => { this.dragging = false; });

      // 오토플레이: 프리로드가 어느정도 되면 시작, 사용자가 만지면 정지
      this._startAutoplayWhenReady();
    }
  }

  _addButtons() {
    const mk = (txt, side) => {
      const b = document.createElement('button');
      b.textContent = txt;
      Object.assign(b.style, {
        position: 'absolute', top: '50%', [side]: '8px', transform: 'translateY(-50%)',
        width: '34px', height: '34px', borderRadius: '50%', border: 'none',
        background: 'rgba(0,0,0,0.5)', color: '#fff', fontSize: '18px',
        cursor: 'pointer', zIndex: 3, lineHeight: '34px', padding: 0,
      });
      b.addEventListener('click', () => {
        this._stopAutoplay();
        this._step(side === 'left' ? -1 : 1);
      });
      this.container.appendChild(b);
    };
    mk('‹', 'left');
    mk('›', 'right');
  }

  _startAutoplayWhenReady() {
    let tries = 0;
    const wait = setInterval(() => {
      tries++;
      if (this._loaded >= this.frames.length || tries > 40) {
        clearInterval(wait);
        if (!this.userInteracted) this._startAutoplay();
      }
    }, 150);
  }

  _startAutoplay() {
    if (this._auto) return;
    this._auto = setInterval(() => this._step(1), 550);
  }

  _stopAutoplay() {
    this.userInteracted = true;
    if (this._auto) { clearInterval(this._auto); this._auto = null; }
    if (this.hint) this.hint.style.opacity = '0';
  }

  _step(dir) {
    this.index = (this.index + dir + this.frames.length) % this.frames.length;
    this.img.src = this.frames[this.index];
    this._updateDots();
  }

  _updateDots() {
    if (this.dots) this.dots.textContent = `${this.index + 1} / ${this.frames.length}`;
  }

  _down(e) {
    this._stopAutoplay();
    this.dragging = true;
    this.lastX = e.clientX;
  }

  _move(e) {
    if (!this.dragging) return;
    const dx = e.clientX - this.lastX;
    if (Math.abs(dx) < 14) return;          // 드래그 감도(px/프레임)
    this._step(dx > 0 ? 1 : -1);
    this.lastX = e.clientX;
  }
}

// 전역 노출
window.SpinViewer = SpinViewer;

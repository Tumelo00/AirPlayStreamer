/**
 * AirPlay Video Sync
 * Video karelerini gecikmeyle gostererek HomePod sesiyle senkronize eder.
 * DRM korumalı sitelerde (Netflix, Disney+ vb.) otomatik devre disi kalir.
 */

let enabled = false;
let delayMs = 1500;
let state = null;

// DRM kullanan siteler - bu sitelerde uzanti calismaz
const DRM_SITES = ['netflix.com', 'disneyplus.com', 'primevideo.com',
                   'hulu.com', 'hbomax.com', 'max.com', 'peacocktv.com',
                   'paramountplus.com', 'appletv.apple.com'];

function isDRMSite() {
  return DRM_SITES.some(site => location.hostname.includes(site));
}

chrome.storage.local.get(['enabled', 'delayMs'], (data) => {
  enabled = data.enabled || false;
  delayMs = data.delayMs || 1500;
  if (enabled && !isDRMSite()) tryAttach();
});

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === 'sync-update') {
    enabled = msg.enabled;
    delayMs = msg.delayMs;
    if (enabled && !state && !isDRMSite()) tryAttach();
    if (!enabled && state) cleanup();
    if (state) state.delayMs = delayMs;
  }
});

function tryAttach() {
  let attempts = 0;
  const check = () => {
    const v = document.querySelector('video');
    if (v && v.videoWidth > 0 && v.readyState >= 2 && !v.paused) {
      setTimeout(() => testAndAttach(v), 500);
    } else if (attempts++ < 30) {
      setTimeout(check, 500);
    }
  };
  check();
}

function testAndAttach(video) {
  // DRM testi: bir frame ciz ve siyah mi kontrol et
  const tc = document.createElement('canvas');
  tc.width = 32; tc.height = 32;
  const tctx = tc.getContext('2d');
  try {
    tctx.drawImage(video, 0, 0, 32, 32);
    const px = tctx.getImageData(0, 0, 32, 32).data;
    let nonBlack = 0;
    for (let i = 0; i < px.length; i += 4) {
      if (px[i] > 10 || px[i+1] > 10 || px[i+2] > 10) nonBlack++;
    }
    if (nonBlack < 5) {
      console.log('[AirPlay Sync] DRM algilandi, devre disi');
      return; // DRM - don't attach
    }
  } catch (e) {
    console.log('[AirPlay Sync] Canvas tainted, devre disi');
    return;
  }
  attach(video);
}

function attach(video) {
  if (state) return;

  const FPS = 30;
  const BUFFER_COUNT = 3 * FPS;
  const vw = video.videoWidth, vh = video.videoHeight;

  const frames = [];
  for (let i = 0; i < BUFFER_COUNT; i++) {
    const c = document.createElement('canvas');
    c.width = vw; c.height = vh;
    frames.push({ canvas: c, ctx: c.getContext('2d'), time: 0 });
  }
  let writeIdx = 0;

  const display = document.createElement('canvas');
  display.width = vw; display.height = vh;

  const vidStyle = getComputedStyle(video);
  display.style.position = vidStyle.position || 'absolute';
  display.style.top = vidStyle.top || '0';
  display.style.left = vidStyle.left || '0';
  display.style.width = vidStyle.width;
  display.style.height = vidStyle.height;
  display.style.zIndex = '1';
  display.style.pointerEvents = 'none';

  video.parentNode.insertBefore(display, video.nextSibling);

  const dCtx = display.getContext('2d');
  let lastCapture = 0, bufferReady = false, capturedCount = 0;

  state = { video, display, frames, delayMs, running: true };

  video.addEventListener('seeking', () => {
    if (!state) return;
    bufferReady = false;
    capturedCount = 0;
    writeIdx = 0;
    for (const f of frames) f.time = 0;
    video.style.opacity = '1';
  });

  function loop() {
    if (!state || !state.running) return;
    const now = performance.now();

    if (!video.paused && !video.ended && video.readyState >= 2) {
      if (now - lastCapture >= 1000 / FPS) {
        lastCapture = now;
        const f = frames[writeIdx];
        if (f.canvas.width !== video.videoWidth) {
          f.canvas.width = video.videoWidth;
          f.canvas.height = video.videoHeight;
          display.width = video.videoWidth;
          display.height = video.videoHeight;
        }
        f.ctx.drawImage(video, 0, 0);
        f.time = now;
        capturedCount++;
        writeIdx = (writeIdx + 1) % BUFFER_COUNT;

        if (!bufferReady && capturedCount > (state.delayMs / 1000) * FPS) {
          bufferReady = true;
          video.style.opacity = '0';
        }
      }

      if (bufferReady) {
        const target = now - state.delayMs;
        let bestIdx = -1, bestDiff = Infinity;
        for (let i = 0; i < BUFFER_COUNT; i++) {
          if (frames[i].time === 0) continue;
          const d = Math.abs(frames[i].time - target);
          if (d < bestDiff) { bestDiff = d; bestIdx = i; }
        }
        if (bestIdx >= 0) dCtx.drawImage(frames[bestIdx].canvas, 0, 0);
      }

      const w = video.clientWidth + 'px', h = video.clientHeight + 'px';
      if (display.style.width !== w) display.style.width = w;
      if (display.style.height !== h) display.style.height = h;
    }
    requestAnimationFrame(loop);
  }
  loop();
}

function cleanup() {
  if (!state) return;
  state.running = false;
  state.video.style.opacity = '';
  if (state.display.parentNode) state.display.parentNode.removeChild(state.display);
  state = null;
}

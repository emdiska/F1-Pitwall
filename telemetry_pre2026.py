import fastf1
import numpy as np
import json

fastf1.Cache.enable_cache('cache')

# ── CONFIG ─────────────────────────────────────────────
YEAR     = 2024
RACE     = 'Bahrain'
SESSION  = 'Q'
DRIVER_1 = 'VER'
DRIVER_2 = 'LEC'
# ───────────────────────────────────────────────────────

session = fastf1.get_session(YEAR, RACE, SESSION)
session.load()

d1 = session.laps.pick_drivers(DRIVER_1).pick_fastest()
d2 = session.laps.pick_drivers(DRIVER_2).pick_fastest()

def format_laptime(td):
    total = td.total_seconds()
    mins  = int(total // 60)
    secs  = total % 60
    return f"{mins}:{secs:06.3f}"

t1 = d1.get_telemetry().add_distance()
t2 = d2.get_telemetry().add_distance()

N = 1000
dist = np.linspace(0, min(t1['Distance'].max(),
                           t2['Distance'].max()), N)

speed1    = np.interp(dist, t1['Distance'], t1['Speed'])
speed2    = np.interp(dist, t2['Distance'], t2['Speed'])
throttle1 = np.interp(dist, t1['Distance'], t1['Throttle'])
throttle2 = np.interp(dist, t2['Distance'], t2['Throttle'])
brake1    = np.interp(dist, t1['Distance'], t1['Brake'].astype(float)) * 100
brake2    = np.interp(dist, t2['Distance'], t2['Brake'].astype(float)) * 100
gear1     = np.interp(dist, t1['Distance'], t1['nGear'].astype(float))
gear2     = np.interp(dist, t2['Distance'], t2['nGear'].astype(float))
drs1      = np.interp(dist, t1['Distance'], t1['DRS'].astype(float))
drs2      = np.interp(dist, t2['Distance'], t2['DRS'].astype(float))
x1 = np.interp(dist, t1['Distance'], t1['X'])
y1 = np.interp(dist, t1['Distance'], t1['Y'])
x2 = np.interp(dist, t2['Distance'], t2['X'])
y2 = np.interp(dist, t2['Distance'], t2['Y'])

# Align D2 start to D1 start
start_x1, start_y1 = x1[0], y1[0]
distances_to_start = np.sqrt((x2 - start_x1)**2 + (y2 - start_y1)**2)
offset = int(np.argmin(distances_to_start))
x2 = np.roll(x2, -offset)
y2 = np.roll(y2, -offset)

ds    = np.diff(dist)
time1 = np.concatenate([[0], np.cumsum(ds / (speed1[:-1] / 3.6))])
time2 = np.concatenate([[0], np.cumsum(ds / (speed2[:-1] / 3.6))])
delta = time2 - time1
final_delta = delta[-1]

d1_time     = format_laptime(d1['LapTime'])
d2_time     = format_laptime(d2['LapTime'])
lap_seconds = float(d1['LapTime'].total_seconds())

drs_active = (drs1 > 9) | (drs2 > 9)
drs_zones  = []
in_zone    = False
for i, active in enumerate(drs_active):
    if active and not in_zone:
        zone_start = float(dist[i])
        in_zone = True
    elif not active and in_zone:
        drs_zones.append([zone_start, float(dist[i])])
        in_zone = False
if in_zone:
    drs_zones.append([zone_start, float(dist[-1])])

try:
    circuit_info = session.get_circuit_info()
    corner_positions = []
    x1n_tmp = (x1 - x1.min()) / (x1.max() - x1.min())
    y1n_tmp = (y1 - y1.min()) / (y1.max() - y1.min())
    for _, row in circuit_info.corners.iterrows():
        idx = int(np.argmin(np.abs(dist - float(row['Distance']))))
        corner_positions.append({
            'number': int(row['Number']),
            'x': float(x1n_tmp[idx]),
            'y': float(y1n_tmp[idx]),
        })
except Exception:
    corner_positions = []

x1n = (x1 - x1.min()) / (x1.max() - x1.min())
y1n = (y1 - y1.min()) / (y1.max() - y1.min())
x2n = (x2 - x2.min()) / (x2.max() - x2.min())
y2n = (y2 - y2.min()) / (y2.max() - y2.min())

C1 = '#3671C6'
C2 = '#E8002D'

data = {
    'dist':          dist.tolist(),
    'speed1':        speed1.tolist(),
    'speed2':        speed2.tolist(),
    'throttle1':     throttle1.tolist(),
    'throttle2':     throttle2.tolist(),
    'brake1':        brake1.tolist(),
    'brake2':        brake2.tolist(),
    'gear1':         gear1.tolist(),
    'gear2':         gear2.tolist(),
    'delta':         delta.tolist(),
    'x1':            x1n.tolist(),
    'y1':            y1n.tolist(),
    'x2':            x2n.tolist(),
    'y2':            y2n.tolist(),
    'drs_zones':     drs_zones,
    'corners':       corner_positions,
    'driver1':       DRIVER_1,
    'driver2':       DRIVER_2,
    'c1':            C1,
    'c2':            C2,
    'final_delta':   round(float(final_delta), 3),
    'd1_time':       d1_time,
    'd2_time':       d2_time,
    'year':          YEAR,
    'race':          RACE,
    'session':       SESSION,
    'lap_seconds':   lap_seconds,
}

html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{DRIVER_1} vs {DRIVER_2} — {YEAR} {RACE}</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: #0a0a0a; color: #fff;
        font-family: 'Segoe UI', sans-serif; overflow: hidden; }}
#header {{ padding: 14px 24px; border-bottom: 1px solid #222;
           height: 64px; }}
#header h1 {{ font-size: 15px; font-weight: 500; }}
#header p  {{ font-size: 11px; color: #666; margin-top: 3px; }}
#main {{ display: grid; grid-template-columns: 1fr 320px;
         height: calc(100vh - 64px); }}
#left {{ display: flex; flex-direction: column;
         border-right: 1px solid #1a1a1a; }}
#chart-area {{ flex: 1; overflow: hidden; }}
canvas#telemetry {{ display: block; width: 100%; height: 100%; }}
#controls {{ height: 44px; padding: 0 20px; background: #0f0f0f;
             border-top: 1px solid #1a1a1a;
             display: flex; align-items: center; gap: 14px; }}
#controls button {{
    background: #181818; border: 1px solid #2a2a2a;
    color: #ccc; padding: 5px 16px; border-radius: 4px;
    cursor: pointer; font-size: 12px; }}
#controls button:hover {{ background: #222; color: #fff; }}
#scrubber {{ flex: 1; accent-color: #444; height: 3px; }}
#progress-label {{ font-size: 11px; color: #555; min-width: 60px; }}
#right {{ display: flex; flex-direction: column;
          padding: 14px; gap: 10px; overflow: hidden; }}
#track-container {{ flex: 1; min-height: 0; }}
canvas#track {{ width: 100%; height: 100%; display: block; }}
#info-box {{ background: #0f0f0f; border: 1px solid #1e1e1e;
             border-radius: 6px; padding: 12px; }}
#info-box table {{ width: 100%; border-collapse: collapse;
                   font-size: 11px; }}
#info-box td {{ padding: 3px 6px; }}
#info-box .lbl {{ color: #555; }}
#info-box .v1  {{ color: {C1}; font-weight: 600; text-align: right; }}
#info-box .v2  {{ color: {C2}; font-weight: 600; text-align: right; }}
#info-box .dpos {{ color: {C1}; font-weight: 600; text-align: right; }}
#info-box .dneg {{ color: {C2}; font-weight: 600; text-align: right; }}
.tag {{ display:inline-block; padding:2px 7px; border-radius:3px;
        font-size:11px; font-weight:600; margin-right:4px; }}
</style>
</head>
<body>
<div id="header">
  <h1>
    <span class="tag" style="background:{C1}22;color:{C1}">{DRIVER_1}</span>
    {d1_time}
    &nbsp;vs&nbsp;
    <span class="tag" style="background:{C2}22;color:{C2}">{DRIVER_2}</span>
    {d2_time}
    &nbsp;&nbsp;
    <span style="color:#666;font-size:13px">Gap {final_delta:+.3f}s</span>
  </h1>
  <p>{YEAR} {RACE} — {SESSION} &nbsp;|&nbsp;
     Speed · Delta · Throttle · Brake · Gear
     &nbsp;|&nbsp; Green = DRS zones</p>
</div>

<div id="main">
  <div id="left">
    <div id="chart-area">
      <canvas id="telemetry"></canvas>
    </div>
    <div id="controls">
      <button id="btn-play">▶ Play</button>
      <button id="btn-pause">⏸ Pause</button>
      <button id="btn-reset">↺ Reset</button>
      <input type="range" id="scrubber" min="0" max="999" value="0">
      <span id="progress-label">0 m</span>
    </div>
  </div>
  <div id="right">
    <div id="track-container">
      <canvas id="track"></canvas>
    </div>
    <div id="info-box">
      <table>
        <tr>
          <td class="lbl">Distance</td>
          <td colspan="2" id="inf-dist"
              style="color:#aaa;text-align:right">—</td>
        </tr>
        <tr>
          <td class="lbl">Speed</td>
          <td id="inf-spd1" class="v1">—</td>
          <td id="inf-spd2" class="v2">—</td>
        </tr>
        <tr>
          <td class="lbl">Throttle</td>
          <td id="inf-thr1" class="v1">—</td>
          <td id="inf-thr2" class="v2">—</td>
        </tr>
        <tr>
          <td class="lbl">Brake</td>
          <td id="inf-brk1" class="v1">—</td>
          <td id="inf-brk2" class="v2">—</td>
        </tr>
        <tr>
          <td class="lbl">Gear</td>
          <td id="inf-gr1" class="v1">—</td>
          <td id="inf-gr2" class="v2">—</td>
        </tr>
        <tr>
          <td class="lbl">Δ Time</td>
          <td colspan="2" id="inf-delta" class="dpos">—</td>
        </tr>
      </table>
    </div>
  </div>
</div>

<script>
const D = {json.dumps(data)};
const N = D.dist.length;

const tel  = document.getElementById('telemetry');
const tctx = tel.getContext('2d');
const trk  = document.getElementById('track');
const rctx = trk.getContext('2d');

const PAD_L    = 56;
const PAD_R    = 12;
const PAD_T    = 28;
const PAD_B    = 10;
const X_AXIS_H = 22;

const PANELS = [
  {{ label:'Speed (km/h)', k1:'speed1',    k2:'speed2',
     min:50,  max:330, ticks:[100,150,200,250,300] }},
  {{ label:'Δ Time (s)',   k1:'delta',     k2:null,
     min:-0.4,max:0.4, ticks:[-0.3,-0.2,-0.1,0,0.1,0.2,0.3] }},
  {{ label:'Throttle (%)',k1:'throttle1', k2:'throttle2',
     min:0,  max:100,  ticks:[25,50,75,100] }},
  {{ label:'Brake (%)',   k1:'brake1',    k2:'brake2',
     min:0,  max:100,  ticks:[50,100] }},
  {{ label:'Gear',        k1:'gear1',     k2:'gear2',
     min:1,  max:8,    ticks:[2,3,4,5,6,7,8] }},
];

function initCanvas() {{
  tel.width  = tel.offsetWidth;
  tel.height = tel.offsetHeight;
  trk.width  = trk.offsetWidth;
  trk.height = trk.offsetHeight;
}}

function pxD(dv) {{
  return PAD_L + (dv / D.dist[N-1]) * (tel.width - PAD_L - PAD_R);
}}
function pyV(val, min, max, y0, h) {{
  return y0 + h - ((val - min) / (max - min)) * h;
}}

function drawTelemetry(cur) {{
  const W = tel.width, H = tel.height;
  tctx.clearRect(0, 0, W, H);
  tctx.fillStyle = '#0a0a0a';
  tctx.fillRect(0, 0, W, H);

  const usableH   = H - X_AXIS_H;
  const panelSlot = usableH / PANELS.length;
  const plotH     = panelSlot - PAD_T - PAD_B;

  PANELS.forEach((p, pi) => {{
    const y0 = pi * panelSlot + PAD_T;

    tctx.fillStyle = '#ffffff';
    tctx.font = 'bold 11px Segoe UI';
    tctx.textAlign = 'left';
    tctx.fillText(p.label, PAD_L, y0 - 8);

    D.drs_zones.forEach(([za, zb]) => {{
      tctx.fillStyle = 'rgba(0,200,0,0.07)';
      tctx.fillRect(pxD(za), y0, pxD(zb)-pxD(za), plotH);
    }});

    p.ticks.forEach(tv => {{
      const gy = pyV(tv, p.min, p.max, y0, plotH);
      tctx.strokeStyle = tv === 0 ? '#2a2a2a' : '#161616';
      tctx.lineWidth   = tv === 0 ? 1 : 0.5;
      tctx.beginPath();
      tctx.moveTo(PAD_L, gy); tctx.lineTo(W - PAD_R, gy);
      tctx.stroke();
    }});

    tctx.strokeStyle = 'rgba(255,255,255,0.6)';
    tctx.lineWidth = 1;
    tctx.beginPath();
    tctx.moveTo(PAD_L, y0); tctx.lineTo(PAD_L, y0 + plotH);
    tctx.stroke();

    tctx.strokeStyle = 'rgba(255,255,255,0.2)';
    tctx.lineWidth = 0.5;
    tctx.beginPath();
    tctx.moveTo(PAD_L, y0 + plotH);
    tctx.lineTo(W - PAD_R, y0 + plotH);
    tctx.stroke();

    p.ticks.forEach(tv => {{
      const gy = pyV(tv, p.min, p.max, y0, plotH);
      tctx.strokeStyle = 'rgba(255,255,255,0.5)';
      tctx.lineWidth = 1;
      tctx.beginPath();
      tctx.moveTo(PAD_L - 4, gy); tctx.lineTo(PAD_L, gy);
      tctx.stroke();
      tctx.fillStyle = '#ffffff';
      tctx.font = '9px Segoe UI';
      tctx.textAlign = 'right';
      tctx.fillText(tv, PAD_L - 6, gy + 3);
    }});

    [[p.k1, D.c1], [p.k2, D.c2]].forEach(([key, col]) => {{
      if (!key) return;
      const arr = D[key];
      tctx.strokeStyle = col;
      tctx.lineWidth = 1.5;
      tctx.beginPath();
      for (let i = 0; i < N; i++) {{
        const x = pxD(D.dist[i]);
        const y = pyV(arr[i], p.min, p.max, y0, plotH);
        i === 0 ? tctx.moveTo(x, y) : tctx.lineTo(x, y);
      }}
      tctx.stroke();
    }});

    const cx = pxD(D.dist[cur]);
    if (p.k1) {{
      const v1  = D[p.k1][cur];
      const vy1 = pyV(v1, p.min, p.max, y0, plotH);
      const lbl = p.label.includes('Δ')
        ? (v1 >= 0 ? '+' : '') + v1.toFixed(3)
        : Math.round(v1);
      tctx.fillStyle = D.c1;
      tctx.font = 'bold 10px Segoe UI';
      tctx.textAlign = 'left';
      tctx.fillText(lbl, cx + 4,
        Math.max(y0 + 10, Math.min(y0 + plotH - 4, vy1 - 2)));
    }}
    if (p.k2) {{
      const v2  = D[p.k2][cur];
      const vy2 = pyV(v2, p.min, p.max, y0, plotH);
      tctx.fillStyle = D.c2;
      tctx.font = 'bold 10px Segoe UI';
      tctx.textAlign = 'left';
      tctx.fillText(Math.round(v2), cx + 4,
        Math.max(y0 + 20, Math.min(y0 + plotH - 14, vy2 + 11)));
    }}
  }});

  // X-axis
  const xAxisY = H - X_AXIS_H + 4;
  tctx.strokeStyle = 'rgba(255,255,255,0.6)';
  tctx.lineWidth = 1;
  tctx.beginPath();
  tctx.moveTo(PAD_L, xAxisY);
  tctx.lineTo(W - PAD_R, xAxisY);
  tctx.stroke();

  const maxDist = D.dist[N-1];
  [0,500,1000,1500,2000,2500,3000,3500,4000,4500,5000,5500]
    .forEach(tv => {{
      if (tv > maxDist) return;
      const gx = pxD(tv);
      tctx.strokeStyle = 'rgba(255,255,255,0.5)';
      tctx.lineWidth = 1;
      tctx.beginPath();
      tctx.moveTo(gx, xAxisY); tctx.lineTo(gx, xAxisY + 4);
      tctx.stroke();
      tctx.fillStyle = '#ffffff';
      tctx.font = '9px Segoe UI';
      tctx.textAlign = 'center';
      tctx.fillText(tv === 0 ? '0' : tv + 'm', gx, xAxisY + 14);
    }});

  // Cursor
  const cx = pxD(D.dist[cur]);
  tctx.strokeStyle = 'rgba(255,255,255,0.5)';
  tctx.lineWidth = 1;
  tctx.setLineDash([4, 4]);
  tctx.beginPath();
  tctx.moveTo(cx, 0); tctx.lineTo(cx, H - X_AXIS_H);
  tctx.stroke();
  tctx.setLineDash([]);
}}

function drawTrack(cur) {{
  const W = trk.width, H = trk.height;
  rctx.clearRect(0, 0, W, H);
  rctx.fillStyle = '#0a0a0a';
  rctx.fillRect(0, 0, W, H);

  const pad = 32;
  const tw = W - pad*2, th = H - pad*2;
  const tx = xn => pad + xn * tw;
  const ty = yn => pad + (1 - yn) * th;

  rctx.strokeStyle = 'rgba(255,255,255,0.1)';
  rctx.lineWidth = 10;
  rctx.lineCap = 'round';
  rctx.lineJoin = 'round';
  rctx.beginPath();
  for (let i = 0; i < N; i++) {{
    i === 0 ? rctx.moveTo(tx(D.x1[i]), ty(D.y1[i]))
            : rctx.lineTo(tx(D.x1[i]), ty(D.y1[i]));
  }}
  rctx.closePath();
  rctx.stroke();

  for (let i = 1; i < N; i++) {{
    const t = Math.max(0, Math.min(1, (D.speed1[i] - 50) / 280));
    const r = Math.round(255 * Math.min(1, 2*t));
    const g = Math.round(255 * Math.min(1, 2*(1-t)));
    rctx.strokeStyle = `rgba(${{r}},${{g}},0,0.8)`;
    rctx.lineWidth = 3;
    rctx.beginPath();
    rctx.moveTo(tx(D.x1[i-1]), ty(D.y1[i-1]));
    rctx.lineTo(tx(D.x1[i]),   ty(D.y1[i]));
    rctx.stroke();
  }}

  D.corners.forEach(c => {{
    const cx = tx(c.x), cy = ty(c.y);
    rctx.beginPath();
    rctx.arc(cx, cy, 7, 0, Math.PI*2);
    rctx.fillStyle = 'rgba(0,0,0,0.8)';
    rctx.fill();
    rctx.strokeStyle = 'rgba(255,255,255,0.25)';
    rctx.lineWidth = 0.5;
    rctx.stroke();
    rctx.fillStyle = '#ccc';
    rctx.font = 'bold 8px Segoe UI';
    rctx.textAlign = 'center';
    rctx.fillText(c.number, cx, cy + 3);
  }});

  [[D.x1[cur], D.y1[cur], D.c1, D.driver1],
   [D.x2[cur], D.y2[cur], D.c2, D.driver2]].forEach(
    ([xn, yn, col, name]) => {{
      const dx = tx(xn), dy = ty(yn);
      rctx.beginPath();
      rctx.arc(dx, dy, 7, 0, Math.PI*2);
      rctx.fillStyle = col;
      rctx.fill();
      rctx.strokeStyle = '#fff';
      rctx.lineWidth = 2;
      rctx.stroke();
      rctx.fillStyle = '#fff';
      rctx.font = 'bold 9px Segoe UI';
      rctx.textAlign = 'left';
      rctx.fillText(name, dx + 10, dy + 3);
  }});

  [['#00cc00','Low'], ['#aaaa00','Mid'], ['#cc0000','High']].forEach(
    ([col, lbl], i) => {{
      rctx.fillStyle = col;
      rctx.font = '8px Segoe UI';
      rctx.textAlign = 'left';
      rctx.fillText('■ ' + lbl, pad + i * 55, H - 6);
  }});
}}

function updateInfo(i) {{
  document.getElementById('inf-dist').textContent =
    Math.round(D.dist[i]) + ' m';
  document.getElementById('inf-spd1').textContent =
    Math.round(D.speed1[i]) + ' km/h';
  document.getElementById('inf-spd2').textContent =
    Math.round(D.speed2[i]) + ' km/h';
  document.getElementById('inf-thr1').textContent =
    Math.round(D.throttle1[i]) + '%';
  document.getElementById('inf-thr2').textContent =
    Math.round(D.throttle2[i]) + '%';
  document.getElementById('inf-brk1').textContent =
    Math.round(D.brake1[i]) + '%';
  document.getElementById('inf-brk2').textContent =
    Math.round(D.brake2[i]) + '%';
  document.getElementById('inf-gr1').textContent =
    Math.round(D.gear1[i]);
  document.getElementById('inf-gr2').textContent =
    Math.round(D.gear2[i]);
  const dv = D.delta[i];
  const el = document.getElementById('inf-delta');
  el.textContent = (dv >= 0 ? '+' : '') + dv.toFixed(3) + 's';
  el.className = dv >= 0 ? 'dpos' : 'dneg';
}}

let cursor    = 0;
let playing   = false;
let animId    = null;
let lastTime  = null;

const MS_PER_FRAME = (D.lap_seconds / N) * 1000;

const scrubber  = document.getElementById('scrubber');
const progLabel = document.getElementById('progress-label');

function step(timestamp) {{
  if (!playing) return;
  if (lastTime === null) lastTime = timestamp;
  const elapsed = timestamp - lastTime;
  if (elapsed >= MS_PER_FRAME) {{
    const steps = Math.floor(elapsed / MS_PER_FRAME);
    cursor = (cursor + steps) % N;
    lastTime = timestamp;
    scrubber.value = cursor;
    progLabel.textContent = Math.round(D.dist[cursor]) + ' m';
    drawTelemetry(cursor); drawTrack(cursor); updateInfo(cursor);
  }}
  animId = requestAnimationFrame(step);
}}

document.getElementById('btn-play').onclick = () => {{
  playing = true;
  lastTime = null;
  animId = requestAnimationFrame(step);
}};
document.getElementById('btn-pause').onclick = () => {{
  playing = false;
  cancelAnimationFrame(animId);
}};
document.getElementById('btn-reset').onclick = () => {{
  playing = false;
  cancelAnimationFrame(animId);
  cursor = 0; scrubber.value = 0;
  lastTime = null;
  progLabel.textContent = '0 m';
  drawTelemetry(0); drawTrack(0); updateInfo(0);
}};

scrubber.addEventListener('input', () => {{
  playing = false; cancelAnimationFrame(animId);
  cursor = parseInt(scrubber.value);
  progLabel.textContent = Math.round(D.dist[cursor]) + ' m';
  drawTelemetry(cursor); drawTrack(cursor); updateInfo(cursor);
}});

tel.addEventListener('mousemove', e => {{
  if (playing) return;
  const rect = tel.getBoundingClientRect();
  const t = Math.max(0, Math.min(1,
    (e.clientX - rect.left - PAD_L) /
    (tel.width - PAD_L - PAD_R)));
  cursor = Math.round(t * (N-1));
  scrubber.value = cursor;
  progLabel.textContent = Math.round(D.dist[cursor]) + ' m';
  drawTelemetry(cursor); drawTrack(cursor); updateInfo(cursor);
}});

window.addEventListener('load', () => {{
  initCanvas();
  drawTelemetry(0); drawTrack(0); updateInfo(0);
}});
window.addEventListener('resize', () => {{
  initCanvas();
  drawTelemetry(cursor); drawTrack(cursor);
}});
</script>
</body>
</html>"""

with open('telemetry_pre2026.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Saved — open telemetry_pre2026.html")
print(f"{DRIVER_1} {d1_time} | {DRIVER_2} {d2_time} | Gap {final_delta:+.3f}s")
print(f"DRS zones: {len(drs_zones)} | Corners: {len(corner_positions)}")

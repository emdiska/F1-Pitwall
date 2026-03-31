import os
import fastf1
import numpy as np
import json
import threading
import webbrowser
from flask import Flask, Response, jsonify, request

os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.makedirs('cache', exist_ok=True)

fastf1.Cache.enable_cache('cache')

app = Flask(__name__)

LAUNCHER_HTML = '''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>F1 Insight</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: #0a0a0a; color: #fff;
  font-family: 'Segoe UI', sans-serif;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  min-height: 100vh; padding: 40px;
}
h1 {
  font-size: 28px; font-weight: 300; letter-spacing: 4px;
  text-transform: uppercase; margin-bottom: 6px;
}
.subtitle {
  font-size: 12px; color: #444; letter-spacing: 2px;
  text-transform: uppercase; margin-bottom: 48px;
}
.card {
  background: #0f0f0f; border: 1px solid #1e1e1e;
  border-radius: 12px; padding: 40px; width: 100%;
  max-width: 560px;
}
.row {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 16px; margin-bottom: 16px;
}
.row.three { grid-template-columns: 1fr 1fr 1fr; }
.field { display: flex; flex-direction: column; gap: 6px; }
label {
  font-size: 10px; color: #555; text-transform: uppercase;
  letter-spacing: 1.5px;
}
select, input {
  background: #161616; border: 1px solid #2a2a2a;
  color: #fff; padding: 10px 14px; border-radius: 6px;
  font-size: 13px; font-family: 'Segoe UI', sans-serif;
  appearance: none; cursor: pointer;
  transition: border-color 0.2s;
}
select:hover, input:hover { border-color: #444; }
select:focus, input:focus { outline: none; border-color: #555; }
select:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-load {
  width: 100%; padding: 12px; border-radius: 6px;
  background: #1e1e1e; border: 1px solid #2a2a2a;
  color: #888; font-size: 13px; font-weight: 600;
  cursor: pointer; letter-spacing: 1px;
  text-transform: uppercase; transition: all 0.2s;
}
.btn-load:hover:not(:disabled) { background: #252525; color: #fff; }
.btn-run {
  width: 100%; padding: 14px; border-radius: 6px;
  background: #e8002d; border: none; color: #fff;
  font-size: 13px; font-weight: 600; cursor: pointer;
  letter-spacing: 1px; text-transform: uppercase;
  transition: all 0.2s; margin-top: 16px;
}
.btn-run:hover:not(:disabled) {
  background: #ff0033; transform: translateY(-1px);
}
.btn-run:disabled, .btn-load:disabled {
  opacity: 0.4; cursor: not-allowed; transform: none;
}
.status-box {
  margin-top: 24px; background: #080808;
  border: 1px solid #1a1a1a; border-radius: 6px;
  padding: 16px; min-height: 80px;
  font-size: 11px; font-family: monospace; display: none;
}
.status-line { color: #666; margin-bottom: 4px; }
.status-line.active { color: #4a9eff; }
.status-line.done { color: #22cc55; }
.status-line.error { color: #e8002d; }
.divider {
  border: none; border-top: 1px solid #1a1a1a; margin: 24px 0;
}
.mode-badge {
  display: inline-block; padding: 3px 10px; border-radius: 20px;
  font-size: 10px; font-weight: 600; letter-spacing: 1px;
  text-transform: uppercase; margin-bottom: 20px;
}
.mode-pre  { background: #1a2a3a; color: #4a9eff; }
.mode-2026 { background: #2a1a1a; color: #ff6633; }
</style>
</head>
<body>
<h1>F1 Insight</h1>
<p class="subtitle">Lap Comparison Tool</p>

<div class="card">
  <div id="mode-badge" style="display:none"></div>

  <div class="row three">
    <div class="field">
      <label>Year</label>
      <select id="year">
        <option value="2026">2026</option>
        <option value="2025">2025</option>
        <option value="2024" selected>2024</option>
        <option value="2023">2023</option>
        <option value="2022">2022</option>
        <option value="2021">2021</option>
        <option value="2020">2020</option>
        <option value="2019">2019</option>
        <option value="2018">2018</option>
      </select>
    </div>
    <div class="field">
      <label>Session</label>
      <select id="session">
        <option value="Q" selected>Qualifying</option>
        <option value="R">Race</option>
      </select>
    </div>
    <div class="field">
      <label>Round</label>
      <input type="number" id="round" value="1" min="1" max="24">
    </div>
  </div>

  <button class="btn-load" id="btn-load" onclick="loadSession()">
    Load Session
  </button>

  <hr class="divider">

  <div class="row">
    <div class="field">
      <label>Driver 1</label>
      <select id="d1" disabled>
        <option>load session first</option>
      </select>
    </div>
    <div class="field">
      <label>Driver 2</label>
      <select id="d2" disabled>
        <option>load session first</option>
      </select>
    </div>
  </div>

  <button class="btn-run" id="btn-run" disabled onclick="runAnalysis()">
    Run Analysis
  </button>

  <div class="status-box" id="status-box"></div>
</div>

<script>
let sessionLoaded = false;

function setStatus(msg, type) {
  type = type || 'active';
  const box = document.getElementById('status-box');
  box.style.display = 'block';
  const line = document.createElement('div');
  line.className = 'status-line ' + type;
  line.textContent = '> ' + msg;
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
  return line;
}

function clearStatus() {
  document.getElementById('status-box').innerHTML = '';
}

async function loadSession() {
  clearStatus();
  const year  = document.getElementById('year').value;
  const round = document.getElementById('round').value;
  const ses   = document.getElementById('session').value;

  document.getElementById('btn-load').disabled = true;
  const line = setStatus('Loading ' + year + ' Round ' + round + ' ' + ses + '...');

  try {
    const res = await fetch('/load_session', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ year, round, session: ses })
    });
    const data = await res.json();

    if (data.error) {
      line.className = 'status-line error';
      line.textContent = 'x ' + data.error;
      document.getElementById('btn-load').disabled = false;
      return;
    }

    line.className = 'status-line done';
    line.textContent = 'v ' + data.event_name;

    const badge = document.getElementById('mode-badge');
    badge.style.display = 'block';
    if (parseInt(year) >= 2026) {
      badge.className = 'mode-badge mode-2026';
      badge.textContent = '2026 Regs - Battery Mode';
    } else {
      badge.className = 'mode-badge mode-pre';
      badge.textContent = 'Pre-2026 - DRS Mode';
    }

    const d1 = document.getElementById('d1');
    const d2 = document.getElementById('d2');
    d1.innerHTML = ''; d2.innerHTML = '';
    data.drivers.forEach(function(d) {
      d1.appendChild(new Option(d.code + ' - ' + d.name, d.code));
      d2.appendChild(new Option(d.code + ' - ' + d.name, d.code));
    });
    if (data.drivers.length > 1) d2.selectedIndex = 1;

    d1.disabled = false;
    d2.disabled = false;
    document.getElementById('btn-run').disabled = false;
    document.getElementById('btn-load').disabled = false;
    sessionLoaded = true;

  } catch(e) {
    line.className = 'status-line error';
    line.textContent = 'x Connection error';
    document.getElementById('btn-load').disabled = false;
  }
}

async function runAnalysis() {
  if (!sessionLoaded) return;
  const year    = document.getElementById('year').value;
  const round   = document.getElementById('round').value;
  const ses     = document.getElementById('session').value;
  const driver1 = document.getElementById('d1').value;
  const driver2 = document.getElementById('d2').value;

  if (driver1 === driver2) {
    setStatus('Select two different drivers', 'error');
    return;
  }

  document.getElementById('btn-run').disabled = true;
  document.getElementById('btn-load').disabled = true;

  const evtSource = new EventSource(
    '/run?year=' + year + '&round=' + round +
    '&session=' + ses + '&d1=' + driver1 + '&d2=' + driver2
  );

  evtSource.onmessage = function(e) {
    const msg = JSON.parse(e.data);
    if (msg.type === 'status') {
      setStatus(msg.text);
    } else if (msg.type === 'done') {
      setStatus(msg.text, 'done');
      evtSource.close();
      setTimeout(function() {
        window.open('/output', '_blank');
        document.getElementById('btn-run').disabled = false;
        document.getElementById('btn-load').disabled = false;
      }, 800);
    } else if (msg.type === 'error') {
      setStatus(msg.text, 'error');
      evtSource.close();
      document.getElementById('btn-run').disabled = false;
      document.getElementById('btn-load').disabled = false;
    }
  };
}
</script>
</body>
</html>'''

output_html_store = {'html': None}


@app.route('/')
def index():
    return LAUNCHER_HTML


@app.route('/load_session', methods=['POST'])
def load_session():
    body    = request.get_json()
    year    = int(body['year'])
    rnd     = int(body['round'])
    session = body['session']
    try:
        ses = fastf1.get_session(year, rnd, session)
        ses.load(telemetry=False, weather=False,
                 messages=False, laps=True)
        drivers = []
        for abbr in ses.drivers:
            try:
                info = ses.get_driver(abbr)
                full = info.get('FullName', abbr)
                drivers.append({'code': abbr, 'name': full})
            except Exception:
                drivers.append({'code': abbr, 'name': abbr})
        return jsonify({
            'event_name': ses.event['EventName'],
            'drivers': drivers
        })
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/run')
def run():
    year    = int(request.args.get('year'))
    rnd     = int(request.args.get('round'))
    session = request.args.get('session')
    d1_code = request.args.get('d1')
    d2_code = request.args.get('d2')

    def generate():
        def send(msg, typ='status'):
            yield 'data: ' + json.dumps(
                {'type': typ, 'text': msg}) + '\n\n'

        try:
            yield from send(
                'Loading ' + str(year) + ' Round ' +
                str(rnd) + ' ' + session + '...')
            ses = fastf1.get_session(year, rnd, session)
            ses.load()

            yield from send('Fetching fastest laps...')
            lap1 = ses.laps.pick_drivers(d1_code).pick_fastest()
            lap2 = ses.laps.pick_drivers(d2_code).pick_fastest()

            yield from send('Processing telemetry...')
            t1 = lap1.get_telemetry().add_distance()
            t2 = lap2.get_telemetry().add_distance()

            N    = 1000
            dist = np.linspace(
                0,
                min(t1['Distance'].max(), t2['Distance'].max()),
                N)

            speed1    = np.interp(dist, t1['Distance'], t1['Speed'])
            speed2    = np.interp(dist, t2['Distance'], t2['Speed'])
            throttle1 = np.interp(dist, t1['Distance'], t1['Throttle'])
            throttle2 = np.interp(dist, t2['Distance'], t2['Throttle'])
            brake1    = np.interp(
                dist, t1['Distance'],
                t1['Brake'].astype(float)) * 100
            brake2    = np.interp(
                dist, t2['Distance'],
                t2['Brake'].astype(float)) * 100
            gear1     = np.interp(
                dist, t1['Distance'],
                t1['nGear'].astype(float))
            gear2     = np.interp(
                dist, t2['Distance'],
                t2['nGear'].astype(float))
            x1 = np.interp(dist, t1['Distance'], t1['X'])
            y1 = np.interp(dist, t1['Distance'], t1['Y'])
            x2 = np.interp(dist, t2['Distance'], t2['X'])
            y2 = np.interp(dist, t2['Distance'], t2['Y'])

            offset = int(np.argmin(
                np.sqrt((x2 - x1[0])**2 + (y2 - y1[0])**2)))
            x2 = np.roll(x2, -offset)
            y2 = np.roll(y2, -offset)

            yield from send('Computing lap time delta...')
            ds    = np.diff(dist)
            time1 = np.concatenate(
                [[0], np.cumsum(ds / (speed1[:-1] / 3.6))])
            time2 = np.concatenate(
                [[0], np.cumsum(ds / (speed2[:-1] / 3.6))])
            delta       = time2 - time1
            final_delta = float(delta[-1])

            d_min   = float(delta.min())
            d_max   = float(delta.max())
            d_pad   = max(0.05, (d_max - d_min) * 0.15)
            d_lo    = round(d_min - d_pad, 2)
            d_hi    = round(d_max + d_pad, 2)
            d_step  = round((d_hi - d_lo) / 4, 2)
            d_ticks = [round(d_lo + i * d_step, 2) for i in range(5)]
            delta_panel = (
                "{ label:'\u0394 Time (s)', k1:'delta',"
                " k2:null, min:" + str(d_lo) +
                ", max:" + str(d_hi) +
                ", ticks:" + str(d_ticks) + " },"
            )

            def fmt(td):
                s = td.total_seconds()
                return (str(int(s // 60)) + ':' +
                        '{:06.3f}'.format(s % 60))

            d1_time     = fmt(lap1['LapTime'])
            d2_time     = fmt(lap2['LapTime'])
            lap_seconds = float(lap1['LapTime'].total_seconds())

            drs_zones = []
            if year < 2026:
                drs1 = np.interp(
                    dist, t1['Distance'],
                    t1['DRS'].astype(float))
                drs2 = np.interp(
                    dist, t2['Distance'],
                    t2['DRS'].astype(float))
                active = (drs1 > 9) | (drs2 > 9)
                in_z = False
                for i, a in enumerate(active):
                    if a and not in_z:
                        zs = float(dist[i])
                        in_z = True
                    elif not a and in_z:
                        drs_zones.append([zs, float(dist[i])])
                        in_z = False
                if in_z:
                    drs_zones.append([zs, float(dist[-1])])

            battery_soc = []
            if year >= 2026:
                quali_sessions = ['Q', 'FP1', 'FP2', 'FP3', 'SQ']
                reserve = 0.0 if session in quali_sessions else 0.15
                reserve_str = (
                    '0% reserve - full deploy'
                    if reserve == 0.0
                    else '15% reserve - race strategy'
                )
                yield from send(
                    'Modelling battery SOC (' +
                    reserve_str +
                    ', straight-only, corner-gated, 95% start)...')

                MGU_K_POWER      = 350000
                HARVEST_POWER    = 33000
                CAPACITY_J       = 4000000
                CORNER_THRESHOLD = 0.15

                dx  = np.gradient(x1)
                dy  = np.gradient(y1)
                ddx = np.gradient(dx)
                ddy = np.gradient(dy)
                curvature = np.abs(
                    dx * ddy - dy * ddx) / (
                    (dx**2 + dy**2)**1.5 + 1e-10)
                curv_norm = curvature / (
                    curvature.max() + 1e-10)

                soc = CAPACITY_J * 0.95

                for i in range(N):
                    spd       = speed1[i] / 3.6
                    thr       = throttle1[i] / 100
                    brk       = brake1[i] / 100
                    dt        = (dist[1] - dist[0]) / max(spd, 1)
                    in_corner = curv_norm[i] > CORNER_THRESHOLD

                    if brk > 0.1:
                        soc = min(CAPACITY_J,
                                  soc + HARVEST_POWER * dt)
                    elif (thr > 0.95
                          and not in_corner
                          and speed1[i] > 200
                          and soc > CAPACITY_J * reserve):
                        soc = max(CAPACITY_J * reserve,
                                  soc - MGU_K_POWER * dt * 0.3)
                    elif thr < 0.5 and brk < 0.1:
                        soc = min(CAPACITY_J,
                                  soc + HARVEST_POWER * dt * 0.3)

                    battery_soc.append(
                        round(soc / CAPACITY_J * 100, 1))

            yield from send('Building track map...')
            x1n = (x1 - x1.min()) / (x1.max() - x1.min())
            y1n = (y1 - y1.min()) / (y1.max() - y1.min())
            x2n = (x2 - x2.min()) / (x2.max() - x2.min())
            y2n = (y2 - y2.min()) / (y2.max() - y2.min())

            corners = []
            try:
                ci = ses.get_circuit_info()
                for _, row in ci.corners.iterrows():
                    idx = int(np.argmin(
                        np.abs(dist - float(row['Distance']))))
                    corners.append({
                        'number': int(row['Number']),
                        'x':      float(x1n[idx]),
                        'y':      float(y1n[idx])
                    })
            except Exception:
                pass

            C1 = '#3671C6'
            C2 = '#E8002D'
            event_name = ses.event['EventName']

            speed_panel = (
                "{ label:'Speed (km/h)', k1:'speed1',"
                " k2:'speed2', min:50, max:330,"
                " ticks:[100,150,200,250,300] },"
            )
            throttle_panel = (
                "{ label:'Throttle (%)', k1:'throttle1',"
                " k2:'throttle2', min:0, max:100,"
                " ticks:[25,50,75,100] },"
            )
            brake_panel = (
                "{ label:'Brake (%)', k1:'brake1',"
                " k2:'brake2', min:0, max:100,"
                " ticks:[50,100] },"
            )
            gear_panel = (
                "{ label:'Gear', k1:'gear1', k2:'gear2',"
                " min:1, max:8, ticks:[2,3,4,5,6,7,8] },"
            )
            battery_panel = (
                "{ label:'Battery SOC (%)', k1:'battery_soc',"
                " k2:null, min:0, max:100,"
                " ticks:[25,50,75,100] },"
            )

            if year >= 2026:
                panels_js = (
                    "[\n  " + speed_panel +
                    "\n  " + delta_panel +
                    "\n  " + throttle_panel +
                    "\n  " + brake_panel +
                    "\n  " + battery_panel +
                    "\n  " + gear_panel +
                    "\n]"
                )
                mode_label = '2026 REGS - BATTERY MODE | NO DRS'
                drs_label  = ''
                extra_col  = ' - Battery SOC'
                bat_row = (
                    "<tr><td class='lbl'>Battery</td>"
                    "<td colspan='2' id='inf-bat' "
                    "style='color:#ff9933;font-weight:600;"
                    "text-align:right'>-</td></tr>"
                )
            else:
                panels_js = (
                    "[\n  " + speed_panel +
                    "\n  " + delta_panel +
                    "\n  " + throttle_panel +
                    "\n  " + brake_panel +
                    "\n  " + gear_panel +
                    "\n]"
                )
                mode_label = 'PRE-2026 REGS | DRS ACTIVE'
                drs_label  = 'Green = DRS zones'
                extra_col  = ''
                bat_row    = ''

            drs_note = (' | ' + drs_label) if drs_label else ''

            data = {
                'dist':        dist.tolist(),
                'speed1':      speed1.tolist(),
                'speed2':      speed2.tolist(),
                'throttle1':   throttle1.tolist(),
                'throttle2':   throttle2.tolist(),
                'brake1':      brake1.tolist(),
                'brake2':      brake2.tolist(),
                'gear1':       gear1.tolist(),
                'gear2':       gear2.tolist(),
                'delta':       delta.tolist(),
                'x1':          x1n.tolist(),
                'y1':          y1n.tolist(),
                'x2':          x2n.tolist(),
                'y2':          y2n.tolist(),
                'drs_zones':   drs_zones,
                'battery_soc': battery_soc,
                'corners':     corners,
                'driver1':     d1_code,
                'driver2':     d2_code,
                'c1':          C1,
                'c2':          C2,
                'final_delta': round(final_delta, 3),
                'd1_time':     d1_time,
                'd2_time':     d2_time,
                'year':        year,
                'race':        event_name,
                'session':     session,
                'lap_seconds': lap_seconds,
                'is_2026':     year >= 2026,
            }

            yield from send('Generating visualisation...')

            gap_str = (
                ('+' if final_delta >= 0 else '') +
                str(round(final_delta, 3)) + 's'
            )

            js = (
                'const D = ' + json.dumps(data) + ';\n'
                'const N = D.dist.length;\n'
                'const PANELS = ' + panels_js + ';\n\n'
                'const tel=document.getElementById("telemetry");\n'
                'const tctx=tel.getContext("2d");\n'
                'const trk=document.getElementById("track");\n'
                'const rctx=trk.getContext("2d");\n'
                'const PAD_L=56,PAD_R=12,PAD_T=28,PAD_B=10,X_AXIS_H=22;\n\n'
                'function initCanvas(){\n'
                '  tel.width=tel.offsetWidth;\n'
                '  tel.height=tel.offsetHeight;\n'
                '  trk.width=trk.offsetWidth;\n'
                '  trk.height=trk.offsetHeight;\n'
                '}\n'
                'function pxD(dv){\n'
                '  return PAD_L+(dv/D.dist[N-1])*(tel.width-PAD_L-PAD_R);\n'
                '}\n'
                'function pyV(val,min,max,y0,h){\n'
                '  return y0+h-((val-min)/(max-min))*h;\n'
                '}\n'
                'function drawTelemetry(cur){\n'
                '  var W=tel.width,H=tel.height;\n'
                '  tctx.clearRect(0,0,W,H);\n'
                '  tctx.fillStyle="#0a0a0a";\n'
                '  tctx.fillRect(0,0,W,H);\n'
                '  var usableH=H-X_AXIS_H;\n'
                '  var panelSlot=usableH/PANELS.length;\n'
                '  var plotH=panelSlot-PAD_T-PAD_B;\n'
                '  PANELS.forEach(function(p,pi){\n'
                '    var y0=pi*panelSlot+PAD_T;\n'
                '    tctx.fillStyle="#fff";\n'
                '    tctx.font="bold 11px Segoe UI";\n'
                '    tctx.textAlign="left";\n'
                '    tctx.fillText(p.label,PAD_L,y0-8);\n'
                '    if(!D.is_2026){\n'
                '      D.drs_zones.forEach(function(z){\n'
                '        tctx.fillStyle="rgba(0,200,0,0.07)";\n'
                '        tctx.fillRect(pxD(z[0]),y0,pxD(z[1])-pxD(z[0]),plotH);\n'
                '      });\n'
                '    }\n'
                '    if(D.is_2026&&p.k1==="battery_soc"){\n'
                '      var warningY=pyV(25,p.min,p.max,y0,plotH);\n'
                '      tctx.fillStyle="rgba(255,50,0,0.06)";\n'
                '      tctx.fillRect(PAD_L,warningY,W-PAD_L-PAD_R,y0+plotH-warningY);\n'
                '    }\n'
                '    p.ticks.forEach(function(tv){\n'
                '      var gy=pyV(tv,p.min,p.max,y0,plotH);\n'
                '      tctx.strokeStyle=tv===0?"#2a2a2a":"#161616";\n'
                '      tctx.lineWidth=tv===0?1:0.5;\n'
                '      tctx.beginPath();\n'
                '      tctx.moveTo(PAD_L,gy);tctx.lineTo(W-PAD_R,gy);\n'
                '      tctx.stroke();\n'
                '    });\n'
                '    if(p.k1==="delta"){\n'
                '      var zeroY=pyV(0,p.min,p.max,y0,plotH);\n'
                '      tctx.strokeStyle="rgba(255,255,255,0.15)";\n'
                '      tctx.lineWidth=1;\n'
                '      tctx.setLineDash([3,3]);\n'
                '      tctx.beginPath();\n'
                '      tctx.moveTo(PAD_L,zeroY);tctx.lineTo(W-PAD_R,zeroY);\n'
                '      tctx.stroke();\n'
                '      tctx.setLineDash([]);\n'
                '    }\n'
                '    tctx.strokeStyle="rgba(255,255,255,0.6)";\n'
                '    tctx.lineWidth=1;\n'
                '    tctx.beginPath();\n'
                '    tctx.moveTo(PAD_L,y0);tctx.lineTo(PAD_L,y0+plotH);\n'
                '    tctx.stroke();\n'
                '    tctx.strokeStyle="rgba(255,255,255,0.2)";\n'
                '    tctx.lineWidth=0.5;\n'
                '    tctx.beginPath();\n'
                '    tctx.moveTo(PAD_L,y0+plotH);tctx.lineTo(W-PAD_R,y0+plotH);\n'
                '    tctx.stroke();\n'
                '    p.ticks.forEach(function(tv){\n'
                '      var gy=pyV(tv,p.min,p.max,y0,plotH);\n'
                '      tctx.strokeStyle="rgba(255,255,255,0.5)";\n'
                '      tctx.lineWidth=1;\n'
                '      tctx.beginPath();\n'
                '      tctx.moveTo(PAD_L-4,gy);tctx.lineTo(PAD_L,gy);\n'
                '      tctx.stroke();\n'
                '      tctx.fillStyle="#fff";\n'
                '      tctx.font="9px Segoe UI";\n'
                '      tctx.textAlign="right";\n'
                '      tctx.fillText(tv,PAD_L-6,gy+3);\n'
                '    });\n'
                '    [[p.k1,D.c1],[p.k2,D.c2]].forEach(function(pair){\n'
                '      var key=pair[0],col=pair[1];\n'
                '      if(!key)return;\n'
                '      var arr=D[key];\n'
                '      if(!arr||arr.length===0)return;\n'
                '      var lineCol=key==="battery_soc"?"#ff9933":(key==="delta"?"#ffffff":col);\n'
                '      tctx.strokeStyle=lineCol;\n'
                '      tctx.lineWidth=1.5;\n'
                '      if(key==="delta"){\n'
                '        tctx.beginPath();\n'
                '        var zeroY=pyV(0,p.min,p.max,y0,plotH);\n'
                '        tctx.moveTo(pxD(D.dist[0]),zeroY);\n'
                '        for(var i=0;i<N;i++){\n'
                '          tctx.lineTo(pxD(D.dist[i]),pyV(arr[i],p.min,p.max,y0,plotH));\n'
                '        }\n'
                '        tctx.lineTo(pxD(D.dist[N-1]),zeroY);\n'
                '        tctx.closePath();\n'
                '        tctx.fillStyle="rgba(255,255,255,0.04)";\n'
                '        tctx.fill();\n'
                '      }\n'
                '      tctx.beginPath();\n'
                '      for(var i=0;i<N;i++){\n'
                '        var x=pxD(D.dist[i]);\n'
                '        var y=pyV(arr[i],p.min,p.max,y0,plotH);\n'
                '        if(i===0)tctx.moveTo(x,y);else tctx.lineTo(x,y);\n'
                '      }\n'
                '      tctx.stroke();\n'
                '    });\n'
                '    var cx=pxD(D.dist[cur]);\n'
                '    if(p.k1&&D[p.k1]&&D[p.k1].length>0){\n'
                '      var v1=D[p.k1][cur];\n'
                '      var vy1=pyV(v1,p.min,p.max,y0,plotH);\n'
                '      var lbl=p.label.indexOf("Time")>=0?(v1>=0?"+":"")+v1.toFixed(3):Math.round(v1).toString();\n'
                '      var col1=p.k1==="battery_soc"?"#ff9933":(p.k1==="delta"?"#ffffff":D.c1);\n'
                '      tctx.fillStyle=col1;\n'
                '      tctx.font="bold 10px Segoe UI";\n'
                '      tctx.textAlign="left";\n'
                '      tctx.fillText(lbl,cx+4,Math.max(y0+10,Math.min(y0+plotH-4,vy1-2)));\n'
                '    }\n'
                '    if(p.k2&&D[p.k2]&&D[p.k2].length>0){\n'
                '      var v2=D[p.k2][cur];\n'
                '      var vy2=pyV(v2,p.min,p.max,y0,plotH);\n'
                '      tctx.fillStyle=D.c2;\n'
                '      tctx.font="bold 10px Segoe UI";\n'
                '      tctx.textAlign="left";\n'
                '      tctx.fillText(Math.round(v2).toString(),cx+4,Math.max(y0+20,Math.min(y0+plotH-14,vy2+11)));\n'
                '    }\n'
                '  });\n'
                '  var xAxisY=H-X_AXIS_H+4;\n'
                '  tctx.strokeStyle="rgba(255,255,255,0.6)";\n'
                '  tctx.lineWidth=1;\n'
                '  tctx.beginPath();\n'
                '  tctx.moveTo(PAD_L,xAxisY);tctx.lineTo(W-PAD_R,xAxisY);\n'
                '  tctx.stroke();\n'
                '  var maxDist=D.dist[N-1];\n'
                '  [0,500,1000,1500,2000,2500,3000,3500,4000,4500,5000,5500].forEach(function(tv){\n'
                '    if(tv>maxDist)return;\n'
                '    var gx=pxD(tv);\n'
                '    tctx.strokeStyle="rgba(255,255,255,0.5)";\n'
                '    tctx.lineWidth=1;\n'
                '    tctx.beginPath();\n'
                '    tctx.moveTo(gx,xAxisY);tctx.lineTo(gx,xAxisY+4);\n'
                '    tctx.stroke();\n'
                '    tctx.fillStyle="#fff";\n'
                '    tctx.font="9px Segoe UI";\n'
                '    tctx.textAlign="center";\n'
                '    tctx.fillText(tv===0?"0":tv+"m",gx,xAxisY+14);\n'
                '  });\n'
                '  var cx2=pxD(D.dist[cur]);\n'
                '  tctx.strokeStyle="rgba(255,255,255,0.5)";\n'
                '  tctx.lineWidth=1;\n'
                '  tctx.setLineDash([4,4]);\n'
                '  tctx.beginPath();\n'
                '  tctx.moveTo(cx2,0);tctx.lineTo(cx2,H-X_AXIS_H);\n'
                '  tctx.stroke();\n'
                '  tctx.setLineDash([]);\n'
                '}\n'
                'function drawTrack(cur){\n'
                '  var W=trk.width,H=trk.height;\n'
                '  rctx.clearRect(0,0,W,H);\n'
                '  rctx.fillStyle="#0a0a0a";\n'
                '  rctx.fillRect(0,0,W,H);\n'
                '  var pad=32;\n'
                '  var tw=W-pad*2,th=H-pad*2;\n'
                '  function tx(xn){return pad+xn*tw;}\n'
                '  function ty(yn){return pad+(1-yn)*th;}\n'
                '  rctx.strokeStyle="rgba(255,255,255,0.1)";\n'
                '  rctx.lineWidth=10;\n'
                '  rctx.lineCap="round";rctx.lineJoin="round";\n'
                '  rctx.beginPath();\n'
                '  for(var i=0;i<N;i++){\n'
                '    if(i===0)rctx.moveTo(tx(D.x1[i]),ty(D.y1[i]));\n'
                '    else rctx.lineTo(tx(D.x1[i]),ty(D.y1[i]));\n'
                '  }\n'
                '  rctx.closePath();rctx.stroke();\n'
                '  for(var i=1;i<N;i++){\n'
                '    var t=Math.max(0,Math.min(1,(D.speed1[i]-50)/280));\n'
                '    var r=Math.round(255*Math.min(1,2*t));\n'
                '    var g=Math.round(255*Math.min(1,2*(1-t)));\n'
                '    rctx.strokeStyle="rgba("+r+","+g+",0,0.8)";\n'
                '    rctx.lineWidth=3;\n'
                '    rctx.beginPath();\n'
                '    rctx.moveTo(tx(D.x1[i-1]),ty(D.y1[i-1]));\n'
                '    rctx.lineTo(tx(D.x1[i]),ty(D.y1[i]));\n'
                '    rctx.stroke();\n'
                '  }\n'
                '  D.corners.forEach(function(c){\n'
                '    var cx=tx(c.x),cy=ty(c.y);\n'
                '    rctx.beginPath();\n'
                '    rctx.arc(cx,cy,7,0,Math.PI*2);\n'
                '    rctx.fillStyle="rgba(0,0,0,0.8)";rctx.fill();\n'
                '    rctx.strokeStyle="rgba(255,255,255,0.25)";\n'
                '    rctx.lineWidth=0.5;rctx.stroke();\n'
                '    rctx.fillStyle="#ccc";\n'
                '    rctx.font="bold 8px Segoe UI";\n'
                '    rctx.textAlign="center";\n'
                '    rctx.fillText(c.number,cx,cy+3);\n'
                '  });\n'
                '  var pairs=[[D.x1[cur],D.y1[cur],D.c1,D.driver1],\n'
                '             [D.x2[cur],D.y2[cur],D.c2,D.driver2]];\n'
                '  var ddx=tx(D.x1[cur])-tx(D.x2[cur]);\n'
                '  var ddy=ty(D.y1[cur])-ty(D.y2[cur]);\n'
                '  var screenDist=Math.sqrt(ddx*ddx+ddy*ddy);\n'
                '  if(screenDist<20&&D.delta[cur]<0){pairs=pairs.slice().reverse();}\n'
                '  pairs.forEach(function(p){\n'
                '    var dx=tx(p[0]),dy=ty(p[1]);\n'
                '    rctx.beginPath();\n'
                '    rctx.arc(dx,dy,7,0,Math.PI*2);\n'
                '    rctx.fillStyle=p[2];rctx.fill();\n'
                '    rctx.strokeStyle="#fff";rctx.lineWidth=2;rctx.stroke();\n'
                '    rctx.fillStyle="#fff";\n'
                '    rctx.font="bold 9px Segoe UI";\n'
                '    rctx.textAlign="left";\n'
                '    rctx.fillText(p[3],dx+10,dy+3);\n'
                '  });\n'
                '  [["#00cc00","Low"],["#aaaa00","Mid"],["#cc0000","High"]].forEach(function(item,i){\n'
                '    rctx.fillStyle=item[0];rctx.font="8px Segoe UI";\n'
                '    rctx.textAlign="left";\n'
                '    rctx.fillText("■ "+item[1],pad+i*55,H-6);\n'
                '  });\n'
                '}\n'
                'function updateInfo(i){\n'
                '  document.getElementById("inf-dist").textContent=Math.round(D.dist[i])+" m";\n'
                '  document.getElementById("inf-spd1").textContent=Math.round(D.speed1[i])+" km/h";\n'
                '  document.getElementById("inf-spd2").textContent=Math.round(D.speed2[i])+" km/h";\n'
                '  document.getElementById("inf-thr1").textContent=Math.round(D.throttle1[i])+"%";\n'
                '  document.getElementById("inf-thr2").textContent=Math.round(D.throttle2[i])+"%";\n'
                '  document.getElementById("inf-brk1").textContent=Math.round(D.brake1[i])+"%";\n'
                '  document.getElementById("inf-brk2").textContent=Math.round(D.brake2[i])+"%";\n'
                '  document.getElementById("inf-gr1").textContent=Math.round(D.gear1[i]);\n'
                '  document.getElementById("inf-gr2").textContent=Math.round(D.gear2[i]);\n'
                '  var bat=document.getElementById("inf-bat");\n'
                '  if(bat&&D.battery_soc.length>0){\n'
                '    var bv=D.battery_soc[i];\n'
                '    bat.textContent=Math.round(bv)+"%";\n'
                '    bat.style.color=bv<25?"#ff3300":"#ff9933";\n'
                '  }\n'
                '  var dv=D.delta[i];\n'
                '  var el=document.getElementById("inf-delta");\n'
                '  el.textContent=(dv>=0?"+":"")+dv.toFixed(3)+"s";\n'
                '  el.className=dv>=0?"dpos":"dneg";\n'
                '}\n'
                'var cursor=0,playing=false,animId=null,lastTime=null;\n'
                'var MS_PER_FRAME=(D.lap_seconds/N)*1000;\n'
                'var scrubber=document.getElementById("scrubber");\n'
                'var progLabel=document.getElementById("progress-label");\n'
                'function step(timestamp){\n'
                '  if(!playing)return;\n'
                '  if(lastTime===null)lastTime=timestamp;\n'
                '  var elapsed=timestamp-lastTime;\n'
                '  if(elapsed>=MS_PER_FRAME){\n'
                '    var steps=Math.floor(elapsed/MS_PER_FRAME);\n'
                '    cursor=(cursor+steps)%N;\n'
                '    lastTime=timestamp;\n'
                '    scrubber.value=cursor;\n'
                '    progLabel.textContent=Math.round(D.dist[cursor])+" m";\n'
                '    drawTelemetry(cursor);drawTrack(cursor);updateInfo(cursor);\n'
                '  }\n'
                '  animId=requestAnimationFrame(step);\n'
                '}\n'
                'document.getElementById("btn-play").onclick=function(){playing=true;lastTime=null;animId=requestAnimationFrame(step);};\n'
                'document.getElementById("btn-pause").onclick=function(){playing=false;cancelAnimationFrame(animId);};\n'
                'document.getElementById("btn-reset").onclick=function(){playing=false;cancelAnimationFrame(animId);cursor=0;scrubber.value=0;lastTime=null;progLabel.textContent="0 m";drawTelemetry(0);drawTrack(0);updateInfo(0);};\n'
                'scrubber.addEventListener("input",function(){playing=false;cancelAnimationFrame(animId);cursor=parseInt(scrubber.value);progLabel.textContent=Math.round(D.dist[cursor])+" m";drawTelemetry(cursor);drawTrack(cursor);updateInfo(cursor);});\n'
                'tel.addEventListener("mousemove",function(e){if(playing)return;var rect=tel.getBoundingClientRect();var t=Math.max(0,Math.min(1,(e.clientX-rect.left-PAD_L)/(tel.width-PAD_L-PAD_R)));cursor=Math.round(t*(N-1));scrubber.value=cursor;progLabel.textContent=Math.round(D.dist[cursor])+" m";drawTelemetry(cursor);drawTrack(cursor);updateInfo(cursor);});\n'
                'window.addEventListener("load",function(){initCanvas();drawTelemetry(0);drawTrack(0);updateInfo(0);});\n'
                'window.addEventListener("resize",function(){initCanvas();drawTelemetry(cursor);drawTrack(cursor);});\n'
            )

            output_html = (
                '<!DOCTYPE html><html><head>'
                '<meta charset="utf-8">'
                '<title>' + d1_code + ' vs ' + d2_code +
                ' - ' + str(year) + ' ' + event_name + '</title>'
                '<style>'
                '*{box-sizing:border-box;margin:0;padding:0;}'
                'html,body{height:100%;background:#0a0a0a;'
                'color:#fff;font-family:Segoe UI,sans-serif;overflow:hidden;}'
                '#header{padding:14px 24px;border-bottom:1px solid #222;'
                'height:64px;display:flex;align-items:center;'
                'justify-content:space-between;}'
                '#header h1{font-size:15px;font-weight:500;}'
                '#header p{font-size:11px;color:#666;margin-top:3px;}'
                '.mode{font-size:10px;color:#555;letter-spacing:1px;'
                'text-transform:uppercase;}'
                '#main{display:grid;grid-template-columns:1fr 320px;'
                'height:calc(100vh - 64px);}'
                '#left{display:flex;flex-direction:column;'
                'border-right:1px solid #1a1a1a;}'
                '#chart-area{flex:1;overflow:hidden;}'
                'canvas#telemetry{display:block;width:100%;height:100%;}'
                '#controls{height:44px;padding:0 20px;background:#0f0f0f;'
                'border-top:1px solid #1a1a1a;display:flex;'
                'align-items:center;gap:14px;}'
                '#controls button{background:#181818;border:1px solid #2a2a2a;'
                'color:#ccc;padding:5px 16px;border-radius:4px;'
                'cursor:pointer;font-size:12px;}'
                '#controls button:hover{background:#222;color:#fff;}'
                '#scrubber{flex:1;accent-color:#444;height:3px;}'
                '#progress-label{font-size:11px;color:#555;min-width:60px;}'
                '#right{display:flex;flex-direction:column;'
                'padding:14px;gap:10px;overflow:hidden;}'
                '#track-container{flex:1;min-height:0;}'
                'canvas#track{width:100%;height:100%;display:block;}'
                '#info-box{background:#0f0f0f;border:1px solid #1e1e1e;'
                'border-radius:6px;padding:12px;}'
                '#info-box table{width:100%;border-collapse:collapse;'
                'font-size:11px;}'
                '#info-box td{padding:3px 6px;}'
                '#info-box .lbl{color:#555;}'
                '#info-box .v1{color:' + C1 + ';font-weight:600;text-align:right;}'
                '#info-box .v2{color:' + C2 + ';font-weight:600;text-align:right;}'
                '#info-box .dpos{color:' + C1 + ';font-weight:600;text-align:right;}'
                '#info-box .dneg{color:' + C2 + ';font-weight:600;text-align:right;}'
                '.tag{display:inline-block;padding:2px 7px;border-radius:3px;'
                'font-size:11px;font-weight:600;margin-right:4px;}'
                '</style></head><body>'
                '<div id="header"><div><h1>'
                '<span class="tag" style="background:' + C1 + '22;color:' + C1 + '">' + d1_code + '</span>'
                ' ' + d1_time + ' &nbsp;vs&nbsp; '
                '<span class="tag" style="background:' + C2 + '22;color:' + C2 + '">' + d2_code + '</span>'
                ' ' + d2_time +
                ' &nbsp;&nbsp;<span style="color:#666;font-size:13px">Gap ' + gap_str + '</span>'
                '</h1>'
                '<p>' + str(year) + ' ' + event_name + ' - ' + session +
                ' | Speed - Delta - Throttle - Brake - Gear' +
                extra_col + drs_note + '</p>'
                '</div><span class="mode">' + mode_label + '</span></div>'
                '<div id="main">'
                '<div id="left">'
                '<div id="chart-area"><canvas id="telemetry"></canvas></div>'
                '<div id="controls">'
                '<button id="btn-play">&#9654; Play</button>'
                '<button id="btn-pause">&#9646;&#9646; Pause</button>'
                '<button id="btn-reset">&#8634; Reset</button>'
                '<input type="range" id="scrubber" min="0" max="999" value="0">'
                '<span id="progress-label">0 m</span>'
                '</div></div>'
                '<div id="right">'
                '<div id="track-container"><canvas id="track"></canvas></div>'
                '<div id="info-box"><table>'
                '<tr><td class="lbl">Distance</td>'
                '<td colspan="2" id="inf-dist" style="color:#aaa;text-align:right">-</td></tr>'
                '<tr><td class="lbl">Speed</td>'
                '<td id="inf-spd1" class="v1">-</td>'
                '<td id="inf-spd2" class="v2">-</td></tr>'
                '<tr><td class="lbl">Throttle</td>'
                '<td id="inf-thr1" class="v1">-</td>'
                '<td id="inf-thr2" class="v2">-</td></tr>'
                '<tr><td class="lbl">Brake</td>'
                '<td id="inf-brk1" class="v1">-</td>'
                '<td id="inf-brk2" class="v2">-</td></tr>'
                '<tr><td class="lbl">Gear</td>'
                '<td id="inf-gr1" class="v1">-</td>'
                '<td id="inf-gr2" class="v2">-</td></tr>'
                + bat_row +
                '<tr><td class="lbl">&#916; Time</td>'
                '<td colspan="2" id="inf-delta" class="dpos">-</td></tr>'
                '</table></div>'
                '</div></div>'
                '<script>' + js + '<' + '/script>'
                '</body></html>'
            )

            output_html_store['html'] = output_html
            yield from send(
                'Done - ' + d1_code + ' ' + d1_time +
                ' | ' + d2_code + ' ' + d2_time +
                ' | Gap ' + gap_str,
                'done'
            )

        except Exception as e:
            yield from send('Error: ' + str(e), 'error')

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@app.route('/output')
def output():
    if output_html_store['html']:
        return output_html_store['html']
    return 'No output generated yet', 404


def open_browser():
    import time
    time.sleep(1)
    webbrowser.open('http://127.0.0.1:5000')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    is_local = port == 5000
    if is_local:
        threading.Thread(target=open_browser, daemon=True).start()
        print('F1 Insight starting locally...')
        print('Opening browser at http://127.0.0.1:5000')
    app.run(debug=False, host='0.0.0.0', port=port)

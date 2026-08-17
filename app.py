### =========================================================================
### FILE 2: THE CENTRAL SCADA DASHBOARD BACKEND (app.py)
### =========================================================================
import os
import json
import time
import base64
import hmac
import hashlib
import threading
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

AZURE_CONN_STR = os.environ.get("AZURE_IOT_HUB_CONN_STR")
PI_DEVICE_ID = "RE-01"

LIVE_SCADA_DATA = {
    "s1_v": "0.0", "s1_i": "0.00", "s1_p": "0", "s1_q": "0",
    "s2_v": "0.0", "s2_i": "0.00", "s2_p": "0", "s2_q": "0",
    "s3_v": "0.0", "s3_i": "0.00", "s3_p": "0", "s3_q": "0",
    "r1_v": "0.0", "r1_i": "0.00", "r1_p": "0", "r1_q": "0",
    "r2_v": "0.0", "r2_i": "0.00", "r2_p": "0", "r2_q": "0",
    "r3_v": "0.0", "r3_i": "0.00", "r3_p": "0", "r3_q": "0",
    "relay_state": "FETCHING STREAM DATA..."
}

def parse_connection_string(conn_str):
    props = dict(item.split('=', 1) for item in conn_str.split(';'))
    return props.get('HostName'), props.get('SharedAccessKeyName'), props.get('SharedAccessKey')

def generate_sas_token(hub_host, key_name, key_val, target_uri, expiry_hours=1):
    ttl = int(time.time()) + (expiry_hours * 3600)
    encoded_uri = quote_plus(target_uri)
    string_to_sign = f"{encoded_uri}\n{ttl}"
    decoded_key = base64.b64decode(key_val)
    signature = hmac.new(decoded_key, string_to_sign.encode('utf-8'), hashlib.sha256).digest()
    return f"SharedAccessSignature sr={encoded_uri}&sig={quote_plus(base64.b64encode(signature).decode('utf-8'))}&se={ttl}&skn={key_name}"

def scada_sync_loop():
    global LIVE_SCADA_DATA
    print("🚀 [CLOUD SCADA] Background thread is actively running...", flush=True)
    while True:
        if not AZURE_CONN_STR:
            time.sleep(5)
            continue
        try:
            host, key_name, key_val = parse_connection_string(AZURE_CONN_STR)
            target_uri = f"{host}/twins/{PI_DEVICE_ID}"
            sas_token = generate_sas_token(host, key_name, key_val, target_uri)
            
            url = f"https://{target_uri}?api-version=2021-04-12"
            req = Request(url, method="GET")
            req.add_header("Authorization", sas_token)
            req.add_header("Content-Type", "application/json")
            
            with urlopen(req, timeout=5) as response:
                master_twin = json.loads(response.read().decode('utf-8'))
                if master_twin and "properties" in master_twin:
                    reported = master_twin["properties"].get("reported", {})
                    print(f"📦 [AZURE TWIN DATA RAW] -> {json.dumps(reported)}", flush=True)
                    
                    # Read directly from clean, flat keys
                    LIVE_SCADA_DATA.update({
                        "s1_v": str(reported.get("s_L1_V", "0.0")), "s1_i": str(reported.get("s_L1_I", "0.00")), "s1_p": str(reported.get("s_L1_P", "0")), "s1_q": str(reported.get("s_L1_Q", "0")),
                        "s2_v": str(reported.get("s_L2_V", "0.0")), "s2_i": str(reported.get("s_L2_I", "0.00")), "s2_p": str(reported.get("s_L2_P", "0")), "s2_q": str(reported.get("s_L2_Q", "0")),
                        "s3_v": str(reported.get("s_L3_V", "0.0")), "s3_i": str(reported.get("s_L3_I", "0.00")), "s3_p": str(reported.get("s_L3_P", "0")), "s3_q": str(reported.get("s_L3_Q", "0")),
                        "r1_v": str(reported.get("r_L1_V", "0.0")), "r1_i": str(reported.get("r_L1_I", "0.00")), "r1_p": str(reported.get("r_L1_P", "0")), "r1_q": str(reported.get("r_L1_Q", "0")),
                        "r2_v": str(reported.get("r_L2_V", "0.0")), "r2_i": str(reported.get("r_L2_I", "0.00")), "r2_p": str(reported.get("r_L2_P", "0")), "r2_q": str(reported.get("r_L2_Q", "0")),
                        "r3_v": str(reported.get("r_L3_V", "0.0")), "r3_i": str(reported.get("r_L3_I", "0.00")), "r3_p": str(reported.get("r_L3_P", "0")), "r3_q": str(reported.get("r_L3_Q", "0")),
                        "relay_state": str(reported.get("relay_state", "SYSTEM READY"))
                    })
        except Exception as e:
            print(f"💥 HTTP Ingestion Loop Error: {str(e)}", flush=True)
        time.sleep(3)

HTML_DASHBOARD = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Global SCADA Power Panel</title>
    <style>
        body { font-family: -apple-system, sans-serif; background: #0f172a; padding: 15px; margin: 0; color: #f8fafc; }
        .container { max-width: 650px; margin: auto; }
        h2 { text-align: center; color: #38bdf8; margin-bottom: 5px; }
        h5 { text-align: center; color: #94a3b8; margin-top: 0; font-weight: normal; }
        .card { background: #1e293b; padding: 20px; border-radius: 12px; margin-bottom: 15px; border: 1px solid #334155; }
        .card-title { font-size: 12px; color: #38bdf8; text-transform: uppercase; font-weight: bold; margin-bottom: 10px; }
        .card-value { font-size: 14px; font-weight: bold; color: #f8fafc; margin-top: 4px; }
        .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 12px; border-bottom: 1px solid #334155; padding-bottom: 8px; }
        .grid:last-of-type { border-bottom: none; padding-bottom: 0; }
        .btn { width: 100%; padding: 14px; font-size: 15px; font-weight: bold; border: none; border-radius: 8px; color: white; cursor: pointer; margin-top: 10px; }
        .btn-on { background: #10b981; } .btn-off { background: #ef4444; }
        #status-bar { text-align: center; font-weight: bold; padding: 12px; border-radius: 8px; background: #334155; margin-top: 15px; color: #38bdf8; }
        span.label { font-size: 10px; color: #64748b; text-transform: uppercase; display: block; }
    </style>
    <script>
        async function updateDashboard() {
            try {
                const res = await fetch('/api/telemetry');
                const data = await res.json();
                
                document.getElementById('s1-v').innerText = data.s1_v + ' V';
                document.getElementById('s1-i').innerText = data.s1_i + ' A';
                document.getElementById('s1-p').innerText = data.s1_p + ' W';
                document.getElementById('s1-q').innerText = data.s1_q + ' var';
                
                document.getElementById('s2-v').innerText = data.s2_v + ' V';
                document.getElementById('s2-i').innerText = data.s2_i + ' A';
                document.getElementById('s2-p').innerText = data.s2_p + ' W';
                document.getElementById('s2-q').innerText = data.s2_q + ' var';
                
                document.getElementById('s3-v').innerText = data.s3_v + ' V';
                document.getElementById('s3-i').innerText = data.s3_i + ' A';
                document.getElementById('s3-p').innerText = data.s3_p + ' W';
                document.getElementById('s3-q').innerText = data.s3_q + ' var';
                
                document.getElementById('r1-v').innerText = data.r1_v + ' V';
                document.getElementById('r1-i').innerText = data.r1_i + ' A';
                document.getElementById('r1-p').innerText = data.r1_p + ' W';
                document.getElementById('r1-q').innerText = data.r1_q + ' var';
                
                document.getElementById('r2-v').innerText = data.r2_v + ' V';
                document.getElementById('r2-i').innerText = data.r2_i + ' A';
                document.getElementById('r2-p').innerText = data.r2_p + ' W';
                document.getElementById('r2-q').innerText = data.r2_q + ' var';
                
                document.getElementById('r3-v').innerText = data.r3_v + ' V';
                document.getElementById('r3-i').innerText = data.r3_i + ' A';
                document.getElementById('r3-p').innerText = data.r3_p + ' W';
                document.getElementById('r3-q').innerText = data.r3_q + ' var';
                
                document.getElementById('status-bar').innerText = "SYSTEM STATE: " + data.relay_state;
            } catch (e) {}
        }
        
        async function sendCommand(state) {
            const statusBar = document.getElementById('status-bar');
            statusBar.innerText = `TRANSMITTING INTERNET OVERRIDE: FORCE ${state}...`;
            statusBar.style.color = "#38bdf8";
            try {
                const res = await fetch('/api/command', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action: state})
                });
                const out = await res.json();
                statusBar.innerText = "✔ AZURE CONFIRMATION: " + out.message;
                statusBar.style.color = "#10b981";
                await updateDashboard();
            } catch (error) { 
                statusBar.innerText = "❌ CLOUD ROUTE BLOCKED: SYSTEM UNREACHABLE";
                statusBar.style.color = "#ef4444";
                await updateDashboard();
            }
        }
        setInterval(updateDashboard, 2000);
    </script>
</head>
<body>
    <div class="container">
        <h2>⚡ Global SCADA Panel</h2>
        <h5>Mapúa MCL Electrical Engineering Capstone</h5>
        <div class="card">
            <div class="card-title">📡 Transmission Sending End (SE-01)</div>
            <div class="grid">
                <div><span class="label">L1 Voltage</span><div class="card-value" id="s1-v">0.0 V</div></div>
                <div><span class="label">L1 Current</span><div class="card-value" id="s1-i">0.00 A</div></div>
                <div><span class="label">L1 Active</span><div class="card-value" id="s1-p">0 W</div></div>
                <div><span class="label">L1 Reactive</span><div class="card-value" id="s1-q">0 var</div></div>
            </div>
            <div class="grid">
                <div><span class="label">L2 Voltage</span><div class="card-value" id="s2-v">0.0 V</div></div>
                <div><span class="label">L2 Current</span><div class="card-value" id="s2-i">0.00 A</div></div>
                <div><span class="label">L2 Active</span><div class="card-value" id="s2-p">0 W</div></div>
                <div><span class="label">L2 Reactive</span><div class="card-value" id="s2-q">0 var</div></div>
            </div>
            <div class="grid">
                <div><span class="label">L3 Voltage</span><div class="card-value" id="s3-v">0.0 V</div></div>
                <div><span class="label">L3 Current</span><div class="card-value" id="s3-i">0.00 A</div></div>
                <div><span class="label">L3 Active</span><div class="card-value" id="s3-p">0 W</div></div>
                <div><span class="label">L3 Reactive</span><div class="card-value" id="s3-q">0 var</div></div>
            </div>
        </div>
        <div class="card">
            <div class="card-title">🔌 Regulation Substation Receiving End (RE-01)</div>
            <div class="grid">
                <div><span class="label">L1 Voltage</span><div class="card-value" id="r1-v">0.0 V</div></div>
                <div><span class="label">L1 Current</span><div class="card-value" id="r1-i">0.00 A</div></div>
                <div><span class="label">L1 Active</span><div class="card-value" id="r1-p">0 W</div></div>
                <div><span class="label">L1 Reactive</span><div class="card-value" id="r1-q">0 var</div></div>
            </div>
            <div class="grid">
                <div><span class="label">L2 Voltage</span><div class="card-value" id="r2-v">0.0 V</div></div>
                <div><span class="label">L2 Current</span><div class="card-value" id="r2-i">0.00 A</div></div>
                <div><span class="label">L2 Active</span><div class="card-value" id="r2-p">0 W</div></div>
                <div><span class="label">L2 Reactive</span><div class="card-value" id="r2-q">0 var</div></div>
            </div>
            <div class="grid">
                <div><span class="label">L3 Voltage</span><div class="card-value" id="r3-v">0.0 V</div></div>
                <div><span class="label">L3 Current</span><div class="card-value" id="r3-i">0.00 A</div></div>
                <div><span class="label">L3 Active</span><div class="card-value" id="r3-p">0 W</div></div>
                <div><span class="label">L3 Reactive</span><div class="card-value" id="r3-q">0 var</div></div>
            </div>
        </div>
        <div class="card">
            <div class="card-title">🚨 SCADA Control Interface</div>
            <button class="btn btn-on" onclick="sendCommand('ON')">FORCE RELAYS ACTIVE</button>
            <button class="btn btn-off" onclick="sendCommand('OFF')">RELEASE RELAYS / SYSTEM CLEAR</button>
            <div id="status-bar">RELAY OVERRIDE: FETCHING STATE...</div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def home(): return render_template_string(HTML_DASHBOARD)

SYNC_THREAD_STARTED = False

@app.route('/api/telemetry')
def api_get_telemetry():
    global SYNC_THREAD_STARTED
    if not SYNC_THREAD_STARTED:
        threading.Thread(target=scada_sync_loop, daemon=True).start()
        SYNC_THREAD_STARTED = True
    return jsonify(LIVE_SCADA_DATA)

@app.route('/api/command', methods=['POST'])
def api_send_command():
    if not AZURE_CONN_STR: return jsonify({"status": "failed", "message": "Missing Key"}), 500
    action = request.json.get("action")
    try:
        host, key_name, key_val = parse_connection_string(AZURE_CONN_STR)
        target_uri = f"{host}/twins/{PI_DEVICE_ID}"
        sas_token = generate_sas_token(host, key_name, key_val, target_uri)
        url = f"https://{host}/twins/{PI_DEVICE_ID}/methods?api-version=2021-04-12"
        payload = json.dumps({"methodName": "SetRelay", "responseTimeoutInSeconds": 15, "payload": {"command": action}}).encode('utf-8')
        req = Request(url, data=payload, method="POST")
        req.add_header("Authorization", sas_token)
        req.add_header("Content-Type", "application/json")
        with urlopen(req, timeout=15) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return jsonify({"status": "success", "message": res_data.get("payload", {}).get("result", "Done")})
    except Exception as e: return jsonify({"status": "failed", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

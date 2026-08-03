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

# 🔑 Load secure connection data from Render environment configurations
AZURE_CONN_STR = os.environ.get("AZURE_IOT_HUB_CONN_STR")
PI_DEVICE_ID = "RE-01"
SENDER_DEVICE_ID = "SE-01"

# --- Live Global Memory Bank ---
LIVE_SCADA_DATA = {
    "sender": {"L1": {"V": 155.0, "I": 0.0}, "L2": {"V": 0.0, "I": 0.0}, "L3": {"V": 0.0, "I": 0.0}},
    "receiver": {"voltage": 0.0, "current": 0.0, "active_power": 0.0},
    "relay_state": "AWAITING FIELD DATA..."
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
    encoded_sig = quote_plus(base64.b64encode(signature).decode('utf-8'))
    return f"SharedAccessSignature sr={encoded_uri}&sig={encoded_sig}&se={ttl}&skn={key_name}"

def fetch_twin_data(host, key_name, key_val, device_id):
    try:
        target_uri = f"{host}/twins/{device_id}"
        sas_token = generate_sas_token(host, key_name, key_val, target_uri)
        url = f"https://{target_uri}?api-version=2021-04-12"
        
        req = Request(url, method="GET")
        req.add_header("Authorization", sas_token)
        req.add_header("Content-Type", "application/json")
        
        with urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception:
        return None

def scada_sync_loop():
    global LIVE_SCADA_DATA
    print("🔍 [CLOUD SCADA] Background thread is actively running...")
    while True:
        if not registry_manager:
            time.sleep(4)
            continue
            
        try:
            # Query the live Azure digital twin registry database
            twin = registry_manager.get_twin(PI_DEVICE_ID)
            
            if twin and twin.properties and twin.properties.reported:
                reported = twin.properties.reported
                
                # 💡 DEBUG PRINT: This will print the exact JSON map Azure sends your server
                print(f"📦 [AZURE TWIN DATA RAW] -> {json.dumps(reported)}")
                
                # Dynamic mapping with fallback protection checks
                if "sender" in reported:
                    s = reported["sender"]
                    LIVE_SCADA_DATA["sender"] = {
                        "L1": {"V": str(s.get('L1', {}).get('V', 0.0)), "I": str(s.get('L1', {}).get('I', 0.0))},
                        "L2": {"V": str(s.get('L2', {}).get('V', 0.0)), "I": str(s.get('L2', {}).get('I', 0.0))},
                        "L3": {"V": str(s.get('L3', {}).get('V', 0.0)), "I": str(s.get('L3', {}).get('I', 0.0))}
                    }
                else:
                    # Let's check if the keys are hidden inside an uppercase or nested format
                    print("⚠️ Key 'sender' not found in root reported layout.")
                    
                if "receiver" in reported:
                    r = reported["receiver"]
                    LIVE_SCADA_DATA["receiver"] = {
                        "voltage": str(r.get("voltage", 0.0)),
                        "current": str(r.get("current", 0.0)),
                        "active_power": str(r.get("active_power", 0.0))
                    }
                if "relay_state" in reported:
                    LIVE_SCADA_DATA["relay_state"] = str(reported["relay_state"])
                    
        except Exception as e:
            print(f"💥 SDK Ingestion Loop Error: {e}")
        time.sleep(3)


# ================= HTTP WEB INTERFACE =================

HTML_DASHBOARD = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Global SCADA Power Panel</title>
    <style>
        body { font-family: -apple-system, sans-serif; background: #0f172a; padding: 15px; margin: 0; color: #f8fafc; }
        .container { max-width: 500px; margin: auto; }
        h2 { text-align: center; color: #38bdf8; margin-bottom: 5px; }
        h5 { text-align: center; color: #94a3b8; margin-top: 0; font-weight: normal; }
        .card { background: #1e293b; padding: 20px; border-radius: 12px; margin-bottom: 15px; border: 1px solid #334155; }
        .card-title { font-size: 11px; color: #38bdf8; text-transform: uppercase; font-weight: bold; }
        .card-value { font-size: 26px; font-weight: bold; color: #f8fafc; margin-top: 5px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 10px; }
        .btn { width: 100%; padding: 14px; font-size: 15px; font-weight: bold; border: none; border-radius: 8px; color: white; cursor: pointer; margin-top: 10px; }
        .btn-on { background: #10b981; }
        .btn-off { background: #ef4444; }
        #status-bar { text-align: center; font-weight: bold; padding: 12px; border-radius: 8px; background: #334155; margin-top: 15px; color: #38bdf8; }
    </style>
    <script>

        async function updateDashboard() {
            try {
                const res = await fetch('/api/telemetry');
                const data = await res.json();
                
                // 💡 FIXED: Read values directly as clean display strings compiled by the server
                document.getElementById('s-v').innerText = data.sender.L1.V + ' V';
                document.getElementById('s-i').innerText = data.sender.L1.I + ' A';
                
                document.getElementById('r-v').innerText = data.receiver.voltage + ' V';
                document.getElementById('r-i').innerText = data.receiver.current + ' A';
                document.getElementById('r-p').innerText = data.receiver.active_power + ' W';
                
                document.getElementById('status-bar').innerText = "SYSTEM STATE: " + data.relay_state;
            } catch (e) { console.log("Parsing crash cleared."); }
        }
        
        async function sendCommand(state) {
            document.getElementById('status-bar').innerText = "TRANSMITTING COMMAND VIA AZURE...";
            try {
                const res = await fetch('/api/command', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action: state})
                });
                const out = await res.json();
                alert(out.message);
                updateDashboard();
            } catch (error) { alert("Failed to route command."); }
        }
        setInterval(updateDashboard, 2000);
    </script>
</head>
<body>
    <div class="container">
        <h2>⚡ Global SCADA Panel</h2>
        <h5>Mapúa MCL Electrical Engineering Capstone</h5>
        
        <div class="card">
            <div class="card-title">📡 Transmission Line Entry (ESP32)</div>
            <div class="grid">
                <div><span style="font-size:11px; color:#64748b;">L1 Voltage</span><div class="card-value" id="s-v">0.0 V</div></div>
                <div><span style="font-size:11px; color:#64748b;">L1 Current</span><div class="card-value" id="s-i">0.00 A</div></div>
            </div>
        </div>

        <div class="card">
            <div class="card-title">🔌 Regulation Substation (Raspberry Pi)</div>
            <div class="grid">
                <div><span style="font-size:11px; color:#64748b;">Line Voltage</span><div class="card-value" id="r-v">0.0 V</div></div>
                <div><span style="font-size:11px; color:#64748b;">Total Current</span><div class="card-value" id="r-i">0.00 A</div></div>
            </div>
            <div style="margin-top:10px;"><span style="font-size:11px; color:#64748b;">Active Load Power</span><div class="card-value" id="r-p">0 W</div></div>
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
def home():
    return render_template_string(HTML_DASHBOARD)

@app.route('/api/telemetry')
def api_get_telemetry():
    return jsonify(LIVE_SCADA_DATA)

@app.route('/api/command', methods=['POST'])
def api_send_command():
    if not AZURE_CONN_STR:
        return jsonify({"status": "failed", "message": "Missing key configuration setup."}), 500
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
            execution_msg = res_data.get("payload", {}).get("result", "Action completed.")
            return jsonify({"status": "success", "message": execution_msg})
    except Exception:
        return jsonify({"status": "failed", "message": "Pi is offline or unreachable via Azure."}), 500

# 💡 FORCED GLOBAL INITIALIZATION (Gunicorn Compatible)
print("🚀 [CLOUD INIT] Spawning global SCADA background syncing thread...")
threading.Thread(target=scada_sync_loop, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)


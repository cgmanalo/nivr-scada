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

# 🔑 Read the secure Master Key from the Render environment screen
AZURE_CONN_STR = os.environ.get("AZURE_IOT_HUB_CONN_STR")
PI_DEVICE_ID = "RE-01"

# --- Live Global Memory Bank ---
LIVE_SCADA_DATA = {
    "sender": {"L1": {"V": 0.0, "I": 0.0}, "L2": {"V": 0.0, "I": 0.0}, "L3": {"V": 0.0, "I": 0.0}},
    "receiver": {"voltage": 0.0, "current": 0.0, "active_power": 0.0},
    "relay_state": "AWAITING FIELD DATA..."
}

def parse_connection_string(conn_str):
    """Extracts credentials from standard connection strings safely"""
    props = dict(item.split('=', 1) for item in conn_str.split(';'))
    return props.get('HostName'), props.get('SharedAccessKeyName'), props.get('SharedAccessKey')

def generate_sas_token(hub_host, key_name, key_val, target_uri, expiry_hours=1):
    """Computes a secure temporary access token for the API call"""
    ttl = int(time.time()) + (expiry_hours * 3600)
    encoded_uri = quote_plus(target_uri)
    string_to_sign = f"{encoded_uri}\n{ttl}"
    
    decoded_key = base64.b64decode(key_val)
    signature = hmac.new(decoded_key, string_to_sign.encode('utf-8'), hashlib.sha256).digest()
    encoded_sig = quote_plus(base64.b64encode(signature).decode('utf-8'))
    
    return f"SharedAccessSignature sr={encoded_uri}&sig={encoded_sig}&se={ttl}&skn={key_name}"

def scada_sync_loop():
    """Pulls and parses the consolidated field station matrix with full datatype safety protection"""
    global LIVE_SCADA_DATA
    print("🚀 [CLOUD SCADA] Background thread is actively running...", flush=True)
    
    while True:
        if not AZURE_CONN_STR:
            print("⚠️ [DEBUG ERROR] AZURE_IOT_HUB_CONN_STR environment variable is EMPTY!", flush=True)
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
                    print("PRINTING THE DUMP...")
                    print(f"📦 [AZURE TWIN DATA RAW] -> {json.dumps(reported)}", flush=True)
                    
                    # 1. Map the forwarded ESP32 data structure safely with type checking
                    if "sender" in reported:
                        s = reported["sender"]
                        l1 = s.get('L1', {})
                        l2 = s.get('L2', {})
                        l3 = s.get('L3', {})
                        
                        # Helper to format values cleanly or catch -1 errors
                        fmt_v = lambda v: f"{float(v):.1f}" if float(v) >= 0 else "0.0"
                        fmt_i = lambda i: f"{float(i):.2f}" if float(i) >= 0 else "0.00"
                        
                        LIVE_SCADA_DATA["sender"] = {
                            "L1": {"V": fmt_v(l1.get('V', 0)), "I": fmt_i(l1.get('I', 0))},
                            "L2": {"V": fmt_v(l2.get('V', 0)), "I": fmt_i(l2.get('I', 0))},
                            "L3": {"V": fmt_v(l3.get('V', 0)), "I": fmt_i(l3.get('I', 0))}
                        }
                        
                    # 2. Map the local Substation data structure safely (Catches the negative float math bug)
                    if "receiver" in reported:
                        r = reported["receiver"]
                        v_rx = float(r.get("voltage", 0.0))
                        i_rx = float(r.get("current", 0.0))
                        p_rx = float(r.get("active_power", 0.0))
                        
                        LIVE_SCADA_DATA["receiver"] = {
                            "voltage": f"{v_rx:.1f}" if v_rx >= 0 else "ERR",
                            "current": f"{i_rx:.2f}" if i_rx >= 0 else "ERR",
                            "active_power": f"{p_rx:.0f}" if p_rx >= 0 else "ERR"
                        }
                        
                    if "relay_state" in reported:
                        LIVE_SCADA_DATA["relay_state"] = str(reported["relay_state"])

                    print(LIVE_SCADA_DATA)
                        
        except Exception as e:
            print(f"💥 HTTP Ingestion Loop Error: {str(e)}", flush=True)
            
        time.sleep(3)


# ================= HTML/JS VISUAL FRONT END =================

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
                // 🚀 Fetch the updated dictionary directly from your Render endpoint
                const res = await fetch('/api/telemetry');
                const data = await res.json();
                
                // 📡 1. Safely render the ESP32 Sending End data
                if (data && data.sender && data.sender.L1) {
                    try {
                        alert(data);
                        document.getElementById('s-v').innerText = (data.sender.L1.V || "0.0") + ' V';
                        document.getElementById('s-i').innerText = (data.sender.L1.I || "0.00") + ' A';
                    } catch(err) { console.log("L1 card drawing block protected."); }
                }
                
                // 🔌 2. Safely render the Raspberry Pi Receiving End data
                if (data && data.receiver) {
                    try {
                        document.getElementById('r-v').innerText = (data.receiver.voltage || "0.0") + ' V';
                        document.getElementById('r-i').innerText = (data.receiver.current || "0.00") + ' A';
                        document.getElementById('r-p').innerText = (data.receiver.active_power || "0") + ' W';
                    } catch(err) { console.log("Receiver card drawing block protected."); }
                }
                
                // 🛠️ 3. Render the operational relay tracking state
                if (data && data.relay_state) {
                    document.getElementById('status-bar').innerText = "SYSTEM STATE: " + data.relay_state;
                }
                
            } catch (e) { 
                console.log("Global JSON streaming parsing error caught securely."); 
            }
        }
        
        async function sendCommand(state) {
            const statusBar = document.getElementById('status-bar');
            statusBar.innerText = `TRANSMITTING INTERNET OVERRIDE: FORCE ${state}...`;
            statusBar.style.color = "#38bdf8"; // Changes to a warning blue shade
            
            try {
                const res = await fetch('/api/command', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action: state})
                });
                
                const out = await res.json();
                
                // 💡 CRITICAL FIX: Removed the blocking alert() completely!
                // Instead, print the success log straight to the UI text stream.
                statusBar.innerText = "✔ AZURE CONFIRMATION: " + out.message;
                statusBar.style.color = "#10b981"; // Changes text to a success green shade
                
                // Execute an immediate telemetry pass now that the UI is unblocked
                await updateDashboard();
                
            } catch (error) { 
                statusBar.innerText = "❌ CLOUD ROUTE BLOCKED: SYSTEM UNREACHABLE";
                statusBar.style.color = "#ef4444"; // Changes text to a warning red shade
                
                // Run fallback pass on failure
                await updateDashboard();
            }
        }

        
        // Execute an immediate render pass on page launch, then poll every 2 seconds
        updateDashboard();
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
        return jsonify({"status": "failed", "message": "Missing API Key configuration setup."}), 500
        
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

# 💡 Global scope thread launch (Gunicorn Compatible)
print("🚀 [CLOUD INIT] Spawning global SCADA background syncing thread...", flush=True)
threading.Thread(target=scada_sync_loop, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

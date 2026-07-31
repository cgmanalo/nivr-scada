import os
import json
from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
from azure.iot.hub import IoTHubRegistryManager
from azure.iot.hub.models import CloudToDeviceMethod

app = Flask(__name__)
CORS(app)

# 🔑 YOUR AZURE SERVICE CONNECTION STRING
AZURE_CONN_STR = os.environ.get("AZURE_IOT_HUB_CONN_STR")
PI_DEVICE_ID = "RE-01"

if not AZURE_CONN_STR:
    print("⚠️ WARNING: AZURE_IOT_HUB_CONN_STR environment variable is missing!")
else:
    registry_manager = IoTHubRegistryManager(AZURE_CONN_STR)

# Placeholder variables for display until real data is requested
MOCK_DATA = {
    "sender": {"L1": {"V": 224.5, "I": 3.12}, "L2": {"V": 223.1, "I": 2.98}, "L3": {"V": 225.0, "I": 3.05}},
    "receiver": {"voltage": 387.4, "current": 3.05, "active_power": 1950.0},
    "relay_state": "SYSTEM READY"
}

# --- HTML/JS Visual Front End (Optimized for Laptop and Mobile) ---
HTML_DASHBOARD = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Global SCADA Power Panel</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; padding: 15px; margin: 0; color: #f8fafc; }
        .container { max-width: 500px; margin: auto; }
        h2 { text-align: center; color: #38bdf8; margin-bottom: 5px; }
        h5 { text-align: center; color: #94a3b8; margin-top: 0; font-weight: normal; }
        .card { background: #1e293b; padding: 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); margin-bottom: 15px; border: 1px solid #334155; }
        .card-title { font-size: 11px; color: #38bdf8; text-transform: uppercase; font-weight: bold; letter-spacing: 1px; }
        .card-value { font-size: 26px; font-weight: bold; color: #f8fafc; margin-top: 5px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 10px; }
        .btn { width: 100%; padding: 14px; font-size: 15px; font-weight: bold; border: none; border-radius: 8px; color: white; cursor: pointer; margin-top: 10px; transition: 0.2s; }
        .btn-on { background: #10b981; }
        .btn-on:hover { background: #059669; }
        .btn-off { background: #ef4444; }
        .btn-off:hover { background: #dc2626; }
        #status-bar { text-align: center; font-weight: bold; padding: 12px; border-radius: 8px; background: #334155; margin-top: 15px; color: #38bdf8; }
    </style>
    <script>
        async function updateDashboard() {
            try {
                const res = await fetch('/api/telemetry');
                const data = await res.json();
                
                document.getElementById('s-v').innerText = data.sender.L1.V.toFixed(1) + ' V';
                document.getElementById('s-i').innerText = data.sender.L1.I.toFixed(2) + ' A';
                
                document.getElementById('r-v').innerText = data.receiver.voltage.toFixed(1) + ' V';
                document.getElementById('r-i').innerText = data.receiver.current.toFixed(2) + ' A';
                document.getElementById('r-p').innerText = data.receiver.active_power.toFixed(0) + ' W';
                
                document.getElementById('status-bar').innerText = "SYSTEM STATE: " + data.relay_state;
            } catch (e) {}
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
            } catch (error) {
                alert("Failed to route command through Azure cloud framework.");
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
    return jsonify(MOCK_DATA)

@app.route('/api/command', methods=['POST'])
def api_send_command():
    action = request.json.get("action") # Expects "ON" or "OFF"
    try:
        # Packages direct method request for the Raspberry Pi listening task
        method = CloudToDeviceMethod(method_name="SetRelay", payload={"command": action}, response_timeout_in_seconds=15)
        response = registry_manager.invoke_device_method(PI_DEVICE_ID, method)
        return jsonify({"status": "success", "message": response.payload.get("result")})
    except Exception as e:
        return jsonify({"status": "failed", "message": f"Cloud Route Blocked: Pi is likely offline."}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

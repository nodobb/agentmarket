import urllib.request
import json
import os

LOG_PATH = "/Users/noeldobbin/Downloads/agent-market/visits.log"

def check_status():
    report = []
    
    # 1. Check local server
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/", timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            report.append(f"✅ Local FastAPI Server: ONLINE (Service: {data.get('service_name')})")
    except Exception as e:
        report.append(f"❌ Local FastAPI Server: OFFLINE! (Error: {e})")
        
    # 2. Check visits log
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, "r") as f:
            lines = f.readlines()
        unique_ips = set()
        agent_visits = 0
        for line in lines:
            if "IP:" in line:
                ip = line.split("IP:")[1].split("|")[0].strip()
                if ip != "127.0.0.1":
                    unique_ips.add(ip)
                if "curl" not in line.lower() and "python" not in line.lower() and "127.0.0.1" not in line:
                    agent_visits += 1
                    
        report.append(f"📊 Traffic Summary: {len(lines)} total hits | {len(unique_ips)} unique external visitors | {agent_visits} external AI agent visits.")
    else:
        report.append("⚠️ Visits log file not found.")
        
    return "\n".join(report)

if __name__ == "__main__":
    print(check_status())

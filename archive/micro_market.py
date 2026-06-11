import http.server
import json
import threading
import urllib.request
import urllib.parse
import sys
import time

# =====================================================================
# 1. THE MICROSCOPIC SERVER (Standard Library http.server - Zero Deps)
# =====================================================================
class MicroMarketHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Suppress default logging to keep terminal output clean

    def do_GET(self):
        if self.path == '/':
            # Micro Manifest
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            manifest = {
                "service": "MicroCompute",
                "price_per_ms": 0.01,
                "instructions": "POST to /dry-run with {'quantity_ms': N} to get a token."
            }
            self.wfile.write(json.dumps(manifest).encode('utf-8'))
            
        elif self.path.startswith('/products'):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"item": "1-GPU-Millisecond", "price": 0.01}).encode('utf-8'))
        else:
            self.send_error(404)

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        payload = json.loads(post_data.decode('utf-8'))

        if self.path == '/dry-run':
            quantity = payload.get("quantity_ms", 1)
            budget = payload.get("budget", 1.0)
            total = round(quantity * 0.01, 2)
            
            requires_approval = total > budget
            
            response = {
                "handshake_token": f"hs_micro_{int(time.time())}",
                "total_cost": total,
                "requires_human_approval": requires_approval,
                "reason": f"Cost ${total:.2f} exceeds micro-budget of ${budget:.2f}." if requires_approval else None
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        elif self.path == '/commit':
            token = payload.get("handshake_token", "")
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "receipt": "rec_tiny_12345",
                "status": "completed",
                "message": f"Successfully activated resource using token {token}!"
            }).encode('utf-8'))
        else:
            self.send_error(404)

def run_server():
    server = http.server.HTTPServer(('127.0.0.1', 8888), MicroMarketHandler)
    server.serve_forever()

# =====================================================================
# 2. THE MICROSCOPIC AGENT CLIENT
# =====================================================================
def run_agent():
    time.sleep(1) # Let server start
    print("=" * 60)
    print("      TINY AGENT-TO-API PROGRAMMATIC HANDSHAKE")
    print("=" * 60)

    # Step 1: Discover
    print("[\033[94mAgent\033[0m] Hitting tiny manifest...")
    req = urllib.request.urlopen("http://127.0.0.1:8888/")
    manifest = json.loads(req.read().decode('utf-8'))
    print(f"[\033[93mAPI\033[0m] Manifest: {manifest}")

    # Case A: Buy 5ms (Cost $0.05, Budget $0.10) -> Success!
    print("\n[\033[94mAgent\033[0m] Trying to buy 5ms GPU time (Budget: $0.10)...")
    data = json.dumps({"quantity_ms": 5, "budget": 0.10}).encode('utf-8')
    req = urllib.request.Request("http://127.0.0.1:8888/dry-run", data=data, headers={'Content-Type': 'application/json'})
    res = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))
    print(f"[\033[93mAPI\033[0m] Dry-run: {res}")

    if not res["requires_human_approval"]:
        print("[\033[94mAgent\033[0m] Budget check passed! Committing purchase...")
        commit_data = json.dumps({"handshake_token": res["handshake_token"]}).encode('utf-8')
        req_commit = urllib.request.Request("http://127.0.0.1:8888/commit", data=commit_data, headers={'Content-Type': 'application/json'})
        commit_res = json.loads(urllib.request.urlopen(req_commit).read().decode('utf-8'))
        print(f"[\033[92mSUCCESS\033[0m] Receipt: {commit_res}")
    
    # Case B: Buy 20ms (Cost $0.20, Budget $0.10) -> Safety Pause!
    print("\n[\033[94mAgent\033[0m] Trying to buy 20ms GPU time (Budget: $0.10)...")
    data_large = json.dumps({"quantity_ms": 20, "budget": 0.10}).encode('utf-8')
    req_large = urllib.request.Request("http://127.0.0.1:8888/dry-run", data=data_large, headers={'Content-Type': 'application/json'})
    res_large = json.loads(urllib.request.urlopen(req_large).read().decode('utf-8'))
    print(f"[\033[93mAPI\033[0m] Dry-run: {res_large}")

    if res_large["requires_human_approval"]:
        print("\n\033[91m[PAUSED] SAFETY GATE TRIGGERED!\033[0m")
        print(f"Reason: {res_large['reason']}")
        print("Agent refused to commit the purchase. No funds were spent.")
        print("=" * 60)

    # Exit the script
    sys.exit(0)

if __name__ == '__main__':
    # Start server in background thread so the user doesn't need 2 terminals
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    run_agent()

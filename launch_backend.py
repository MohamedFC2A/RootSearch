import os
import sys
import re
import time
import base64
import subprocess
import threading
import urllib.request

APP_KEY = "bjalhi4q"
KEY = "backend_url"
PORT = 8123
CLOUDFLARED_PATH = r"C:\Program Files (x86)\cloudflared\cloudflared.exe"

def update_key_value(url: str):
    """Base64 encodes the URL and updates keyvalue.immanuel.co"""
    try:
        # Encode URL to base64
        encoded = base64.b64encode(url.encode("utf-8")).decode("utf-8")
        # keyvalue.immanuel.co endpoint format:
        # https://keyvalue.immanuel.co/api/KeyVal/UpdateValue/{app-key}/{key}/{value}
        api_url = f"https://keyvalue.immanuel.co/api/KeyVal/UpdateValue/{APP_KEY}/{KEY}/{encoded}"
        
        req = urllib.request.Request(api_url, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            result = response.read().decode("utf-8").strip()
            if result.lower() == "true":
                print(f"[KV STORE] Successfully updated database with URL: {url}")
            else:
                print(f"[KV STORE] Warning: Server returned '{result}' when saving URL.")
    except Exception as e:
        print(f"[KV STORE] Error updating database: {e}")

def monitor_stream(stream, prefix, is_cloudflared=False):
    """Reads a stream line by line, prints it, and extracts the Cloudflare URL if found."""
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
    url_found = False
    
    for line_bytes in stream:
        line = line_bytes.decode("utf-8", errors="replace")
        # Print output to console
        sys.stdout.write(f"[{prefix}] {line}")
        sys.stdout.flush()
        
        if is_cloudflared and not url_found:
            match = url_pattern.search(line)
            if match:
                url = match.group(0)
                print(f"\n[LAUNCHER] Found Cloudflare URL: {url}")
                url_found = True
                # Run the update in a separate thread to not block stream reading
                threading.Thread(target=update_key_value, args=(url,), daemon=True).start()

def main():
    print("===================================================")
    print("   RootSearch Orchestrated Backend Launcher        ")
    print("===================================================")
    
    # 1. Start FastAPI backend (uvicorn)
    backend_cmd = [
        sys.executable, "-m", "uvicorn", "web.app:app",
        "--host", "127.0.0.1",
        "--port", str(PORT)
    ]
    print(f"[LAUNCHER] Starting FastAPI server on port {PORT}...")
    backend_proc = subprocess.Popen(
        backend_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    
    # Start thread to read backend output
    t_backend = threading.Thread(
        target=monitor_stream,
        args=(backend_proc.stdout, "BACKEND"),
        daemon=True
    )
    t_backend.start()
    
    # Wait a bit for backend to start up
    time.sleep(2)
    
    # 2. Start Cloudflare Tunnel
    if not os.path.exists(CLOUDFLARED_PATH):
        print(f"[LAUNCHER] Error: cloudflared.exe not found at {CLOUDFLARED_PATH}")
        backend_proc.terminate()
        sys.exit(1)
        
    tunnel_cmd = [
        CLOUDFLARED_PATH, "tunnel",
        "--protocol", "http2",
        "--url", f"http://127.0.0.1:{PORT}"
    ]
    print(f"[LAUNCHER] Starting Cloudflare Quick Tunnel...")
    tunnel_proc = subprocess.Popen(
        tunnel_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,  # cloudflared logs primarily to stderr
        cwd=os.path.dirname(os.path.abspath(__file__))
    )
    
    # Start thread to read cloudflared output (stderr)
    t_tunnel_err = threading.Thread(
        target=monitor_stream,
        args=(tunnel_proc.stderr, "TUNNEL", True),
        daemon=True
    )
    t_tunnel_err.start()
    
    # Start thread to read cloudflared stdout
    t_tunnel_out = threading.Thread(
        target=monitor_stream,
        args=(tunnel_proc.stdout, "TUNNEL_OUT"),
        daemon=True
    )
    t_tunnel_out.start()
    
    # Keep main thread alive and monitor processes
    try:
        while True:
            # Check if either process has exited
            backend_exit = backend_proc.poll()
            tunnel_exit = tunnel_proc.poll()
            
            if backend_exit is not None:
                print(f"[LAUNCHER] Backend process exited with code {backend_exit}.")
                break
            if tunnel_exit is not None:
                print(f"[LAUNCHER] Tunnel process exited with code {tunnel_exit}.")
                break
                
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[LAUNCHER] Shutting down gracefully...")
    finally:
        # Terminate both processes
        try:
            backend_proc.terminate()
        except:
            pass
        try:
            tunnel_proc.terminate()
        except:
            pass
        print("[LAUNCHER] Finished.")

if __name__ == "__main__":
    main()

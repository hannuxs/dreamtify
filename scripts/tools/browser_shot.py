"""Alat dev: screenshot dengan viewport HP sungguhan via Edge DevTools Protocol.
Pemakaian: python scripts/tools/browser_shot.py URL OUT.png WIDTH [HEIGHT] [--full]
Hanya stdlib (websocket minimal)."""
import base64, json, os, socket, struct, subprocess, sys, tempfile, time, urllib.request

EDGE = next(p for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"] if os.path.exists(p))
PORT = 9333


class WS:
    def __init__(self, url):
        hostport, path = url[len("ws://"):].split("/", 1)
        host, port = hostport.split(":")
        self.s = socket.create_connection((host, int(port)))
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\n"
                        f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.s.recv(1)
        self.id = 0

    def _recv_exact(self, n):
        data = b""
        while len(data) < n:
            chunk = self.s.recv(n - len(data))
            if not chunk:
                raise ConnectionError
            data += chunk
        return data

    def send(self, method, **params):
        self.id += 1
        payload = json.dumps({"id": self.id, "method": method, "params": params}).encode()
        header = bytearray([0x81])
        n = len(payload)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126); header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127); header += struct.pack(">Q", n)
        mask = os.urandom(4)
        header += mask
        self.s.sendall(bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))
        while True:
            msg = json.loads(self._recv_msg())
            if msg.get("id") == self.id:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})

    def _recv_msg(self):
        out = b""
        while True:
            b1, b2 = self._recv_exact(2)
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._recv_exact(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._recv_exact(8))[0]
            out += self._recv_exact(n)
            if b1 & 0x80:
                return out


def main():
    url, out, width = sys.argv[1], sys.argv[2], int(sys.argv[3])
    height = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4].isdigit() else 800
    full = "--full" in sys.argv
    profile = tempfile.mkdtemp()
    proc = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", f"--remote-debugging-port={PORT}",
                             f"--user-data-dir={profile}", "--hide-scrollbars", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
                page = next(t for t in targets if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.2)
        ws = WS(page["webSocketDebuggerUrl"])
        ws.send("Emulation.setDeviceMetricsOverride", width=width, height=height,
                deviceScaleFactor=1, mobile=width < 800)
        ws.send("Page.enable")
        ws.send("Page.navigate", url=url)
        time.sleep(2.5)
        clip = None
        if full:
            m = ws.send("Page.getLayoutMetrics")
            h = int(m["cssContentSize"]["height"])
            ws.send("Emulation.setDeviceMetricsOverride", width=width, height=h,
                    deviceScaleFactor=1, mobile=width < 800)
            time.sleep(0.8)
        if "--click" in sys.argv:
            sel = sys.argv[sys.argv.index("--click") + 1]
            box = ws.send("Runtime.evaluate", returnByValue=True, expression=(
                f"(()=>{{const e=document.querySelector({json.dumps(sel)});e.scrollIntoView({{block:'center'}});"
                "const r=e.getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]})()"))
            box = box["result"]["value"]
            time.sleep(0.3)
            for t in ("mousePressed", "mouseReleased"):
                ws.send("Input.dispatchMouseEvent", type=t, x=box[0], y=box[1], button="left", clickCount=1)
            time.sleep(0.5)
        if "--eval" in sys.argv:
            js = sys.argv[sys.argv.index("--eval") + 1]
            r = ws.send("Runtime.evaluate", expression=js, returnByValue=True, awaitPromise=True)
            print("eval =", r.get("result", {}).get("value"), r.get("exceptionDetails", {}).get("text", ""))
            time.sleep(1.0)
        logs = ws.send("Runtime.evaluate", expression="window.__errs ? window.__errs.join('|') : ''", returnByValue=True)
        sw = ws.send("Runtime.evaluate", expression="document.documentElement.scrollWidth+'/'+innerWidth",
                     returnByValue=True)["result"]["value"]
        print("scrollWidth/innerWidth =", sw)
        data = ws.send("Page.captureScreenshot", format="png")["data"]
        with open(out, "wb") as f:
            f.write(base64.b64decode(data))
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()

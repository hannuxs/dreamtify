"""Alat dev: skenario browser (Edge headless via CDP) — navigasi/eval/klik/screenshot + tangkap error JS.
Pemakaian: python scripts/tools/browser_flow.py skenario.json (screenshot ke $SHOT_DIR)"""
import base64, json, os, subprocess, sys, tempfile, time, urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from browser_shot import EDGE, WS  # noqa: E402

PORT = 9334
OUT = os.environ.get("SHOT_DIR", os.path.dirname(__file__))


class Browser:
    def __init__(self, width, height):
        self.profile = tempfile.mkdtemp()
        self.proc = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", f"--remote-debugging-port={PORT}",
                                      f"--user-data-dir={self.profile}", "--hide-scrollbars", "about:blank"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                page = next(t for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json")) if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.2)
        self.ws = WS(page["webSocketDebuggerUrl"])
        self.errors = []
        orig = self.ws._recv_msg

        def recv():
            raw = orig()
            msg = json.loads(raw)
            if msg.get("method") == "Runtime.exceptionThrown":
                d = msg["params"]["exceptionDetails"]
                self.errors.append("EXC " + (d.get("exception", {}).get("description") or d.get("text", ""))[:300])
            elif msg.get("method") == "Runtime.consoleAPICalled" and msg["params"]["type"] in ("error", "warning"):
                self.errors.append("CONSOLE " + " ".join(str(a.get("value", a.get("description", ""))) for a in msg["params"]["args"])[:300])
            return raw

        self.ws._recv_msg = recv
        self.ws.send("Runtime.enable")
        self.ws.send("Page.enable")
        self.size(width, height)

    def size(self, width, height):
        self.width = width
        self.ws.send("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=1,
                     mobile=width < 800)

    def go(self, url, wait=2.0):
        self.ws.send("Page.navigate", url=url)
        time.sleep(wait)

    def eval(self, js, wait=0.6):
        r = self.ws.send("Runtime.evaluate", expression=js, returnByValue=True, awaitPromise=True)
        time.sleep(wait)
        if "exceptionDetails" in r:
            return "ERROR: " + r["exceptionDetails"].get("exception", {}).get("description", "")[:200]
        return r.get("result", {}).get("value")

    def click(self, selector, wait=0.8):
        box = self.eval(f"(()=>{{const e=document.querySelector({json.dumps(selector)});if(!e)return null;"
                        "e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();"
                        "return [r.x+r.width/2,r.y+r.height/2]})()", wait=0.3)
        if not box:
            return f"TIDAK ADA {selector}"
        for t in ("mousePressed", "mouseReleased"):
            self.ws.send("Input.dispatchMouseEvent", type=t, x=box[0], y=box[1], button="left", clickCount=1)
        time.sleep(wait)
        return "ok"

    def set_file(self, selector, path):
        """Pilih file asli pada <input type=file> (memicu event change seperti pengguna)."""
        root = self.ws.send("DOM.getDocument")["root"]["nodeId"]
        node = self.ws.send("DOM.querySelector", nodeId=root, selector=selector)["nodeId"]
        if not node:
            return f"TIDAK ADA {selector}"
        self.ws.send("DOM.setFileInputFiles", files=[os.path.abspath(path)], nodeId=node)
        time.sleep(0.8)
        return "ok"

    def key(self, key, wait=1.5):
        """Tekan satu tombol keyboard (event asli)."""
        for t in ("keyDown", "keyUp"):
            self.ws.send("Input.dispatchKeyEvent", type=t, key=key, text=key if t == "keyDown" else "",
                         code=f"Key{key.upper()}", windowsVirtualKeyCode=ord(key.upper()))
        time.sleep(wait)
        return "ok"

    def shot(self, name, full=False):
        if full:
            h = int(self.ws.send("Page.getLayoutMetrics")["cssContentSize"]["height"])
            self.ws.send("Emulation.setDeviceMetricsOverride", width=self.width, height=min(h, 9000),
                         deviceScaleFactor=1, mobile=self.width < 800)
            time.sleep(0.6)
        data = self.ws.send("Page.captureScreenshot", format="png")["data"]
        with open(os.path.join(OUT, name + ".png"), "wb") as f:
            f.write(base64.b64decode(data))
        if full:
            self.size(self.width, 800)
        return name

    def close(self):
        self.proc.terminate()


def main():
    steps = json.load(open(sys.argv[1], encoding="utf-8"))
    b = Browser(*steps[0]["size"])
    try:
        for step in steps[1:]:
            kind = step["do"]
            if kind == "size":
                b.size(*step["size"]); res = "ok"
            elif kind == "go":
                b.go(step["url"], step.get("wait", 2.0)); res = "ok"
            elif kind == "eval":
                res = b.eval(step["js"], step.get("wait", 0.6))
            elif kind == "click":
                res = b.click(step["sel"], step.get("wait", 0.8))
            elif kind == "file":
                res = b.set_file(step["sel"], step["path"])
            elif kind == "key":
                res = b.key(step["key"], step.get("wait", 1.5))
            elif kind == "shot":
                res = b.shot(step["name"], step.get("full", False))
            print(f"[{kind}] {step.get('label', '')} -> {res}")
        print("JS ERRORS:", b.errors or "tidak ada")
    finally:
        b.close()


if __name__ == "__main__":
    main()

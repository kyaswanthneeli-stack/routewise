"""Generate a silent, captioned architecture explainer. Not a live app recording."""
import subprocess
import tempfile
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PROJECT = Path.cwd().name
CONTENT = {
  "agentgate": [
    ("AgentGate", ["Agent tool policy gateway", "FastAPI plus one-use approvals", "Architecture explainer; no live API capture"]),
    ("Request path", ["API key then tool allowlist", "Validation, rate cap, approval check", "Redact before and after fixed demo adapter"]),
    ("Demo sequence", ["Missing API key yields HTTP 401", "Disallowed tool yields HTTP 403", "Approval permits one simulated action"]),
    ("Engineering evidence", ["14 documented tests", "Python CI plus Docker build", "Hosting requires two private credentials"]),
    ("Boundaries", ["No real notification is sent", "Browser demo is simulated", "Not a production security certification"]),
  ],
  "routewise": [
    ("RouteWise", ["LLM model routing and failover", "Authenticated FastAPI gateway", "Architecture explainer; no live model capture"]),
    ("Request path", ["Bearer token then input validation", "Deterministic fast/reasoning selection", "429 or timeout triggers one fallback"]),
    ("Demo sequence", ["Short question selects fast", "Complex tradeoff query selects reasoning", "Mocked provider outage tests failover"]),
    ("Engineering evidence", ["14 documented tests", "Python CI plus Docker build", "Real models require backend credentials"]),
    ("Boundaries", ["Browser demo is simulated", "Heuristic, not semantic classification", "No measured cost savings"]),
  ],
  "codeatlas-mcp": [
    ("CodeAtlas MCP", ["Local code structure for Python repositories", "Python AST, SQLite, stdio MCP", "Architecture explainer; no live MCP capture"]),
    ("Index path", ["Read source without executing it", "Extract definitions and static call candidates", "Store bounded-query snapshot in SQLite"]),
    ("Query path", ["Symbol search and module summary", "Call graph and potential impacted tests", "Dynamic calls may remain unresolved"]),
    ("Engineering evidence", ["16 documented tests including MCP protocol", "Automated Python CI", "Real tokenizer measurements in CI artifact"]),
    ("Boundaries", ["Graph payload is less informative than source", "Impact candidates are not coverage", "Token counts are not agent cost savings"]),
  ],
}
def main():
    if PROJECT not in CONTENT:
        raise SystemExit("Run from one of the three project repository roots")
    target = Path("docs/walkthrough.mp4")
    target.parent.mkdir(parents=True, exist_ok=True)
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    heading = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
    body = ImageFont.truetype(font, 36)
    footer = ImageFont.truetype(font, 21)
    with tempfile.TemporaryDirectory() as temp:
        for i, (title, lines) in enumerate(CONTENT[PROJECT]):
            im = Image.new("RGB", (1280, 720), "#101b31")
            d = ImageDraw.Draw(im)
            d.rectangle((68, 82, 85, 180), fill="#67d5ff")
            d.text((118, 90), title, font=heading, fill="#ffffff")
            y = 250
            for line in lines:
                for j, part in enumerate(textwrap.wrap(line, width=48)):
                    d.text((120, y), ("- " if j == 0 else "  ") + part, font=body, fill="#dbe7f7")
                    y += 55
                y += 16
            d.text((120, 640), f"{PROJECT} | Captioned explainer | {i+1}/{len(CONTENT[PROJECT])}", font=footer, fill="#a5b5ca")
            im.save(Path(temp) / f"slide-{i:02d}.png")
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-framerate", "1/4", "-i", str(Path(temp) / "slide-%02d.png"),
            "-r", "24", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(target)
        ], check=True)
    print(f"Created captioned explainer: {target}; {target.stat().st_size} bytes")
if __name__ == "__main__":
    main()

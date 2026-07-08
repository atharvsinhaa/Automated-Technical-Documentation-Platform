import os
import subprocess
import tempfile


class MermaidRenderer:

    def render(self, mermaid_code: str, output_file: str):
        import json

        cfg = {
            "theme": "base",
            "themeVariables": {
                "fontSize": "12px",
                "fontFamily": "Arial, sans-serif"
            }
        }
        cfg_f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False)
        json.dump(cfg, cfg_f)
        cfg_f.close()

        mmd_f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".mmd", delete=False)
        mmd_f.write(mermaid_code)
        mmd_f.close()

        puppeteer_cfg = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False)
        json.dump({"args": ["--no-sandbox"]}, puppeteer_cfg)
        puppeteer_cfg.close()

        import re
        node_count = len(re.findall(r'\[.*?\]|\(.*?\)', mermaid_code))
        if node_count == 0:
            node_count = len(mermaid_code.split('\n')) // 2
        dynamic_width = max(2400, node_count * 160)
        dynamic_width = min(8000, dynamic_width)

        try:
            subprocess.run([
                "mmdc",
                "-i", mmd_f.name,
                "-o", output_file,
                "-C", cfg_f.name,
                "-p", puppeteer_cfg.name,
                "-w", str(dynamic_width),
                "-s", "3",
                "-H", "1600",
                "--backgroundColor", "white"
            ], check=True, capture_output=True)
            print(f"[RENDER] OK: {output_file}")
        except subprocess.CalledProcessError as e:
            print(f"[RENDER ERROR] {e.stderr.decode()[:200]}")
        finally:
            for f in [mmd_f.name, cfg_f.name, puppeteer_cfg.name]:
                if os.path.exists(f):
                    os.remove(f)
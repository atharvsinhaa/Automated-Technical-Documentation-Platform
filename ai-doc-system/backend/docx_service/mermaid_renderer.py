"""
docx_service/mermaid_renderer.py
────────────────────────────────────────────────────────────────
Mermaid → PNG rendering pipeline.

Flow:  Mermaid code → temp .mmd file → mmdc → PNG output
Fallback: If mmdc fails, generates a styled placeholder PNG
          via Pillow showing the diagram title.

Requires:
  - mmdc (Mermaid CLI) — installed via npm
  - Pillow — for fallback image generation
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Optional


class MermaidToPng:
    """
    Renders Mermaid diagram code to PNG images.
    """

    def __init__(
        self,
        mmdc_path: str = "mmdc",
        width: int = 1200,
        height: int = 800,
        background: str = "white",
        theme: str = "default",
        verbose: bool = True,
    ):
        self.mmdc_path = mmdc_path
        self.width = width
        self.height = height
        self.background = background
        self.theme = theme
        self.verbose = verbose

    def render(
        self,
        mermaid_code: str,
        output_dir: str,
        name: str = "diagram",
    ) -> Optional[str]:
        """
        Render a single Mermaid diagram to PNG.

        Args:
            mermaid_code: The Mermaid diagram source code.
            output_dir: Directory where the PNG will be saved.
            name: Base name for the output file (without extension).

        Returns:
            Absolute path to the generated PNG, or None on failure.
        """
        os.makedirs(output_dir, exist_ok=True)

        output_path = os.path.join(output_dir, f"{name}.png")

        # Try mmdc first
        result = self._render_with_mmdc(mermaid_code, output_path)
        if result:
            return result

        # Fallback: generate placeholder with Pillow
        self._log(f"  [mermaid] Falling back to placeholder for '{name}'")
        return self._render_placeholder(mermaid_code, output_path, name)

    def render_batch(
        self,
        diagrams: Dict[str, str],
        output_dir: str,
    ) -> Dict[str, Optional[str]]:
        """
        Render multiple diagrams.

        Args:
            diagrams: Dict of name → mermaid_code.
            output_dir: Directory for output PNGs.

        Returns:
            Dict of name → PNG path (or None on failure).
        """
        results = {}
        for name, code in diagrams.items():
            results[name] = self.render(code, output_dir, name)
        return results

    def is_available(self) -> bool:
        """Check if mmdc is installed and accessible."""
        try:
            result = subprocess.run(
                [self.mmdc_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    # ──────────────────────────────────────────────────────────
    #  mmdc rendering
    # ──────────────────────────────────────────────────────────

    def _render_with_mmdc(
        self,
        mermaid_code: str,
        output_path: str,
    ) -> Optional[str]:
        """Attempt to render using mmdc CLI."""

        # Write Mermaid code to temp file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".mmd",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(mermaid_code)
            tmp_path = tmp.name

        # Write puppeteer config for headless chromium
        import json
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            encoding="utf-8",
        ) as pcfg:
            json.dump({"args": ["--no-sandbox"]}, pcfg)
            pcfg_path = pcfg.name

        import re
        node_count = len(re.findall(r'\[.*?\]|\(.*?\)', mermaid_code))
        if node_count == 0:
            node_count = len(mermaid_code.split('\n')) // 2
        dynamic_width = max(self.width, node_count * 160)
        dynamic_width = min(8000, dynamic_width)

        try:
            cmd = [
                self.mmdc_path,
                "-i", tmp_path,
                "-o", output_path,
                "-w", str(dynamic_width),
                "-s", "3",
                "-H", str(self.height),
                "-b", self.background,
                "-t", self.theme,
                "-p", pcfg_path,
                "--quiet",
            ]

            self._log(f"  [mermaid] Rendering → {output_path}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0 and os.path.exists(output_path):
                size_kb = os.path.getsize(output_path) / 1024
                self._log(
                    f"  [mermaid] ✓ Rendered ({size_kb:.1f} KB)"
                )
                return output_path

            self._log(
                f"  [mermaid] ✗ mmdc failed: {result.stderr.strip()}"
            )
            return None

        except FileNotFoundError:
            self._log("  [mermaid] ✗ mmdc not found on PATH")
            return None

        except subprocess.TimeoutExpired:
            self._log("  [mermaid] ✗ mmdc timed out (60s)")
            return None

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            if 'pcfg_path' in locals() and os.path.exists(pcfg_path):
                os.remove(pcfg_path)

    # ──────────────────────────────────────────────────────────
    #  Pillow fallback
    # ──────────────────────────────────────────────────────────

    def _render_placeholder(
        self,
        mermaid_code: str,
        output_path: str,
        name: str,
    ) -> Optional[str]:
        """
        Generate a styled placeholder image when mmdc is unavailable.
        Shows the diagram title and first few lines of code.
        """
        try:
            from PIL import Image, ImageDraw, ImageFont

            width, height = 800, 400
            img = Image.new("RGB", (width, height), color=(242, 243, 244))
            draw = ImageDraw.Draw(img)

            # Try to use a nice font, fall back to default
            try:
                title_font = ImageFont.truetype(
                    "/System/Library/Fonts/Helvetica.ttc", 24
                )
                body_font = ImageFont.truetype(
                    "/System/Library/Fonts/Menlo.ttc", 14
                )
            except (IOError, OSError):
                title_font = ImageFont.load_default()
                body_font = ImageFont.load_default()

            # Title bar
            draw.rectangle(
                [(0, 0), (width, 50)],
                fill=(27, 42, 74),  # NAVY
            )

            # Title
            title = name.replace("_", " ").title()
            draw.text(
                (20, 12),
                f"📊 {title}",
                fill=(255, 255, 255),
                font=title_font,
            )

            # Diagram type detection
            first_line = mermaid_code.strip().split("\n")[0].strip()
            diagram_type = first_line.split()[0] if first_line else "diagram"
            draw.text(
                (20, 70),
                f"Diagram Type: {diagram_type}",
                fill=(46, 134, 193),  # ACCENT_BLUE
                font=body_font,
            )

            # Show first few lines of code
            lines = mermaid_code.strip().split("\n")[:10]
            y = 100
            for line in lines:
                draw.text(
                    (30, y),
                    line[:80],
                    fill=(44, 62, 80),  # DARK_GRAY
                    font=body_font,
                )
                y += 22

            # Footer note
            draw.text(
                (20, height - 30),
                "Install mmdc (npm install -g @mermaid-js/mermaid-cli) for full rendering",
                fill=(127, 140, 141),  # MID_GRAY
                font=body_font,
            )

            img.save(output_path, "PNG")
            self._log(f"  [mermaid] ✓ Placeholder saved: {output_path}")
            return output_path

        except ImportError:
            self._log("  [mermaid] ✗ Pillow not installed, cannot generate placeholder")
            return None

        except Exception as e:
            self._log(f"  [mermaid] ✗ Placeholder generation failed: {e}")
            return None

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)

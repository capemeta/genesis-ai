# 将天青 logo SVG 导出为多尺寸 PNG（Playwright 渲染，透明背景），并生成多尺寸 ICO
# 用法：genesis-ai-platform\.venv\Scripts\python.exe tools/export_tianqing_logo_png.py

from __future__ import annotations

import asyncio
from pathlib import Path

from PIL import Image
from playwright.async_api import async_playwright

# Windows 文件名不能包含 *，使用 @128x128 形式
SIZES = (128, 64, 48, 32, 24)
SVG_PATH = Path(r"C:\Users\csl2021\Downloads\favicon_light.svg")
OUT_DIR = Path(r"C:\Users\csl2021\Downloads")

# ICO 内嵌档位（由 128×128 高质量缩放生成，适配任务栏/标签页等）
ICO_SIZES = ((16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128))
ICO_NAME = "logo.ico"


def _wrap_svg(svg_xml: str, w: int, h: int) -> str:
    # 强制按输出像素铺满，避免子像素模糊
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <style>
    html, body {{
      margin: 0;
      padding: 0;
      width: {w}px;
      height: {h}px;
      overflow: hidden;
      background: transparent;
    }}
    svg {{
      display: block;
      width: {w}px;
      height: {h}px;
    }}
  </style>
</head>
<body>
{svg_xml}
</body>
</html>"""


def build_ico(out_dir: Path) -> None:
    """从已导出的 logo@128x128.png 生成多分辨率 ICO（透明底）。"""
    src = out_dir / "logo@128x128.png"
    if not src.is_file():
        raise FileNotFoundError(f"缺少 {src}，请先完成 PNG 导出")
    im = Image.open(src).convert("RGBA")
    try:
        out = out_dir / ICO_NAME
        im.save(out, format="ICO", sizes=list(ICO_SIZES))
        print(f"OK {out}")
    finally:
        im.close()


async def main() -> None:
    svg_xml = SVG_PATH.read_text(encoding="utf-8")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            for size in SIZES:
                page = await browser.new_page(
                    viewport={"width": size, "height": size},
                    device_scale_factor=1,
                )
                await page.set_content(_wrap_svg(svg_xml, size, size), wait_until="load")
                out = OUT_DIR / f"logo@{size}x{size}.png"
                await page.screenshot(
                    path=str(out),
                    type="png",
                    omit_background=True,
                )
                await page.close()
                print(f"OK {out}")
        finally:
            await browser.close()

    build_ico(OUT_DIR)


if __name__ == "__main__":
    asyncio.run(main())

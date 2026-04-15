"""
MinerU /file_parse 接口测试用例

服务启动方式：
    docker compose -f compose.yaml --profile api up -d
API 文档：
    http://127.0.0.1:8000/docs

实际响应结构（v2.7.6）：
{
  "backend": "hybrid-auto-engine",
  "version": "2.7.6",
  "results": {
    "<file_stem>": {
      "md_content":   str,
      "content_list": str  (JSON字符串，需 json.loads),
      "middle_json":  str  (JSON字符串，需 json.loads),
      "model_output": str  (JSON字符串，需 json.loads),
      "images":       dict { filename: "data:image/jpeg;base64,<b64>" }
    }
  }
}

输出目录结构：
  out/
  ├── response_raw.json
  ├── <stem>.md                   ← md 内图片引用为 images/xxx.jpg
  ├── images/                     ← 与 md 引用路径一致
  │   └── xxx.jpg
  ├── <stem>_content_list.json
  ├── <stem>_middle.json
  └── <stem>_model_output.json
"""

import base64
import json
import sys
from pathlib import Path

import requests

# ═══════════════════════════ 配置区（按需修改）═══════════════════════════

BASE_URL = "http://127.0.0.1:8000"
BASE_URL = "https://458c-182-84-138-168.ngrok-free.app"

base_dir = Path(r"d:\workspace\python\genesis-ai\genesis-ai-platform")
data_dir = base_dir / "tests" / "data"
INPUT_PDF    = data_dir / "2014年广东省中考化学试题(清晰扫描版).pdf"
INPUT_PDF    = data_dir / "江西开普元AI中台对外接口规范_v1.2.pdf"
INPUT_PDF    = data_dir / "标识标牌合同-扫描版.pdf"


OUT_DIR      = Path(__file__).resolve().parent / "out"

PARSE_PARAMS = {
    "output_dir":          "./output",
    "backend":             "hybrid-auto-engine",
    "lang_list":           ["ch"],
    "parse_method":        "auto",
    "formula_enable":      True,
    "table_enable":        True,
    "return_md":           True,
    "return_content_list": True,
    "return_middle_json":  True,
    "return_model_output": True,
    "return_images":       True,
    "response_format_zip": False,
    "start_page_id":       0,
    "end_page_id":         99999,
}

# ════════════════════════════════════════════════════════════════════════


def _build_form_data(params: dict) -> list:
    fields = []
    for key, val in params.items():
        if isinstance(val, list):
            for item in val:
                fields.append((key, str(item)))
        elif isinstance(val, bool):
            fields.append((key, "true" if val else "false"))
        else:
            fields.append((key, str(val)))
    return fields


def _load_field(val):
    """字段值可能是 JSON 字符串，统一 loads 成 Python 对象。"""
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return val
    return val


def _decode_image(b64_str: str) -> bytes:
    """
    解码 base64 图片，自动剥离 data URI 前缀。
    支持：
      - "data:image/jpeg;base64,/9j/4AAQ..."
      - 纯 base64 字符串
    """
    if "," in b64_str:
        # 去掉 "data:image/jpeg;base64," 这部分
        b64_str = b64_str.split(",", 1)[1]
    return base64.b64decode(b64_str)


def _save_result(result: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 完整原始响应
    raw_path = OUT_DIR / "response_raw.json"
    raw_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[saved] 完整原始响应   → {raw_path}")
    print(f"[INFO]  backend={result.get('backend')}  version={result.get('version')}\n")

    results: dict = result.get("results", {})
    if not results:
        print("[WARN] 响应中无 results 字段，请查看 response_raw.json")
        return

    for file_stem, item in results.items():
        if not isinstance(item, dict):
            continue
        print(f"── 文件: {file_stem} ──")

        # ── images：存到 out/images/，与 md 引用路径 images/xxx.jpg 一致 ──
        images = item.get("images") or item.get("image_list") or item.get("imgs")
        if images and isinstance(images, dict):
            img_dir = OUT_DIR / "images"
            img_dir.mkdir(exist_ok=True)
            for img_name, img_data in images.items():
                img_path = img_dir / img_name
                if isinstance(img_data, str):
                    img_path.write_bytes(_decode_image(img_data))
                elif isinstance(img_data, bytes):
                    img_path.write_bytes(img_data)
            print(f"[saved] images         → {img_dir}/  ({len(images)} files)")

        # ── md_content ──
        md = item.get("md_content", "")
        if md:
            p = OUT_DIR / f"{file_stem}.md"
            p.write_text(md, encoding="utf-8")
            print(f"[saved] Markdown       → {p}  ({len(md):,} chars)")

        # ── content_list ──
        raw_cl = item.get("content_list")
        if raw_cl:
            content_list = _load_field(raw_cl)
            p = OUT_DIR / f"{file_stem}_content_list.json"
            p.write_text(json.dumps(content_list, ensure_ascii=False, indent=2), encoding="utf-8")
            count = len(content_list) if isinstance(content_list, list) else "?"
            print(f"[saved] content_list   → {p}  ({count} items)")

        # ── middle_json ──
        raw_mj = item.get("middle_json")
        if raw_mj:
            middle_json = _load_field(raw_mj)
            p = OUT_DIR / f"{file_stem}_middle.json"
            p.write_text(json.dumps(middle_json, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[saved] middle_json    → {p}")

        # ── model_output ──
        raw_mo = item.get("model_output")
        if raw_mo:
            model_output = _load_field(raw_mo)
            p = OUT_DIR / f"{file_stem}_model_output.json"
            p.write_text(json.dumps(model_output, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[saved] model_output   → {p}")


def main() -> None:
    if not INPUT_PDF.exists():
        print(f"[ERROR] 输入文件不存在: {INPUT_PDF}", file=sys.stderr)
        sys.exit(1)

    url = f"{BASE_URL.rstrip('/')}/file_parse"
    print(f"[INFO] POST {url}")
    print(f"[INFO] 输入文件 : {INPUT_PDF}")
    print(f"[INFO] 输出目录 : {OUT_DIR}")
    print(f"[INFO] backend  : {PARSE_PARAMS['backend']}\n")

    with open(INPUT_PDF, "rb") as fp:
        resp = requests.post(
            url,
            files=[("files", (INPUT_PDF.name, fp, "application/pdf"))],
            data=_build_form_data(PARSE_PARAMS),
            timeout=300,
        )

    print(f"[INFO] HTTP {resp.status_code}\n")

    if not resp.ok:
        print(f"[ERROR] 请求失败:\n{resp.text}", file=sys.stderr)
        resp.raise_for_status()

    _save_result(resp.json())
    print("\n[DONE] 解析完成")


if __name__ == "__main__":
    main()

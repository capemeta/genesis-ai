from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests  # type: ignore[import-untyped]


def _build_form_data(params: Dict[str, Any]) -> List[Tuple[str, str]]:
    fields: List[Tuple[str, str]] = []
    for key, val in params.items():
        if isinstance(val, list):
            for item in val:
                fields.append((key, str(item)))
            continue
        if isinstance(val, bool):
            fields.append((key, "true" if val else "false"))
            continue
        if val is None:
            continue
        fields.append((key, str(val)))
    return fields


def _summarize_error_response(url: str, response: requests.Response) -> str:
    """提炼远端错误，优先给出可执行的排查信息。"""
    snippet = (response.text or "")[:1000]
    body_lower = snippet.lower()
    url_lower = url.lower()

    # ngrok 返回 HTML 且包含静态资源域名时，基本可以判定为隧道页或上游不可达。
    if "ngrok" in url_lower or "assets.ngrok.com" in body_lower:
        return (
            f"MinerU API request failed: status={response.status_code}, "
            f"url={url}. 检测到 ngrok HTML 响应，通常表示隧道未连到 MinerU 服务、"
            "上游服务不可用，或访问到了浏览提示页而不是 API。请检查 MINERU_BASE_URL / "
            "MINERU_FILE_PARSE_URL 是否仍然有效，并确认 /file_parse 在隧道后端可直接访问。"
        )

    content_type = response.headers.get("content-type", "")
    return (
        f"MinerU API request failed: status={response.status_code}, "
        f"url={url}, content_type={content_type}, body={snippet}"
    )


class MinerUClient:
    """
    HTTP client for MinerU /file_parse.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def _resolve_url(self) -> str:
        endpoint = str(self.config.get("mineru_file_parse_url") or "").strip()
        if not endpoint:
            endpoint = str(os.getenv("MINERU_FILE_PARSE_URL", "")).strip()
        if endpoint:
            return endpoint

        base_url = (
            str(self.config.get("mineru_base_url") or "").strip()
            or str(self.config.get("mineru_api_base_url") or "").strip()
            or str(self.config.get("base_url") or "").strip()
            or str(os.getenv("MINERU_BASE_URL", "")).strip()
            or str(os.getenv("MINERU_API_BASE_URL", "")).strip()
        )
        if not base_url:
            base_url = "http://127.0.0.1:8000"
        return f"{base_url.rstrip('/')}/file_parse"

    def _build_params(self) -> Dict[str, Any]:
        cfg = self.config
        params: Dict[str, Any] = {
            "output_dir": str(cfg.get("mineru_output_dir") or "./output"),
            "backend": str(cfg.get("mineru_backend") or cfg.get("backend") or "hybrid-auto-engine"),
            "server_url": cfg.get("mineru_server_url") or cfg.get("server_url"),
            "lang_list": cfg.get("mineru_lang_list") or cfg.get("lang_list") or ["ch"],
            "parse_method": str(cfg.get("mineru_parse_method") or cfg.get("parse_method") or "auto"),
            "formula_enable": bool(cfg.get("mineru_formula_enable", cfg.get("formula_enable", True))),
            "table_enable": bool(cfg.get("mineru_table_enable", cfg.get("table_enable", True))),
            "return_md": bool(cfg.get("mineru_return_md", cfg.get("return_md", True))),
            "return_content_list": True,
            "return_middle_json": bool(
                # 坐标换算依赖 middle_json.pdf_info[].page_size，默认开启。
                cfg.get("mineru_return_middle_json", cfg.get("return_middle_json", True))
            ),
            "return_model_output": bool(
                cfg.get("mineru_return_model_output", cfg.get("return_model_output", False))
            ),
            "return_images": bool(cfg.get("mineru_return_images", cfg.get("return_images", True))),
            "response_format_zip": bool(
                cfg.get("mineru_response_format_zip", cfg.get("response_format_zip", False))
            ),
            "start_page_id": int(cfg.get("mineru_start_page_id", cfg.get("start_page_id", 0))),
            "end_page_id": int(cfg.get("mineru_end_page_id", cfg.get("end_page_id", 99999))),
        }
        return params

    def _resolve_timeout(self) -> tuple[int, int] | int:
        """支持分别配置连接超时与读取超时，适配长时间解析任务。"""
        cfg = self.config
        connect_timeout = int(
            cfg.get("mineru_connect_timeout", os.getenv("MINERU_CONNECT_TIMEOUT", 30))
        )
        read_timeout_raw = cfg.get("mineru_read_timeout", os.getenv("MINERU_READ_TIMEOUT"))
        if read_timeout_raw is None or str(read_timeout_raw).strip() == "":
            read_timeout_raw = cfg.get("mineru_timeout", os.getenv("MINERU_TIMEOUT", 3600))
        read_timeout = int(read_timeout_raw)
        return (connect_timeout, read_timeout)

    def parse_pdf(self, file_buffer: bytes, file_name: str = "document.pdf") -> Dict[str, Any]:
        url = self._resolve_url()
        params = self._build_params()
        timeout = self._resolve_timeout()
        verify_raw = self.config.get("mineru_verify_ssl", os.getenv("MINERU_VERIFY_SSL", "true"))
        verify = str(verify_raw).strip().lower() not in {"0", "false", "no", "off"}

        files = [("files", (Path(file_name).name, io.BytesIO(file_buffer), "application/pdf"))]
        headers = {
            "Accept": "application/json",
            "ngrok-skip-browser-warning": "true",
        }
        response = requests.post(
            url,
            files=files,
            data=_build_form_data(params),
            headers=headers,
            timeout=timeout,
            verify=verify,
        )

        if not response.ok:
            raise RuntimeError(_summarize_error_response(url, response))

        try:
            result = response.json()
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"MinerU API returned invalid JSON: {exc}") from exc

        if not isinstance(result, dict):
            raise RuntimeError("MinerU API returned non-object JSON payload")
        return result

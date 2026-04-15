"""
Excel Token 超限处理工具

供 ExcelGeneralChunker 和 ExcelTableChunker 共用，
实现三级降级策略处理 embedding token 超限问题。

三级降级策略：
    第一级：key_columns 过滤
        仅用 key_columns 列构建 content，过滤掉非关键列。
        filter_columns 始终存入 metadata，不受此级影响。
    ↓ 仍超限
    第二级：按字段边界截列
        在 key_columns 内逐字段累加，到达 token 上限时停止。
        保证不在字段值中间截断，维持"字段: 值"完整颗粒。
    ↓ 仍超限（单个字段值本身极长，如"详细描述"含数千字）
    第三级：字段值内拆分
        对超长字段值做 RecursiveCharacterTextSplitter 拆分，
        拆出的多个 sub-chunk 共享同一 row_index，
        并标记 is_row_overflow=True。

设计原则：
    content（向量化层）在超限时截断。
    content_blocks（展示层）始终保留完整原始数据，不受截断影响。
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from rag.utils.token_utils import count_tokens as canonical_count_tokens

logger = logging.getLogger(__name__)

# 默认 token 计量方式："chars"（字符数近似）/ "tokenizer"（精准，需 tokenizer）
DEFAULT_TOKEN_METHOD = "chars"
# 中文字符平均 token 系数（1 汉字 ≈ 1.5 token，保守估计用 2.0）
CHARS_PER_TOKEN = 2.0
# 字段值内拆分时的最小片段长度
MIN_SPLIT_LEN = 50


def count_tokens(text: str, method: str = DEFAULT_TOKEN_METHOD, tokenizer: Any = None) -> int:
    """
    计算文本 token 数。

    Args:
        text: 待计量文本
        method: "chars"（快速近似）或 "tokenizer"（精准，需 tokenizer 参数）
        tokenizer: tokenizer 对象（method="tokenizer" 时必须传入）

    Returns:
        token 数估算值
    """
    if not text:
        return 0
    if method == "tokenizer":
        if tokenizer is not None:
            try:
                return len(tokenizer.encode(text))
            except Exception:
                pass
        # 与存库/前端展示口径保持一致：默认走 cl100k_base
        return canonical_count_tokens(text)
    # chars 模式：字符数 / CHARS_PER_TOKEN（向上取整）
    return max(1, int(len(text) / CHARS_PER_TOKEN + 0.5))


class ExcelTokenHandler:
    """
    Excel Token 超限三级降级处理器。

    同时被 ExcelGeneralChunker 和 ExcelTableChunker 使用。
    """

    def __init__(
        self,
        max_embed_tokens: int = 512,
        token_count_method: str = DEFAULT_TOKEN_METHOD,
        tokenizer: Any = None,
    ):
        """
        Args:
            max_embed_tokens: embedding 模型 token 上限（建议从 KB 配置动态读取）
            token_count_method: "chars" 或 "tokenizer"
            tokenizer: tokenizer 对象（method="tokenizer" 时传入）
        """
        self.max_embed_tokens = max_embed_tokens
        self.token_count_method = token_count_method
        self.tokenizer = tokenizer

    def handle_row(
        self,
        header: List[str],
        values: List[str],
        key_columns: Optional[List[str]] = None,
        filter_columns: Optional[List[str]] = None,
        text_prefix: str = "",
        repeat_prefix_each_chunk: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        处理单行数据，返回一个或多个 content 片段（三级降级）。

        Args:
            header: 表头列名列表
            values: 数据行值列表（已规范化为字符串）
            key_columns: 向量化列名列表（None 表示全部非过滤列参与 embedding）
            filter_columns: 过滤列名列表（不进 content，单独存 metadata）
            text_prefix: content 前缀模板（如 "政务事项: "）
            repeat_prefix_each_chunk: 是否为每个输出 chunk 都重复附加 text_prefix

        Returns:
            列表，通常只有一项；第三级降级时可能有多项（共享 row_index）。
            每项格式：{
                "content": str,
                "is_overflow": bool,
            }
        """
        filter_cols = set(filter_columns or [])
        key_cols = set(key_columns) if key_columns else None

        # 构建字段映射（过滤列不参与 content）
        fields: List[Tuple[str, str]] = []
        for col, val in zip(header, values):
            if col in filter_cols:
                continue
            if key_cols is not None and col not in key_cols:
                continue
            fields.append((col, val))

        if not fields:
            return []

        # 构建完整 content
        content = self._build_kv_text(fields, text_prefix)

        if count_tokens(content, self.token_count_method, self.tokenizer) <= self.max_embed_tokens:
            return [{"content": content, "is_overflow": False}]

        # 第一级：key_columns 过滤（若未设置 key_columns 则此级已是全量，直接进入第二级）
        if key_cols is None:
            # 无 key_columns 设置，第一级无效，直接进入第二级
            return self._level2_truncate_by_field(fields, text_prefix, repeat_prefix_each_chunk)

        # key_columns 已经是精简后的字段，仍超限，进入第二级
        return self._level2_truncate_by_field(fields, text_prefix, repeat_prefix_each_chunk)

    def handle_general_chunk(
        self,
        content: str,
        cell_max_chars: int = 200,
    ) -> str:
        """
        处理通用模式 chunk 的 token 超限（简化版三级降级）。

        第一步：截断超长单元格（content 中）。
        第二步：若仍超限，按 token 边界硬截断（最后兜底）。

        注意：content_blocks 由调用方负责保留完整数据，此函数仅处理 content。

        Args:
            content: 通用模式 chunk 的 Markdown 文本
            cell_max_chars: 单元格值最大字符数（超出则在 content 中加 "..."）

        Returns:
            处理后的 content 字符串
        """
        if count_tokens(content, self.token_count_method, self.tokenizer) <= self.max_embed_tokens:
            return content

        # 第一步：截断表格单元格内的超长内容（按 | 分割重建）
        truncated = self._truncate_markdown_cells(content, cell_max_chars)
        if count_tokens(truncated, self.token_count_method, self.tokenizer) <= self.max_embed_tokens:
            return truncated

        # 第二步：按 token 边界硬截断
        return self._hard_truncate(truncated)

    # ------------------------------------------------------------------ #
    # 私有方法
    # ------------------------------------------------------------------ #

    def _build_kv_text(self, fields: List[Tuple[str, str]], prefix: str = "") -> str:
        """构建 "字段: 值; 字段: 值" 格式文本（MaxKB/WeKnora 风格）。"""
        parts = [f"{k}: {v}" for k, v in fields if v.strip()]
        text = "; ".join(parts)
        if prefix:
            return f"{prefix}{text}"
        return text

    def _level2_truncate_by_field(
        self,
        fields: List[Tuple[str, str]],
        text_prefix: str,
        repeat_prefix_each_chunk: bool,
    ) -> List[Dict[str, Any]]:
        """
        第二级降级：按字段边界截列，处理所有字段（不丢弃剩余字段）。

        算法：遍历全部字段，按 token 预算贪心填充；
        当前字段加入后超限时：
          - 若 accumulated 非空：先提交一个 chunk，重置累积，当前字段在下次迭代重试
          - 若 accumulated 为空（该字段本身超限）：进入第三级拆分该字段值，然后继续下一字段

        可按需为每个输出 chunk 重复附加同一份前缀。
        """
        result: List[Dict[str, Any]] = []
        accumulated: List[Tuple[str, str]] = []
        first_chunk = True

        i = 0
        while i < len(fields):
            col, val = fields[i]
            current_prefix = text_prefix if (repeat_prefix_each_chunk or first_chunk) else ""
            test_fields = accumulated + [(col, val)]
            test_content = self._build_kv_text(test_fields, current_prefix)

            if count_tokens(test_content, self.token_count_method, self.tokenizer) > self.max_embed_tokens:
                if not accumulated:
                    # 该字段本身已超限，进入第三级拆分，然后继续处理后续字段
                    result.extend(self._level3_split_field_value(col, val, current_prefix))
                    first_chunk = False
                    i += 1
                else:
                    # 已累积字段合法，提交为一个 chunk，重置后重试当前字段（不推进 i）
                    result.append({
                        "content": self._build_kv_text(accumulated, current_prefix),
                        "is_overflow": False,
                    })
                    accumulated = []
                    first_chunk = False
                    # 不推进 i，下次循环重试同一字段（此时 accumulated 为空）
            else:
                accumulated.append((col, val))
                i += 1

        # 提交最后剩余的已累积字段
        if accumulated:
            current_prefix = text_prefix if (repeat_prefix_each_chunk or first_chunk) else ""
            result.append({
                "content": self._build_kv_text(accumulated, current_prefix),
                "is_overflow": False,
            })

        return result or [{"content": "", "is_overflow": False}]

    def _level3_split_field_value(
        self,
        col: str,
        val: str,
        text_prefix: str,
    ) -> List[Dict[str, Any]]:
        """
        第三级降级：字段值内拆分。
        对超长字段值按句子/段落边界拆分，产出多个 sub-chunk。
        每个 sub-chunk 标记 is_overflow=True。

        注意：拆分预算要扣除 "col: " 和 text_prefix 占用的 token，
        确保最终 content 不超过 max_embed_tokens。
        """
        if not val or not val.strip():
            return []

        # 计算固定前缀的 token 占用，从可用预算中扣除
        col_prefix = f"{col}: " if col else ""
        fixed_prefix = f"{text_prefix}{col_prefix}"
        fixed_tokens = count_tokens(fixed_prefix, self.token_count_method, self.tokenizer)
        available_tokens = max(1, self.max_embed_tokens - fixed_tokens)

        # 按剩余预算拆分字段值
        parts = _split_text(val, available_tokens, self.token_count_method, self.tokenizer)

        result = []
        for part in parts:
            content = f"{fixed_prefix}{part}"
            result.append({"content": content, "is_overflow": True})

        return result if result else [{"content": f"{fixed_prefix}{val[:200]}...", "is_overflow": True}]

    def _truncate_markdown_cells(self, markdown: str, max_chars: int) -> str:
        """截断 Markdown 表格中超长的单元格值（仅截断 content，不影响 content_blocks）。"""
        lines = markdown.split("\n")
        result = []
        for line in lines:
            if line.startswith("|") and "---" not in line:
                cells = line.split("|")
                new_cells = []
                for cell in cells:
                    stripped = cell.strip()
                    if len(stripped) > max_chars:
                        new_cells.append(f" {stripped[:max_chars]}... ")
                    else:
                        new_cells.append(cell)
                result.append("|".join(new_cells))
            else:
                result.append(line)
        return "\n".join(result)

    def _hard_truncate(self, text: str) -> str:
        """按 token 上限硬截断文本（最后兜底，保留尽可能多的字符）。"""
        if count_tokens(text, self.token_count_method, self.tokenizer) <= self.max_embed_tokens:
            return text

        lo, hi = 1, len(text)
        best = 1
        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = text[:mid]
            if count_tokens(candidate, self.token_count_method, self.tokenizer) <= self.max_embed_tokens:
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1
        return text[:best]


def _split_text(
    text: str,
    max_tokens: int,
    method: str,
    tokenizer: Any,
) -> List[str]:
    """
    按句子/段落边界拆分超长文本（简单实现，不引入额外依赖）。

    优先在以下分隔符处拆分（优先级从高到低）：
    段落换行 → 句末标点（。！？.!?）→ 逗号顿号 → 强制按字符截断
    """
    import re

    if count_tokens(text, method, tokenizer) <= max_tokens:
        return [text]

    def split_by_budget(segment: str) -> List[str]:
        """按 token 预算强制拆分，保证每一片都不超限。"""
        result: List[str] = []
        remaining = segment.strip()
        while remaining:
            if count_tokens(remaining, method, tokenizer) <= max_tokens:
                result.append(remaining)
                break
            lo, hi = 1, len(remaining)
            best = 1
            while lo <= hi:
                mid = (lo + hi) // 2
                candidate = remaining[:mid]
                if count_tokens(candidate, method, tokenizer) <= max_tokens:
                    best = mid
                    lo = mid + 1
                else:
                    hi = mid - 1
            piece = remaining[:best].strip()
            if not piece:
                piece = remaining[:1]
            result.append(piece)
            remaining = remaining[len(piece):].lstrip()
        return result

    paragraphs = [p for p in re.split(r"\n{2,}", text) if p and p.strip()]
    chunks: List[str] = []
    current = ""

    for para in paragraphs:
        candidate = (current + "\n\n" + para).strip() if current else para.strip()
        if candidate and count_tokens(candidate, method, tokenizer) <= max_tokens:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if count_tokens(para, method, tokenizer) <= max_tokens:
            current = para.strip()
            continue

        sentences = [s for s in re.split(r"(?<=[。！？.!?])", para) if s and s.strip()]
        for sent in sentences:
            sent = sent.strip()
            candidate = (current + sent).strip() if current else sent
            if candidate and count_tokens(candidate, method, tokenizer) <= max_tokens:
                current = candidate
                continue

            if current:
                chunks.append(current)
                current = ""

            if count_tokens(sent, method, tokenizer) <= max_tokens:
                current = sent
            else:
                chunks.extend(split_by_budget(sent))

    if current.strip():
        chunks.append(current.strip())

    return [c for c in chunks if c] or split_by_budget(text)

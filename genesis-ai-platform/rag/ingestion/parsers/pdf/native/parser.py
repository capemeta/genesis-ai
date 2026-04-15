import os
import pypdfium2 as pdfium  # type: ignore[import-untyped]
import pdfplumber
import logging
from typing import List, Dict, Any, Optional, Tuple
from .font_analysis import FontAnalyzer
from .layout import LayoutEngine
from .reflow import ReflowEngine
from ...ocr import OCRPipeline, OCRPipelineConfig
from ..base_pdf_parser import ParserElement

logger = logging.getLogger(__name__)

TESSERACT_SETUP_HINT = (
    "Tesseract is not configured. Please set env var TESSERACT_HOME "
    "(e.g. D:\\Software\\Tesseract-OCR)."
)

class NativePDFParser:
    """
    Native PDF Parser (Migrated to Pypdfium2 + pdfplumber)
    
    核心能力：
    1. 动态标题引擎 (font_analysis): 基于全文权重统计。
    2. 图形感知 (layout): 使用 pdfplumber 识别矢量图。
    3. 空间隔离 (layout): 彻底解决表格文本重复噪音。
    4. 语义自愈 (reflow): 智能处理断行、连字符及中英文排版。
    5. 无版权风险: 采用 Apache/BSD & MIT 协议库。
    """
    
    def __init__(self, 
                 enable_ocr: bool = False, 
                 ocr_engine: str = "auto",
                 ocr_languages: Optional[List[str]] = None,
                 extract_images: bool = False,
                 extract_tables: bool = True,
                 **kwargs):
        self.enable_ocr = enable_ocr
        self.ocr_engine = (ocr_engine or "auto").lower()
        self.ocr_languages = ocr_languages or ["ch", "en"]
        self.extract_images = extract_images
        self.extract_tables = extract_tables
        self.ocr_min_text_chars = int(kwargs.get("ocr_min_text_chars", 50))
        self.ocr_render_scale = float(kwargs.get("ocr_render_scale", 2.0))
        self.ocr_preprocess_enabled = bool(kwargs.get("ocr_preprocess_enabled", True))
        self.ocr_red_seal_suppression = bool(kwargs.get("ocr_red_seal_suppression", True))
        self.ocr_post_correction_enabled = bool(kwargs.get("ocr_post_correction_enabled", True))
        self.ocr_tesseract_psm_list = kwargs.get("ocr_tesseract_psm_list")
        self.ocr_min_confidence = float(kwargs.get("ocr_min_confidence", 45.0))
        self.ocr_legacy_mode = bool(kwargs.get("ocr_legacy_mode", False))
        self.ocr_pipeline = OCRPipeline(
            OCRPipelineConfig(
                legacy_mode=self.ocr_legacy_mode,
                preprocess_enabled=self.ocr_preprocess_enabled,
                red_seal_suppression_enabled=self.ocr_red_seal_suppression,
                post_correction_enabled=self.ocr_post_correction_enabled,
                tesseract_psm_list=self.ocr_tesseract_psm_list,
                min_confidence=self.ocr_min_confidence,
                enable_paddle_ocr=bool(kwargs.get("enable_paddle_ocr", False)),
            )
        )
        self.ocr_reflow_enabled = bool(kwargs.get("ocr_reflow_enabled", False))
        self.ocr_merge_profile = str(kwargs.get("ocr_merge_profile", "balanced")).lower()
        _ocr_merge_min_score = kwargs.get("ocr_merge_min_score")
        self.ocr_merge_min_score = None if _ocr_merge_min_score is None else float(_ocr_merge_min_score)
        self.font_analyzer = FontAnalyzer()
        self.layout_engine = LayoutEngine()
        self.reflow_engine = ReflowEngine()
        self._resolved_ocr_engine: Optional[str] = None

    def parse(self, file_path_or_data: str | bytes) -> List[ParserElement]:
        """
        解析 PDF 文件
        
        Args:
            file_path_or_data: 文件路径（str）或文件内容（bytes）
        Returns:
            List[ParserElement]: 解析后的元素列表
            
        Note:
            - 图片数据通过 metadata["image_bytes"] 传递
            - PDFRouter 会提取图片数据并转换为占位符
        """
        # 判断输入类型
        if isinstance(file_path_or_data, bytes):
            # 如果是 bytes，直接使用
            pdf_data = file_path_or_data
            # 使用 pdfium 打开主文档（从内存）
            pdf = pdfium.PdfDocument(pdf_data)
            # 使用 pdfplumber 打开用于表格和矢量图识别（从内存）
            from io import BytesIO
            plumber_pdf = pdfplumber.open(BytesIO(pdf_data))
        elif isinstance(file_path_or_data, str):
            # 如果是文件路径
            if not os.path.exists(file_path_or_data):
                raise FileNotFoundError(f"File not found: {file_path_or_data}")
            # 使用 pdfium 打开主文档
            pdf = pdfium.PdfDocument(file_path_or_data)
            # 使用 pdfplumber 打开用于表格和矢量图识别
            plumber_pdf = pdfplumber.open(file_path_or_data)
        else:
            raise TypeError(f"file_path_or_data must be str or bytes, got {type(file_path_or_data)}")
        
        all_elements: List[ParserElement] = []

        try:
            # --- 阶段 1: 全局统计扫描 ---
            # 构建一个类似 PyMuPDF dict 的结构供 FontAnalyzer 使用
            pages_dict = []
            for page_no in range(len(pdf)):
                p_dict = self._get_page_dict_compat(plumber_pdf.pages[page_no])
                pages_dict.append(p_dict)
            
            self.font_analyzer.collect_font_statistics(pages_dict)
            
            # --- 阶段 2: 精准解析与空间隔离 ---
            for page_no in range(len(pdf)):
                page = pdf[page_no]
                plumber_page = plumber_pdf.pages[page_no]
                elements = self._process_page_combined(page, plumber_page, page_no)
                all_elements.extend(elements)

            # --- 阶段 3: 语义级后处理 ---
            all_elements = self.layout_engine.filter_header_footer_statistical(all_elements, len(pdf))
            all_elements = self._filter_page_numbers(all_elements, len(pdf))
            all_elements = self._merge_cross_page_tables(all_elements)
            all_elements = self._stitch_code_sequences(all_elements)
            all_elements = self.reflow_engine.reflow(
                all_elements,
                ocr_reflow_enabled=self.ocr_reflow_enabled,
                ocr_merge_profile=self.ocr_merge_profile,
                ocr_merge_min_score=self.ocr_merge_min_score,
            )

            return all_elements

        finally:
            pdf.close()
            plumber_pdf.close()

    def _filter_page_numbers(self, elements: List[ParserElement], total_pages: int) -> List[ParserElement]:
        """
        过滤页码
        
        页码特征：
        1. 纯数字（可能包含前后缀，如 "- 1 -"、"第1页"、"Page 1"）
        2. 通常位于页面顶部或底部（y坐标接近0或接近页面高度）
        3. 内容简短（通常不超过20个字符）
        4. 数字与页码相关（1到total_pages范围内）
        """
        if not elements:
            return []
        
        import re
        
        filtered = []
        for el in elements:
            content = el["content"].strip()
            
            # 跳过空内容
            if not content:
                continue
            
            # 检查是否为纯数字或包含页码模式
            is_page_number = False
            
            # 模式1: 纯数字
            if content.isdigit():
                page_num = int(content)
                if 1 <= page_num <= total_pages + 10:  # 允许一些误差
                    is_page_number = True
            
            # 模式2: 带前后缀的页码（如 "- 1 -"、"第1页"、"Page 1"、"1/10"）
            elif len(content) <= 20:
                # 提取数字
                numbers = re.findall(r'\d+', content)
                if numbers:
                    # 检查是否只有一个主要数字，且在合理范围内
                    main_num = int(numbers[0])
                    if 1 <= main_num <= total_pages + 10:
                        # 检查是否符合常见页码格式
                        page_patterns = [
                            r'^\d+$',                    # 纯数字
                            r'^-\s*\d+\s*-$',           # - 1 -
                            r'^第\s*\d+\s*页$',         # 第1页
                            r'^Page\s+\d+$',            # Page 1
                            r'^\d+\s*/\s*\d+$',         # 1/10
                            r'^\[\s*\d+\s*\]$',         # [1]
                            r'^\(\s*\d+\s*\)$',         # (1)
                        ]
                        for pattern in page_patterns:
                            if re.match(pattern, content, re.IGNORECASE):
                                is_page_number = True
                                break
            
            # 如果不是页码，保留该元素
            if not is_page_number:
                filtered.append(el)
            else:
                logger.debug(f"Filtered page number: '{content}' at page {el['page_no']}")
        
        return filtered

    def _is_bold_font(self, font_name: str) -> bool:
        """强化版粗体检测，兼容中文字体名"""
        if not font_name: return False
        fn = font_name.lower()
        # 1. 英文关键字
        if any(x in fn for x in ["bold", "heavy", "black", "semibold", "medium", "demi"]):
            return True
        # 2. 中文常见粗体/黑体 hints
        if any(x in fn for x in ["hei", "yahei", "simhei", "gotik", "strong"]):
            # 但要排除 Light 等关键字
            if "light" in fn: return False
            return True
        return False

    def _get_page_dict_compat(self, plumber_page) -> Dict[str, Any]:
        """构建兼容 PyMuPDF 格式的页面信息映射 (增强行聚合法)"""
        width, height = plumber_page.width, plumber_page.height
        chars = plumber_page.chars
        if not chars:
            return {"width": width, "height": height, "blocks": []}

        # 1. 按行聚合 (基于 y 中点重叠，而非固定 y-key)
        lines_data: List[Dict[str, Any]] = []
        for c in chars:
            text = c["text"]
            if not text.strip(): continue
            
            x0, y0, x1, y1 = c["x0"], c["top"], c["x1"], c["bottom"]
            y_mid = (y0 + y1) / 2
            size = round(c["size"], 1)
            is_bold = self._is_bold_font(c.get("fontname"))
            
            # 查找是否存在 y-区间重叠的行
            found_line = None
            for line in lines_data:
                # 💡 优化：放宽重叠判定到 30%，处理基准线稍微偏移的标题
                l_y0, l_y1 = line["y0"], line["y1"]
                overlap = min(y1, l_y1) - max(y0, l_y0)
                h = max(y1 - y0, l_y1 - l_y0, 1)
                if overlap > h * 0.3:
                    found_line = line
                    break
            
            char_info = {
                "text": text,
                "bbox": [x0, y0, x1, y1],
                "size": size,
                "font": c.get("fontname", "default"),
                "is_bold": is_bold
            }
            
            if found_line:
                found_line["chars"].append(char_info)
                # 更新行边界
                found_line["y0"] = min(found_line["y0"], y0)
                found_line["y1"] = max(found_line["y1"], y1)
            else:
                lines_data.append({
                    "y0": y0, "y1": y1,
                    "chars": [char_info]
                })

        blocks = []
        # 按 y 排序所有行
        lines_data.sort(key=lambda x: x["y0"])
        
        for line in lines_data:
            line_chars = sorted(line["chars"], key=lambda x: x["bbox"][0])
            spans = []
            
            current_span = None
            for c in line_chars:
                # 合并相邻且相同属性的字符
                if current_span and abs(c["size"] - current_span["size"]) < 0.1 and c["font"] == current_span["font"]:
                    gap = c["bbox"][0] - current_span["bbox"][2]
                    # 如果间距极小，直接合并
                    if gap < c["size"] * 0.1:
                        current_span["text"] += c["text"]
                        current_span["bbox"][2] = max(current_span["bbox"][2], c["bbox"][2])
                        current_span["bbox"][3] = max(current_span["bbox"][3], c["bbox"][3])
                        continue
                    # 如果间距适中 (0.1 ~ 0.8 倍字号)，增加一个空格并合并
                    elif gap < c["size"] * 0.8:
                        current_span["text"] += " " + c["text"]
                        current_span["bbox"][2] = max(current_span["bbox"][2], c["bbox"][2])
                        current_span["bbox"][3] = max(current_span["bbox"][3], c["bbox"][3])
                        continue
                
                if current_span: spans.append(current_span)
                current_span = {
                    "text": c["text"],
                    "bbox": list(c["bbox"]),
                    "size": c["size"],
                    "font": c["font"],
                    "is_bold": c["is_bold"]
                }
            if current_span: spans.append(current_span)
            
            if not spans: continue
            
            # 计算 line bbox
            l_x0 = min(s["bbox"][0] for s in spans)
            l_y0 = min(s["bbox"][1] for s in spans)
            l_x1 = max(s["bbox"][2] for s in spans)
            l_y1 = max(s["bbox"][3] for s in spans)
            
            blocks.append({
                "type": 0,
                "bbox": [l_x0, l_y0, l_x1, l_y1],
                "lines": [{"spans": spans, "bbox": [l_x0, l_y0, l_x1, l_y1]}]
            })

        return {"width": width, "height": height, "blocks": blocks}

    def _stitch_code_sequences(self, elements: List[ParserElement]) -> List[ParserElement]:
        if not elements:
            return []
        
        stitched: List[ParserElement] = []
        for el in elements:
            if not stitched:
                stitched.append(el)
                continue
            
            prev = stitched[-1]
            
            # 模式 A：code + code
            if el["type"] == "code" and prev["type"] == "code":
                prev_height = prev["bbox"][3] - prev["bbox"][1]
                gap = el["bbox"][1] - prev["bbox"][3]
                if gap <= prev_height * 3:
                    prev["content"] += "\n" + el["content"]
                    prev["bbox"][3] = max(prev["bbox"][3], el["bbox"][3])
                    continue
            
            # 模式 B：code + text (像注释)
            if prev["type"] == "code" and el["type"] == "text":
                prev_height = max(prev["bbox"][3] - prev["bbox"][1], 8)
                gap = el["bbox"][1] - prev["bbox"][3]
                text_stripped = el["content"].strip()
                if gap <= prev_height * 1.5 and (text_stripped.startswith(('#', '//', '/*')) or len(text_stripped) < 4):
                    prev["content"] += "\n" + el["content"]
                    prev["bbox"][3] = max(prev["bbox"][3], el["bbox"][3])
                    continue
            
            stitched.append(el)
        return stitched

    def _process_page_combined(self, page: pdfium.PdfPage, plumber_page, page_no: int) -> List[ParserElement]:
        elements: List[ParserElement] = []
        # 使用 pdfium page 的原始尺寸进行渲染和坐标转换
        width, height = page.get_size()
        # pdfplumber 的尺寸通常一致，但以 pdfium 为准进行渲染裁剪
        p_width, p_height = plumber_page.width, plumber_page.height
        
        # 1. 建立避让区 (使用 pdfplumber)
        # 优化表格检测：调整设置避免误判代码块
        table_settings = {
            "vertical_strategy": "lines", 
            "horizontal_strategy": "lines",
            "snap_tolerance": 3,
            "join_tolerance": 3,
        }
        tabs = plumber_page.find_tables(table_settings=table_settings)
        table_bboxes = []
        for t in tabs:
            try:
                table_data = t.extract()
                if table_data and len(table_data) > 1:
                    # 获取表头和数据
                    header = [str(x or "").replace("\n", " ") for x in table_data[0]]
                    rows = [[str(cell or "").replace("\n", " ") for cell in row] for row in table_data[1:]]
                    
                    import pandas as pd  # type: ignore[import-untyped]
                    df = pd.DataFrame(rows, columns=header)
                    # 只有当列数 > 1 时才认为是真正的表格，否则可能是代码框
                    if len(df.columns) > 1:
                        table_bboxes.append(t.bbox)
                        md_table = df.to_markdown(index=False)
                        elements.append({
                            "type": "table",
                            "content": md_table,
                            "bbox": list(t.bbox),
                            "page_no": page_no,
                            "metadata": {
                                "raw_header": header,
                                "raw_rows": rows
                            }
                        })
            except Exception as e:
                logger.debug(f"Table extraction failed on page {page_no}: {e}")

        # 识别矢量图与容器区
        pure_graphics, container_boxes = self.layout_engine.detect_vector_graphics(plumber_page)
        
        # --- 渲染逻辑 (使用 PIL 裁剪避免 pdfium 坐标精度报错) ---
        page_render_cache = [None] # 用 list 包裹以在闭包中修改
        
        def get_pil_crop(bbox_topdown):
            if page_render_cache[0] is None:
                # 预先渲染全页 (Scale 2 = 144 DPI)
                bitmap = page.render(scale=2)
                page_render_cache[0] = bitmap.to_pil()
            
            # 适配坐标比率
            sc_x = width / p_width
            sc_y = height / p_height
            
            # PIL 裁剪坐标 (left, top, right, bottom) * 2 (因为 scale=2)
            left = max(0, bbox_topdown[0] * sc_x * 2)
            top = max(0, bbox_topdown[1] * sc_y * 2)
            right = min(page_render_cache[0].width, bbox_topdown[2] * sc_x * 2)
            bottom = min(page_render_cache[0].height, bbox_topdown[3] * sc_y * 2)
            
            if right <= left or bottom <= top:
                return None
            return page_render_cache[0].crop((left, top, right, bottom))

        # 2a. 处理矢量插图
        for i, g_bbox in enumerate(pure_graphics):
            try:
                cropped = get_pil_crop(g_bbox)
                if cropped:
                    import io
                    img_byte_arr = io.BytesIO()
                    cropped.save(img_byte_arr, format='PNG')
                    
                    # 生成唯一图片ID
                    image_id = f"graphics_{page_no+1}_{i+1}"
                    filename = f"{image_id}.png"
                    
                    elements.append(ParserElement(
                        type="image",
                        content=filename,
                        bbox=g_bbox,
                        page_no=page_no,
                        metadata={
                            "image_id": image_id,
                            "blob": img_byte_arr.getvalue(),
                            "content_type": "image/png",
                            "ext": ".png",
                            "is_vector": True
                        }
                    ))
            except Exception as e:
                logger.warning(f"Vector graphics crop failed on page {page_no+1}: {e}")

        # 2b. 处理位图 (pdfplumber.images)
        image_bboxes = []
        for img_obj in plumber_page.images:
            bbox = [img_obj["x0"], img_obj["top"], img_obj["x1"], img_obj["bottom"]]
            # 过滤装饰性小图
            if (bbox[2]-bbox[0] > width * 0.05) and (bbox[3]-bbox[1] > height * 0.03):
                if not self.layout_engine.outside_all_bboxes(bbox, table_bboxes):
                    continue
                
                image_bboxes.append(bbox)
                try:
                    cropped = get_pil_crop(bbox)
                    if cropped:
                        import io
                        img_byte_arr = io.BytesIO()
                        cropped.save(img_byte_arr, format='PNG')
                        
                        # 生成唯一图片ID
                        image_id = f"image_{page_no+1}_{len(image_bboxes)}"
                        filename = f"{image_id}.png"
                        
                        elements.append(ParserElement(
                            type="image",
                            content=filename,
                            bbox=bbox,
                            page_no=page_no,
                            metadata={
                                "image_id": image_id,
                                "blob": img_byte_arr.getvalue(),
                                "content_type": "image/png",
                                "ext": ".png",
                                "is_vector": False
                            }
                        ))
                except Exception as e:
                    logger.warning(f"Bitmap crop failed on page {page_no+1} at {bbox}: {e}")

        avoid_bboxes = table_bboxes + image_bboxes + pure_graphics

        # 2. 提取文本流 (兼容 layer)
        # 这里为了复用 FontAnalyzer，我们使用刚才构建的 dict 逻辑
        page_dict = self._get_page_dict_compat(plumber_page)
        
        for b in page_dict.get("blocks", []):
            if not self.layout_engine.outside_all_bboxes(b["bbox"], avoid_bboxes):
                continue
                
            # 判定容器盒
            is_block_in_container = any(
                self.layout_engine.outside_all_bboxes(b["bbox"], [cb]) == False 
                for cb in container_boxes
            )
            
            for line in b["lines"]:
                line_text = ""
                max_size = 0
                is_bold = False 
                font_name = "default"
                
                prev_span = None
                for span in line["spans"]:
                    # 💡 优化：span 之间如果存在物理间距，补回空格
                    if prev_span:
                        gap = span["bbox"][0] - prev_span["bbox"][2]
                        if gap > span["size"] * 0.1:
                            line_text += " "
                    
                    line_text += span["text"]
                    max_size = max(max_size, span["size"])
                    if span.get("is_bold"):
                        is_bold = True
                    font_name = span.get("font", font_name)
                    prev_span = span
                
                if not line_text.strip(): continue

                # 判定类型
                if is_block_in_container:
                    el_type = "code"
                    el_metadata = {"size": max_size, "bold": is_bold, "font": font_name}
                else:
                    level = self.font_analyzer.get_heading_level(max_size, is_bold, line_text, line["bbox"], font_name)
                    if level > 0:
                        # 标题：使用 type="title" + metadata["level"]
                        el_type = "title"
                        el_metadata = {
                            "level": level,
                            "size": max_size,
                            "bold": is_bold,
                            "font": font_name
                        }
                    else:
                        # 普通文本
                        el_type = "text"
                        el_metadata = {"size": max_size, "bold": is_bold, "font": font_name}
                
                el_metadata.update(
                    {
                        "source": "native",
                        "modality": "pdf_text_layer",
                        "vision_enabled": False,
                        "vision_model": None,
                        "vision_text": None,
                        "vision_confidence": None,
                    }
                )

                elements.append(ParserElement(
                    type=el_type,
                    content=line_text,
                    bbox=list(line["bbox"]),
                    page_no=page_no,
                    metadata=el_metadata
                ))

        # 排序
        if self.enable_ocr:
            should_ocr, reason = self._should_apply_ocr(elements, width, height)
            if should_ocr:
                ocr_elements = self._extract_ocr_elements(page, page_no, width, height, reason)
                if ocr_elements:
                    structured = [e for e in elements if e.get("type") in {"table", "image"}]
                    elements = structured + ocr_elements

        elements.sort(key=lambda x: (x["bbox"][1], x["bbox"][0]))
        return elements

    def _should_apply_ocr(
        self,
        page_elements: List[ParserElement],
        page_width: float,
        page_height: float,
    ) -> Tuple[bool, str]:
        import re

        text_like = [
            el for el in page_elements
            if el.get("type") in {"text", "title", "code"}
        ]
        if not text_like:
            return True, "no_text_layer"

        joined_text = "\n".join((el.get("content") or "").strip() for el in text_like).strip()
        if len(joined_text) < self.ocr_min_text_chars:
            return True, f"text_too_short:{len(joined_text)}"

        # Fast-path: text layer is already rich and readable, skip OCR.
        non_ws = re.sub(r"\s+", "", joined_text)
        non_ws_len = len(non_ws)
        readable_chars = len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", joined_text))
        readable_ratio = (readable_chars / non_ws_len) if non_ws_len > 0 else 0.0
        if (
            len(text_like) >= 4
            and len(joined_text) >= max(self.ocr_min_text_chars * 3, 150)
            and readable_ratio >= 0.55
        ):
            return False, f"text_layer_sufficient:len={len(joined_text)},ratio={readable_ratio:.2f}"

        try:
            from .text_quality_checker import TextQualityChecker
            should_ocr, reason = TextQualityChecker.should_use_ocr(joined_text, page_width, page_height)
            return should_ocr, reason
        except Exception:
            return False, "quality_checker_unavailable"

    def _extract_ocr_elements(
        self,
        page: pdfium.PdfPage,
        page_no: int,
        page_width: float,
        page_height: float,
        reason: str,
    ) -> List[ParserElement]:
        engine = self._resolve_ocr_engine()
        if not engine:
            return []

        logger.info(
            "[NativePDFParser] 第 %d 页使用 OCR，引擎 %s，原因 %s",
            page_no + 1,
            engine,
            reason,
        )
        try:
            bitmap = page.render(scale=self.ocr_render_scale)
            image = bitmap.to_pil()
        except Exception as e:
            logger.warning(f"OCR render failed on page {page_no + 1}: {e}")
            return []

        try:
            raw_lines = self.ocr_pipeline.recognize(
                image=image,
                engine=engine,
                languages=self.ocr_languages,
            )
        except Exception as e:
            logger.warning(f"OCR pipeline failed on page {page_no + 1}: {e}")
            return []

        if not raw_lines:
            logger.debug("[NativePDFParser] 第 %d 页 OCR 未识别到文本", page_no + 1)
            return []

        logger.info(
            "[NativePDFParser] page=%d OCR done, engine=%s, lines=%d",
            page_no + 1,
            engine,
            len(raw_lines),
        )
        scale_x = page_width / max(float(image.width), 1.0)
        scale_y = page_height / max(float(image.height), 1.0)
        out: List[ParserElement] = []
        for item in raw_lines:
            text = (item.get("text") or "").strip()
            if not text:
                continue

            px_bbox = item.get("bbox") or [0.0, 0.0, 0.0, 0.0]
            x0 = float(px_bbox[0]) * scale_x
            y0 = float(px_bbox[1]) * scale_y
            x1 = float(px_bbox[2]) * scale_x
            y1 = float(px_bbox[3]) * scale_y

            out.append(
                ParserElement(
                    type="text",
                    content=text,
                    bbox=[x0, y0, x1, y1],
                    page_no=page_no,
                    metadata={
                        "source": "ocr",
                        "modality": "ocr_text",
                        "ocr_engine": engine,
                        "ocr_languages": list(self.ocr_languages),
                        "ocr_confidence": float(item.get("confidence") or 0.0),
                        "ocr_reason": reason,
                        "vision_enabled": False,
                        "vision_model": None,
                        "vision_text": None,
                        "vision_confidence": None,
                    }
                )
            )
        return out

    def _resolve_ocr_engine(self) -> Optional[str]:
        if self._resolved_ocr_engine is not None:
            return self._resolved_ocr_engine
        resolved = self.ocr_pipeline.resolve_engine(self.ocr_engine)

        if not resolved:
            logger.warning(
                "OCR is enabled but no OCR engine is available. requested=%s",
                self.ocr_engine,
            )
        else:
            logger.info(
                "[NativePDFParser] 已选择 OCR 引擎: %s (配置: %s)",
                resolved,
                self.ocr_engine,
            )
        self._resolved_ocr_engine = resolved
        return resolved

    def _merge_cross_page_tables(self, elements: List[ParserElement]) -> List[ParserElement]:
        """合并跨页打断的表格（方案 A：完整合并，支持多位置追踪）"""
        if not elements:
            return []
            
        merged: List[ParserElement] = []
        i = 0
        import pandas as pd  # type: ignore[import-untyped]
        
        while i < len(elements):
            el = elements[i]
            if el["type"] != "table":
                merged.append(el)
                i += 1
                continue
                
            cur_table: ParserElement = ParserElement(**el)  # copy to avoid mutating original if needed
            cur_meta: Dict[str, Any] = dict(cur_table.get("metadata") or {})
            cur_header: List[str] = list(cur_meta.get("raw_header") or [])
            cur_rows: List[List[Any]] = [list(row) for row in (cur_meta.get("raw_rows") or [])]  # copy list
            
            if not cur_header:
                merged.append(cur_table)
                i += 1
                continue
                
            col_count = len(cur_header)
            positions: List[Dict[str, Any]] = [{
                "page_no": cur_table["page_no"], 
                "bbox": cur_table["bbox"]
            }]
            
            j = i + 1
            while j < len(elements):
                nxt = elements[j]
                
                if nxt["type"] != "table":
                    break
                    
                nxt_meta: Dict[str, Any] = dict(nxt.get("metadata") or {})
                nxt_header: List[str] = list(nxt_meta.get("raw_header") or [])
                nxt_rows: List[List[Any]] = [list(row) for row in (nxt_meta.get("raw_rows") or [])]
                
                if len(nxt_header) != col_count:
                    break
                    
                if nxt_header == cur_header:
                    # 表头相同（表头跨页重复了），直接追加数据行
                    cur_rows.extend(nxt_rows)
                else:
                    # 表头不同（第二页没表头，第一行数据被当作表头了）
                    # 💡 智能行缝合引擎：应对跨页断行
                    # 如果该行首列为空，大概率是左侧（如 Key）短，右侧（如 Value）长导致的跨页截断。
                    # 我们将其从物理分离状态“缝合”回上一页的最后一行中。
                    is_continuation = False
                    if cur_rows and nxt_header and not nxt_header[0].strip():
                        # 如果不只有首列为空，其他列有实质内容，则认为是跨页截断
                        if any(str(c).strip() for c in nxt_header[1:]):
                            is_continuation = True
                            
                    if is_continuation:
                        for c_idx in range(col_count):
                            val = str(nxt_header[c_idx]).strip()
                            if val:
                                cur_rows[-1][c_idx] = (str(cur_rows[-1][c_idx]) + " " + val).strip()
                    else:
                        cur_rows.append(nxt_header)
                        
                    cur_rows.extend(nxt_rows)
                    
                positions.append({
                    "page_no": nxt["page_no"],
                    "bbox": nxt["bbox"]
                })
                j += 1
                
            if len(positions) > 1:
                # 重新生成带数据的 Markdown
                df = pd.DataFrame(cur_rows, columns=cur_header)
                cur_table["content"] = df.to_markdown(index=False)
                
                # 更新坐标追踪信息到 metadata 中，支持前端高亮多页
                cur_meta["positions"] = positions
                cur_table["metadata"] = cur_meta
                
            merged.append(cur_table)
            i = j
            
        return merged


import collections
import re
from typing import Counter, List, Dict, Any, Tuple

class FontAnalyzer:
    """
    Native PDF 字体统计分析 (Statistical & Heuristic Hybrid)
    
    核心算法：
    1. 众数统计法 (Statistical Size Logic): 统计全文子符数加权频率。
    2. 动态分级: 将大于正文的字号按权重排名，映射为 H1-H6。
    3. 启发式修正: 处理相同字号加粗、居中等典型标题特征。
    """
    
    MONOSPACE_FONTS = {
        'courier', 'consolas', 'monaco', 'menlo', 'source code pro',
        'fira code', 'jetbrains mono', 'inconsolata', 'dejavu sans mono',
        'courier new', 'lucida console', 'andale mono'
    }
    
    def __init__(self, max_levels: int = 6):
        self.font_counts: Counter[float] = collections.Counter()  # 字号 -> 总字符数
        self.body_font_size = 0.0
        self.heading_map: Dict[float, int] = {}  # 字号 -> 级别 (1-6)
        
        self.page_width = 0.0
        self.page_height = 0.0
        self.left_margin = 0.0
        self.max_levels = max_levels
        
    def collect_font_statistics(self, pages_dict: List[Dict[str, Any]]):
        """
        第一阶段：全文预热扫描
        从  的 dict 输出中提取字号统计权重
        """
        if not pages_dict:
            return

        # 记录基准尺寸（取第一页）
        self.page_width = pages_dict[0].get("width", 0)
        self.page_height = pages_dict[0].get("height", 0)
        
        left_positions = []

        for page in pages_dict:
            for block in page.get("blocks", []):
                if block.get("type") == 0:  # Text block
                    left_positions.append(block["bbox"][0])
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            content = span.get("text", "").strip()
                            if not content:
                                continue
                                
                            # 字号降噪 (取一位小数)
                            size = round(span.get("size", 0), 1)
                            font_name = span.get("font", "").lower()
                            
                            # 排除等宽字体（代码块不参与标题统计）
                            if size > 0 and not self._is_monospace_font(font_name):
                                # 💡 权重计算：字号的重要性由其覆盖的字符数决定
                                self.font_counts[size] += len(content)
        
        # 统计正文左边界众数
        if left_positions:
            left_counter = collections.Counter([round(x, 0) for x in left_positions])
            self.left_margin = left_counter.most_common(1)[0][0]
            
        if self.font_counts:
            # 1. 众数即为正文大小
            self.body_font_size = self.font_counts.most_common(1)[0][0]
            
            # 2. 动态生成标题映射表
            # 候选条件：
            # A. 必须比正文大至少 1.5pt (忽略 0.5pt 左右的微调字号)
            # B. 权重必须在 0.01% 到 10% 之间 (过滤杂讯和“伪装成标题的超长段落”)
            total_chars = sum(self.font_counts.values())
            candidate_sizes = sorted(
                [sz for sz, count in self.font_counts.items() 
                 if sz >= self.body_font_size + 1.5 
                 and total_chars * 0.0001 < count < total_chars * 0.1], 
                reverse=True
            )[:self.max_levels]
            
            # 最大的 size 为 H1, 次之为 H2...
            for i, sz in enumerate(candidate_sizes, start=1):
                self.heading_map[sz] = i
        else:
            self.body_font_size = 10.0

    def get_heading_level(
        self, 
        size: float, 
        is_bold: bool, 
        content: str, 
        bbox: List[float], 
        font_name: str = ""
    ) -> int:
        """
        混合判定：基于统计表 + 严格语义过滤
        """
        size = round(size, 1)
        text = content.strip()
        
        # 1. 强力语义过滤 (针对接口文档中的参数说明列表)
        if not text or len(text) < 2 or len(text) > 60:
            return 0
            
        # 💡 核心策略：如果包含全角冒号并且冒号后有实质性描述，这绝对是正文描述而非标题
        if "：" in text:
            parts = text.split("：", 1)
            if len(parts) > 1 and len(parts[1].strip()) > 3:
                return 0
        
        # 2. 基础噪音过滤
        if self._is_list_marker(text) or self._is_monospace_font(font_name):
            return 0
        # 注意：不再用 bbox 硬编码的 5%/95% 来过滤页眉页脚。
        # 因为合法的标题可能出现在页面顶部（如"1.4 对接方式"出现在第7页顶部，y0=29）。
        # 真正的页眉/页脚过滤由 layout.filter_header_footer_statistical() 统计方法处理。

        # 3. 统计学初步匹配
        base_level = self.heading_map.get(size, 0)
        
        # 💡 新增针对代码片段的强制过滤 (即便统计字号符合)
        # 如果包含大量 JSON/代码特征符号，严禁作为标题
        code_indicators = ['{', '}', '[', ']', '"', ':', 'http', ' = ', '(', ')']
        if sum(1 for c in code_indicators if c in text) >= 2:
            return 0
        
        # --- 4. 设置“标题门槛” (校验统计学的过拟合) ---
        # A. 如果字号只是比正文大了一点点 (1.5pt 左右)，且没有加粗，不应作为标题
        is_significant_size = size >= self.body_font_size + 2.5
        
        # B. 强编号模式识别 (如 1.1, 1), 1.4, 1.2.3, 一、)
        # 修正：支持各种多层级编号
        has_number_pattern = bool(re.match(r'^(\d+(\.\d+)*[\.、\)\s]|[一二三四五六七八九十]+[、\.])', text))
        # 判定是否为多级编号 (如 1.4, 2.1)
        is_hierarchical = bool(re.match(r'^\d+\.\d+', text))
        
        # C. 针对字面 MD 标记的处理 (处理如 ### 1.4 对接方式)
        md_marker_match = re.match(r'^(#{1,6})\s+', text)
        if md_marker_match:
            # 💡 防御性降级：如果是 body size 且没有加粗，或者是单一个 '#' 且字号不大，极可能是代码注释
            level = len(md_marker_match.group(1))
            if level == 1 and size < self.body_font_size + 1.5 and not is_bold:
                return 0
            
            if size >= self.body_font_size + 0.5 or is_bold or level >= 2:
                return level
        
        # 最终判定：必须是大字号，或者虽然字号一般但有加粗且有编号
        if base_level > 0:
            # 💡 改进：如果是多级编号 (如 1.4, 2.1, 二、)，其重要等级很高，即便不满足加粗或显著大字号，也应保留标题身份
            is_major_section = is_hierarchical or bool(re.match(r'^[一二三四五六七八九十]+[、\.]', text))
            if is_major_section:
                return base_level
            
            if not (is_significant_size or (is_bold and has_number_pattern)):
                # 如果只是字号略大但没编号也长得像描述，退化为文本
                return 0
                
        # 5. 特殊情况补偿：即便统计映射没抓到 (针对 1.4 或 二、 等强特征)
        if base_level <= 0:
            # A. 优先判定多级/大级编号
            is_chinese_num = bool(re.match(r'^[一二三四五六七八九十]+[、\.]', text))
            if is_chinese_num:
                return 2
            
            if is_hierarchical:
                # 类似 1.4 这种作为 H3 返回合适
                return 3
            
            # B. 如果有加粗且有强编号
            if is_bold and has_number_pattern:
                return 3

        return base_level

    def _is_monospace_font(self, font_name: str) -> bool:
        font_lower = font_name.lower()
        return any(mono in font_lower for mono in self.MONOSPACE_FONTS)

    def _is_list_marker(self, text: str) -> bool:
        # 无序
        if re.match(r'^[•\-\*○●■□]\s+', text):
            return True
        # 有序列表: 仅匹配单个数字层级，如 "1. " 或 "1) "
        # 排除多级编号如 "1.4 "，因为它们通常是标题
        if re.match(r'^\d{1,2}[\.\)]\s+', text):
            # 进一步检查是否为多级，如果是则不是 list marker
            if re.match(r'^\d+\.\d+', text):
                return False
            return True
        return False

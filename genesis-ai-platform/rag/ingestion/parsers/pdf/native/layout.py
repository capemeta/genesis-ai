import collections
from typing import Counter, List, Dict, Any, Tuple

class Rect:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.width = x1 - x0
        self.height = y1 - y0

    def intersects(self, other, padding=(0,0,0,0)):
        # Apply padding: (left, top, right, bottom)
        ax0, ay0, ax1, ay1 = self.x0 - padding[0], self.y0 - padding[1], self.x1 + padding[2], self.y1 + padding[3]
        bx0, by0, bx1, by1 = other.x0, other.y0, other.x1, other.y1
        return not (ax1 < bx0 or ax0 > bx1 or ay1 < by0 or ay0 > by1)

    def __or__(self, other):
        return Rect(min(self.x0, other.x0), min(self.y0, other.y0), max(self.x1, other.x1), max(self.y1, other.y1))

    def intersect(self, other):
        x0 = max(self.x0, other.x0)
        y0 = max(self.y0, other.y0)
        x1 = min(self.x1, other.x1)
        y1 = min(self.y1, other.y1)
        if x1 < x0 or y1 < y0:
            return Rect(0, 0, -1, -1)
        return Rect(x0, y0, x1, y1)

    def get_area(self):
        if self.x1 < self.x0 or self.y1 < self.y0: return 0
        return (self.x1 - self.x0) * (self.y1 - self.y0)

    def is_empty(self):
        return self.x1 < self.x0 or self.y1 < self.y0

class LayoutEngine:
    """
    Native PDF 布局分析与图形感知引擎
    
    采用 Pypdfium2 + Pdfplumber 核心算法：
    1. 矢量图形聚类: 识别线条组成的流程图/架构图，解决插图丢失问题。
    2. 增强型避让: 针对表格、图片、矢量图建立“干扰保护区”。
    3. 自适应分栏: 处理论文等双栏场景读取顺序。
    """
    
    @staticmethod
    def detect_vector_graphics(plumber_page) -> Tuple[List[List[float]], List[List[float]]]:
        """
        精细化矢量图识别 (使用 pdfplumber 对象)
        返回：(pure_graphics, container_boxes)
        """
        # pdfplumber 中的 rects 和 lines
        rects = plumber_page.rects
        if not rects:
            return [], []
            
        # 提前获取本页所有文字块的范围，用于交叉比对
        text_objects = plumber_page.extract_words()
        text_rects = [Rect(w["x0"], w["top"], w["x1"], w["bottom"]) for w in text_objects]
            
        # 1. 提取有效路径矩形
        raw_rects = []
        page_width = plumber_page.width
        page_height = plumber_page.height
        
        for r in rects:
            # 过滤全屏背景或装饰性极小的
            if (r["x1"] - r["x0"]) > page_width * 0.9 or (r["bottom"] - r["top"]) > page_height * 0.9:
                continue
            if (r["x1"] - r["x0"]) < 3 and (r["bottom"] - r["top"]) < 3:
                continue
            raw_rects.append(Rect(r["x0"], r["top"], r["x1"], r["bottom"]))
            
        if not raw_rects:
            return [], []
            
        # 2. 聚类合并
        merged_rects: List[Rect] = []
        for r in raw_rects:
            found = False
            for i in range(len(merged_rects)):
                # 检查相交（带 5pt 冗余）
                if r.intersects(merged_rects[i], padding=(5, 5, 5, 5)):
                    merged_rects[i] = merged_rects[i] | r
                    found = True
                    break
            if not found:
                merged_rects.append(r)
                
        # 3. 核心分类
        pure_graphics = []
        container_boxes = []
        for r in merged_rects:
            if r.width < 10 or r.height < 10:
                continue
                
            has_text = False
            for t_rect in text_rects:
                intersection = r.intersect(t_rect)
                if not intersection.is_empty() and intersection.get_area() > t_rect.get_area() * 0.3:
                    has_text = True
                    break
            
            bbox = [r.x0, r.y0, r.x1, r.y1]
            if has_text:
                container_boxes.append(bbox)
            else:
                pure_graphics.append(bbox)
                
        return pure_graphics, container_boxes

    @staticmethod
    def outside_all_bboxes(rect: List[float], bboxes: List[List[float]]) -> bool:
        """
        几何隔离算法 (Spatial Avoidance)
        判定当前文本行是否落在表格或图形内部
        """
        r = Rect(rect[0], rect[1], rect[2], rect[3])
        for bbox in bboxes:
            b = Rect(bbox[0], bbox[1], bbox[2], bbox[3])
            intersection = r.intersect(b)
            if not intersection.is_empty():
                if intersection.get_area() > r.get_area() * 0.5:
                    return False
        return True

    def detect_columns_adaptive(self, page_blocks: List[Dict[str, Any]], page_width: float) -> List[List[Dict[str, Any]]]:
        """
        自适应分栏逻辑
        """
        if not page_blocks:
            return []
            
        # 过滤出文本块
        text_blocks = [b for b in page_blocks if b.get("type") == 0]
        if not text_blocks:
            return []
            
        x_positions = [b["bbox"][0] for b in text_blocks]
        min_x = min(x_positions)
        max_x = max(x_positions)
        
        # 如果列间距足够大，执行分栏提取 (通常 > 页面宽度的 20%)
        if max_x - min_x > page_width * 0.2:
            mid = (min_x + max_x) / 2
            left = sorted([b for b in text_blocks if b["bbox"][0] < mid], key=lambda x: x["bbox"][1])
            right = sorted([b for b in text_blocks if b["bbox"][0] >= mid], key=lambda x: x["bbox"][1])
            # 返回按列顺序排列的列表
            cols = []
            if left: cols.append(left)
            if right: cols.append(right)
            return cols
            
        return [sorted(text_blocks, key=lambda x: x["bbox"][1])]

    def filter_header_footer_statistical(self, all_elements: List[Any], total_pages: int) -> List[Any]:
        """
        跨页噪音过滤
        """
        if total_pages < 3:
            return all_elements
            
        sigs: Counter[Tuple[int, str]] = collections.Counter()
        for el in all_elements:
            # 缩写指纹: (近似 y 坐标, 文字前缀)
            y_sig = round(el["bbox"][1] / 5) * 5 # 5pt 聚合
            text_sig = el["content"][:15].strip()
            if text_sig:
                sigs[(y_sig, text_sig)] += 1
                
        # 判定: 出现频率超过总页数的 60% 为噪音
        threshold = int(total_pages * 0.6)
        noise_sigs = {k for k, v in sigs.items() if v >= threshold}
        
        return [el for el in all_elements if (round(el["bbox"][1] / 5) * 5, el["content"][:15].strip()) not in noise_sigs]

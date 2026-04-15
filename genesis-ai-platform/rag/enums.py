"""
分块流程相关枚举定义
"""

from enum import Enum


class DocumentStatus(str, Enum):
    """文档处理状态"""
    UPLOADED = "uploaded"           # 已上传
    PARSING = "parsing"             # 解析中
    PARSE_FAILED = "parse_failed"   # 解析失败
    CHUNKING = "chunking"           # 分块中
    CHUNK_FAILED = "chunk_failed"   # 分块失败
    TRAINING = "training"           # 训练中（向量化等）
    TRAIN_FAILED = "train_failed"   # 训练失败
    BUILDING_KG = "building_kg"     # 构建知识图谱中
    KG_FAILED = "kg_failed"         # 知识图谱构建失败
    COMPLETED = "completed"         # 完成


class TaskType(str, Enum):
    """任务类型"""
    PARSE = "parse"                 # 解析
    PARSE_MINERU = "parse_mineru"   # MinerU 解析
    PARSE_VISION = "parse_vision"   # 视觉模型解析
    PARSE_OCR = "parse_ocr"         # OCR 解析
    PARSE_DOCLING = "parse_docling" # Docling 解析
    PARSE_TCADP = "parse_tcadp"     # 腾讯云智能体开发平台 TCADP 解析
    LAYOUT_ANALYSIS = "layout_analysis"  # 版面分析
    CHUNK = "chunk"                 # 分块
    VECTORIZE = "vectorize"         # 向量化
    SUMMARIZE = "summarize"         # 摘要
    EXTRACT_QA = "extract_qa"       # 提取问题
    EXTRACT_KW = "extract_kw"       # 提取关键词
    BUILD_KG = "build_kg"           # 构建知识图谱
    EXTRACT_ENTITY = "extract_entity"     # 提取实体
    EXTRACT_RELATION = "extract_relation" # 提取关系


class ParseStrategy(str, Enum):
    """解析策略"""
    BASIC = "basic"           # 基础解析（PyPDF2/python-docx）
    QA = "qa"                 # QA 结构化解析（FAQ/问答对）
    MINERU = "mineru"         # MinerU 解析（高质量 PDF）
    DOCLING = "docling"       # Docling 解析 (IBM 深度文档理解)
    TCADP = "tcadp"           # 腾讯云智能体开发平台 TCADP 解析 (Tencent Cloud Advanced Document Parsing)
    VISION = "vision"         # 视觉大模型解析（复杂布局）
    OCR = "ocr"               # OCR 解析（扫描件/图片）
    AUTO = "auto"             # 自动选择（根据文件特征）


class ChunkStrategy(str, Enum):
    """分块策略"""
    QA = "qa"                             # QA 问答对分块（问题主块 + 答案子块）
    FIXED_SIZE = "fixed_size"           # 固定长度分块
    SEMANTIC = "semantic"               # 语义分块
    MARKDOWN = "markdown"               # Markdown 结构分块
    SENTENCE = "sentence"               # 句子分块
    PARAGRAPH = "paragraph"             # 段落分块
    RECURSIVE = "recursive"             # 递归分块
    SMART = "smart"                     # 智能模式（路由引擎）
    GENERAL = "general"                 # 通用分块（智能探测复杂度）
    PDF_LAYOUT = "pdf_layout"           # PDF 版面分块（坐标优先）
    EXCEL_GENERAL = "excel_general"     # Excel 通用模式（表头+行累积 Markdown 块）
    EXCEL_TABLE = "excel_table"         # Excel 表格模式（一行一 chunk，支持过滤列）
    WEB_PAGE = "web_page"               # 网页分块（标题/段落语义优先）
    RULE_BASED = "rule_based"           # 用户规则分块（前端配置标题规则，后端通用执行）


class SearchStrategy(str, Enum):
    """检索策略"""
    VECTOR_ONLY = "vector_only"           # 纯向量检索
    KG_ONLY = "kg_only"                   # 纯知识图谱检索
    HYBRID = "hybrid"                     # 混合检索（推荐）
    VECTOR_THEN_KG = "vector_then_kg"     # 先向量后图谱
    KG_THEN_VECTOR = "kg_then_vector"     # 先图谱后向量


class ChunkType(str, Enum):
    """切片类型"""
    TEXT = "text"           # 文本（Markdown）
    HTML = "html"           # HTML（复杂表格、网页片段，保留样式和跨行跨列）
    IMAGE = "image"         # 图片（Image URL + Caption）
    TABLE = "table"         # 表格（Markdown Table，简单表格） PDF 插图, PPT 图片, 工程图纸
    MEDIA = "media"         # 媒体（音视频片段，带时间戳） MP3/WAV/MP4/MOV
    QA = "qa"               # 问答对（Q&A） 人工问答对, 自动生成的 Q&A
    CODE = "code"           # 代码块 .py, .java, .cpp ... (纯代码文件)
    JSON = "json"           # 结构化数据（日志、配置、API响应），前端使用 Tree Viewer 渲染 	.json, .yaml, Logs, Configs
    SUMMARY = "summary"     # 摘要块（表语义 summary，作为行级 chunk 的父节点）

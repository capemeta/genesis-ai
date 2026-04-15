"""
知识库 Schema 定义
"""
import re
from typing import Optional, Dict, Any, Literal, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator


# 分块策略可选值（与 rag.enums.ChunkStrategy 一致）
CHUNK_STRATEGY_VALUES = (
    "qa",
    "fixed_size",
    "markdown",
    "recursive",
    "semantic",
    "general",
    "smart",
    "pdf_layout",
    "excel_general",
    "excel_table",
    "rule_based",
)


# PDF 解析器配置子Schema
class PdfParserConfig(BaseModel):
    """PDF 解析器配置"""
    parser: str = Field(default="native", description="PDF解析器: native, mineru, docling, tcadp")
    enable_ocr: bool = Field(default=True, description="是否启用 OCR（智能检测扫描页）")
    ocr_engine: str = Field(default="auto", description="OCR 引擎: auto, paddleocr, tesseract")
    ocr_languages: List[str] = Field(default=["ch", "en"], description="识别语言列表")
    extract_images: bool = Field(default=False, description="是否提取图片")
    extract_tables: bool = Field(default=True, description="是否提取表格")
    
    @field_validator("parser")
    @classmethod
    def validate_parser(cls, v: str) -> str:
        if v not in ["native", "mineru", "docling", "tcadp"]:
            raise ValueError("PDF解析器必须是 native, mineru, docling 或 tcadp")
        return v
    
    @field_validator("ocr_engine")
    @classmethod
    def validate_ocr_engine(cls, v: str) -> str:
        if v not in ["auto", "paddleocr", "tesseract"]:
            raise ValueError("OCR 引擎必须是 auto, paddleocr 或 tesseract")
        return v


class HeadingRuleConfig(BaseModel):
    """用户配置的标题识别规则。"""

    name: str = Field(default="", max_length=64, description="标题规则名称，仅用于展示和调试")
    level: int = Field(ge=1, le=6, description="标题层级，当前支持 1-6 级")
    pattern: str = Field(min_length=1, max_length=512, description="单行标题正则表达式")
    keep_heading: bool = Field(default=True, description="是否把标题行保留到正文")

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, v: str) -> str:
        """校验标题正则，避免非法正则和空匹配规则进入任务链。"""
        pattern = v.strip()
        if not pattern:
            raise ValueError("标题规则正则不能为空")
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"标题规则正则无效: {exc}") from exc
        if compiled.search("") is not None:
            raise ValueError("标题规则正则不能匹配空字符串")
        return pattern


class SplitRuleConfig(BaseModel):
    """自定义切分规则。每一条规则独立决定是否按正则解释。"""

    pattern: str = Field(min_length=1, max_length=512, description="切分规则内容")
    is_regex: bool = Field(default=False, description="当前规则是否按正则解释")

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, v: str) -> str:
        if v == "":
            raise ValueError("切分规则不能为空")
        return v


# 分块配置子Schema
class ChunkingConfig(BaseModel):
    """分块配置"""
    separator: str = Field(default="\n\n", description="文本分段标识符")
    split_rules: List[SplitRuleConfig] = Field(default_factory=list, description="自定义切分规则列表，按顺序递归兜底")
    separators: List[str] = Field(default_factory=list, description="多分隔符配置，按优先级递归兜底")
    regex_separators: List[str] = Field(default_factory=list, description="正则分隔符配置")
    is_regex: bool = Field(default=False, description="separator 是否按正则表达式解释")
    chunk_size: int = Field(default=500, ge=100, le=2000, description="切片大小")
    overlap: int = Field(default=50, ge=0, le=500, description="重叠长度")
    chunk_strategy: Optional[str] = Field(
        default=None,
        description=(
            "分块策略: fixed_size, markdown, recursive, semantic, general, smart, "
            "pdf_layout, excel_general, excel_table, rule_based；为空时 smart 模式按文件类型自动选择"
        )
    )
    pdf_chunk_strategy: Optional[str] = Field(
        default="markdown",
        description="PDF切分策略: 默认 markdown（结构优先）；仅显式传 pdf_layout 时使用版面优先。auto 仅为兼容旧配置，后端会按 markdown 处理"
    )
    max_heading_level: int = Field(default=3, ge=1, le=6, description="规则分块标题最大层级，默认展示 3 级，能力上支持到 6 级")
    heading_rules: List[HeadingRuleConfig] = Field(default_factory=list, description="前端配置的 1-6 级标题识别规则")
    fallback_separators: List[str] = Field(default_factory=list, description="规则分块未命中标题时的兜底分隔符")
    preserve_headings: bool = Field(default=True, description="规则分块时是否保留标题行正文")

    @field_validator("pdf_chunk_strategy")
    @classmethod
    def validate_pdf_chunk_strategy(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return "markdown"
        if v not in ["auto", "markdown", "pdf_layout"]:
            raise ValueError("pdf_chunk_strategy 必须是 auto, markdown 或 pdf_layout")
        if v == "auto":
            return "markdown"
        return v

    @field_validator("chunk_strategy")
    @classmethod
    def validate_chunk_strategy(cls, v: Optional[str]) -> Optional[str]:
        """校验前端传入的分块策略，避免无效策略进入 Celery 任务。"""
        if v is None:
            return v
        if v not in CHUNK_STRATEGY_VALUES:
            raise ValueError(f"chunk_strategy 必须是以下之一: {', '.join(CHUNK_STRATEGY_VALUES)}")
        return v

    @field_validator("heading_rules")
    @classmethod
    def validate_heading_rules(cls, v: List[HeadingRuleConfig]) -> List[HeadingRuleConfig]:
        """限制规则数量，第一版避免把规则分块变成复杂正则脚本系统。"""
        if len(v) > 10:
            raise ValueError("heading_rules 最多支持 10 条规则")
        return v

    @field_validator("split_rules")
    @classmethod
    def validate_split_rules(cls, v: List[SplitRuleConfig]) -> List[SplitRuleConfig]:
        """限制普通自定义切分规则数量，避免配置面板退化成脚本系统。"""
        if len(v) > 12:
            raise ValueError("split_rules 最多支持 12 条规则")
        return v

    @model_validator(mode="after")
    def validate_strategy_specific_config(self) -> "ChunkingConfig":
        """校验策略专属配置，避免错误正则或空规则静默进入任务链。"""
        if self.chunk_strategy == "rule_based" and not self.heading_rules:
            raise ValueError("rule_based 分块策略至少需要配置 1 条 heading_rules")

        for split_rule in self.split_rules:
            if not split_rule.is_regex:
                continue
            try:
                compiled = re.compile(split_rule.pattern)
            except re.error as exc:
                raise ValueError(f"切分规则正则无效: {exc}") from exc
            if compiled.search("") is not None:
                raise ValueError("切分规则正则不能匹配空字符串")

        regex_patterns: List[str] = []
        if self.is_regex and self.separator:
            regex_patterns.append(self.separator)
        regex_patterns.extend(item.strip() for item in self.regex_separators if item.strip())
        for pattern in regex_patterns:
            try:
                compiled = re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"分隔符正则无效: {exc}") from exc
            if compiled.search("") is not None:
                raise ValueError("分隔符正则不能匹配空字符串")
        return self


class IntelligenceConfig(BaseModel):
    """智能能力配置。"""

    enhancement: Dict[str, Any] = Field(default_factory=dict, description="分块智能增强配置")
    knowledge_graph: Dict[str, Any] = Field(default_factory=dict, description="知识图谱配置")
    raptor: Dict[str, Any] = Field(default_factory=dict, description="RAPTOR 递归摘要配置")


class KnowledgeBaseCreate(BaseModel):
    """知识库创建 Schema"""
    name: str = Field(..., min_length=1, max_length=255, description="知识库名称")
    description: Optional[str] = Field(None, description="描述信息")
    icon_url: Optional[str] = Field(None, max_length=512, description="图标URL")
    visibility: str = Field(default="private", description="可见性: private-只是我, tenant_public-团队")
    type: str = Field(default="general", description="类型: general, qa, table, web, media, connector")
    
    # RAG 配置
    chunking_mode: Literal["smart", "custom"] = Field(default="smart", description="分块模式：smart-智能分块, custom-自定义分块")
    chunking_config: ChunkingConfig = Field(default_factory=ChunkingConfig, description="分块配置（custom 时生效）")
    embedding_model: Optional[str] = Field(None, max_length=100, description="嵌入模型")
    embedding_model_id: Optional[UUID] = Field(None, description="向量租户模型ID（可选）")
    index_model: Optional[str] = Field(None, max_length=100, description="索引模型")
    index_model_id: Optional[UUID] = Field(None, description="索引租户模型ID（可选）")
    vision_model: Optional[str] = Field(None, max_length=100, description="视觉模型")
    vision_model_id: Optional[UUID] = Field(None, description="视觉租户模型ID（可选）")
    pdf_parser_config: PdfParserConfig = Field(default_factory=PdfParserConfig, description="PDF解析器配置")
    retrieval_config: Dict[str, Any] = Field(default_factory=dict, description="检索配置")
    intelligence_config: IntelligenceConfig = Field(default_factory=IntelligenceConfig, description="智能能力配置")
    
    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v: str) -> str:
        if v not in ["private", "tenant_public"]:
            raise ValueError("可见性必须是 private 或 tenant_public")
        return v
    
    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        valid_types = ["general", "qa", "table", "web", "media", "connector"]
        if v not in valid_types:
            raise ValueError(f"类型必须是以下之一: {', '.join(valid_types)}")
        return v


class KnowledgeBaseUpdate(BaseModel):
    """知识库更新 Schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    icon_url: Optional[str] = Field(None, max_length=512)
    visibility: Optional[str] = None
    type: Optional[str] = None
    
    # RAG 配置（可选更新）
    chunking_mode: Optional[Literal["smart", "custom"]] = None
    chunking_config: Optional[ChunkingConfig] = None
    embedding_model: Optional[str] = Field(None, max_length=100)
    embedding_model_id: Optional[UUID] = None
    index_model: Optional[str] = Field(None, max_length=100)
    index_model_id: Optional[UUID] = None
    vision_model: Optional[str] = Field(None, max_length=100)
    vision_model_id: Optional[UUID] = None
    pdf_parser_config: Optional[PdfParserConfig] = None
    retrieval_config: Optional[Dict[str, Any]] = None
    intelligence_config: Optional[IntelligenceConfig] = None
    
    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ["private", "tenant_public"]:
            raise ValueError("可见性必须是 private 或 tenant_public")
        return v
    
    @field_validator("type")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> Optional[str]:
        valid_types = ["general", "qa", "table", "web", "media", "connector"]
        if v and v not in valid_types:
            raise ValueError(f"类型必须是以下之一: {', '.join(valid_types)}")
        return v


class KnowledgeBaseRead(BaseModel):
    """知识库读取 Schema"""
    id: UUID
    tenant_id: UUID
    owner_id: UUID
    name: str
    description: Optional[str] = None
    icon_url: Optional[str] = None
    visibility: str
    type: str = "general"
    
    # RAG 配置
    chunking_mode: str = "smart"
    chunking_config: Dict[str, Any] = {}
    embedding_model: Optional[str] = None
    embedding_model_id: Optional[UUID] = None
    index_model: Optional[str] = None
    index_model_id: Optional[UUID] = None
    vision_model: Optional[str] = None
    vision_model_id: Optional[UUID] = None
    pdf_parser_config: Dict[str, Any] = {}
    retrieval_config: Dict[str, Any] = {}
    intelligence_config: Dict[str, Any] = {}
    
    # 审计字段
    created_by_id: Optional[UUID] = None
    created_by_name: Optional[str] = None
    updated_by_id: Optional[UUID] = None
    updated_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    @field_validator("type", mode="before")
    @classmethod
    def validate_type_default(cls, v):
        """处理 type 为 None 的情况"""
        return v if v is not None else "general"
    
    @field_validator("chunking_mode", mode="before")
    @classmethod
    def validate_chunking_mode_default(cls, v):
        """处理 chunking_mode 为 None 的情况"""
        return v if v is not None else "smart"
    
    @field_validator("chunking_config", mode="before")
    @classmethod
    def validate_chunking_config_default(cls, v):
        """处理 chunking_config 为 None 的情况"""
        return v if v is not None else {}
    
    @field_validator("pdf_parser_config", mode="before")
    @classmethod
    def validate_pdf_parser_config_default(cls, v):
        """处理 pdf_parser_config 为 None 的情况，提供完整默认值"""
        if v is None or v == {}:
            return {
                "parser": "native",
                "enable_ocr": True,
                "ocr_engine": "auto",
                "ocr_languages": ["ch", "en"],
                "extract_images": False,
                "extract_tables": True,
            }
        # 确保 parser 字段存在
        if isinstance(v, dict) and "parser" not in v:
            v["parser"] = "native"
        return v
    
    @field_validator("retrieval_config", mode="before")
    @classmethod
    def validate_retrieval_config_default(cls, v):
        """处理 retrieval_config 为 None 的情况"""
        return v if v is not None else {}

    @field_validator("intelligence_config", mode="before")
    @classmethod
    def validate_intelligence_config_default(cls, v):
        """处理 intelligence_config 为 None 的情况"""
        return v if v is not None else {}
    
    model_config = {"from_attributes": True}

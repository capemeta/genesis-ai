import os
import sys
import logging
from pathlib import Path

# 添加项目根目录到 sys.path
# 结构: d:\workspace\python\genesis-ai\genesis-ai-platform\tests\native\test_native_parser.py
# 导入路径应为 rag.ingestion...
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
sys.path.append(str(project_root))

from rag.ingestion.parsers.pdf.native.parser import NativePDFParser

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def elements_to_markdown(elements, asset_dir_name=None):
    """
    将 ParserElement 列表转换为 Markdown 字符串
    - 增加代码块自动成组逻辑
    - 增加图片相对路径支持
    - 兼容 type="title" + metadata["level"] 格式
    """
    md_lines = []
    in_code_block = False

    for i, el in enumerate(elements):
        el_type = el["type"]
        content = el["content"]
        metadata = el.get("metadata", {})

        # 处理代码块自动成组
        if el_type == "code":
            if not in_code_block:
                md_lines.append("```")
                in_code_block = True
            md_lines.append(content)

            # 检查下一行是否还是代码，如果不是，闭合代码块
            is_next_code = (i + 1 < len(elements) and elements[i+1]["type"] == "code")
            if not is_next_code:
                md_lines.append("```")
                in_code_block = False
            continue

        # 如果之前在代码块中（防御性），先闭合
        if in_code_block:
            md_lines.append("```")
            in_code_block = False

        # 处理标题（兼容两种格式）
        if el_type == "title":
            # 新格式：type="title" + metadata["level"]
            level = metadata.get("level", 1)
            md_lines.append(f"\n{'#' * level} {content.strip()}")
        elif el_type.startswith('h') and el_type[1:].isdigit():
            # 旧格式：type="h1", "h2" 等（向后兼容）
            level = int(el_type[1:])
            md_lines.append(f"\n{'#' * level} {content.strip()}")
        elif el_type == "table":
            md_lines.append(f"\n{content}\n")
        elif el_type == "image":
            # 从元数据中获取图片数据（兼容新旧格式）
            image_bytes = metadata.get("blob") or metadata.get("image_bytes")

            if image_bytes and asset_dir_name:
                # 保存图片到本地
                img_filename = content
                # 输出图片引用
                img_ref = f"{asset_dir_name}/{img_filename}"
                md_lines.append(f"\n![{img_filename}]({img_ref})\n")
            else:
                # 没有图片数据或资源目录，只输出占位符
                md_lines.append(f"\n![{content}]({content})\n")
        else:
            md_lines.append(content)

    return "\n".join(md_lines)

def test_native_parser():
    # 路径配置
    base_dir = Path(r"d:\workspace\python\genesis-ai\genesis-ai-platform")
    data_dir = base_dir / "tests" / "data"
    output_dir = base_dir / "tests" / "native" / "output"

    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)

    test_files = [
        "江西开普元AI中台对外接口规范_v1.2.pdf",
        "1.【鼓励企业营收上台阶奖励】惠企事项模板.pdf",
        "数据要素大赛申报书（字数删减）.pdf",
        "2014年广东省中考化学试题(清晰扫描版).pdf"
    ]

    parser = NativePDFParser(enable_ocr=False)

    for file_name in test_files:
        input_path = data_dir / file_name
        output_path = output_dir / f"{Path(file_name).stem}_out.md"

        if not input_path.exists():
            logger.error(f"Input file not found: {input_path}")
            continue

        logger.info(f"Processing: {file_name}...")
        try:
            # 执行解析（测试模式：返回元素列表）
            elements = parser.parse(str(input_path))

            # 创建资源目录并保存图片
            asset_dir_name = f"{Path(file_name).stem}_assets"
            asset_path = output_dir / asset_dir_name
            asset_path.mkdir(parents=True, exist_ok=True)

            # 保存图片（兼容新旧元数据格式）
            for el in elements:
                if el["type"] == "image":
                    metadata = el.get("metadata", {})
                    image_bytes = metadata.get("blob") or metadata.get("image_bytes")
                    if image_bytes:
                        img_filename = el["content"]
                        with open(asset_path / img_filename, "wb") as img_f:
                            img_f.write(image_bytes)

            # 转换为 Markdown
            markdown_content = elements_to_markdown(elements, asset_dir_name=asset_dir_name)

            # 写入文件
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            logger.info(f"Successfully saved to: {output_path}")

        except Exception as e:
            logger.exception(f"Error processing {file_name}: {e}")

if __name__ == "__main__":
    test_native_parser()

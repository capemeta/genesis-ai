import importlib.util
from pathlib import Path


def _load_pgvector_utils_module():
    """直接按文件路径加载模块，避免测试期触发 rag 包的重型导入。"""
    module_path = Path(__file__).resolve().parents[2] / "rag" / "pgvector_utils.py"
    spec = importlib.util.spec_from_file_location("test_pgvector_utils_module", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError("无法加载 rag.pgvector_utils 模块")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MODULE = _load_pgvector_utils_module()
build_vector_cast_type = _MODULE.build_vector_cast_type
ensure_pgvector_dimension_compatible = _MODULE.ensure_pgvector_dimension_compatible
parse_vector_dimension = _MODULE.parse_vector_dimension


def test_parse_vector_dimension_returns_fixed_dimension() -> None:
    """固定维度类型应能被正确解析。"""
    assert parse_vector_dimension("vector(1536)") == 1536


def test_parse_vector_dimension_returns_none_for_unbounded_vector() -> None:
    """未固定维度时返回 None。"""
    assert parse_vector_dimension("vector") is None


def test_build_vector_cast_type_prefers_index_dimension() -> None:
    """SQL cast 应优先跟随数据库列定义。"""
    assert build_vector_cast_type(index_dimension=1024, fallback_dimension=1536) == "vector(1024)"


def test_ensure_pgvector_dimension_compatible_raises_on_mismatch() -> None:
    """维度不一致时应给出明确异常。"""
    try:
        ensure_pgvector_dimension_compatible(
            actual_dimension=1024,
            index_dimension=1536,
            scene="检索测试",
        )
    except RuntimeError as exc:
        assert "1024" in str(exc)
        assert "1536" in str(exc)
    else:
        raise AssertionError("预期维度不匹配时抛出 RuntimeError")

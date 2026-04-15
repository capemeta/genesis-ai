"""
嵌入模型字符与 Token 关系统计测试。

调用 OpenAI 兼容的 Embeddings API，用多组中英文样本统计：
- 字符数（含空格、标点）
- 单词数（按空白切分，适用于英文）
- Token 数（来自 API 返回的 usage）
- 字符数/Token数、单词数/Token数 比值（以 token 为分母）

用于评估分块、限长时按字符/单词估算 token 的合理性。

结论：虽然tiktoken是估计openai更准，但是用tiktoken估算比其他嵌入模型 千问、bge等更严格，所以能保证不超嵌入模型上下文。
"""
import json
import sys
from pathlib import Path

# 保证能导入项目根
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests
from rag.utils.model_utils import model_config_manager
from rag.utils.token_utils import count_tokens

EMBEDDING_URL = "https://api.siliconflow.cn/v1/embeddings"
API_KEY = "sk-telnbzunlurdfbtzdaothodsqrhaxrvntirueupqzuppglnt"
# BAAI/bge-large-zh-v1.5 BAAI/bge-m3  Pro/BAAI/bge-m3  Qwen/Qwen3-Embedding-4B  Qwen/Qwen3-Embedding-0.6B
MODEL = "BAAI/bge-large-zh-v1.5" 

# EMBEDDING_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
# API_KEY = "sk-d9ca67dd361c4347b582386197867c05"
# MODEL = "text-embedding-v4" 

def count_chinese_chars(s: str) -> int:
    """统计中文字符数（CJK 统一汉字等）。"""
    return sum(1 for c in s if "\u4e00" <= c <= "\u9fff" or "\u3400" <= c <= "\u4dbf")


def count_ascii_chars(s: str) -> int:
    """统计 ASCII 字符数（英文、数字、常见标点）。"""
    return sum(1 for c in s if ord(c) < 128)


def count_words(s: str) -> int:
    """统计单词数（按空白切分，英文等以空格分隔的语言适用）。"""
    return len(s.split())


def _is_cjk_or_cjk_punct(c: str) -> bool:
    """单字符是否为 CJK 汉字或中文标点（含 \u3000-\u303f 等）。"""
    o = ord(c)
    if "\u4e00" <= c <= "\u9fff" or "\u3400" <= c <= "\u4dbf":
        return True
    if 0x3000 <= o <= 0x303F:  # CJK 符号与标点（、。，「」等）
        return True
    if 0xFF00 <= o <= 0xFFEF:  # 全角字符（含全角标点）
        return True
    return False


from rag.utils.token_utils import count_mixed_units, is_chunk_safe


def classify_lang(chinese_count: int, ascii_count: int, char_count: int, word_count: int) -> str:
    """判定样本主语言：zh=中文（看字符数）, en=英文（看单词数）, mixed=混合（两都看）。"""
    if char_count == 0:
        return "mixed"
    if chinese_count >= 0.5 * char_count:
        return "zh"
    if ascii_count >= 0.6 * char_count and word_count >= 2:
        return "en"
    return "mixed"


def openai_estimate_tokens(chinese_count: int, char_count: int) -> int:
    """OpenAI 文档常见经验估算：英文约 4 字符/token，中文约 1.5 字符/token。"""
    if char_count == 0:
        return 0
    other_count = char_count - chinese_count
    est = chinese_count / 1.5 + other_count / 4.0
    return max(1, int(round(est)))


def call_embedding(texts: list[str]) -> dict:
    """调用 Embeddings API，返回原始 JSON。"""
    resp = requests.post(
        EMBEDDING_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={"input": texts, "model": MODEL},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


# 多组测试样本：覆盖纯中文、纯英文、中英混合、长短不一
TEST_CASES = [
    {
        "name": "短句-纯中文",
        "text": "今天天气很好，适合出门散步。",
    },
    {
        "name": "短句-纯英文",
        "text": "The quick brown fox jumps over the lazy dog.",
    },
    {
        "name": "中等-纯中文",
        "text": "人工智能是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统，"
        "包括视觉感知、语音识别、决策和语言翻译等。近年来深度学习的发展极大地推动了该领域的进步。",
    },
    {
        "name": "中等-纯英文",
        "text": "Artificial intelligence is a branch of computer science devoted to building systems "
        "that can perform tasks typically requiring human intelligence, including visual perception, "
        "speech recognition, decision-making and language translation. Deep learning has greatly advanced the field.",
    },
    {
        "name": "中等-中英混合",
        "text": "大模型（Large Language Model）如 GPT、Claude 在自然语言处理（NLP）任务上表现优异，"
        "被广泛应用于问答、摘要、代码生成等场景。RAG 技术结合检索与生成，提升了回答的准确性。",
    },
    {
        "name": "长段-纯中文",
        "text": "知识库是组织内部用于存储、管理和检索知识的系统。构建企业题一起送入大模型知识库时，通常需要将文档进行分块（将文档进行分）"
        "然后对每个文本块调用嵌入模型得到向题一起送入大模型量，再存入向量数据库。检题一起送入大模型索时用查询文本的向量做相似度搜索，"
        "取相关块作为上下文，与用户问题一起送入大模型生成最终答案。分块策略和题一起送入大模型嵌入模型的为上下文，与用户问题一起送入大模型生成最终答案。分块策略和嵌入模型的为上下文，与用户问题一起送入大模型生成最终答案。分块策略和嵌入模型的为上下文，与用户问题一起送入大模型生成最终答案。分块策略和嵌入模型的为上下文，与用户问题一起送入大模型生成最终答案。分块策略和嵌入模型的为上下文，与用户问题一起送入大模型生成最终答案。分块策略和嵌入模型的选择会直接影响的效果。",
    },
    {
        "name": "长段-中英混合",
        "text": "在 RAG（Retrieval-Augmented Generation）流程中，embedding 模型将文本映射为高维向量。"
        "常用的开源模型包括 m3e、bge、GTE 等，它们在中文语义表示上各有特点。实际部署时需要考虑最大序列长度，"
        "例如 512 或 8192 tokens，超过部分需要截断或分段处理。统计字符与 token 的对应关系有助于合理设置 chunk size。"
        "用 AST（抽象语法树）解析代码，优先按函数、类、方法边界切分，而不是盲目按 token/行用 AST（抽象语法树）解析代码，优先按函数、类、方法边界切分",
    },
    {
        "name": "含数字与标点",
        "text": "2024年Q1季度，公司营收同比增长约 15.3%；研发投入占比 22.5%。主要产品线包括：API 服务、SaaS 平台、企业定制方案。",
    },
]


def main():
    print("=" * 60)
    print("嵌入模型 字符 vs Token 统计（OpenAI 兼容 API）")
    print(f"API: {EMBEDDING_URL}")
    print(f"Model: {MODEL}")
    print("=" * 60)

    # 逐条请求，便于从 usage 里拿到每条输入的 token 数（若 API 按条返回）
    results = []
    for case in TEST_CASES:
        name = case["name"]
        text = case["text"]
        char_count = len(text)
        word_count = count_words(text)
        mixed_units = count_mixed_units(text)
        chinese_count = count_chinese_chars(text)
        ascii_count = count_ascii_chars(text)
        tiktoken_count = count_tokens(text)  # 使用 tiktoken 计算

        lang = classify_lang(chinese_count, ascii_count, char_count, word_count)
        try:
            data = call_embedding([text])
        except requests.RequestException as e:
            print(f"[{name}] 请求失败: {e}")
            openai_est = openai_estimate_tokens(chinese_count, char_count)
            mixed_units = count_mixed_units(text)
            results.append({
                "name": name,
                "chars": char_count,
                "words": word_count,
                "mixed_units": mixed_units,
                "chinese": chinese_count,
                "ascii": ascii_count,
                "tokens": None,
                "tiktoken": tiktoken_count,
                "openai_est": openai_est,
                "ratio": None,
                "ratio_word": None,
                "ratio_mixed": None,
                "ratio_tiktoken": ratio_tiktoken,
                "lang": lang,
                "error": str(e),
            })
            continue

        # 兼容 usage 在顶层或 per-item
        usage = data.get("usage") or {}
        total_tokens = usage.get("total_tokens")
        prompt_tokens = usage.get("prompt_tokens")
        token_count = total_tokens or prompt_tokens
        tokens_from_api = token_count is not None

        # 若 API 不返回 token，不做假数据：占位仅用于标注，不参与汇总与平均
        if token_count is None:
            token_count = char_count  # 仅用于本行打印，汇总表里显示 N/A
            token_note = "（API 未返回 usage，此处为占位，非真实 Token 数）"
        else:
            token_note = ""

        ratio = (char_count / token_count) if (token_count and tokens_from_api) else None
        ratio_word = (word_count / token_count) if (token_count and tokens_from_api and word_count) else None
        ratio_mixed = (mixed_units / token_count) if (token_count and tokens_from_api) else None
        ratio_tiktoken = (char_count / tiktoken_count) if tiktoken_count else None  # 字符/tiktoken
        openai_est = openai_estimate_tokens(chinese_count, char_count)
        genesis_safe_limit = model_config_manager.get_safe_token_limit(MODEL)

        # 首次请求时打印响应结构，便于确认 API 是否返回 usage
        if not results and not tokens_from_api:
            print("\n[调试] 本次响应顶层键:", list(data.keys()))
            if "usage" in data:
                print("[调试] usage 内容:", data["usage"])
            else:
                print("[调试] 响应中无 usage 字段，无法获取真实 Token 数。")

        results.append({
            "name": name,
            "chars": char_count,
            "words": word_count,
            "mixed_units": mixed_units,
            "chinese": chinese_count,
            "ascii": ascii_count,
            "tokens": token_count if tokens_from_api else None,
            "tokens_placeholder": char_count if not tokens_from_api else None,
            "tiktoken": tiktoken_count,
            "openai_est": openai_est,
            "ratio": ratio,
            "ratio_word": ratio_word,
            "ratio_mixed": ratio_mixed,
            "ratio_tiktoken": ratio_tiktoken,
            "lang": lang,
            "from_api": tokens_from_api,
            "note": token_note,
        })

        print(f"\n[{name}] [{'中文' if lang == 'zh' else '英文' if lang == 'en' else '混合'}]")
        print(f"  Token 数: {token_count}{token_note}")
        print(f"  Tiktoken 数: {tiktoken_count} (cl100k_base)")
        print(f"  OpenAI 估算: {openai_est} (对照组)")
        print(f"  Genesis 安全限额: {genesis_safe_limit} (配置值)")
        print(f"  安全检查 (is_chunk_safe): {'通过' if is_chunk_safe(text, MODEL) else '超限'}")
        if lang == "zh":
            print(f"  字符数: {char_count}（中文 {chinese_count}）")
            if ratio is not None:
                print(f"  字符数/Token数: {ratio:.4f} ← 中文看此项")
            else:
                print("  字符数/Token数: N/A（API 未返回 Token）")
            if ratio_tiktoken is not None:
                print(f"  字符数/Tiktoken数: {ratio_tiktoken:.4f}")
        elif lang == "en":
            print(f"  单词数: {word_count}（ASCII {ascii_count}）")
            if ratio_word is not None:
                print(f"  单词数/Token数: {ratio_word:.4f} ← 英文看此项")
            else:
                print("  单词数/Token数: N/A")
            if ratio_tiktoken is not None:
                print(f"  字符数/Tiktoken数: {ratio_tiktoken:.4f}")
        else:
            print(f"  字符数: {char_count} | 单词数: {word_count} | 混合单位: {mixed_units}（中文按字符，英/数按单位）")
            if ratio is not None:
                print(f"  字符数/Token数: {ratio:.4f}")
            else:
                print("  字符数/Token数: N/A")
            if ratio_word is not None:
                print(f"  单词数/Token数: {ratio_word:.4f}")
            elif word_count > 0:
                print("  单词数/Token数: N/A")
            if ratio_mixed is not None:
                print(f"  混合单位/Token数: {ratio_mixed:.4f}（英、数按独立算）")
            if ratio_tiktoken is not None:
                print(f"  字符数/Tiktoken数: {ratio_tiktoken:.4f}")

    # 汇总表（字符/Token、单词/Token、字符/Token(英数按单位)、字符/Tiktoken；含 OpenAI 估算）
    print("\n" + "=" * 120)
    print("汇总（字符/Token | 单词/Token | 字符/Token(英文单词、数字按独立算) | 字符/Tiktoken）")
    print("=" * 120)
    print(f"{'案例':<20} {'字符':>6} {'单词':>6} {'混合单位':>8} {'API Token':>10} {'Tiktoken':>10} {'OpenAI估算':>10} {'字符/Token':>10}  {'字符/Tiktoken':>12} {'单词/Token':>10} {'混合/Token':>10}")
    print("-" * 120)
    for r in results:
        if r.get("error"):
            print(f"{r['name']:<20} 请求失败: {r['error'][:28]}")
        elif r.get("from_api"):
            tok_str = str(r["tokens"]) if r.get("tokens") is not None else "N/A"
            tiktoken_str = str(r.get("tiktoken", "N/A"))
            oa_str = str(r.get("openai_est", ""))
            
            # 计算所有四个比率
            ratio_str = f"{r['ratio']:.4f}" if r.get("ratio") is not None else "N/A"
            rw = r.get("ratio_word")
            ratio_word_str = f"{rw:.4f}" if rw is not None else "N/A"
            rm = r.get("ratio_mixed")
            ratio_mixed_str = f"{rm:.4f}" if rm is not None else "N/A"
            rt = r.get("ratio_tiktoken")
            ratio_tiktoken_str = f"{rt:.4f}" if rt is not None else "N/A"
            
            print(f"{r['name']:<20} {r['chars']:>6} {r['words']:>6} {r.get('mixed_units', 0):>8} {tok_str:>10} {tiktoken_str:>10} {oa_str:>10} {ratio_str:>10} {ratio_tiktoken_str:>12} {ratio_word_str:>10} {ratio_mixed_str:>10} ")
        else:
            tiktoken_str = str(r.get("tiktoken", "N/A"))
            oa_str = str(r.get("openai_est", ""))
            rt = r.get("ratio_tiktoken")
            ratio_tiktoken_str = f"{rt:.4f}" if rt is not None else "N/A"
            print(f"{r['name']:<20} {r['chars']:>6} {r['words']:>6} {r.get('mixed_units', 0):>8} {'N/A(占位)':>10} {tiktoken_str:>10} {oa_str:>10} {'N/A':>10} {'N/A':>10} {'N/A':>10} {ratio_tiktoken_str:>12}")
    print("-" * 120)

    # 中文样本只算平均 字符/Token，英文样本只算平均 单词/Token（均以 token 为分母）
    valid_zh = [r for r in results if r.get("from_api") and r.get("lang") == "zh" and r.get("ratio") is not None]
    valid_en = [r for r in results if r.get("from_api") and r.get("lang") == "en" and r.get("ratio_word") is not None]
    if valid_zh:
        avg_zh = sum(r["ratio"] for r in valid_zh) / len(valid_zh)
        print(f"【中文】平均 字符数/Token数: {avg_zh:.4f}（共 {len(valid_zh)} 条）")
    if valid_en:
        avg_en = sum(r["ratio_word"] for r in valid_en) / len(valid_en)
        print(f"【英文】平均 单词数/Token数: {avg_en:.4f}（共 {len(valid_en)} 条）")
    if valid_zh or valid_en:
        print("\n说明：字符/Token、单词/Token 以 token 为分母；混合/Token = 混合单位/Token，中文按字符、英文单词与数字按独立单位算。")
        print("字符/Tiktoken 使用 tiktoken (cl100k_base) 计算，作为工业标准参考。")
    print("OpenAI 估算规则（经验值，非本接口真实 tokenizer）：英文约 4 字符/token，中文约 1.5 字符/token。")
    if not valid_zh and not valid_en:
        print("平均: 无（需 API 返回 usage；中文类算 字符/Token，英文类算 单词/Token）。")
        if not any(r.get("from_api") for r in results):
            print("建议：确认接口是否返回 usage.total_tokens / usage.prompt_tokens。")

    return 0 if not any(r.get("error") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())

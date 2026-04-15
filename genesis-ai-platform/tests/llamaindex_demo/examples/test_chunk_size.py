"""
测试 SentenceSplitter 的 chunk_size 是基于 token 还是字符
"""

# 简单测试文本
test_text = "这是第一句话。这是第二句话。这是第三句话。这是第四句话。这是第五句话。"

print(f"测试文本: {test_text}")
print(f"文本字符数: {len(test_text)}")
print("-" * 100)

# 使用 tiktoken 计算 token 数（LlamaIndex 默认使用 tiktoken）
try:
    import tiktoken
    
    # 使用 cl100k_base 编码器（GPT-3.5/GPT-4 使用的编码器）
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(test_text)
    
    print(f"\n使用 tiktoken (cl100k_base) 计算:")
    print(f"Token 数量: {len(tokens)}")
    print(f"Token 详情: {tokens}")
    print(f"平均每个Token的 字符 数: {len(test_text) / len(tokens):.2f}")
    
except ImportError:
    print("\ntiktoken 未安装，无法测试 token 计算")

print("\n" + "=" * 100)

# 测试 SentenceSplitter
try:
    from llama_index.core.node_parser import SentenceSplitter
    
    print("\n测试 SentenceSplitter:")
    
    # 创建一个 chunk_size=10 的分割器
    splitter = SentenceSplitter(
        chunk_size=10,
        chunk_overlap=0,
        separator=" "
    )
    
    # 分割文本
    chunks = splitter.split_text(test_text)
    
    print(f"\nchunk_size=10 的分块结果:")
    print(f"分块数量: {len(chunks)}")
    for i, chunk in enumerate(chunks):
        print(f"\n块 {i+1}:")
        print(f"  字符数: {len(chunk)}")
        print(f"  内容: {chunk}")
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            chunk_tokens = encoding.encode(chunk)
            print(f"  Token数: {len(chunk_tokens)}")
        except:
            pass
    
    print("\n" + "=" * 100)
    print("结论:")
    print("如果 chunk_size 是基于 token：每个块的 token 数应该 ≤ 10")
    print("如果 chunk_size 是基于字符：每个块的字符数应该 ≤ 10")
    
except ImportError as e:
    print(f"\nLlamaIndex 未安装: {e}")
    print("\n但从源码分析:")
    print("SentenceSplitter 使用 self._tokenizer 来计算大小")
    print("默认使用 tiktoken.get_encoding('cl100k_base')")
    print("因此 chunk_size 确实是基于 TOKEN 而非字符")

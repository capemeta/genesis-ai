
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
core_path = os.path.join(current_dir, "llama-index-core")
if os.path.exists(core_path):
    sys.path.append(core_path)

from llama_index.core.utils import get_tokenizer

def test_token_ratio():
    # 默认 tokenizer 通常是 tiktoken (cl100k_base for GPT-4/3.5)
    tokenizer = get_tokenizer()
    
    print(f"Tokenizer class: {tokenizer.__class__}")
    if hasattr(tokenizer, "name"):
         print(f"Tokenizer name: {tokenizer.name}")

    # Case 1: Short text
    text = """
    
~~~shell
$ grep -E 'ssl_certificate|ssl_certificate_key' /home/coremail/conf/nginx.conf

$ grep -E 'SSLCertFileName|SSLKeyFileName|SSLChainCertFileName' /home/coremail/conf/services.cf
~~~

- **获取新的公钥证书、私钥和中间证书命名为：server.crt  server.key  chain.crt。**

  !
"""
    tokens = tokenizer(text)
    
    print("-" * 30)
    print(f"Case 1: Short Text")
    print(f"Text content: '{text}'")
    print(f"Character count (len): {len(text)}")
    print(f"Token count: {len(tokens)}")
    print(f"Ratio (Chars/Token): {len(text)/len(tokens):.2f}")
    
    # Case 2: Longer Mixed text
    long_text = (
        "水电费加快速度开发建设到啦开发机来看你束带结发莱克斯顿九分裤记录卡"
    ) * 5
    tokens_long = tokenizer(long_text)
    
    print("-" * 30)
    print(f"Case 2: Long Text (Mixed)")
    print(f"Character count: {len(long_text)}")
    print(f"Token count: {len(tokens_long)}")
    print(f"Ratio (Chars/Token): {len(long_text)/len(tokens_long):.2f}")

    # Case 3: Verify SentenceSplitter defaults
    print("-" * 30)
    try:
        from llama_index.core.node_parser import SentenceSplitter
        splitter = SentenceSplitter(chunk_size=100, chunk_overlap=0)
        print("SentenceSplitter initialized successfully.")
        print(f"Splitter chunk_size: {splitter.chunk_size}")
        
        # Test splitting
        chunks = splitter.split_text(long_text)
        print(f"Split long text into {len(chunks)} chunks with size limit 100 tokens.")
        for i, chunk in enumerate(chunks):
            t_count = len(tokenizer(chunk))
            print(f"  Chunk {i+1}: {len(chunk)} chars, {t_count} tokens")
            
    except ImportError:
        print("Could not import SentenceSplitter for verification.")

if __name__ == "__main__":
    test_token_ratio()

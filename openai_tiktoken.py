import tiktoken

if __name__ == '__main__':
    encoding = tiktoken.encoding_for_model("gpt-4")
    prompt = """"
你好，帮我写一段关于计算token的代码。
"""
    tokens = encoding.encode(prompt)
    print("Token 数量:", len(tokens))

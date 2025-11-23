# test_imports.py
print("🧪 패키지 import 테스트 시작...\n")

try:
    import langchain
    print("✅ langchain:", langchain.__version__)
except Exception as e:
    print("❌ langchain:", e)

try:
    import langchain_community
    print("✅ langchain_community")
except Exception as e:
    print("❌ langchain_community:", e)

try:
    import langchain_openai
    print("✅ langchain_openai")
except Exception as e:
    print("❌ langchain_openai:", e)

# ✨ 최신 import 방식으로 변경
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    print("✅ RecursiveCharacterTextSplitter (langchain_text_splitters)")
except Exception as e:
    print("❌ RecursiveCharacterTextSplitter:", e)

try:
    from langchain.chains.retrieval_qa.base import RetrievalQA
    print("✅ RetrievalQA (langchain.chains.retrieval_qa.base)")
except Exception as e:
    print("❌ RetrievalQA:", e)

try:
    from langchain_core.documents import Document
    print("✅ Document (langchain_core.documents)")
except Exception as e:
    print("❌ Document:", e)

try:
    from langchain_core.prompts import PromptTemplate
    print("✅ PromptTemplate (langchain_core.prompts)")
except Exception as e:
    print("❌ PromptTemplate:", e)

try:
    import faiss
    print("✅ faiss-cpu")
except Exception as e:
    print("❌ faiss-cpu:", e)

try:
    import openai
    print("✅ openai:", openai.__version__)
except Exception as e:
    print("❌ openai:", e)

print("\n✅ 모든 import 테스트 완료!")
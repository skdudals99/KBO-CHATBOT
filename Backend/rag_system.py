# rag_system.py
# ============================================
# ⚾ RAG 시스템 (LangChain + FAISS + OpenAI)
# ============================================

import os
import pandas as pd
from typing import List, Dict
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

class RAGSystem:
    def __init__(self, csv_path: str, vector_store_path: str = None):
        """
        RAG 시스템 초기화
        
        Args:
            csv_path: final_final4_docs.csv 경로
            vector_store_path: FAISS 인덱스 저장/로드 경로
        """
        self.csv_path = csv_path
        self.vector_store_path = vector_store_path
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        self.llm = ChatOpenAI(
            model="gpt-4",
            temperature=0.3,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        self.vectorstore = None
        self.retriever = None
        
        # 벡터 스토어 초기화
        self._initialize_vectorstore()
    
    def _load_documents_from_csv(self) -> List[Document]:
        """CSV에서 문서 로드"""
        print(f"📂 CSV 로드 중: {self.csv_path}")
        
        df = pd.read_csv(self.csv_path, encoding="utf-8-sig")
        print(f"✅ 로드 완료: {len(df)} 행")
        
        documents = []
        for idx, row in df.iterrows():
            # DOC_TEXT를 content로
            content = str(row.get("DOC_TEXT", ""))
            
            # 메타데이터 구성
            metadata = {
                "season": int(row.get("SEASON_ID", 0)),
                "pitcher": str(row.get("PITCHER_NAME", "")),
                "batter": str(row.get("BATTER_NAME", "")),
                "pitcher_hand": str(row.get("PITCHER_HAND", "")),
                "batter_hand": str(row.get("BATTER_HAND", "")),
                "pitcher_pitch_type": str(row.get("PITCHER_BEST_PITCH_TYPE", "")),
                "batter_pitch_type": str(row.get("BATTER_BEST_PITCH_TYPE", "")),
                "row_id": idx
            }
            
            doc = Document(page_content=content, metadata=metadata)
            documents.append(doc)
        
        return documents
    
    def _initialize_vectorstore(self):
        """벡터 스토어 초기화 (저장된 것 로드 or 새로 생성)"""
        
        # 기존 벡터 스토어가 있으면 로드
        if self.vector_store_path and os.path.exists(self.vector_store_path):
            print(f"📦 기존 벡터 스토어 로드 중: {self.vector_store_path}")
            try:
                self.vectorstore = FAISS.load_local(
                    self.vector_store_path,
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                print("✅ 벡터 스토어 로드 완료")
            except Exception as e:
                print(f"⚠️ 벡터 스토어 로드 실패: {e}")
                print("🔄 새로 생성합니다...")
                self._create_new_vectorstore()
        else:
            print("🆕 새 벡터 스토어 생성 중...")
            self._create_new_vectorstore()
        
        # Retriever 구성
        self._setup_retriever()
    
    def _create_new_vectorstore(self):
        """새 벡터 스토어 생성"""
        # 문서 로드
        documents = self._load_documents_from_csv()
        
        # 텍스트 분할 (한글 최적화)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", ".", ",", " ", ""]
        )
        split_docs = text_splitter.split_documents(documents)
        print(f"📄 분할된 문서 수: {len(split_docs)}")
        
        # 벡터 스토어 생성
        print("🔄 임베딩 생성 중... (시간이 걸릴 수 있습니다)")
        self.vectorstore = FAISS.from_documents(split_docs, self.embeddings)
        print("✅ 벡터 스토어 생성 완료")
        
        # 저장
        if self.vector_store_path:
            os.makedirs(os.path.dirname(self.vector_store_path), exist_ok=True)
            self.vectorstore.save_local(self.vector_store_path)
            print(f"💾 벡터 스토어 저장 완료: {self.vector_store_path}")
    
    def _setup_retriever(self):
        """Retriever 구성"""
        self.retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 5}  # 상위 5개 문서 검색
        )
        print("✅ Retriever 구성 완료")
    
    def query(self, question: str) -> Dict:
        """
        질문에 대한 답변 생성
        
        Args:
            question: 사용자 질문
            
        Returns:
            {
                "answer": "답변 텍스트",
                "sources": [관련 문서 메타데이터 리스트]
            }
        """
        if not self.retriever:
            return {
                "answer": "RAG 시스템이 초기화되지 않았습니다.",
                "sources": []
            }
        
        try:
            print(f"\n🔍 RAG 질의: {question}")
            
            # 관련 문서 검색
            docs = self.retriever.get_relevant_documents(question)
            
            # 컨텍스트 구성
            context = "\n\n".join([doc.page_content for doc in docs])
            
            # 프롬프트 구성
            prompt = f"""당신은 KBO(한국프로야구) 매치업 분석 전문가입니다.
아래 제공된 컨텍스트를 바탕으로 질문에 답변하세요.

컨텍스트:
{context}

질문: {question}

답변 가이드라인:
1. 컨텍스트에 정보가 있으면 구체적인 수치와 함께 답변하세요.
2. 정보가 부족하면 "데이터에서 해당 정보를 찾을 수 없습니다"라고 말하세요.
3. 추측하지 말고 데이터 기반으로만 답변하세요.
4. 자연스러운 한국어로 답변하세요.

답변:"""
            
            # LLM 호출
            answer = self.llm.predict(prompt)
            
            # 소스 문서 메타데이터 추출
            sources = []
            for doc in docs:
                sources.append({
                    "season": doc.metadata.get("season"),
                    "pitcher": doc.metadata.get("pitcher"),
                    "batter": doc.metadata.get("batter"),
                    "content_preview": doc.page_content[:100] + "..."
                })
            
            print(f"✅ 답변 생성 완료 (소스: {len(sources)}개)")
            
            return {
                "answer": answer,
                "sources": sources
            }
            
        except Exception as e:
            print(f"❌ RAG 질의 오류: {e}")
            return {
                "answer": f"죄송합니다. 답변 생성 중 오류가 발생했습니다: {str(e)}",
                "sources": []
            }
    
    def search_similar_documents(self, query: str, k: int = 5) -> List[Document]:
        """유사 문서 검색"""
        if not self.vectorstore:
            return []
        
        return self.vectorstore.similarity_search(query, k=k)


# 전역 인스턴스 (싱글톤)
_rag_system_instance = None

def get_rag_system() -> RAGSystem:
    """RAG 시스템 싱글톤 인스턴스 반환"""
    global _rag_system_instance
    
    if _rag_system_instance is None:
        data_dir = os.getenv("DATA_DIR", "./data")
        csv_path = os.path.join(data_dir, "final_final4_docs.csv")
        vector_store_path = os.getenv("VECTOR_STORE_PATH", "./data/vector_store")
        
        _rag_system_instance = RAGSystem(csv_path, vector_store_path)
    
    return _rag_system_instance


# 테스트 코드
if __name__ == "__main__":
    print("🧪 RAG 시스템 테스트")
    
    # 시스템 초기화
    rag = get_rag_system()
    
    # 테스트 질의
    test_questions = [
        "2024년 김광현과 최정의 매치업은 어때?",
        "양현종이 좌타자를 상대할 때 성적은?",
        "체인지업을 잘 던지는 투수는 누가 있어?"
    ]
    
    for q in test_questions:
        print(f"\n{'='*60}")
        result = rag.query(q)
        print(f"질문: {q}")
        print(f"답변: {result['answer']}")
        print(f"소스 수: {len(result['sources'])}")
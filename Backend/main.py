# main.py
# ============================================
# ⚾ FastAPI 백엔드 메인
# ============================================

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv

from hybrid_engine import get_hybrid_engine
from rag_system import get_rag_system

# 환경 변수 로드
load_dotenv()

# FastAPI 앱 생성
app = FastAPI(
    title="KBO 매치업 챗봇 API",
    description="규칙 기반 엔진 + RAG를 결합한 하이브리드 야구 분석 챗봇",
    version="1.0.0"
)

# CORS 설정 (React 프론트엔드 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React 개발 서버
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 엔진 인스턴스
hybrid_engine = None

# 요청/응답 모델
class ChatRequest(BaseModel):
    question: str
    use_rag: bool = True  # RAG 사용 여부 (디폴트: True)

class ChatResponse(BaseModel):
    answer: str
    source: str  # "rule" | "rag" | "hybrid" | "none"
    rule_answer: Optional[str] = None
    rag_answer: Optional[str] = None
    sources: list = []
    debug_info: Optional[Dict[str, Any]] = None


# 시작 이벤트
@app.on_event("startup")
async def startup_event():
    """서버 시작 시 엔진 초기화"""
    global hybrid_engine
    
    print("🚀 서버 시작 중...")
    print("📦 하이브리드 엔진 초기화 중...")
    
    try:
        hybrid_engine = get_hybrid_engine()
        print("✅ 하이브리드 엔진 초기화 완료")
    except Exception as e:
        print(f"❌ 엔진 초기화 실패: {e}")
        raise


# 엔드포인트
@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "KBO 매치업 챗봇 API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {
        "status": "healthy",
        "engine_initialized": hybrid_engine is not None
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    채팅 엔드포인트
    
    Args:
        request: ChatRequest (question, use_rag)
    
    Returns:
        ChatResponse
    """
    if not hybrid_engine:
        raise HTTPException(
            status_code=500,
            detail="엔진이 초기화되지 않았습니다."
        )
    
    if not request.question or len(request.question.strip()) == 0:
        raise HTTPException(
            status_code=400,
            detail="질문을 입력해주세요."
        )
    
    try:
        print(f"\n📨 질문 수신: {request.question}")
        
        # 하이브리드 엔진으로 처리
        result = hybrid_engine.process_query(request.question)
        
        return ChatResponse(
            answer=result["answer"],
            source=result["source"],
            rule_answer=result.get("rule_answer"),
            rag_answer=result.get("rag_answer"),
            sources=result.get("sources", []),
            debug_info=result.get("debug_info")
        )
        
    except Exception as e:
        print(f"❌ 처리 중 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"답변 생성 중 오류가 발생했습니다: {str(e)}"
        )

@app.post("/search")
async def search_documents(query: str, k: int = 5):
    """
    유사 문서 검색 엔드포인트
    
    Args:
        query: 검색어
        k: 반환할 문서 수
    
    Returns:
        검색된 문서 리스트
    """
    try:
        rag = get_rag_system()
        docs = rag.search_similar_documents(query, k=k)
        
        results = []
        for doc in docs:
            results.append({
                "content": doc.page_content,
                "metadata": doc.metadata
            })
        
        return {
            "query": query,
            "count": len(results),
            "results": results
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"검색 중 오류가 발생했습니다: {str(e)}"
        )


# 서버 실행
if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,  # 개발 모드
        log_level="info"
    )
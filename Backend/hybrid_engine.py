# hybrid_engine.py
# ============================================
# ⚾ 하이브리드 엔진 (규칙 기반 + RAG)
# ============================================

from typing import Dict, Any
from router import route_question, dispatch_to_engine
from rag_system import get_rag_system

class HybridEngine:
    """
    규칙 기반 엔진과 RAG를 결합한 하이브리드 시스템
    
    전략:
    1. 먼저 규칙 기반 엔진으로 답변 시도
    2. 규칙 기반으로 답변 못 하면 RAG로 전환
    3. 두 가지 모두 활용 가능한 경우 결합
    """
    
    def __init__(self):
        self.rag_system = get_rag_system()
    
    def process_query(self, question: str) -> Dict[str, Any]:
        """
        질문 처리
        
        Returns:
            {
                "answer": str,
                "source": "rule" | "rag" | "hybrid",
                "rule_answer": str | None,
                "rag_answer": str | None,
                "sources": List[Dict],
                "debug_info": Dict
            }
        """
        print(f"\n🎯 하이브리드 엔진 시작: {question}")
        
        # 1단계: 규칙 기반 엔진 시도
        rule_result = self._try_rule_engine(question)
        
        # 2단계: 규칙 기반 성공 여부 판단
        if rule_result["success"]:
            print("✅ 규칙 기반 엔진으로 답변 생성 성공")
            
            # 규칙 기반만으로 충분한 경우
            if self._is_sufficient_answer(rule_result["answer"]):
                return {
                    "answer": rule_result["answer"],
                    "source": "rule",
                    "rule_answer": rule_result["answer"],
                    "rag_answer": None,
                    "sources": [],
                    "debug_info": rule_result["debug_info"]
                }
            
            # 규칙 기반 답변이 있지만 RAG로 보강 가능
            print("🔄 RAG로 추가 컨텍스트 검색...")
            rag_result = self._try_rag_engine(question)
            
            if rag_result["success"]:
                # 하이브리드: 규칙 기반 + RAG 보강
                hybrid_answer = self._combine_answers(
                    rule_result["answer"],
                    rag_result["answer"]
                )
                return {
                    "answer": hybrid_answer,
                    "source": "hybrid",
                    "rule_answer": rule_result["answer"],
                    "rag_answer": rag_result["answer"],
                    "sources": rag_result.get("sources", []),
                    "debug_info": {
                        "rule": rule_result["debug_info"],
                        "rag": rag_result.get("debug_info", {})
                    }
                }
            else:
                # RAG 실패, 규칙 기반만 사용
                return {
                    "answer": rule_result["answer"],
                    "source": "rule",
                    "rule_answer": rule_result["answer"],
                    "rag_answer": None,
                    "sources": [],
                    "debug_info": rule_result["debug_info"]
                }
        
        # 3단계: 규칙 기반 실패 → RAG로 전환
        print("⚠️ 규칙 기반 엔진 실패, RAG로 전환")
        rag_result = self._try_rag_engine(question)
        
        if rag_result["success"]:
            return {
                "answer": rag_result["answer"],
                "source": "rag",
                "rule_answer": None,
                "rag_answer": rag_result["answer"],
                "sources": rag_result.get("sources", []),
                "debug_info": rag_result.get("debug_info", {})
            }
        
        # 4단계: 둘 다 실패
        return {
            "answer": (
                "죄송합니다. 해당 질문에 대한 답변을 찾을 수 없습니다.\n"
                "다른 방식으로 질문해주시거나, 구체적인 선수 이름과 시즌을 포함해주세요.\n\n"
                "예시:\n"
                "- 2024년 김광현 vs 최정 매치업 알려줘\n"
                "- 양현종이 좌타자를 상대할 때 약한 타자는?\n"
                "- 2사 만루에서 원태인이 나성범에게 슬라이더를 던지면?"
            ),
            "source": "none",
            "rule_answer": None,
            "rag_answer": None,
            "sources": [],
            "debug_info": {
                "rule": rule_result["debug_info"],
                "rag": rag_result.get("debug_info", {})
            }
        }
    
    def _try_rule_engine(self, question: str) -> Dict[str, Any]:
        """규칙 기반 엔진 시도"""
        try:
            route_result = route_question(question)
            answer = dispatch_to_engine(question, route_result)
            
            # 실패 판단 키워드
            failure_keywords = [
                "지원하지 않",
                "인식하지 못했",
                "데이터가 없습니다",
                "찾을 수 없습니다",
                "컬럼이 없습니다",
                "랜덤 데이터만으로는"
            ]
            
            is_failure = any(kw in answer for kw in failure_keywords)
            
            return {
                "success": not is_failure,
                "answer": answer,
                "debug_info": {
                    "intent": route_result.intent,
                    "params": route_result.params
                }
            }
        except Exception as e:
            print(f"❌ 규칙 엔진 오류: {e}")
            return {
                "success": False,
                "answer": str(e),
                "debug_info": {"error": str(e)}
            }
    
    def _try_rag_engine(self, question: str) -> Dict[str, Any]:
        """RAG 엔진 시도"""
        try:
            result = self.rag_system.query(question)
            
            # RAG 답변이 유효한지 확인
            answer = result.get("answer", "")
            
            failure_keywords = [
                "찾을 수 없습니다",
                "정보가 없습니다",
                "오류가 발생했습니다"
            ]
            
            is_failure = any(kw in answer for kw in failure_keywords)
            
            return {
                "success": not is_failure and len(answer) > 10,
                "answer": answer,
                "sources": result.get("sources", []),
                "debug_info": {
                    "source_count": len(result.get("sources", []))
                }
            }
        except Exception as e:
            print(f"❌ RAG 엔진 오류: {e}")
            return {
                "success": False,
                "answer": str(e),
                "debug_info": {"error": str(e)}
            }
    
    def _is_sufficient_answer(self, answer: str) -> bool:
        """
        규칙 기반 답변이 충분한지 판단
        
        기준:
        - 길이가 충분함
        - 구체적인 수치 포함
        - TOP N 리스트 포함
        """
        if len(answer) < 50:
            return False
        
        # 수치나 리스트가 포함되어 있으면 충분
        has_numbers = any(char.isdigit() for char in answer)
        has_ranking = "1)" in answer or "TOP" in answer
        
        return has_numbers or has_ranking
    
    def _combine_answers(self, rule_answer: str, rag_answer: str) -> str:
        """규칙 기반 답변과 RAG 답변 결합"""
        
        combined = f"{rule_answer}\n\n"
        combined += "📚 **추가 컨텍스트 (RAG 검색 결과)**\n"
        combined += f"{rag_answer}"
        
        return combined


# 전역 인스턴스
_hybrid_engine_instance = None

def get_hybrid_engine() -> HybridEngine:
    """하이브리드 엔진 싱글톤 인스턴스 반환"""
    global _hybrid_engine_instance
    
    if _hybrid_engine_instance is None:
        _hybrid_engine_instance = HybridEngine()
    
    return _hybrid_engine_instance


# 테스트 코드
if __name__ == "__main__":
    print("🧪 하이브리드 엔진 테스트")
    
    engine = get_hybrid_engine()
    
    test_questions = [
        "2024년 김광현 vs 최정 매치업 알려줘",
        "양현종이 삼진을 많이 잡을 수 있는 타자는?",
        "체인지업을 잘 던지는 투수는 누가 있어?",
        "2사 만루에서 김광현이 양의지에게 슬라이더를 던지면?",
    ]
    
    for q in test_questions:
        print(f"\n{'='*60}")
        result = engine.process_query(q)
        print(f"질문: {q}")
        print(f"소스: {result['source']}")
        print(f"답변:\n{result['answer']}")
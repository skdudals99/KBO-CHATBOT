📦 설치 및 실행

### 1. Backend
```bash
backend 폴더에 해당되는 터미널 창 열어서 밑에 해당되는 것들 설치하면 됨

# 1. 가상환경 생성
python -m venv venv
venv\Scripts\activate  # Windows

# 2. 패키지 설치
pip install -r requirements.txt

#3. 환경 변수 설정
.env 파일에 OpenAI API 키 입력 

#4. 데이터 파일 배치
Backend/data/ 폴더에 CSV 파일 복사. add_random_final_2.csv랑 final_final4_docs.csv 이거 파일 복사해서 붙여넣기.

# 서버 실행
python main.py

# 백엔드 제대로 실행되는지 확인해보기 

http://localhost:8000
```

⭐ 백엔드가 실행되어 있는 터미널 창 상태에서 Front도 실행해야 해. 백엔드 터미널 창 삭제하거나 닫지 마.

### 2. Frontend

```bash
frontend 폴더에 해당되는 터미널 창 열어서 밑에 해당되는 것들 설치하면 됨. 

1. node.js 설치가 되어 있어야 해. 이거는 node.js 공식 홈 가서 설치해.

# deactivate 먼저 실행

# 패키지 설치
npm install

# 개발 서버 실행
npm run dev
```

### 3. 브라우저에서 접속
```
http://localhost:3000
```

## 📊 데이터 구조

- `add_random_final_2.csv`: 매치업 통계 데이터
- `final_final4_docs.csv`: RAG용 문서 데이터

## 🔑 환경 변수

`.env` 파일에 다음 설정 필요:
```env
OPENAI_API_KEY=your_api_key_here
DATA_DIR=./data
VECTOR_STORE_PATH=./data/vector_store
```
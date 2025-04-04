# 실시간 환율 대시보드

실시간으로 주요 통화(USD, EUR, CAD, AUD)의 대한민국 원화(KRW) 환율을 확인하고 계산할 수 있는 대시보드입니다.

## 주요 기능

- 실시간 환율 모니터링 (USD, EUR, CAD, AUD)
- 30일 환율 추이 차트
- 7일 환율 예측
- 통화 환율 계산기
- 10분 주기 자동 업데이트
- 수동 새로고침 기능
- 모바일 화면 지원

## 데모

온라인 데모는 다음 URL에서 확인할 수 있습니다:
[Streamlit Cloud URL]

## 로컬 실행 방법

1. 저장소 클론
```bash
git clone [repository-url]
cd [repository-name]
```

2. 가상환경 생성 및 활성화
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. 필요한 패키지 설치
```bash
pip install -r requirements.txt
```

4. 실행
```bash
streamlit run fx_dashboard_public.py
```

## 데이터 출처

- 네이버 금융 (실시간 환율 정보)

## 업데이트 주기

- 자동 업데이트: 10분
- 수동 업데이트: 새로고침 버튼 클릭

## 기술 스택

- Python
- Streamlit
- Pandas
- Scikit-learn
- Altair
- BeautifulSoup4 
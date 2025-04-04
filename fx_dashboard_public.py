import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import time
import altair as alt
from datetime import datetime, timedelta
import pytz

# 상수 정의
CURRENCIES = {
    'USD': {'name': '미국 달러', 'code': 'FX_USDKRW'},
    'EUR': {'name': '유럽 유로', 'code': 'FX_EURKRW'},
    'CAD': {'name': '캐나다 달러', 'code': 'FX_CADKRW'},
    'AUD': {'name': '호주 달러', 'code': 'FX_AUDKRW'}
}

# 환율 데이터 크롤링 함수
@st.cache_data(ttl=600, show_spinner=False)
def get_exchange_rates(refresh=False):
    if refresh:
        st.cache_data.clear()
    
    data = {}
    for currency, info in CURRENCIES.items():
        url = f"https://finance.naver.com/marketindex/exchangeDailyQuote.nhn?marketindexCd={info['code']}"
        headers = {"User-Agent": "Mozilla/5.0"}
        
        try:
            res = requests.get(url, headers=headers)
            soup = BeautifulSoup(res.text, "html.parser")
            rows = soup.select("table.tbl_exchange tbody tr")
            
            currency_data = []
            for row in rows[:30]:  # 최근 30일 데이터
                cols = row.select("td")
                if len(cols) < 2:
                    continue
                date = cols[0].text.strip()
                rate = float(cols[1].text.strip().replace(",", ""))
                currency_data.append({"날짜": pd.to_datetime(date), "환율": rate})
            
            df = pd.DataFrame(currency_data)
            df = df.sort_values("날짜").reset_index(drop=True)
            data[currency] = df
            
            time.sleep(0.3)  # 서버 과부하 방지
            
        except Exception as e:
            st.error(f"{currency} 환율 데이터를 가져오는 중 오류가 발생했습니다: {str(e)}")
            data[currency] = pd.DataFrame(columns=["날짜", "환율"])
    
    return data

# 현재 시간을 KST로 변환하는 함수
def get_kst_time():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    return now.strftime('%y%m%d %H:%M')

# 환율 계산 함수
def calculate_exchange(amount, from_currency, to_currency, rates_data):
    if from_currency == to_currency:
        return amount
    
    # KRW로 변환 후 목표 통화로 변환
    if from_currency == 'KRW':
        return amount / rates_data[to_currency]['환율'].iloc[-1]
    elif to_currency == 'KRW':
        return amount * rates_data[from_currency]['환율'].iloc[-1]
    else:
        krw_amount = amount * rates_data[from_currency]['환율'].iloc[-1]
        return krw_amount / rates_data[to_currency]['환율'].iloc[-1]

# 환율 예측 함수
def predict_exchange_rate(df, days=7):
    # 날짜를 숫자로 변환 (시계열 특성)
    df = df.copy()
    df['날짜_num'] = (df['날짜'] - df['날짜'].min()).dt.days
    
    # 학습 데이터 준비
    X = df['날짜_num'].values.reshape(-1, 1)
    y = df['환율'].values
    
    # 선형 회귀 모델 학습
    model = LinearRegression()
    model.fit(X, y)
    
    # 예측 기간 생성
    last_date = df['날짜'].max()
    future_dates = pd.date_range(start=last_date + timedelta(days=1), periods=days, freq='D')
    future_dates_num = np.array([(date - df['날짜'].min()).days for date in future_dates]).reshape(-1, 1)
    
    # 예측 수행
    predicted_rates = model.predict(future_dates_num)
    
    # 예측 결과 데이터프레임 생성
    prediction_df = pd.DataFrame({
        '날짜': future_dates,
        '환율': predicted_rates,
        '구분': '예측'
    })
    
    # 기존 데이터에 '구분' 열 추가
    df['구분'] = '실제'
    
    # 실제 데이터와 예측 데이터 결합
    result_df = pd.concat([
        df[['날짜', '환율', '구분']],
        prediction_df
    ]).reset_index(drop=True)
    
    return result_df

# 차트 생성 함수
def create_currency_chart(df, currency):
    # 예측 데이터 생성
    df_with_prediction = predict_exchange_rate(df)
    
    # 동적 y축 범위 설정
    y_min = min(df_with_prediction['환율'].min() - 100, df['환율'].min() - 100)
    y_max = max(df_with_prediction['환율'].max() + 100, df['환율'].max() + 100)
    
    # 실제 데이터 라인
    base = alt.Chart(df_with_prediction).encode(
        x=alt.X('날짜:T', 
                title='날짜',
                axis=alt.Axis(
                    format='%m/%d',
                    labelAngle=-45,
                    labelFontSize=12
                )),
        y=alt.Y('환율:Q', 
                title='환율 (KRW)',
                scale=alt.Scale(
                    domain=[y_min, y_max]
                ),
                axis=alt.Axis(
                    labelFontSize=12
                )),
        color=alt.Color('구분:N', 
                       scale=alt.Scale(
                           domain=['실제', '예측'],
                           range=['#1f77b4', '#ff7f0e']
                       ),
                       legend=alt.Legend(title="데이터 구분")),
        tooltip=['날짜', '환율', '구분']
    )
    
    # 실제 데이터 라인
    actual_line = base.mark_line(size=2).transform_filter(
        alt.datum.구분 == '실제'
    )
    
    # 예측 데이터 라인 (점선)
    prediction_line = base.mark_line(
        size=2,
        strokeDash=[6, 4]
    ).transform_filter(
        alt.datum.구분 == '예측'
    )
    
    # 차트 결합
    chart = (actual_line + prediction_line).properties(
        title=alt.TitleParams(
            text=f'{currency}/KRW 환율 추이 및 예측 ({y_min:,.0f}원 ~ {y_max:,.0f}원)',
            fontSize=14
        ),
        height=400  # 차트 높이 증가
    ).configure_axis(
        labelFontSize=12,
        titleFontSize=14
    ).configure_title(
        fontSize=16,
        anchor='middle'
    )
    
    return chart

# 🖥️ Streamlit UI 시작
st.set_page_config(page_title="실시간 환율 대시보드", layout="wide")
st.title("💱 실시간 환율 대시보드")

# 자동 새로고침 설정
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()

# 10분마다 자동 새로고침
if time.time() - st.session_state.last_refresh > 600:
    st.session_state.last_refresh = time.time()
    st.experimental_rerun()

# 새로고침 버튼
col_time, col_refresh = st.columns([0.85, 0.15])
with col_time:
    st.caption(f"마지막 업데이트: {get_kst_time()} KST")
with col_refresh:
    refresh = st.button("🔄 새로고침")

# 환율 데이터 불러오기
with st.spinner("환율 데이터를 불러오는 중..."):
    rates_data = get_exchange_rates(refresh=refresh)

# 상단 섹션: 주요 환율 현황
st.subheader("📊 주요 환율 현황")
cols = st.columns(len(CURRENCIES))
for idx, (currency, info) in enumerate(CURRENCIES.items()):
    with cols[idx]:
        current_rate = rates_data[currency]['환율'].iloc[-1]
        prev_rate = rates_data[currency]['환율'].iloc[-2]
        change_pct = ((current_rate - prev_rate) / prev_rate) * 100
        
        st.metric(
            label=f"{currency}/KRW ({info['name']})",
            value=f"{current_rate:,.2f}",
            delta=f"{change_pct:+.2f}%"
        )

# 중간 섹션: 환율 추이 그래프
st.subheader("📈 30일 환율 추이")

# 모바일 화면 대응을 위한 동적 컬럼 설정
screen_width = st.session_state.get('screen_width', 1200)
if screen_width < 768:  # 모바일 화면
    chart_columns = 1
else:  # 데스크톱 화면
    chart_columns = 2

# 차트 그리기
for i in range(0, len(CURRENCIES), chart_columns):
    cols = st.columns(chart_columns)
    for j in range(chart_columns):
        if i + j < len(CURRENCIES):
            currency = list(CURRENCIES.keys())[i + j]
            with cols[j]:
                chart = create_currency_chart(
                    rates_data[currency],
                    currency
                )
                st.altair_chart(chart, use_container_width=True)

# 하단 섹션: 환율 계산기
st.subheader("🧮 환율 계산기")
col1, col2, col3 = st.columns([2, 0.5, 2])

with col1:
    amount = st.number_input("금액", min_value=0.0, value=1000.0, step=100.0)
    from_currency = st.selectbox(
        "변환할 통화",
        ['KRW'] + list(CURRENCIES.keys()),
        key='from_currency'
    )

with col2:
    st.write("")
    st.write("")
    st.write("")
    st.button("⇄", key="swap", help="통화 교환")

with col3:
    converted_amount = 0.0
    to_currency = st.selectbox(
        "변환된 통화",
        ['KRW'] + list(CURRENCIES.keys()),
        key='to_currency'
    )
    
    if st.session_state.get('swap', False):
        # 통화 교환
        st.session_state.from_currency, st.session_state.to_currency = st.session_state.to_currency, st.session_state.from_currency
        st.experimental_rerun()

# 환율 계산 및 결과 표시
converted_amount = calculate_exchange(amount, from_currency, to_currency, rates_data)
st.success(f"변환 결과: **{amount:,.2f} {from_currency}** = **{converted_amount:,.2f} {to_currency}**")

# 적용된 환율 정보 표시
if from_currency != to_currency:
    if from_currency == 'KRW':
        rate = 1 / rates_data[to_currency]['환율'].iloc[-1]
        st.caption(f"적용 환율: 1 {to_currency} = {1/rate:,.2f} {from_currency}")
    elif to_currency == 'KRW':
        rate = rates_data[from_currency]['환율'].iloc[-1]
        st.caption(f"적용 환율: 1 {from_currency} = {rate:,.2f} {to_currency}")
    else:
        from_rate = rates_data[from_currency]['환율'].iloc[-1]
        to_rate = rates_data[to_currency]['환율'].iloc[-1]
        cross_rate = from_rate / to_rate
        st.caption(f"적용 환율: 1 {from_currency} = {cross_rate:,.4f} {to_currency}")

# JavaScript를 사용하여 화면 너비 감지
st.markdown("""
<script>
    // 화면 너비를 감지하여 세션 상태에 저장
    function updateScreenWidth() {
        window.parent.postMessage({
            type: 'streamlit:setSessionState',
            data: { screen_width: window.innerWidth }
        }, '*');
    }
    
    // 초기 로드 및 화면 크기 변경 시 실행
    updateScreenWidth();
    window.addEventListener('resize', updateScreenWidth);
</script>
""", unsafe_allow_html=True) 
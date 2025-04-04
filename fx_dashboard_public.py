import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import datetime, timedelta
import time
import altair as alt
import pytz

# 페이지 설정
st.set_page_config(
    page_title="실시간 환율 대시보드",
    page_icon="💱",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS 스타일 적용
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #4CAF50;
        color: white;
    }
    .stMetric {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    div[data-testid="stVerticalBlock"] > div {
        padding: 5px;
    }
    .reportview-container {
        background: #fafafa;
    }
    .main {
        background: #fafafa;
    }
    /* 환율 표시 스타일 개선 */
    div[data-testid="stMetricValue"] {
        color: #1E88E5 !important;
        font-size: 1.5rem !important;
        font-weight: bold !important;
    }
    div[data-testid="stMetricDelta"] {
        font-size: 1rem !important;
    }
    div[data-testid="stMetricLabel"] {
        color: #424242 !important;
        font-size: 1rem !important;
    }
    /* 환율 계산기 결과 스타일 개선 */
    .exchange-result {
        background-color: #E3F2FD;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .exchange-result h3 {
        color: #1976D2;
        margin: 0;
        font-size: 1.2rem;
    }
    .exchange-result p {
        color: #1565C0;
        font-size: 1.5rem;
        margin: 10px 0;
        font-weight: bold;
    }
    /* 차트 컨테이너 스타일 */
    .chart-container {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 10px 0;
    }
    /* 섹션 제목 스타일 */
    h2 {
        color: #1976D2;
        font-size: 1.5rem;
        margin: 1.5rem 0 1rem 0;
    }
    /* 캡션 스타일 */
    .stCaption {
        color: #666666;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# 상수 정의
CURRENCIES = {
    'USD': {'name': '미국 달러', 'code': 'FX_USDKRW', 'color': '#1f77b4'},
    'EUR': {'name': '유럽 유로', 'code': 'FX_EURKRW', 'color': '#2ca02c'},
    'CAD': {'name': '캐나다 달러', 'code': 'FX_CADKRW', 'color': '#ff7f0e'},
    'AUD': {'name': '호주 달러', 'code': 'FX_AUDKRW', 'color': '#d62728'}
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

# 환율 예측 함수
def predict_exchange_rate(df, days=7):
    df = df.copy()
    df['날짜_num'] = (df['날짜'] - df['날짜'].min()).dt.days
    
    X = df['날짜_num'].values.reshape(-1, 1)
    y = df['환율'].values
    
    model = LinearRegression()
    model.fit(X, y)
    
    last_date = df['날짜'].max()
    future_dates = pd.date_range(start=last_date + timedelta(days=1), periods=days, freq='D')
    future_dates_num = np.array([(date - df['날짜'].min()).days for date in future_dates]).reshape(-1, 1)
    
    predicted_rates = model.predict(future_dates_num)
    
    prediction_df = pd.DataFrame({
        '날짜': future_dates,
        '환율': predicted_rates,
        '구분': '예측'
    })
    
    df['구분'] = '실제'
    
    result_df = pd.concat([
        df[['날짜', '환율', '구분']],
        prediction_df
    ]).reset_index(drop=True)
    
    return result_df

# 현재 시간을 KST로 변환하는 함수
def get_kst_time():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    return now.strftime('%y%m%d %H:%M')

# 환율 계산 함수
def calculate_exchange(amount, from_currency, to_currency, rates_data):
    if from_currency == to_currency:
        return amount
    
    if from_currency == 'KRW':
        return amount / rates_data[to_currency]['환율'].iloc[-1]
    elif to_currency == 'KRW':
        return amount * rates_data[from_currency]['환율'].iloc[-1]
    else:
        krw_amount = amount * rates_data[from_currency]['환율'].iloc[-1]
        return krw_amount / rates_data[to_currency]['환율'].iloc[-1]

# 차트 생성 함수
def create_currency_chart(df, currency, currency_info):
    # 예측 데이터 생성
    df_with_prediction = predict_exchange_rate(df)
    
    # 동적 y축 범위 설정
    y_min = min(df_with_prediction['환율'].min() - 50, df['환율'].min() - 50)
    y_max = max(df_with_prediction['환율'].max() + 50, df['환율'].max() + 50)
    
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
                           range=[currency_info['color'], '#ff9999']
                       ),
                       legend=alt.Legend(
                           title="데이터 구분",
                           orient="top-right"
                       )),
        tooltip=['날짜', '환율', '구분']
    ).properties(
        title=alt.TitleParams(
            text=f'{currency}/KRW ({currency_info["name"]}) 환율 추이 및 예측',
            fontSize=14,
            subtitle=f'범위: {y_min:,.0f}원 ~ {y_max:,.0f}원'
        )
    )
    
    # 실제 데이터 라인
    actual_line = base.mark_line(
        size=3
    ).transform_filter(
        alt.datum.구분 == '실제'
    )
    
    # 예측 데이터 라인
    prediction_line = base.mark_line(
        size=3,
        strokeDash=[6, 4]
    ).transform_filter(
        alt.datum.구분 == '예측'
    )
    
    # 차트 결합
    chart = (actual_line + prediction_line).properties(
        height=350  # 차트 높이 조정
    ).configure_axis(
        labelFontSize=12,
        titleFontSize=14
    ).configure_title(
        fontSize=16,
        anchor='start'
    ).configure_legend(
        labelFontSize=12,
        titleFontSize=14
    )
    
    return chart

# 🖥️ Streamlit UI 시작
st.title("💱 실시간 환율 대시보드")

# 자동 새로고침 설정
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()

# 10분마다 자동 새로고침
if time.time() - st.session_state.last_refresh > 600:
    st.session_state.last_refresh = time.time()
    st.experimental_rerun()

# 새로고침 버튼과 시간 표시
col_time, col_refresh = st.columns([0.85, 0.15])
with col_time:
    st.caption(f"마지막 업데이트: {get_kst_time()} KST")
with col_refresh:
    refresh = st.button("🔄 새로고침", use_container_width=True)

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
            delta=f"{change_pct:+.2f}%",
            help=f"전일 대비 변화율: {change_pct:+.2f}%"
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
                st.markdown('<div class="chart-container">', unsafe_allow_html=True)
                chart = create_currency_chart(
                    rates_data[currency],
                    currency,
                    CURRENCIES[currency]
                )
                st.altair_chart(chart, use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

# 하단 섹션: 환율 계산기
st.markdown("---")
st.subheader("🧮 환율 계산기")

# 계산기 컨테이너 스타일링
with st.container():
    col1, col2, col3 = st.columns([2, 0.5, 2])
    
    with col1:
        amount = st.number_input(
            "금액",
            min_value=0.0,
            value=1000.0,
            step=100.0,
            format="%.2f"
        )
        from_currency = st.selectbox(
            "변환할 통화",
            ['KRW'] + list(CURRENCIES.keys()),
            key='from_currency'
        )

    with col2:
        st.write("")
        st.write("")
        st.write("")
        if st.button("⇄", help="통화 교환", key="swap"):
            st.session_state.from_currency, st.session_state.to_currency = st.session_state.to_currency, st.session_state.from_currency
            st.experimental_rerun()

    with col3:
        to_currency = st.selectbox(
            "변환된 통화",
            ['KRW'] + list(CURRENCIES.keys()),
            key='to_currency'
        )

# 환율 계산 및 결과 표시
converted_amount = calculate_exchange(amount, from_currency, to_currency, rates_data)

# 결과 표시 컨테이너
with st.container():
    st.markdown(
        f"""
        <div class="exchange-result">
            <h3>변환 결과</h3>
            <p>
                {amount:,.2f} {from_currency} = {converted_amount:,.2f} {to_currency}
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

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
    function updateScreenWidth() {
        window.parent.postMessage({
            type: 'streamlit:setSessionState',
            data: { screen_width: window.innerWidth }
        }, '*');
    }
    
    updateScreenWidth();
    window.addEventListener('resize', updateScreenWidth);
</script>
""", unsafe_allow_html=True) 
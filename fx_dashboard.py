import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import altair as alt
from datetime import datetime, timedelta
import pytz
import numpy as np
from sklearn.linear_model import LinearRegression

# 환율 데이터 크롤링 함수
@st.cache_data(ttl=600, show_spinner=False)  # 10분(600초) 캐시 설정
def get_exchange_history(days=30, refresh=False):
    # refresh 파라미터가 True이면 캐시를 무시하고 새로운 데이터를 가져옴
    if refresh:
        st.cache_data.clear()
    
    # 네이버 환율 페이지에서 송금 기준 환율 크롤링
    url = "https://finance.naver.com/marketindex/exchangeDailyQuote.nhn?marketindexCd=FX_USDKRW"
    headers = {"User-Agent": "Mozilla/5.0"}
    data = []

    page = 1
    while len(data) < days:
        res = requests.get(f"{url}&page={page}", headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.select("table.tbl_exchange tbody tr")

        for row in rows:
            cols = row.select("td")
            if len(cols) < 2:
                continue
            date = cols[0].text.strip()
            rate = float(cols[1].text.strip().replace(",", ""))
            data.append({"날짜": pd.to_datetime(date), "환율": rate})
            if len(data) >= days:
                break
        page += 1
        time.sleep(0.3)  # 서버 과부하 방지

    df = pd.DataFrame(data)
    df = df.sort_values("날짜").reset_index(drop=True)
    return df

# 단가 및 마진 계산 함수
def simulate_margin(usd_unit_cost, exchange_rate, selling_price):
    # 환율에 1.3을 곱하여 마진 확보
    krw_cost = usd_unit_cost * exchange_rate * 1.3
    margin = ((selling_price - krw_cost) / selling_price) * 100
    return round(krw_cost, 2), round(margin, 2)

# 현재 시간을 KST로 변환하는 함수
def get_kst_time():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    return now.strftime('%y%m%d %H:%M')

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

# 🖥️ Streamlit UI 시작
st.set_page_config(page_title="외환 리스크 대시보드", layout="wide")
st.title("💱 외환 리스크 대시보드 (USD/KRW)")

# 자동 새로고침 설정
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()

# 10분마다 자동 새로고침
if time.time() - st.session_state.last_refresh > 600:
    st.session_state.last_refresh = time.time()
    st.experimental_rerun()

# 새로고침 버튼 추가
col_title, col_refresh = st.columns([0.9, 0.1])
with col_title:
    st.subheader("📈 최근 30일 환율 추이")
with col_refresh:
    refresh = st.button("🔄 새로고침")

# 환율 데이터 불러오기
with st.spinner("환율 데이터를 불러오는 중..."):
    df = get_exchange_history(30, refresh=refresh)

# 차트 생성 함수
def create_currency_chart(df, currency):
    # 예측 데이터 생성
    df_with_prediction = predict_exchange_rate(df)
    
    # 동적 y축 범위 설정
    y_min = min(df_with_prediction['환율'].min() - 50, df['환율'].min() - 50)
    y_max = max(df_with_prediction['환율'].max() + 50, df['환율'].max() + 50)
    
    # 툴팁 설정
    tooltip = [
        alt.Tooltip('날짜:T', title='날짜', format='%Y-%m-%d'),
        alt.Tooltip('환율:Q', title='환율', format=',.2f'),
        alt.Tooltip('구분:N', title='구분')
    ]
    
    # 실제 데이터 라인
    base = alt.Chart(df_with_prediction).encode(
        x=alt.X('날짜:T', 
                title='날짜',
                axis=alt.Axis(
                    format='%m/%d',
                    labelAngle=-45,
                    labelFontSize=14,
                    titleFontSize=16,
                    grid=True
                )),
        y=alt.Y('환율:Q', 
                title='환율 (KRW)',
                scale=alt.Scale(
                    domain=[y_min, y_max]
                ),
                axis=alt.Axis(
                    labelFontSize=14,
                    titleFontSize=16,
                    grid=True
                )),
        color=alt.Color('구분:N', 
                       scale=alt.Scale(
                           domain=['실제', '예측'],
                           range=['#1f77b4', '#ff7f0e']
                       ),
                       legend=alt.Legend(
                           title="데이터 구분",
                           orient="top-right",
                           labelFontSize=12,
                           titleFontSize=14
                       )),
        tooltip=tooltip
    ).properties(
        title=alt.TitleParams(
            text=f'{currency}/KRW 환율 추이 및 예측',
            fontSize=16,
            subtitle=f'범위: {y_min:,.0f}원 ~ {y_max:,.0f}원'
        )
    )
    
    # 실제 데이터 라인과 포인트
    actual_line = base.mark_line(
        size=3
    ).transform_filter(
        alt.datum.구분 == '실제'
    )
    
    actual_points = base.mark_circle(
        size=60,
        opacity=0.7
    ).transform_filter(
        alt.datum.구분 == '실제'
    )
    
    # 예측 데이터 라인과 포인트
    prediction_line = base.mark_line(
        size=3,
        strokeDash=[8, 6]
    ).transform_filter(
        alt.datum.구분 == '예측'
    )
    
    prediction_points = base.mark_circle(
        size=60,
        opacity=0.7
    ).transform_filter(
        alt.datum.구분 == '예측'
    )
    
    # 차트 결합
    chart = (actual_line + actual_points + prediction_line + prediction_points).properties(
        height=400  # 차트 높이 증가
    ).configure_axis(
        labelFontSize=14,
        titleFontSize=16
    ).configure_title(
        fontSize=18,
        anchor='middle'
    ).configure_legend(
        labelFontSize=12,
        titleFontSize=14
    )
    
    return chart

# 예측 데이터 생성 및 차트 표시
st.subheader("📈 USD/KRW 환율 추이")
chart = create_currency_chart(df, 'USD')
st.altair_chart(chart, use_container_width=True)

# 사용자 입력
st.subheader("📦 수입 원가 & 마진 시뮬레이터")
col1, col2, col3 = st.columns(3)
with col1:
    usd_cost = st.number_input("USD 단가", value=25.00)
with col2:
    selling_price = st.number_input("판매가 (KRW)", value=42000)
with col3:
    current_rate = df['환율'].iloc[-1]
    update_time = get_kst_time()
    st.metric("📌 현재 환율", f"{current_rate:,.2f} KRW/USD")
    st.caption(f"마지막 업데이트: {update_time} KST")

# 결과 출력
krw_cost, margin = simulate_margin(usd_cost, current_rate, selling_price)
st.success(f"🔹 환율 적용 수입단가 (마진 30% 포함): **{krw_cost:,.0f} 원**")
st.success(f"🔹 예상 마진율: **{margin:.2f}%**") 
import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import ta
from pykrx import stock
from datetime import datetime, timedelta
import time
import requests
from bs4 import BeautifulSoup
import urllib.parse
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

# --- 페이지 설정 ---
st.set_page_config(page_title="주식 포착기 Ultimate", page_icon="📈", layout="wide")

# --- 스타일 설정 ---
st.markdown("""
    <style>
        .news-box { padding: 8px; background-color: #f8f9fa; border-left: 4px solid #007bff; margin-bottom: 8px; border-radius: 4px; }
        .news-title a { text-decoration: none; color: #333; font-weight: bold; font-size: 13px; }
        .metric-value { font-size: 16px; font-weight: bold; color: #000; }
        .chart-box { border: 1px solid #ddd; border-radius: 5px; padding: 5px; }
    </style>
""", unsafe_allow_html=True)

st.title("📈 주식 포착기 Ultimate (다중 팩터 전략 적용)")

# --- 사이드바 ---
with st.sidebar:
    st.header("🔍 기본 검색 옵션")
    market_type = st.selectbox("시장 선택", ["KOSPI", "KOSDAQ"])
    search_limit = st.slider("검색 범위 (시총 상위)", 20, 1000, 500)
    rsi_threshold = st.slider("RSI 기준 (이하)", 50, 90, 63)
    
    st.divider()
    st.header("⚙️ 얼티밋 전략 필터")
    use_bb = st.checkbox("🔥 볼린저 밴드 상단 돌파 (변동성 폭발)", value=False)
    use_ichimoku = st.checkbox("☁️ 일목균형표 구름대 돌파 (상승 추세 확인)", value=True)
    use_inst = st.checkbox("🏢 기관 수급 유입 (최근 5일 순매수)", value=False)
    
    run_btn = st.button("🚀 통합 분석 시작", type="primary")

# --- 1. 기술적 분석 함수 (다중 팩터 전략) ---
@st.cache_data(ttl=3600)
def get_stock_data(market, limit):
    stocks = fdr.StockListing(market)
    stocks = stocks.sort_values(by='Marcap', ascending=False).head(limit)
    return stocks

def check_technical_conditions(df, rsi_limit, use_bb, use_ichimoku):
    if len(df) < 60: return False, {}
    try:
        close = df['Close']
        high = df['High']
        low = df['Low']
        volume = df['Volume']
        
        # 기본 지표
        ma5 = ta.trend.sma_indicator(close, window=5)
        ma20 = ta.trend.sma_indicator(close, window=20)
        rsi = ta.momentum.rsi(close, window=14)
        macd_obj = ta.trend.MACD(close)
        vol_ma20 = ta.trend.sma_indicator(volume, window=20)

        # 볼린저 밴드 (20, 2)
        bb = ta.volatility.BollingerBands(close=close, window=20, window_dev=2)
        bb_high = bb.bollinger_hband()

        # 일목균형표 (9, 26, 52)
        ichimoku = ta.trend.IchimokuIndicator(high=high, low=low)
        senkou_a = ichimoku.ichimoku_a()
        senkou_b = ichimoku.ichimoku_b()

        curr_close = close.iloc[-1]
        curr_ma5, curr_ma20 = ma5.iloc[-1], ma20.iloc[-1]
        curr_rsi = rsi.iloc[-1]
        curr_macd = macd_obj.macd().iloc[-1]
        curr_signal = macd_obj.macd_signal().iloc[-1]
        
        curr_vol = volume.iloc[-1]
        curr_vol_ma = vol_ma20.iloc[-1]
        prev_close = close.iloc[-2]
        change_rate = (curr_close - prev_close) / prev_close * 100

        # 선행스팬 A, B 중 큰 값이 구름대 상단(저항선)
        cloud_top = max(senkou_a.iloc[-1], senkou_b.iloc[-1])

        # [기본 조건]
        cond_trend = curr_ma5 > curr_ma20
        cond_rsi = 30 <= curr_rsi <= rsi_limit
        cond_macd = curr_macd > curr_signal
        cond_vol = curr_vol >= (curr_vol_ma * 1.2) # 거래량 평소대비 120% 이상
        cond_power = change_rate >= 2.0 # 2% 이상 상승
        
        # [얼티밋 전략 조건]
        cond_bb_pass = (curr_close >= bb_high.iloc[-1] * 0.98) if use_bb else True
        cond_ichimoku_pass = (curr_close > cloud_top) if use_ichimoku else True
        
        if (cond_trend and cond_rsi and cond_macd and cond_vol and cond_power 
            and cond_bb_pass and cond_ichimoku_pass):
            return True, {
                '현재가': int(curr_close),
                'RSI': round(curr_rsi, 2),
                '등락률': round(change_rate, 2),
                'df': df.tail(60) # 차트 그리기 위해 최근 60일 데이터 저장
            }
    except: return False, {}
    return False, {}

# --- 2. 미니 차트 그리기 함수 ---
def plot_mini_chart(df, title):
    fig, ax = plt.subplots(figsize=(5, 3))
    
    ax.plot(df.index, df['Close'], label='Close', color='#2962FF', linewidth=2)
    ax.plot(df.index, df['Close'].rolling(window=20).mean(), label='MA20', color='#FF6D00', linestyle='--', linewidth=1)
    
    ax.set_title(title, fontsize=10)
    ax.grid(True, which='both', linestyle='--', alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    ax.tick_params(axis='x', rotation=45, labelsize=8)
    ax.tick_params(axis='y', labelsize=8)
    
    plt.tight_layout()
    return fig

# --- 3. 기타 정보 수집 함수 ---
@st.cache_data(ttl=3600)
def get_company_info(code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        per = soup.select_one('#_per')
        pbr = soup.select_one('#_pbr')
        summary = soup.select_one('.summary_info > p')
        
        return {
            'summary': summary.text if summary else "정보 없음",
            'PER': per.text if per else "-",
            'PBR': pbr.text if pbr else "-"
        }
    except: return {'summary': "-", 'PER': "-", 'PBR': "-"}

@st.cache_data(ttl=1800)
def get_related_news(keyword):
    try:
        enc = urllib.parse.quote(keyword)
        url = f"https://search.naver.com/search.naver?where=news&query={enc}&sm=tab_opt&sort=1"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.select('.news_wrap')[:2]
        news = []
        for item in items:
            title = item.select_one('.news_tit').text
            link = item.select_one('.news_tit')['href']
            news.append({'title': title, 'link': link})
        return news
    except: return []

# --- 메인 실행 ---
if run_btn:
    st.divider()
    
    # 1차 분석
    st.subheader(f"1️⃣ {market_type} 유망주 발굴 중...")
    status = st.empty()
    bar = st.progress(0)
    
    stocks = get_stock_data(market_type, search_limit)
    first_pass = []
    
    total = len(stocks)
    for i, (idx, row) in enumerate(stocks.iterrows()):
        status.text(f"스캔 중.. {row['Name']}")
        bar.progress((i + 1) / total)
        try:
            df = fdr.DataReader(row['Code'], '2023-01-01')
            match, info = check_technical_conditions(df, rsi_threshold, use_bb, use_ichimoku)
            if match:
                info.update({'종목코드': row['Code'], '종목명': row['Name']})
                first_pass.append(info)
        except: continue
        
    status.empty()
    bar.empty()
    
    if not first_pass:
        st.error("조건을 만족하는 종목이 없습니다. 검색 범위를 넓히거나 필터 옵션을 완화해 보세요.")
    else:
        st.success(f"✅ {len(first_pass)}개 종목 발견! 상세 분석 시작 (수급 필터 적용 중...)")
        
        # 2차 분석 & 디스플레이
        st.divider()
        
        today = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=5)).strftime("%Y%m%d")
        
        displayed_count = 0
        
        for item in first_pass:
            # 수급 데이터 수집 및 필터링
            try:
                inv = stock.get_market_trading_value_by_date(start, today, item['종목코드'])
                inst_net = inv['기관합계'].sum() if not inv.empty else 0
            except: inst_net = 0
            
            # 기관 수급 필터가 켜져 있는데 순매수가 0 이하면 스킵
            if use_inst and inst_net <= 0:
                continue
                
            displayed_count += 1
            comp = get_company_info(item['종목코드'])
            news = get_related_news(item['종목명'])
            
            # --- 화면 구성 (4단 레이아웃) ---
            with st.expander(f"📌 {item['종목명']} (+{item['등락률']}%)", expanded=True):
                c1, c2, c3 = st.columns([1.5, 1, 1.2])
                
                # [왼쪽] 미니 차트
                with c1:
                    st.markdown("#### 📉 60일 흐름")
                    fig = plot_mini_chart(item['df'], f"{item['종목명']} (Close)")
                    st.pyplot(fig)
                
                # [중간] 수급 & 재무
                with c2:
                    st.markdown("#### 📊 핵심 지표")
                    st.write(f"현재가: **{item['현재가']:,}원**")
                    st.write(f"RSI: **{item['RSI']}**")
                    
                    if inst_net > 0:
                        st.success(f"기관 5일: +{inst_net:,}")
                    else:
                        st.error(f"기관 5일: {inst_net:,}")
                        
                    st.markdown("---")
                    st.caption("기업 정보")
                    c2_1, c2_2 = st.columns(2)
                    c2_1.metric("PER", comp['PER'])
                    c2_2.metric("PBR", comp['PBR'])

                # [오른쪽] 뉴스 & 개요
                with c3:
                    st.markdown("#### 📰 뉴스 & 개요")
                    st.caption(f"{comp['summary'][:80]}...")
                    st.markdown("---")
                    if news:
                        for n in news:
                            st.markdown(f"<div class='news-box'><a href='{n['link']}' target='_blank'>{n['title']}</a></div>", unsafe_allow_html=True)
                    else:
                        st.text("관련 뉴스 없음")
            
            time.sleep(0.1) # 렌더링 안정성
            
        if displayed_count == 0:
            st.warning("기술적 분석은 통과했으나, 기관 수급 조건을 만족하는 종목이 없습니다.")
        else:
            st.balloons()

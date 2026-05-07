import FinanceDataReader as fdr
import pandas as pd
import ta
from datetime import datetime, timedelta
import os
import smtplib
from email.mime.text import MIMEText

# --- 설정 및 환경 변수 ---
EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
RECEIVER_EMAIL = os.environ.get('RECEIVER_EMAIL')

def check_technical_conditions(df, rsi_limit=63):
    if len(df) < 60: return False, {}
    try:
        close = df['Close']
        high = df['High']
        low = df['Low']
        
        # [기존 조건 유지] 지표 계산
        ma5 = ta.trend.sma_indicator(close, window=5)
        ma20 = ta.trend.sma_indicator(close, window=20)
        rsi = ta.momentum.rsi(close, window=14)
        macd_obj = ta.trend.MACD(close)
        
        ichimoku = ta.trend.IchimokuIndicator(high=high, low=low)
        cloud_top = max(ichimoku.ichimoku_a().iloc[-1], ichimoku.ichimoku_b().iloc[-1])

        curr_close = close.iloc[-1]
        curr_rsi = rsi.iloc[-1]
        
        # [기존 조건 유지] 추세, RSI, MACD, 일목균형표 검사
        cond_trend = ma5.iloc[-1] > ma20.iloc[-1]
        cond_rsi = 30 <= curr_rsi <= rsi_limit
        cond_macd = macd_obj.macd().iloc[-1] > macd_obj.macd_signal().iloc[-1]
        cond_ichimoku = curr_close > cloud_top
        
        if cond_trend and cond_rsi and cond_macd and cond_ichimoku:
            return True, {'price': int(curr_close), 'rsi': round(curr_rsi, 2)}
    except: return False, {}
    return False, {}

def main():
    print("분석 시작...")
    # 코스피 상위 200개 종목 분석 (기존 로직 유지)
    stocks = fdr.StockListing('KOSPI').head(200)
    
    found_stocks = []
    
    for _, row in stocks.iterrows():
        try:
            df = fdr.DataReader(row['Code'], (datetime.now() - timedelta(days=100)).strftime('%Y-%m-%d'))
            match, info = check_technical_conditions(df)
            if match:
                # 메일 표에 들어갈 데이터 정리
                found_stocks.append({
                    '종목명': row['Name'], 
                    '코드': row['Code'], 
                    '현재가': f"{info['price']:,}원", 
                    'RSI': info['rsi']
                })
                print(f"포착: {row['Name']}")
        except: continue

    # [핵심 수정] 검색 결과를 데이터프레임으로 변환
    filtered_df = pd.DataFrame(found_stocks)

    # --- 메일 내용 구성 (들여쓰기 및 변수명 일치 완료) ---
    if not filtered_df.empty:
        subject = f"📈 [주식 분석] {len(filtered_df)}개 종목 발견"
        body = f"<h3>오늘의 검색 결과입니다.</h3>{filtered_df.to_html(index=False)}"
    else:
        subject = "🔍 [주식 분석] 오늘 조건에 맞는 종목이 없습니다."
        body = "<h3>분석 완료 보고</h3><p>설정하신 조건(RSI, MACD 등)을 만족하는 종목이 없습니다. 시스템은 정상 작동 중입니다.</p>"

    # --- 메일 발송 로직 ---
    msg = MIMEText(body, 'html')
    msg['Subject'] = subject
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER_EMAIL

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_USER, EMAIL_PASSWORD)
            smtp.send_message(msg)
        print("메일을 성공적으로 보냈습니다!")
    except Exception as e:
        print(f"메일 발송 실패: {e}")

if __name__ == "__main__":
    main()

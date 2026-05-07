import FinanceDataReader as fdr
import pandas as pd
import ta
from datetime import datetime, timedelta
from pykrx import stock
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
        
        ma5 = ta.trend.sma_indicator(close, window=5)
        ma20 = ta.trend.sma_indicator(close, window=20)
        rsi = ta.momentum.rsi(close, window=14)
        macd_obj = ta.trend.MACD(close)
        
        ichimoku = ta.trend.IchimokuIndicator(high=high, low=low)
        cloud_top = max(ichimoku.ichimoku_a().iloc[-1], ichimoku.ichimoku_b().iloc[-1])

        curr_close = close.iloc[-1]
        curr_rsi = rsi.iloc[-1]
        
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
    # [수정된 부분] 명령어 이름을 정확한 버전으로 변경했습니다.
    today_str = datetime.now().strftime('%Y%m%d')
    try:
        df_fundamental = stock.get_market_fundamental(today_str, market="KOSPI")
    except:
        yesterday_str = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        df_fundamental = stock.get_market_fundamental(yesterday_str, market="KOSPI")

    stocks_info = fdr.StockListing('KOSPI').head(200)
    
    found_stocks = []
    
    for _, row in stocks_info.iterrows():
        code = row['Code']
        try:
            df = fdr.DataReader(code, (datetime.now() - timedelta(days=100)).strftime('%Y-%m-%d'))
            match, info = check_technical_conditions(df)
            if match:
                try:
                    per_val = df_fundamental.loc[code, 'PER']
                    if pd.isna(per_val) or per_val == 0: per_val = "N/A"
                except:
                    per_val = "N/A"
                
                found_stocks.append({
                    '종목명': row['Name'], 
                    '코드': code, 
                    '현재가': f"{info['price']:,}원", 
                    'RSI': info['rsi'],
                    'PER': per_val
                })
                print(f"포착: {row['Name']} (PER: {per_val})")
        except: continue

    filtered_df = pd.DataFrame(found_stocks)

    # --- 메일 내용 구성 ---
    if not filtered_df.empty:
        filtered_df['PER_sort'] = pd.to_numeric(filtered_df['PER'], errors='coerce')
        filtered_df = filtered_df.sort_values(by='PER_sort', ascending=True).drop(columns=['PER_sort'])
        
        subject = f"📈 [주식 분석] {len(filtered_df)}개 종목 발견 (PER 적용)"
        body = f"<h3>오늘의 분석 결과입니다. (저PER 순 정렬)</h3>{filtered_df.to_html(index=False)}"
    else:
        subject = "🔍 [주식 분석] 오늘 조건에 맞는 종목이 없습니다."
        body = "<h3>분석 완료 보고</h3><p>기술적 지표를 만족하는 종목이 발견되지 않았습니다.</p>"

    # --- 메일 발송 ---
    msg = MIMEText(body, 'html')
    msg['Subject'] = subject
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER_EMAIL

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_USER, EMAIL_PASSWORD)
            smtp.send_message(msg)
        print("메일 발송 성공!")
    except Exception as e:
        print(f"메일 발송 실패: {e}")

if __name__ == "__main__":
    main()

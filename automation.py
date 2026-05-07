import FinanceDataReader as fdr
import pandas as pd
import ta
from datetime import datetime, timedelta
from pykrx import stock
import os
import smtplib
from email.mime.text import MIMEText

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
        
        # [수정] .iloc[-1] 대신 .dropna().iloc[-1]을 사용하여 NaN 에러 방지
        # 처음 코드의 조건(A, B 중 높은 값보다 주가가 위에 있을 것)은 그대로 유지합니다.
        span_a = ichimoku.ichimoku_a().dropna()
        span_b = ichimoku.ichimoku_b().dropna()
        cloud_top = max(span_a.iloc[-1], span_b.iloc[-1])

        curr_close = close.iloc[-1]
        curr_rsi = rsi.iloc[-1]
        
        # 처음 코드와 동일한 조건문
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
    today_str = datetime.now().strftime('%Y%m%d')
    
    # [수정] 정확한 함수명 사용 및 데이터 존재 여부 체크 루프
    df_fundamental = pd.DataFrame()
    for i in range(5):
        search_date = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
        # 시장 전체 데이터를 가져오기 위해 _by_ticker 사용
        df_fundamental = stock.get_market_fundamental_by_ticker(search_date, market="KOSPI")
        if not df_fundamental.empty: break

    # StockListing 결과의 컬럼명은 환경에 따라 'Code' 혹은 'Symbol'일 수 있음
    stocks_info = fdr.StockListing('KOSPI')
    code_col = 'Code' if 'Code' in stocks_info.columns else 'Symbol'
    
    found_stocks = []
    
    for _, row in stocks_info.head(200).iterrows():
        code = row[code_col]
        try:
            # 일목균형표 계산을 위해 데이터 기간을 150일로 늘림
            df = fdr.DataReader(code, (datetime.now() - timedelta(days=150)).strftime('%Y-%m-%d'))
            match, info = check_technical_conditions(df)
            if match:
                # [수정] KeyError 방지를 위해 index 체크 추가
                per_val = "N/A"
                if code in df_fundamental.index:
                    per_val = df_fundamental.loc[code, 'PER']
                    if pd.isna(per_val) or per_val == 0: per_val = "N/A"
                
                found_stocks.append({
                    '종목명': row['Name'], 
                    '코드': code, 
                    '현재가': f"{info['price']:,}원", 
                    'RSI': info['rsi'],
                    'PER': per_val
                })
                print(f"포착: {row['Name']} (PER: {per_val})")
        except: continue

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

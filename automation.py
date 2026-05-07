import FinanceDataReader as fdr
import pandas as pd
import ta
from pykrx import stock
from datetime import datetime, timedelta
import time
import requests
from bs4 import BeautifulSoup
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 설정 및 환경 변수 ---
# GitHub Secrets에 등록한 값을 불러옵니다.
EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
RECEIVER_EMAIL = os.environ.get('RECEIVER_EMAIL') # 받는 사람 이메일

def send_email(subject, body):
    if not EMAIL_USER or not EMAIL_PASSWORD:
        print("이메일 설정이 되어있지 않습니다.")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
        print("이메일 전송 성공!")
    except Exception as e:
        print(f"이메일 전송 실패: {e}")

# --- 분석 함수 ---
def check_technical_conditions(df, rsi_limit=63):
    if len(df) < 60: return False, {}
    try:
        close = df['Close']
        high = df['High']
        low = df['Low']
        
        # 지표 계산
        ma5 = ta.trend.sma_indicator(close, window=5)
        ma20 = ta.trend.sma_indicator(close, window=20)
        rsi = ta.momentum.rsi(close, window=14)
        macd_obj = ta.trend.MACD(close)
        
        ichimoku = ta.trend.IchimokuIndicator(high=high, low=low)
        cloud_top = max(ichimoku.ichimoku_a().iloc[-1], ichimoku.ichimoku_b().iloc[-1])

        curr_close = close.iloc[-1]
        curr_rsi = rsi.iloc[-1]
        
        # 조건 검사 (추세, RSI, 일목균형표 등)
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
    market = "KOSPI" # 또는 KOSDAQ
    stocks = fdr.StockListing(market).sort_values(by='Marcap', ascending=False).head(200) # 상위 200개
    
    found_stocks = []
    
    for _, row in stocks.iterrows():
        try:
            df = fdr.DataReader(row['Code'], (datetime.now() - timedelta(days=100)).strftime('%Y-%m-%d'))
            match, info = check_technical_conditions(df)
            if match:
                found_stocks.append(f" - {row['Name']}({row['Code']}): {info['price']:,}원 (RSI: {info['rsi']})")
                print(f"포착: {row['Name']}")
        except: continue

    # --- 메일 내용 구성 (들여쓰기 수정됨) ---
    if not filtered_df.empty:
        subject = f"📈 [주식 분석] {len(filtered_df)}개 종목 발견"
        body = f"<h3>오늘의 조건 검색 결과입니다.</h3>{filtered_df.to_html(index=False)}"
    else:
        subject = "🔍 [주식 분석] 오늘 조건에 맞는 종목이 없습니다."
        body = "<h3>분석 완료</h3><p>오늘 설정하신 조건(RSI, 일목균형표 등)에 일치하는 종목이 없습니다. 시스템은 정상 작동 중입니다.</p>"

    # --- 메일 발송 로직 ---
    msg = MIMEText(body, 'html')
    msg['Subject'] = subject
    msg['From'] = EMAIL_USER
    msg['To'] = RECEIVER_EMAIL

    try:
        # 보안을 위해 SSL(465) 방식을 사용합니다.
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_USER, EMAIL_PASSWORD)
            smtp.send_message(msg)
        print("메일을 성공적으로 보냈습니다!")
    except Exception as e:
        print(f"메일 발송 실패: {e}")

if __name__ == "__main__":
    main()

# =============================================================================
#              주식 포착기 Ultimate - 안정화 버전
# =============================================================================

import pandas as pd
import FinanceDataReader as fdr
import pandas_ta as ta
from pykrx import stock
from datetime import datetime, timedelta
import time
import sys
import requests
from bs4 import BeautifulSoup

# ========================== 설정 ==========================
MARKET = "KOSPI"          
LIMIT = 400
RSI_THRESHOLD = 68
USE_INST = False
USE_PER = True

# =========================================================

def get_per(code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        per = soup.select_one('#_per')
        return per.text.strip() if per else '-'
    except:
        return '-'


def check_technical_conditions(df):
    if len(df) < 60:
        return False, {}
    try:
        close = df['Close']
        ma5 = ta.sma(close, length=5)
        ma20 = ta.sma(close, length=20)
        rsi = ta.rsi(close, length=14)
        macd = ta.macd(close)

        curr_close = close.iloc[-1]
        curr_rsi = rsi.iloc[-1]
        curr_macd = macd['MACD_12_26_9'].iloc[-1]
        curr_signal = macd['MACDs_12_26_9'].iloc[-1]
        curr_vol = df['Volume'].iloc[-1]
        vol_ma20 = ta.sma(df['Volume'], length=20).iloc[-1]

        prev_close = close.iloc[-2]
        change_rate = (curr_close - prev_close) / prev_close * 100

        if (ma5.iloc[-1] > ma20.iloc[-1] and 
            30 <= curr_rsi <= RSI_THRESHOLD and
            curr_macd > curr_signal and
            curr_vol >= vol_ma20 * 1.2 and
            change_rate >= 1.5):
            
            return True, {
                '현재가': int(curr_close),
                'RSI': round(curr_rsi, 2),
                '등락률': round(change_rate, 2),
            }
    except:
        pass
    return False, {}


def generate_html(results, date_str):
    df = pd.DataFrame(results)
    if df.empty:
        return f"<h2>{date_str} - 조건을 만족하는 종목이 없습니다.</h2>"

    df = df.sort_values(by='등락률', ascending=False)

    html = f"""
    <html>
    <head><meta charset="utf-8">
    <style>
        body {{font-family: Malgun Gothic, sans-serif; background:#f8f9fa; padding:20px;}}
        .container {{max-width:1100px; margin:auto; background:white; border-radius:10px; box-shadow:0 4px 15px rgba(0,0,0,0.1);}}
        .header {{background: linear-gradient(135deg, #1e40af, #3b82f6); color:white; padding:25px; text-align:center; border-radius:10px 10px 0 0;}}
        table {{width:100%; border-collapse:collapse;}}
        th, td {{padding:12px; text-align:center; border-bottom:1px solid #eee;}}
        th {{background:#f1f5f9;}}
        .stock-name {{text-align:left; font-weight:600;}}
        .positive {{color:#dc2626; font-weight:bold;}}
    </style>
    </head>
    <body>
    <div class="container">
        <div class="header"><h1>📈 주식 포착기 Ultimate</h1><p>{date_str}</p></div>
        <div style="padding:20px 30px;">
            <h2>🎯 오늘의 유망주 ({len(df)}개)</h2>
            <table>
                <tr>
                    <th>종목명</th>
                    <th>현재가</th>
                    <th>등락률</th>
                    <th>RSI</th>
                    <th>PER</th>
                </tr>
    """
    for _, row in df.iterrows():
        color = "positive" if row['등락률'] > 0 else ""
        html += f"""
                <tr>
                    <td class="stock-name">{row['종목명']}<br><small>{row['종목코드']}</small></td>
                    <td>{row['현재가']:,}</td>
                    <td class="{color}">+{row['등락률']}%</td>
                    <td>{row['RSI']}</td>
                    <td>{row['PER']}</td>
                </tr>
        """
    html += """
            </table>
        </div>
    </div>
    </body></html>
    """
    return html


def main():
    print("📈 주식 포착기 시작...")
    stocks = fdr.StockListing(MARKET).sort_values(by='Marcap', ascending=False).head(LIMIT)
    results = []
    today = datetime.now().strftime("%Y%m%d")
    start_5d = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")

    for i, (_, row) in enumerate(stocks.iterrows(), 1):
        sys.stdout.write(f"\r[{i:3d}/{len(stocks)}] {row['Name']}")
        sys.stdout.flush()
        try:
            df = fdr.DataReader(row['Code'], '2024-01-01')
            match, info = check_technical_conditions(df)
            if match:
                per = get_per(row['Code']) if USE_PER else '-'
                info.update({
                    '종목코드': row['Code'],
                    '종목명': row['Name'],
                    'PER': per
                })
                results.append(info)
        except:
            continue
        time.sleep(0.1)

    date_str = datetime.now().strftime("%Y년 %m월 %d일")
    html_content = generate_html(results, date_str)

    with open('today_picks.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\n✅ 완료! 발견 종목: {len(results)}개")
    print("📄 today_picks.html 생성 완료")


if __name__ == "__main__":
    main()

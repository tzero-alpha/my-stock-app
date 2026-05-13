# =============================================================================
#              주식 포착기 Ultimate - 속도 개선 + PER 버전
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
LIMIT = 300
RSI_THRESHOLD = 63
USE_BB = False
USE_ICHIMOKU = True
USE_INST = True
USE_PER = True

# =========================================================

def get_per_pbr(code):
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        per = soup.select_one('#_per')
        return per.text.strip() if per and per.text.strip() else '-'
    except:
        return '-'


def check_technical_conditions(df):
    if len(df) < 60:
        return False, {}
    
    try:
        close = df['Close']
        high = df['High']
        low = df['Low']
        volume = df['Volume']

        ma5 = ta.sma(close, length=5)
        ma20 = ta.sma(close, length=20)
        rsi = ta.rsi(close, length=14)
        macd = ta.macd(close)
        bb = ta.bbands(close, length=20, std=2)
        ichi = ta.ichimoku(high, low, close)

        curr_close = close.iloc[-1]
        curr_rsi = rsi.iloc[-1]
        curr_macd = macd['MACD_12_26_9'].iloc[-1]
        curr_signal = macd['MACDs_12_26_9'].iloc[-1]
        curr_vol = volume.iloc[-1]
        vol_ma20 = ta.sma(volume, length=20).iloc[-1]
        
        prev_close = close.iloc[-2]
        change_rate = (curr_close - prev_close) / prev_close * 100

        cond_trend = ma5.iloc[-1] > ma20.iloc[-1]
        cond_rsi = 30 <= curr_rsi <= RSI_THRESHOLD
        cond_macd = curr_macd > curr_signal
        cond_vol = curr_vol >= (vol_ma20 * 1.25)
        cond_power = change_rate >= 2.0
        cond_bb = True if not USE_BB else (curr_close >= bb['BBU_20_2.0'].iloc[-1] * 0.98)
        cond_ichi = True if not USE_ICHIMOKU else (curr_close > max(ichi[0]['ISA_9'].iloc[-1], ichi[0]['ISB_26'].iloc[-1]))

        if cond_trend and cond_rsi and cond_macd and cond_vol and cond_power and cond_bb and cond_ichi:
            return True, {
                '현재가': int(curr_close),
                'RSI': round(curr_rsi, 2),
                '등락률': round(change_rate, 2),
            }
    except:
        return False, {}
    
    return False, {}


def generate_beautiful_html(df, date_str):
    if df.empty:
        return f"<h2>{date_str} - 조건을 만족하는 종목이 없습니다.</h2>"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Malgun Gothic', sans-serif; background: #f8f9fa; padding: 20px; }}
            .container {{ max-width: 1200px; margin: auto; background: white; border-radius: 12px; box-shadow: 0 4px 25px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #1e3a8a, #3b82f6); color: white; padding: 30px; text-align: center; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th {{ background: #f1f5f9; padding: 14px; text-align: center; }}
            td {{ padding: 12px 8px; text-align: center; border-bottom: 1px solid #eee; }}
            tr:hover {{ background: #f0f9ff; }}
            .stock-name {{ text-align: left; font-weight: 600; }}
            .positive {{ color: #dc2626; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📈 주식 포착기 Ultimate</h1>
                <p>📅 {date_str} Daily Report</p>
            </div>
            <div style="padding: 25px 30px;">
                <h2>🎯 오늘의 유망주 ({len(df)}개)</h2>
                <table>
                    <thead>
                        <tr>
                            <th>종목명</th>
                            <th>현재가</th>
                            <th>등락률</th>
                            <th>RSI</th>
                            <th>PER</th>
                            <th>기관5일순매수</th>
                            <th>시가총액(억)</th>
                        </tr>
                    </thead>
                    <tbody>
    """
    for _, row in df.iterrows():
        change_class = "positive" if row['등락률'] > 0 else ""
        html += f"""
                        <tr>
                            <td class="stock-name">{row['종목명']}<br><small>{row['종목코드']}</small></td>
                            <td>{row['현재가']:,}</td>
                            <td class="{change_class}">+{row['등락률']}%</td>
                            <td>{row['RSI']}</td>
                            <td>{row['PER']}</td>
                            <td>{row['기관5일순매수']:,}</td>
                            <td>{row['시가총액(억)']:,}</td>
                        </tr>
        """
    html += """
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """
    return html


def main():
    start_time = time.time()
    print(f"\n{'='*90}")
    print("📈 주식 포착기 Ultimate 시작")
    print(f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*90}\n")

    stocks = fdr.StockListing(MARKET).sort_values(by='Marcap', ascending=False).head(LIMIT)
    
    results = []
    today = datetime.now().strftime("%Y%m%d")
    start_5d = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")

    for i, (_, row) in enumerate(stocks.iterrows(), 1):
        sys.stdout.write(f"\r[{i:3d}/{len(stocks)}] {row['Name']:<25}")
        sys.stdout.flush()

        try:
            df = fdr.DataReader(row['Code'], '2024-01-01')
            match, info = check_technical_conditions(df)
            
            if match:
                try:
                    inv = stock.get_market_trading_value_by_date(start_5d, today, row['Code'])
                    inst_net = int(inv['기관합계'].tail(5).sum())
                except:
                    inst_net = 0

                if USE_INST and inst_net <= 0:
                    continue

                per = get_per_pbr(row['Code']) if USE_PER else '-'

                info.update({
                    '종목코드': row['Code'],
                    '종목명': row['Name'],
                    '기관5일순매수': inst_net,
                    '시가총액(억)': int(row['Marcap'] / 1e8),
                    'PER': per
                })
                results.append(info)
        except:
            continue
        time.sleep(0.08)

    # ====================== 보고서 생성 ======================
    elapsed = time.time() - start_time
    date_str = datetime.now().strftime("%Y년 %m월 %d일 (%A)")

    if results:
        df_result = pd.DataFrame(results)
        df_result = df_result.sort_values(by='등락률', ascending=False)
        html_content = generate_beautiful_html(df_result, date_str)
        
        with open('today_picks.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"\n✅ 분석 완료! {len(results)}개 종목 발견")
    else:
        print("\n❌ 오늘 조건을 만족하는 종목이 없습니다.")
        with open('today_picks.html', 'w', encoding='utf-8') as f:
            f.write(f"<h2>{date_str} - 조건을 만족하는 종목이 없습니다.</h2>")

    print(f"📄 today_picks.html 생성 완료")
    print(f"⏱ 총 소요시간: {elapsed:.1f}초")
    print(f"{'='*90}")


if __name__ == "__main__":
    main()

# =============================================================================
#                    주식 포착기 Ultimate - 예쁜 보고서 + PER
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
LIMIT = 600
RSI_THRESHOLD = 63
USE_BB = False
USE_ICHIMOKU = True
USE_INST = True

# =========================================================

def get_per_pbr(code):
    """네이버 증권에서 PER, PBR 가져오기"""
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        per = soup.select_one('#_per')
        pbr = soup.select_one('#_pbr')
        
        per_val = per.text.strip() if per and per.text.strip() != '' else '-'
        pbr_val = pbr.text.strip() if pbr and pbr.text.strip() != '' else '-'
        
        return per_val, pbr_val
    except:
        return '-', '-'


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
        senkou_a = ichi[0]['ISA_9']
        senkou_b = ichi[0]['ISB_26']

        curr_close = close.iloc[-1]
        curr_ma5 = ma5.iloc[-1]
        curr_ma20 = ma20.iloc[-1]
        curr_rsi = rsi.iloc[-1]
        curr_macd = macd['MACD_12_26_9'].iloc[-1]
        curr_signal = macd['MACDs_12_26_9'].iloc[-1]
        curr_vol = volume.iloc[-1]
        vol_ma20 = ta.sma(volume, length=20).iloc[-1]
        
        prev_close = close.iloc[-2]
        change_rate = (curr_close - prev_close) / prev_close * 100
        cloud_top = max(senkou_a.iloc[-1], senkou_b.iloc[-1])

        cond_trend = curr_ma5 > curr_ma20
        cond_rsi = 30 <= curr_rsi <= RSI_THRESHOLD
        cond_macd = curr_macd > curr_signal
        cond_vol = curr_vol >= (vol_ma20 * 1.25)
        cond_power = change_rate >= 2.0
        cond_bb = (curr_close >= bb['BBU_20_2.0'].iloc[-1] * 0.98) if USE_BB else True
        cond_ichi = (curr_close > cloud_top) if USE_ICHIMOKU else True

        if cond_trend and cond_rsi and cond_macd and cond_vol and cond_power and cond_bb and cond_ichi:
            return True, {
                '현재가': int(curr_close),
                'RSI': round(curr_rsi, 2),
                '등락률': round(change_rate, 2),
            }
    except:
        return False, {}
    
    return False, {}


def generate_beautiful_html(results, date_str):
    if not results:
        return "<h2>오늘 조건을 만족하는 종목이 없습니다.</h2>"

    df = pd.DataFrame(results)
    df = df.sort_values(by='등락률', ascending=False)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Malgun Gothic', 'Segoe UI', sans-serif; background: #f8f9fa; padding: 20px; }}
            .container {{ max-width: 1200px; margin: auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 25px rgba(0,0,0,0.12); }}
            .header {{ background: linear-gradient(135deg, #1e3a8a, #3b82f6); color: white; padding: 30px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 30px; }}
            .date {{ font-size: 17px; margin-top: 8px; opacity: 0.95; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th {{ background: #f1f5f9; color: #1e40af; padding: 14px 8px; text-align: center; font-weight: 700; }}
            td {{ padding: 13px 8px; text-align: center; border-bottom: 1px solid #e2e8f0; }}
            tr:hover {{ background: #f0f9ff; }}
            .stock-name {{ text-align: left; font-weight: 600; color: #1e2937; }}
            .positive {{ color: #dc2626; font-weight: bold; }}
            .footer {{ text-align: center; padding: 25px; color: #64748b; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📈 주식 포착기 Ultimate</h1>
                <p class="date">📅 {date_str} Daily Report</p>
            </div>
            
            <div style="padding: 25px 30px;">
                <h2 style="color:#1e40af; margin-top:10px;">🎯 오늘의 유망주 ({len(df)}개)</h2>
                <table>
                    <thead>
                        <tr>
                            <th width="22%">종목명</th>
                            <th>현재가</th>
                            <th>등락률</th>
                            <th>RSI</th>
                            <th>PER</th>
                            <th>기관 5일 순매수</th>
                            <th>시가총액(억)</th>
                        </tr>
                    </thead>
                    <tbody>
    """

    for _, row in df.iterrows():
        change_class = "positive" if row['등락률'] > 0 else ""
        html += f"""
                        <tr>
                            <td class="stock-name">{row['종목명']}<br><small style="color:#64748b;">{row['종목코드']}</small></td>
                            <td><strong>{row['현재가']:,}</strong></td>
                            <td class="{change_class}">+{row['등락률']}%</td>
                            <td>{row['RSI']}</td>
                            <td>{row.get('PER', '-')}</td>
                            <td>{row['기관5일순매수']:,}</td>
                            <td>{row['시가총액(억)']:,}</td>
                        </tr>
        """

    html += """
                    </tbody>
                </table>
            </div>
            
            <div class="footer">
                Generated by GitHub Actions • 주식 포착기 Ultimate<br>
                ※ 본 자료는 참고용이며, 투자 책임은 투자자 본인에게 있습니다.
            </div>
        </div>
    </body>
    </html>
    """
    return html


def main():
    print(f"\n{'='*90}")
    print("📈 주식 포착기 Ultimate - 예쁜 보고서 + PER")
    print(f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*90}\n")

    stocks = fdr.StockListing(MARKET).sort_values(by='Marcap', ascending=False).head(LIMIT)
    print(f"🔍 {MARKET} 상위 {LIMIT}개 종목 분석 중...\n")

    results = []
    today = datetime.now().strftime("%Y%m%d")
    start_5d = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")

    for i, (_, row) in enumerate(stocks.iterrows(), 1):
        sys.stdout.write(f"\r[{i:3d}/{len(stocks)}] {row['Name']:<25}")
        sys.stdout.flush()

        try:
            df = fdr.DataReader(row['Code'], '2023-01-01')
            match, info = check_technical_conditions(df)
            
            if match:
                # 기관 수급
                try:
                    inv = stock.get_market_trading_value_by_date(start_5d, today, row['Code'])
                    inst_net = int(inv['기관합계'].tail(5).sum())
                except:
                    inst_net = 0

                if USE_INST and inst_net <= 0:
                    continue

                # PER 가져오기
                per, _ = get_per_pbr(row['Code'])

                info.update({
                    '종목코드': row['Code'],
                    '종목명': row['Name'],
                    '기관5일순매수': inst_net,
                    '시가총액(억)': int(row['Marcap'] / 1e8),
                    'PER': per
                })
                results.append(info)
                print(f"  → 발견! {row['Name']} (+{info['등락률']}%)  PER:{per}")
        except:
            continue
        time.sleep(0.13)

    # ====================== 보고서 생성 ======================
    print(f"\n\n{'='*90}")
    date_str = datetime.now().strftime("%Y년 %m월 %d일 (%A)")

    if results:
        html_content = generate_beautiful_html(results, date_str)
        with open('today_picks.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"✅ 예쁜 HTML 보고서 생성 완료 ({len(results)}개 종목)")
    else:
        print("❌ 조건을 만족하는 종목이 없습니다.")
        with open('today_picks.html', 'w', encoding='utf-8') as f:
            f.write(f"<h2>{date_str} - 조건을 만족하는 종목이 없습니다.</h2>")

    print(f"{'='*90}")


if __name__ == "__main__":
    main()

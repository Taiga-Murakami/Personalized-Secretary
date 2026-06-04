import urllib.request
import json

def fetch_ticker_data(ticker: str, name: str, unit: str = "") -> str:
    """指定したティッカーの現在値と前日比を取得してフォーマットする"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read().decode())
            meta = data['chart']['result'][0]['meta']
            
            current = meta.get('regularMarketPrice')
            # 前日終値（APIの仕様上、previousClose または chartPreviousClose に格納される）
            prev_close = meta.get('previousClose', meta.get('chartPreviousClose', current))
            
            if current is None or prev_close is None:
                return f"・{name}: データ不足"

            diff = current - prev_close
            diff_pct = (diff / prev_close) * 100 if prev_close != 0 else 0
            
            sign = "+" if diff > 0 else ""
            return f"・{name}: {current:,.2f}{unit} (前日比: {sign}{diff:,.2f}{unit} / {sign}{diff_pct:.2f}%)"
    except Exception as e:
        return f"・{name}: 取得エラー"

def get_data() -> str:
    """メインプログラムから呼び出されるデータ取得関数"""
    lines = []
    
    lines.append("【主要株価指数】")
    # 東京: 日経平均株価
    lines.append(fetch_ticker_data("^N225", "日経平均 (東京)", "円"))
    # NY: S&P 500 (米国市場の広範な動向を示すためダウよりS&P500を採用)
    lines.append(fetch_ticker_data("^GSPC", "S&P 500 (NY)", "pt"))
    # 上海: 上海総合指数
    lines.append(fetch_ticker_data("000001.SS", "上海総合 (上海)", "pt"))
    
    lines.append("\n【相互為替レート】")
    # 米ドル/円
    lines.append(fetch_ticker_data("JPY=X", "USD/JPY (ドル円)", "円"))
    # 米ドル/人民元
    lines.append(fetch_ticker_data("CNY=X", "USD/CNY (ドル元)", "元"))
    # 人民元/円
    lines.append(fetch_ticker_data("CNYJPY=X", "CNY/JPY (元円)", "円"))

    return "\n".join(lines)

# 単体テスト用
if __name__ == "__main__":
    print("--- 取得テスト開始 ---")
    print(get_data())
    print("--- 取得テスト終了 ---")
import requests
from bs4 import BeautifulSoup
import urllib.parse
import re

def parse_rxjapan(url: str) -> list:
    """
    RX Japanの展示会スケジュールをスクレイピングする
    """
    results = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        events = soup.find_all('div', class_='event-block')
        
        for event in events:
            # 1. タイトルの取得
            title_tag = event.find('h3', class_='event-title')
            title = title_tag.text.strip() if title_tag else "タイトル不明"
            
            # 2. 日程・会場の取得
            date_tag = event.find('p', class_='event-date')
            if date_tag:
                date_info = re.sub(r'\s+', ' ', date_tag.text).strip()
            else:
                date_info = "日程不明"
                
            # 3. 分野カテゴリの取得
            category = "分類不明"
            metatags = event.find('ul', class_='metatag')
            if metatags:
                li_tags = metatags.find_all('li')
                if len(li_tags) > 0:
                    category = li_tags[0].text.strip()
            
            # 4. URLの取得とデコード
            link = ""
            a_tag = event.find('a')
            if a_tag and a_tag.get('href'):
                raw_href = a_tag.get('href')
                parsed_url = urllib.parse.urlparse(raw_href)
                query_params = urllib.parse.parse_qs(parsed_url.query)
                
                if 'url' in query_params:
                    link = query_params['url'][0]
                else:
                    link = raw_href
                    if not link.startswith('http'):
                        link = f"https://www.rxjapan.jp{link}"
            
            results.append({
                "title": title,
                "date": date_info,
                "url": link,
                "category": category
            })
            
        return results

    except Exception as e:
        print(f"RX Japanの取得中にエラーが発生しました: {e}")
        return []

def get_data() -> str:
    """メインプログラムから呼び出されるデータ取得関数"""
    url = "https://www.rxjapan.jp/schedule?key=6c799e45&page=1&limit=64"
    data = parse_rxjapan(url)
    
    if not data:
        return "【RX Japan 展示会情報】\n・ 現在取得できる展示会情報はありません．"
        
    lines = ["【RX Japan 直近の展示会スケジュール】"]
    
    # 情報量が多すぎるとAIのコンテキストを圧迫するため、上位5件に絞って文字列化します
    for d in data[:5]:
        lines.append(f"・ {d['title']} ({d['category']})")
        lines.append(f"  日程: {d['date']}")
        # 秘書が参照元として使えるようにURLも付与
        lines.append(f"  URL: {d['url']}")
        
    return "\n".join(lines)

# 単体テスト用
if __name__ == "__main__":
    print("--- 技術展取得テスト開始 ---")
    print(get_data())
    print("--- 技術展取得テスト終了 ---")
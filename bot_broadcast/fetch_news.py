import urllib.request
import xml.etree.ElementTree as ET

def fetch_rss_titles(url: str, source_name: str, limit: int = 3) -> str:
    """指定されたRSSフィードからニュースタイトルを取得する"""
    try:
        # ボット弾きを回避するため、一般的なブラウザのUser-Agentを偽装
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=10) as res:
            raw_xml = res.read()
        
        root = ET.fromstring(raw_xml)
        
        # RSS 2.0形式の要素を検索
        items = root.findall('.//item')
        
        # 見つからない場合はAtom形式としてフォールバック検索
        if not items:
            namespace = {'atom': 'http://www.w3.org/2005/Atom'}
            items = root.findall('.//atom:entry', namespace)

        if not items:
            return f"【{source_name}】\n・ 記事が見つかりませんでした．"

        lines = [f"【{source_name}】"]
        for item in items[:limit]:
            # title要素の取得（RSSとAtomの両方のタグ名に対応）
            title_elem = item.find('title')
            if title_elem is None:
                title_elem = item.find('{http://www.w3.org/2005/Atom}title')
            
            title = title_elem.text.strip() if title_elem is not None else "タイトルなし"
            lines.append(f"・ {title}")
            
        return "\n".join(lines)
    except Exception as e:
        return f"【{source_name}】\n・ 取得エラー"

def get_data() -> str:
    """メインプログラムから呼び出されるデータ取得関数"""
    # 安定性を重視し、日米中はパブリックな主要RSSを活用
    feeds = [
        ("日本 (NHK)", "https://www.nhk.or.jp/rss/news/cat0.xml"),
        ("米国 (Google News US)", "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"),
        ("中国 (Google News China)", "https://news.google.com/rss?hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
        ("SCMP (China Section)", "https://www.scmp.com/rss/2/feed"),
        ("CNA (Latest News)", "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml")
    ]
    
    result_texts = []
    # 各メディアから最新の3件ずつを取得
    for name, url in feeds:
        result_texts.append(fetch_rss_titles(url, name, limit=3))
        
    return "\n\n".join(result_texts)

# 単体テスト用
if __name__ == "__main__":
    print("--- ニュース取得テスト開始 ---")
    print(get_data())
    print("--- ニュース取得テスト終了 ---")
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

# bot_broadcast ディレクトリ配下のモジュールをインポート
from bot_broadcast import fetch_market, fetch_news, fetch_tech
# 外部pyで設定したslack_formatter モジュールをインポート
import slack_formatter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_DIR = os.path.join(BASE_DIR, "settings")
load_dotenv(os.path.join(SETTINGS_DIR, ".env"))

# APIキーとAIモデル名の読み込み
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
# 環境変数に設定がない場合はデフォルトとして gemini-3.5-flash を使う安全設計
GEMINI_MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME", "gemini-3.5-flash") 

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

def generate_morning_report() -> str:
    try:
        raw_market = fetch_market.get_data()
        raw_news = fetch_news.get_data()
        raw_tech = fetch_tech.get_data()
    except Exception as e:
        return f"データの取得に一部失敗しました．詳細: {e}"

    # プロンプトをBlock Kit変換を前提とした構造に変更
    prompt = f"""
【本日の収集データ】
市場: {raw_market}
ニュース: {raw_news}
技術展: {raw_tech}
"""

    sys_prompt = """
あなたはCEOを支える優秀なAI秘書です。本日の朝刊レポートを作成してください。

【厳格なフォーマット指定】
後続のシステムで画面UIを構築するため、以下のMarkdownルールを絶対に守ってください。
1. 大見出しは必ず「## 見出し名」のように # を使って独立した行にすること。
2. セクションとセクションの間は必ず「---」（ハイフン3つ）で区切り線を引くこと。
3. 強調したい箇所は **太字** を用いること。
4. 出力では「、」ではなく「，」，「。」ではなく「．」を用いること。
"""

    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=sys_prompt,
                temperature=0.2
            )
        )
        
        # 文字列ではなく、変換済みの Block Kit 配列を返す
        return slack_formatter.markdown_to_slack_blocks(response.text)
        
    except Exception as e:
        # エラー時もセクションブロックの形で返す
        return [{"type": "section", "text": {"type": "mrkdwn", "text": f"エラー: {e}"}}]
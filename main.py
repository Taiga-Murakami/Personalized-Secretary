import os
import json
import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from google import genai
from google.genai import types
from notion_client import Client
from dotenv import load_dotenv

# --- Google Calendar API 用のインポート ---
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from googleapiclient.discovery import build
import pytz

# 同ディレクトリのモジュールからの関数をインポート
import report_generator
import slack_formatter

# --- 設定ファイルのパス解決 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_DIR = os.path.join(BASE_DIR, "settings")

# .env を settings ディレクトリから読み込む
load_dotenv(os.path.join(SETTINGS_DIR, ".env"))

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
GLOBAL_MEMORY_PAGE_ID = os.environ.get("GLOBAL_MEMORY_PAGE_ID")
ACCOUNT_A_EMAIL = os.environ.get("ACCOUNT_A_EMAIL")

GEMINI_MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME")

app = App(token=SLACK_BOT_TOKEN)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
notion = Client(auth=NOTION_API_KEY)

# --- 外部JSONからコンテキストを動的に構築 ---
def load_contexts():
    json_path = os.path.join(SETTINGS_DIR, "contexts.json")
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
        default_ctx = {
            "role_name": config["DEFAULT"]["role_name"],
            "system_prompt": config["DEFAULT"]["system_prompt"],
            "local_memory_id": None
        }
        
        channel_ctx = {}
        for ch in config.get("CHANNELS", []):
            channel_id = os.environ.get(ch["channel_env_key"])
            if channel_id: # .envに該当チャンネルIDが設定されている場合のみ登録
                memory_env_key = ch.get("memory_env_key")
                channel_ctx[channel_id] = {
                    "role_name": ch["role_name"],
                    "system_prompt": ch["system_prompt"],
                    "local_memory_id": os.environ.get(memory_env_key) if memory_env_key else None
                }
        return channel_ctx, default_ctx
    except Exception as e:
        print(f"contexts.json 読み込みエラー: {e}")
        # フォールバック
        return {}, {"role_name": "汎用アシスタント", "system_prompt": "丁寧に対応してください．", "local_memory_id": None}

CHANNEL_CONTEXTS, DEFAULT_CONTEXT = load_contexts()

# ==========================================
# 記憶・データ取得関数群
# ==========================================

def get_slack_history(channel_id: str, ts: str, thread_ts: str = None, limit: int = 6) -> list:
    """Slackから直近の会話履歴を取得する（スレッド対応版）"""
    try:
        contents = []
        if thread_ts:
            # スレッド内の履歴を取得（時系列順に取得される）
            result = app.client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                limit=50 # スレッド内の直近の文脈を拾うため多めに取得
            )
            messages = result.get("messages", [])
            # 今回のトリガーとなった最新のユーザー発言を除外
            messages = [msg for msg in messages if msg.get("ts") != ts]
            # 直近の limit 件に絞る
            messages = messages[-limit:]
        else:
            # チャンネル全体の履歴を取得（新しい順に取得されるため反転）
            result = app.client.conversations_history(
                channel=channel_id, limit=limit, latest=ts, inclusive=False
            )
            messages = result.get("messages", [])
            messages.reverse()

        for msg in messages:
            text = msg.get("text", "")
            if not text:
                continue
            role = "model" if "bot_id" in msg else "user"
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=text)]))
        return contents
    except Exception as e:
        print(f"Slack履歴取得エラー: {e}")
        return []

def read_notion_memory(page_id: str, with_id: bool = False) -> str:
    if not page_id:
        return ""
    try:
        response = notion.blocks.children.list(block_id=page_id)
        blocks = response.get("results", [])
        extracted_text = []
        for block in blocks:
            block_type = block.get("type")
            if block_type in ["paragraph", "bulleted_list_item", "numbered_list_item"]:
                rich_texts = block.get(block_type, {}).get("rich_text", [])
                text_content = "".join([rt.get("plain_text", "") for rt in rich_texts])
                if text_content.strip():
                    if with_id:
                        extracted_text.append(f"[ID: {block['id']}] {text_content}\n")
                    else:
                        extracted_text.append(f"・ {text_content}\n")
        return "".join(extracted_text).strip()
    except Exception as e:
        print(f"Notion読み込みエラー: {e}")
        return ""

def write_local_memory(text: str, page_id: str) -> str:
    if not page_id:
        return "エラー: 保存先のページIDが設定されていません．"
    try:
        notion.blocks.children.append(
            block_id=page_id,
            children=[{
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]}
            }]
        )
        return f"メモリに「{text}」を追加しました．"
    except Exception as e:
        return f"メモリの追加に失敗しました: {e}"

def delete_local_memory(block_id: str) -> str:
    try:
        notion.blocks.delete(block_id=block_id)
        return f"ID: {block_id} の記憶を削除しました．"
    except Exception as e:
        return f"メモリの削除に失敗しました: {e}"

# ==========================================
# カレンダー操作関数群（Tools）
# ==========================================

def get_calendar_service():
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/calendar'])
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GoogleAuthRequest())
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        return build('calendar', 'v3', credentials=creds)
    return None

def get_events() -> str:
    service = get_calendar_service()
    if not service: return "認証エラー：token.jsonが見つかりません．"
    
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    all_events = []
    
    try:
        res_b = service.events().list(calendarId='primary', timeMin=now, maxResults=10, singleEvents=True, orderBy='startTime').execute()
        for ev in res_b.get('items', []):
            ev['source'] = 'AI'
            all_events.append(ev)
    except Exception as e:
        print(f"AIアカウントの予定取得失敗: {e}")
            
    try:
        res_a = service.events().list(calendarId=ACCOUNT_A_EMAIL, timeMin=now, maxResults=10, singleEvents=True, orderBy='startTime').execute()
        for ev in res_a.get('items', []):
            ev['source'] = 'Main'
            all_events.append(ev)
    except Exception as e:
        print(f"メインアカウントの予定取得失敗: {e}")

    all_events.sort(key=lambda x: x['start'].get('dateTime', x['start'].get('date')))
    if not all_events: return "直近の予定はありません．"
        
    result_text = "【直近の予定】\n"
    for ev in all_events:
        start = ev['start'].get('dateTime', ev['start'].get('date'))[:16].replace('T', ' ')
        result_text += f"- [{ev['source']}] {start} : {ev.get('summary', 'タイトルなし')}\n"
    return result_text

def create_event(title: str, start_time: str, end_time: str) -> str:
    service = get_calendar_service()
    if not service: return "認証エラー"
        
    jst = pytz.timezone('Asia/Tokyo')
    try:
        start_dt = jst.localize(datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S'))
        end_dt = jst.localize(datetime.datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S'))
        
        event = {
            'summary': title,
            'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Asia/Tokyo'},
            'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Tokyo'},
        }
        service.events().insert(calendarId='primary', body=event).execute()
        return f"「{title}」を登録しました．"
    except Exception as e:
        return f"予定の作成に失敗しました: {e}"

# ==========================================
# メインのAI応答処理
# ==========================================

# 引数に thread_ts: str = None を追加
def generate_ai_response(channel_id: str, user_message: str, ts: str, thread_ts: str = None) -> str:
    context = CHANNEL_CONTEXTS.get(channel_id, DEFAULT_CONTEXT)
    local_page_id = context.get("local_memory_id")
    
    global_memory = read_notion_memory(GLOBAL_MEMORY_PAGE_ID, with_id=False)
    local_memory = read_notion_memory(local_page_id, with_id=True) if local_page_id else "設定なし"
    
    current_time_str = datetime.datetime.now(pytz.timezone('Asia/Tokyo')).strftime('%Y-%m-%d %H:%M:%S')

    def tool_add_memory(text: str) -> str:
        return write_local_memory(text, local_page_id)

    def tool_delete_memory(block_id: str) -> str:
        return delete_local_memory(block_id)

    tools = [get_events, create_event]
    if local_page_id:
        tools.extend([tool_add_memory, tool_delete_memory])

    final_system_prompt = f"""{context['system_prompt']}

【ユーザーの基本情報（グローバル共通）】
{global_memory}

【プロジェクト固有の記憶（ローカル）】
{local_memory}

【システム情報とルール】
現在時刻（日本時間）: {current_time_str}
1. カレンダー操作: 予定の作成を求められた際は，現在時刻を基準に日時を計算してください．
2. メモリ追加: ユーザーから「記憶して」「メモして」など長期保存の意図を感じた場合は，tool_add_memoryを使用して追記してください．
3. メモリ削除: tool_delete_memoryは，ユーザーから「〇〇の記憶を消して」と【明示的な指示があった場合のみ】実行してください．AIの自己判断での削除は固く禁じます．削除対象のブロックIDはローカル記憶の [ID: xxx] から取得してください．
4. フォーマット: 見出しには「## 見出し名」、セクションの区切りには「---」、強調には「**太字**」を積極的に使用し、視認性の高いマークダウン形式で出力してください。
"""
    
    # ここを変更：thread_ts を渡す
    chat_contents = get_slack_history(channel_id, ts, thread_ts, limit=6)
    chat_contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))
    
    # --- 以降の try: から始まる AI生成処理と Function Calling 処理はそのまま ---
    
    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=chat_contents,
            config=types.GenerateContentConfig(
                system_instruction=final_system_prompt,
                temperature=0.7,
                tools=tools
            )
        )
        
        if response.function_calls:
            chat_contents.append(response.candidates[0].content)
            
            for function_call in response.function_calls:
                name = function_call.name
                args = function_call.args
                api_result = ""
                
                if name == "get_events": api_result = get_events()
                elif name == "create_event": api_result = create_event(args['title'], args['start_time'], args['end_time'])
                elif name == "tool_add_memory": api_result = tool_add_memory(args['text'])
                elif name == "tool_delete_memory": api_result = tool_delete_memory(args['block_id'])
                
                chat_contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_function_response(name=name, response={"result": api_result})]
                    )
                )
            
            final_response = gemini_client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=chat_contents,
                config=types.GenerateContentConfig(system_instruction=final_system_prompt, temperature=0.7)
            )
            return f"【{context['role_name']}】\n{final_response.text}"

        return f"【{context['role_name']}】\n{response.text}"
        
    except Exception as e:
        return f"AIの生成中にエラーが発生しました: {str(e)}"

@app.event("message")
def handle_message_events(body, logger):
    event = body.get("event", {})
    if "bot_id" in event:
        return

    channel_id = event.get("channel")
    user_message = event.get("text")
    ts = event.get("ts")
    # スレッドからのメッセージであれば取得（なければNoneになる）
    thread_ts = event.get("thread_ts")
    
    if not user_message:
        return

    # thread_ts を渡す
    ai_reply_text = generate_ai_response(channel_id, user_message, ts, thread_ts)
    
    try:
        # AIの返答テキストを Block Kit に変換
        reply_blocks = slack_formatter.markdown_to_slack_blocks(ai_reply_text)
        
        post_args = {
            "channel": channel_id,
            "text": "AIからの返信", # 通知用
            "blocks": reply_blocks # 実際の美しいUI
        }
        if thread_ts:
            post_args["thread_ts"] = thread_ts
            
        app.client.chat_postMessage(**post_args)
    except Exception as e:
        logger.error(f"Slack送信エラー: {e}")

# ==========================================
# 定期配信（プッシュ通知）用の処理
# ==========================================
def scheduled_news_delivery():
    channel_id = os.environ.get("SLACK_CHANNEL_DAILY_NEWS")
    if not channel_id: return
        
    try:
        print("朝刊レポートを生成中...")
        # 文字列(text)ではなく、ブロック配列(blocks)を受け取る
        report_blocks = report_generator.generate_morning_report()
        
        # text="新着レポート" は通知ポップアップ等に使われるフォールバック用
        app.client.chat_postMessage(
            channel=channel_id, 
            text="本日の朝刊レポートが届きました", 
            blocks=report_blocks
        )
        print("朝刊レポートを無事に送信しました．")
    except Exception as e:
        print(f"定期送信エラー: {e}")

# ==========================================
# プログラムの起動エントリーポイント
# ==========================================
if __name__ == "__main__":
    print("⚡️ AI Secretary is running in Socket Mode!")
    
    scheduler = BackgroundScheduler(timezone="Asia/Tokyo")
    
    # 本番用：毎日 朝8時00分 に配信する設定
    # scheduler.add_job(scheduled_news_delivery, CronTrigger(hour=8, minute=0))

    # テスト用：起動後1分後に1回だけ配信する設定（動作確認用）
    scheduler.add_job(scheduled_news_delivery, CronTrigger(minute=(datetime.datetime.now().minute + 1) % 60))
    
    scheduler.start()
    print("🕒 Background Scheduler has started.")
    
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
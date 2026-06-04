import re

def markdown_to_slack_blocks(text: str) -> list:
    """
    標準的なMarkdownテキストを、Slack Block KitのJSON配列（リスト）に変換する
    """
    blocks = []
    
    # 1. Slack用の太字変換（**text** -> *text*）
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
    
    # 2. テキストを空行（パラグラフ）ごとに分割
    paragraphs = text.split('\n\n')
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # 3. 見出し（# または ## または ###）の処理
        if para.startswith(('# ', '## ', '### ')):
            # Slackのヘッダーブロックはマークダウン不可、最大150文字という制限があるため整形
            header_text = re.sub(r'^#+\s*', '', para)[:150]
            blocks.append({
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": header_text,
                    "emoji": True
                }
            })
            
        # 4. 区切り線（---）の処理
        elif para == '---':
            blocks.append({
                "type": "divider"
            })
            
        # 5. 通常のテキストブロック
        else:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": para
                }
            })
            
    return blocks
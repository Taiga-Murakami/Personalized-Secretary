# 軽量なPython 3.11環境をベースにする
FROM python:3.11-slim

# 作業ディレクトリの設定
WORKDIR /app

# ライブラリのインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# プログラム本体をコピー
COPY . .

# FastAPIのポート開放と起動コマンド
EXPOSE 8000
CMD ["python", "main.py"]
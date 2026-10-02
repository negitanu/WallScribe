# マルチステージビルド: ビルドステージ
FROM python:3.14-alpine3.24 AS builder

# 作業ディレクトリを設定
WORKDIR /build

# システムパッケージの更新とビルドツールのインストール
RUN apk add --no-cache gcc musl-dev libffi-dev

# 依存関係ファイルをコピー
COPY requirements.txt .

# 依存関係をインストール
# 実行環境にはアプリの依存だけをコピーし、pip の同梱ライブラリを持ち込まない。
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt && \
    /opt/venv/bin/pip uninstall --yes pip

# 本番ステージ
FROM python:3.14-alpine3.24

# メタデータ
LABEL maintainer="WallScribe"
LABEL description="ファイアウォール パラメータシート生成ツール"

# WeasyPrint実行時に必要なランタイムライブラリと日本語フォント、タイムゾーンデータをインストール
RUN apk upgrade --no-cache && apk add --no-cache pango harfbuzz-subset font-noto-cjk tzdata

# ベースイメージのインストール用ツールも本番には不要。
RUN python -m pip uninstall --yes pip

# 旧 Debian イメージと UID/GID を揃え、既存ボリュームの所有権を維持する。
RUN delgroup ping && addgroup -S -g 999 appuser && \
    adduser -S -u 999 -G appuser -h /home/appuser appuser

# 作業ディレクトリを設定
WORKDIR /app

# ビルドステージから依存関係をコピー
COPY --from=builder /opt/venv /opt/venv

# アプリケーションファイルをコピー
COPY app.py main.py exceptions.py ./
COPY parsers/ ./parsers/
COPY models/ ./models/
COPY analyzers/ ./analyzers/
COPY exporters/ ./exporters/
COPY web/ ./web/
COPY static/ ./static/
COPY utils/ ./utils/
COPY api/ ./api/
COPY routes/ ./routes/
COPY jobs/ ./jobs/
COPY services/ ./services/
COPY gunicorn_config.py ./

# アップロードディレクトリとフォントキャッシュディレクトリを作成
RUN mkdir -p /app/uploads /home/appuser/.cache/fontconfig && \
    chown -R appuser:appuser /app /home/appuser

# 環境変数を設定
ENV PATH=/opt/venv/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production
ENV FLASK_PORT=8080
ENV UPLOAD_FOLDER=/app/uploads
ENV MAX_CONTENT_LENGTH=52428800
ENV CLEANUP_INTERVAL=3600
ENV GUNICORN_WORKERS=4
ENV GUNICORN_THREADS=2
ENV FONTCONFIG_CACHE_DIR=/home/appuser/.cache/fontconfig
ENV TZ=Asia/Tokyo

# ユーザーを切り替え
USER appuser

# ポートを公開
EXPOSE 8080

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/')" || exit 1

# エントリーポイント
# 本番環境では gunicorn を使用
CMD ["gunicorn", "--config", "gunicorn_config.py", "app:app"]

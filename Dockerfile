# マルチステージビルド: ビルドステージ
FROM python:3.14-slim AS builder

# 作業ディレクトリを設定
WORKDIR /build

# システムパッケージの更新とビルドツールのインストール
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libcairo2-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-dev \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# 依存関係ファイルをコピー
COPY requirements.txt .

# 依存関係をインストール
RUN pip install --no-cache-dir --user -r requirements.txt

# 本番ステージ
FROM python:3.14-slim

# メタデータ
LABEL maintainer="WallScribe"
LABEL description="ファイアウォール パラメータシート生成ツール"

# WeasyPrint実行時に必要なランタイムライブラリと日本語フォント、タイムゾーンデータをインストール
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    fonts-noto-cjk \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 非rootユーザーを作成
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 作業ディレクトリを設定
WORKDIR /app

# ビルドステージから依存関係をコピー
COPY --from=builder /root/.local /home/appuser/.local

# アプリケーションファイルをコピー
COPY app.py main.py exceptions.py ./
COPY parsers/ ./parsers/
COPY models/ ./models/
COPY exporters/ ./exporters/
COPY web/ ./web/
COPY static/ ./static/
COPY utils/ ./utils/
COPY api/ ./api/
COPY gunicorn_config.py ./

# アップロードディレクトリとフォントキャッシュディレクトリを作成
RUN mkdir -p /app/uploads /home/appuser/.cache/fontconfig && \
    chown -R appuser:appuser /app /home/appuser/.cache

# 環境変数を設定
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production
ENV FLASK_PORT=8080
ENV UPLOAD_FOLDER=/app/uploads
ENV MAX_CONTENT_LENGTH=52428800
ENV CLEANUP_INTERVAL=3600
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
# gunicorn_config.py を使用する場合:
# CMD ["gunicorn", "--config", "gunicorn_config.py", "app:app"]
# または直接指定:
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "4", "--threads", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:app"]

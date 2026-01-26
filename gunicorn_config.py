#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gunicorn設定ファイル
本番環境用のWSGIサーバー設定
"""

import multiprocessing
import os

# サーバーソケット
bind = f"0.0.0.0:{os.environ.get('FLASK_PORT', '8080')}"
backlog = 2048

# ワーカー設定
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 50

# ログ設定
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# プロセス名
proc_name = "WallScribe"

# サーバーメカニズム
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL設定（必要に応じて）
# keyfile = '/path/to/keyfile'
# certfile = '/path/to/certfile'

# パフォーマンス設定
preload_app = True
worker_tmp_dir = "/dev/shm"  # 共有メモリを使用（高速化）

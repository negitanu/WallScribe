#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ファイアウォール パラメータシート生成ツール - Web アプリケーション
"""

import os
import uuid
import json
import logging
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from flask import (
    Flask, render_template, request, jsonify,
    send_file, redirect, url_for
)
from werkzeug.utils import secure_filename

from parsers.base import get_parser_for_content
from exporters.html import HTMLExporter
from exporters.pdf import PDFExporter

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Flask アプリケーション
app = Flask(__name__, template_folder='web/templates', static_folder='static')

# 設定
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', './uploads')
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', 50 * 1024 * 1024))  # 50MB
app.config['CLEANUP_INTERVAL'] = int(os.environ.get('CLEANUP_INTERVAL', 3600))  # 1時間

# 許可拡張子
ALLOWED_EXTENSIONS = {'.conf', '.xml'}

# 生成ファイルのメタデータを保存（ファイルシステムベース）
def get_metadata_path(file_id: str) -> Path:
    """メタデータファイルのパスを取得"""
    upload_folder = Path(app.config['UPLOAD_FOLDER'])
    return upload_folder / f"{file_id}.meta.json"


def save_file_metadata(file_id: str, metadata: dict):
    """ファイルメタデータを保存"""
    try:
        metadata_path = get_metadata_path(file_id)
        # created_atを文字列に変換（JSONシリアライズ可能にする）
        metadata_copy = metadata.copy()
        if 'created_at' in metadata_copy and isinstance(metadata_copy['created_at'], datetime):
            metadata_copy['created_at'] = metadata_copy['created_at'].isoformat()
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata_copy, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"メタデータ保存エラー: {e}", exc_info=True)


def load_file_metadata(file_id: str) -> Optional[Dict[str, Any]]:
    """ファイルメタデータを読み込み"""
    try:
        metadata_path = get_metadata_path(file_id)
        if not metadata_path.exists():
            return None
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
            # created_atをdatetimeに変換
            if 'created_at' in metadata and isinstance(metadata['created_at'], str):
                metadata['created_at'] = datetime.fromisoformat(metadata['created_at'])
            return metadata
    except Exception as e:
        logger.error(f"メタデータ読み込みエラー: {e}", exc_info=True)
        return None


def delete_file_metadata(file_id: str):
    """ファイルメタデータを削除"""
    try:
        metadata_path = get_metadata_path(file_id)
        if metadata_path.exists():
            metadata_path.unlink()
    except Exception as e:
        logger.error(f"メタデータ削除エラー: {e}", exc_info=True)


def allowed_file(filename: str) -> bool:
    """許可されたファイル拡張子かチェック"""
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def get_file_extension(filename: str) -> str:
    """ファイル拡張子を取得"""
    return Path(filename).suffix.lower()


def cleanup_old_files():
    """古いファイルをクリーンアップ"""
    while True:
        try:
            now = datetime.now()
            upload_folder = Path(app.config['UPLOAD_FOLDER'])

            if upload_folder.exists():
                for file_path in upload_folder.iterdir():
                    if file_path.is_file():
                        # 1時間以上前のファイルを削除
                        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if now - mtime > timedelta(hours=1):
                            file_path.unlink()
                            logger.info(f"クリーンアップ: {file_path.name}")

            # メタデータもクリーンアップ
            if upload_folder.exists():
                for meta_path in upload_folder.glob("*.meta.json"):
                    try:
                        # ファイルIDを抽出（例: 93b3a478-83a6-47c0-85bd-8cfe4b85a5ad.meta.json -> 93b3a478-83a6-47c0-85bd-8cfe4b85a5ad）
                        file_id = meta_path.stem.replace('.meta', '')
                        metadata = load_file_metadata(file_id)
                        if metadata:
                            created_at = metadata.get('created_at')
                            if isinstance(created_at, str):
                                created_at = datetime.fromisoformat(created_at)
                            if created_at and now - created_at > timedelta(hours=1):
                                delete_file_metadata(file_id)
                                logger.info(f"メタデータクリーンアップ: {meta_path.name}")
                    except Exception as e:
                        logger.warning(f"メタデータクリーンアップエラー: {meta_path.name}, {e}")

        except Exception as e:
            logger.error(f"クリーンアップエラー: {e}")

        time.sleep(app.config['CLEANUP_INTERVAL'])


# クリーンアップスレッド開始
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()


@app.route('/')
def index():
    """メインページ"""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """ファイルアップロード・変換処理"""
    try:
        # ファイルチェック
        if 'config_file' not in request.files:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'NO_FILE',
                    'message': 'ファイルが選択されていません'
                }
            }), 400

        file = request.files['config_file']

        if file.filename == '':
            return jsonify({
                'success': False,
                'error': {
                    'code': 'NO_FILE',
                    'message': 'ファイルが選択されていません'
                }
            }), 400

        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': {
                    'code': 'UNSUPPORTED_FORMAT',
                    'message': 'サポートされていないファイル形式です',
                    'details': '対応形式: .conf (FortiGate), .xml (Palo Alto)'
                }
            }), 400

        # 出力形式
        output_format = request.form.get('output_format', 'html')

        # 出力セクション
        sections_json = request.form.get('sections', '[]')
        try:
            sections_list = json.loads(sections_json)
            # 型チェック: リストであることを確認
            sections = sections_list if isinstance(sections_list, list) else None
        except json.JSONDecodeError:
            sections = None  # デフォルト（全セクション）

        # ファイル内容読み込み
        content = file.read().decode('utf-8')
        original_filename = secure_filename(file.filename)

        # パーサー取得
        parser = get_parser_for_content(content)
        if parser is None:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'UNSUPPORTED_FORMAT',
                    'message': '設定ファイルの形式を判別できません',
                    'details': '対応形式: .conf (FortiGate), .xml (Palo Alto)'
                }
            }), 400

        # パース実行
        logger.info(f"パース開始: {original_filename}")
        config = parser.parse_content(content, original_filename)

        if parser.errors:
            for error in parser.errors:
                logger.warning(f"パースエラー: {error}")

        # 出力ファイル生成
        # セキュリティ: より安全なID生成（完全なUUIDを使用）
        file_id = str(uuid.uuid4())
        upload_folder = Path(app.config['UPLOAD_FOLDER']).resolve()
        upload_folder.mkdir(parents=True, exist_ok=True)

        if output_format == 'html':
            output_filename = f"{Path(original_filename).stem}_param.html"
            # パストラバーサル対策: パスの正規化と検証
            output_path = (upload_folder / f"{file_id}_{output_filename}").resolve()
            
            # アップロードフォルダ外への書き込みを防止
            if not str(output_path).startswith(str(upload_folder)):
                raise ValueError("Invalid file path detected")

            # sectionsがNoneの場合は全セクション、それ以外はリストを渡す
            # 型チェック: sectionsがリストであることを確認
            if sections is None or not isinstance(sections, list):
                exporter = HTMLExporter(config)
            else:
                # 文字列のリストであることを確認
                sections_list = [s for s in sections if isinstance(s, str)]
                exporter = HTMLExporter(config, sections=sections_list)
            exporter.export(str(output_path))
        elif output_format == 'pdf':
            output_filename = f"{Path(original_filename).stem}_param.pdf"
            # パストラバーサル対策: パスの正規化と検証
            output_path = (upload_folder / f"{file_id}_{output_filename}").resolve()
            
            # アップロードフォルダ外への書き込みを防止
            if not str(output_path).startswith(str(upload_folder)):
                raise ValueError("Invalid file path detected")

            # sectionsがNoneの場合は全セクション、それ以外はリストを渡す
            # 型チェック: sectionsがリストであることを確認
            if sections is None or not isinstance(sections, list):
                exporter = PDFExporter(config)
            else:
                # 文字列のリストであることを確認
                sections_list = [s for s in sections if isinstance(s, str)]
                exporter = PDFExporter(config, sections=sections_list)
            exporter.export(str(output_path))
        else:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'UNSUPPORTED_FORMAT',
                    'message': f'サポートされていない出力形式です: {output_format}',
                    'details': '対応形式: html, pdf'
                }
            }), 400

        # メタデータ保存（パスは正規化して保存）
        summary = config.get_summary()
        # パスを正規化（resolve()で絶対パスに変換）
        normalized_path = str(output_path.resolve())
        metadata = {
            'filename': output_filename,
            'path': normalized_path,
            'device_type': summary['device_type'],
            'hostname': summary['hostname'],
            'version': summary['version'],
            'summary': summary,
            'created_at': datetime.now()
        }
        save_file_metadata(file_id, metadata)

        logger.info(f"生成完了: {output_filename} (ID: {file_id}, Path: {normalized_path})")

        return jsonify({
            'success': True,
            'file_id': file_id,
            'filename': output_filename,
            'device_type': summary['device_type'],
            'hostname': summary['hostname'],
            'version': summary['version'],
            'summary': summary,
            'download_url': f'/download/{file_id}',
            'preview_url': f'/preview/{file_id}'
        })

    except UnicodeDecodeError:
        return jsonify({
            'success': False,
            'error': {
                'code': 'ENCODING_ERROR',
                'message': 'ファイルのエンコーディングを読み取れません',
                'details': 'UTF-8形式のファイルを使用してください'
            }
        }), 400

    except Exception as e:
        logger.error(f"処理エラー: {e}", exc_info=True)
        # セキュリティ: 本番環境では詳細情報を返さない
        is_production = os.environ.get('FLASK_ENV', 'production') == 'production'
        error_details = '詳細はログを確認してください' if is_production else str(e)
        
        return jsonify({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': '予期しないエラーが発生しました',
                'details': error_details
            }
        }), 500


@app.route('/download/<file_id>')
def download_file(file_id):
    """生成ファイルのダウンロード"""
    # セキュリティ: ファイルIDの検証（UUID形式のチェック）
    try:
        uuid.UUID(file_id)
    except (ValueError, AttributeError):
        return jsonify({
            'success': False,
            'error': {
                'code': 'INVALID_FILE_ID',
                'message': '無効なファイルIDです'
            }
        }), 400
    
    file_info = load_file_metadata(file_id)
    if file_info is None:
        logger.warning(f"ファイルIDが見つかりません: {file_id}")
        return jsonify({
            'success': False,
            'error': {
                'code': 'FILE_NOT_FOUND',
                'message': 'ファイルが見つかりません'
            }
        }), 404
    
    # 保存されているパスを使用（既に正規化済み）
    file_path = Path(file_info['path'])
    
    # パストラバーサル対策: パスの検証
    upload_folder = Path(app.config['UPLOAD_FOLDER']).resolve()
    file_path_resolved = file_path.resolve()
    
    # パスの比較（両方ともresolve()で正規化）
    if not str(file_path_resolved).startswith(str(upload_folder)):
        logger.warning(f"パストラバーサル攻撃の可能性: {file_id}, Path: {file_path_resolved}, Upload: {upload_folder}")
        return jsonify({
            'success': False,
            'error': {
                'code': 'INVALID_PATH',
                'message': '無効なファイルパスです'
            }
        }), 400

    if not file_path_resolved.exists():
        logger.warning(f"ファイルが存在しません: {file_path_resolved}")
        return jsonify({
            'success': False,
            'error': {
                'code': 'FILE_NOT_FOUND',
                'message': 'ファイルが削除されました'
            }
        }), 404

    logger.info(f"ファイルダウンロード: {file_path_resolved}")
    return send_file(
        file_path_resolved,
        as_attachment=True,
        download_name=file_info['filename']
    )


@app.route('/preview/<file_id>')
def preview_file(file_id):
    """生成ファイルのプレビュー"""
    # セキュリティ: ファイルIDの検証
    try:
        uuid.UUID(file_id)
    except (ValueError, AttributeError):
        return jsonify({
            'success': False,
            'error': {
                'code': 'INVALID_FILE_ID',
                'message': '無効なファイルIDです'
            }
        }), 400
    
    file_info = load_file_metadata(file_id)
    if file_info is None:
        logger.warning(f"ファイルIDが見つかりません: {file_id}")
        return jsonify({
            'success': False,
            'error': {
                'code': 'FILE_NOT_FOUND',
                'message': 'ファイルが見つかりません'
            }
        }), 404
    
    # 保存されているパスを使用（既に正規化済み）
    file_path = Path(file_info['path'])
    
    # パストラバーサル対策: パスの検証
    upload_folder = Path(app.config['UPLOAD_FOLDER']).resolve()
    file_path_resolved = file_path.resolve()
    
    # パスの比較（両方ともresolve()で正規化）
    if not str(file_path_resolved).startswith(str(upload_folder)):
        logger.warning(f"パストラバーサル攻撃の可能性: {file_id}, Path: {file_path_resolved}, Upload: {upload_folder}")
        return jsonify({
            'success': False,
            'error': {
                'code': 'INVALID_PATH',
                'message': '無効なファイルパスです'
            }
        }), 400

    if not file_path_resolved.exists():
        logger.warning(f"ファイルが存在しません: {file_path_resolved}")
        return jsonify({
            'success': False,
            'error': {
                'code': 'FILE_NOT_FOUND',
                'message': 'ファイルが削除されました'
            }
        }), 404

    logger.info(f"ファイルプレビュー: {file_path_resolved}")
    return send_file(file_path_resolved)


@app.route('/result/<file_id>')
def result_page(file_id):
    """結果ページ"""
    # セキュリティ: ファイルIDの検証
    try:
        uuid.UUID(file_id)
    except (ValueError, AttributeError):
        return redirect(url_for('index'))
    
    file_info = load_file_metadata(file_id)
    if file_info is None:
        return redirect(url_for('index'))
    return render_template('result.html', file_id=file_id, file_info=file_info)


@app.route('/api/status/<file_id>')
def get_status(file_id):
    """ファイルのステータス確認"""
    # セキュリティ: ファイルIDの検証
    try:
        uuid.UUID(file_id)
    except (ValueError, AttributeError):
        return jsonify({
            'success': False,
            'error': {
                'code': 'INVALID_FILE_ID',
                'message': '無効なファイルIDです'
            }
        }), 400
    
    file_info = load_file_metadata(file_id)
    if file_info is None:
        return jsonify({
            'success': False,
            'error': {
                'code': 'FILE_NOT_FOUND',
                'message': 'ファイルが見つかりません'
            }
        }), 404
    return jsonify({
        'success': True,
        'file_id': file_id,
        'filename': file_info['filename'],
        'device_type': file_info['device_type'],
        'hostname': file_info['hostname'],
        'version': file_info['version'],
        'summary': file_info['summary']
    })


@app.errorhandler(413)
def request_entity_too_large(error):
    """ファイルサイズ超過エラー"""
    return jsonify({
        'success': False,
        'error': {
            'code': 'FILE_TOO_LARGE',
            'message': 'ファイルサイズが50MBを超えています'
        }
    }), 413


@app.errorhandler(404)
def not_found(error):
    """404エラー"""
    return render_template('error.html', error={
        'code': '404',
        'message': 'ページが見つかりません'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """500エラー"""
    return render_template('error.html', error={
        'code': '500',
        'message': 'サーバー内部エラーが発生しました'
    }), 500


# セキュリティヘッダーの追加
@app.after_request
def set_security_headers(response):
    """セキュリティヘッダーを設定"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    return response


if __name__ == '__main__':
    port = int(os.environ.get('FLASK_PORT', 8080))
    debug = os.environ.get('FLASK_ENV', 'production') == 'development'

    logger.info(f"サーバー起動: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug)

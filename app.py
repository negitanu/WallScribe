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
from typing import Optional, Dict, Any, List, Tuple, Union

from flask import (
    Flask, render_template, request, jsonify,
    send_file, redirect, url_for
)
from werkzeug.utils import secure_filename

from parsers.base import get_parser_for_content, detect_encoding
from parsers.cluster import parse_ha_cluster_from_contents
from models.cluster import ClusterConfig
from models.config import ConfigModel
from exporters.html import HTMLExporter
from exporters.pdf import PDFExporter
from exporters.excel import ExcelExporter

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

        # JSON読み込み中の部分書き込みを避けるため、テンポラリに書いてから置換する
        tmp_path = metadata_path.with_suffix(metadata_path.suffix + ".tmp")
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(metadata_copy, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, metadata_path)
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

def update_progress(file_id: str, percent: int, message: str, stage: str = "", extra: Optional[Dict[str, Any]] = None):
    """進捗情報をメタデータに書き込む（ワーカー間共有のためファイルに保存）"""
    try:
        percent = max(0, min(100, int(percent)))
    except Exception:
        percent = 0

    metadata = load_file_metadata(file_id) or {}
    metadata.update({
        "status": metadata.get("status", "processing"),
        "progress_percent": percent,
        "progress_message": str(message or ""),
        "progress_stage": str(stage or ""),
        "updated_at": datetime.now().isoformat(),
    })
    if extra:
        metadata.update(extra)
    if "created_at" not in metadata:
        metadata["created_at"] = datetime.now()
    save_file_metadata(file_id, metadata)

def _process_job(
    file_id: str,
    input_path: Path,
    original_filename: str,
    output_format: str,
    sections: Optional[List[str]],
    upload_folder: Path,
    output_path: Path,
    output_filename: str,
):
    """非同期でパース＆出力を実行し、進捗を更新する（単一ファイル用）"""
    _process_job_multi(
        file_id=file_id,
        input_paths=[input_path],
        original_filenames=[original_filename],
        output_format=output_format,
        sections=sections,
        upload_folder=upload_folder,
        output_path=output_path,
        output_filename=output_filename,
        ha_mode='single'
    )


def _process_job_multi(
    file_id: str,
    input_paths: List[Path],
    original_filenames: List[str],
    output_format: str,
    sections: Optional[List[str]],
    upload_folder: Path,
    output_path: Path,
    output_filename: str,
    ha_mode: str = 'auto',
):
    """非同期でパース＆出力を実行し、進捗を更新する（複数ファイル対応）"""
    try:
        update_progress(file_id, 5, "ファイルを受信しました", stage="received")

        # 各ファイルを読み込み
        contents: List[Tuple[str, str]] = []
        for i, (input_path, original_filename) in enumerate(zip(input_paths, original_filenames)):
            update_progress(
                file_id,
                10 + (i * 5),
                f"ファイル {i+1}/{len(input_paths)} を処理中...",
                stage="detect_encoding"
            )
            file_data = input_path.read_bytes()
            content, detected_encoding = detect_encoding(file_data)
            logger.info(f"検出されたエンコーディング ({original_filename}): {detected_encoding}")
            contents.append((original_filename, content))

        # HAモードに応じてパース
        config: Union[ConfigModel, ClusterConfig]

        if ha_mode == 'single' or (ha_mode == 'auto' and len(contents) == 1):
            # 単一ファイルモード
            update_progress(file_id, 25, "設定ファイルの形式を判別しています...", stage="detect_parser")
            filename, content = contents[0]
            parser = get_parser_for_content(content)
            if parser is None:
                update_progress(file_id, 100, "設定ファイルの形式を判別できませんでした", stage="error", extra={
                    "status": "error",
                    "error": {
                        "code": "UNSUPPORTED_FORMAT",
                        "message": "設定ファイルの形式を判別できません",
                        "details": "対応形式: .conf (FortiGate), .xml (Palo Alto)",
                    }
                })
                return

            update_progress(file_id, 35, "設定ファイルを解析しています...", stage="parsing")
            config = parser.parse_content(content, filename)
            if parser.errors:
                for error in parser.errors:
                    logger.warning(f"パースエラー: {error}")
        else:
            # HAクラスタモード
            update_progress(file_id, 25, f"HAクラスタ構成を解析中 ({len(contents)} ファイル)...", stage="detect_parser")
            cluster_config = parse_ha_cluster_from_contents(contents)

            if cluster_config.is_cluster:
                logger.info(f"HAクラスタを検出: グループID={cluster_config.cluster_info.group_id}")
                update_progress(file_id, 35, "HAクラスタ構成を解析しています...", stage="parsing")
            else:
                logger.info("HAクラスタ構成は検出されませんでした。最初のファイルを使用します。")
                update_progress(file_id, 35, "設定ファイルを解析しています...", stage="parsing")

            config = cluster_config

        update_progress(file_id, 70, "出力ファイルを生成しています...", stage="exporting")
        if output_format == 'html':
            exporter = HTMLExporter(config) if sections is None else HTMLExporter(config, sections=sections)
            exporter.export(str(output_path))
        elif output_format == 'pdf':
            exporter = PDFExporter(config) if sections is None else PDFExporter(config, sections=sections)
            exporter.export(str(output_path))
        elif output_format == 'excel':
            exporter = ExcelExporter(config) if sections is None else ExcelExporter(config, sections=sections)
            exporter.export(str(output_path))
        else:
            update_progress(file_id, 100, f"サポートされていない出力形式です: {output_format}", stage="error", extra={
                "status": "error",
                "error": {
                    "code": "UNSUPPORTED_FORMAT",
                    "message": f"サポートされていない出力形式です: {output_format}",
                    "details": "対応形式: html, pdf, excel",
                }
            })
            return

        update_progress(file_id, 95, "メタデータを保存しています...", stage="finalizing")
        summary = config.get_summary()
        normalized_path = str(output_path.resolve())
        metadata = {
            "filename": output_filename,
            "path": normalized_path,
            "device_type": summary["device_type"],
            "hostname": summary["hostname"],
            "version": summary["version"],
            "summary": summary,
            "is_cluster": summary.get("is_cluster", False),
            "created_at": datetime.now(),
            "status": "done",
            "progress_percent": 100,
            "progress_message": "パラメータシートを生成しました",
            "progress_stage": "done",
        }
        save_file_metadata(file_id, metadata)
        logger.info(f"生成完了(非同期): {output_filename} (ID: {file_id}, Path: {normalized_path})")

    except Exception as e:
        logger.error(f"非同期処理エラー: {e}", exc_info=True)
        is_production = os.environ.get('FLASK_ENV', 'production') == 'production'
        error_details = '詳細はログを確認してください' if is_production else str(e)
        update_progress(file_id, 100, "生成中にエラーが発生しました", stage="error", extra={
            "status": "error",
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "予期しないエラーが発生しました",
                "details": error_details,
            }
        })


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

        # ファイル内容読み込み（エンコーディング自動検出）
        file_data = file.read()
        content, detected_encoding = detect_encoding(file_data)
        logger.info(f"検出されたエンコーディング: {detected_encoding}")
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
        elif output_format == 'excel':
            output_filename = f"{Path(original_filename).stem}_param.xlsx"
            # パストラバーサル対策: パスの正規化と検証
            output_path = (upload_folder / f"{file_id}_{output_filename}").resolve()

            # アップロードフォルダ外への書き込みを防止
            if not str(output_path).startswith(str(upload_folder)):
                raise ValueError("Invalid file path detected")

            # sectionsがNoneの場合は全セクション、それ以外はリストを渡す
            if sections is None or not isinstance(sections, list):
                exporter = ExcelExporter(config)
            else:
                sections_list = [s for s in sections if isinstance(s, str)]
                exporter = ExcelExporter(config, sections=sections_list)
            exporter.export(str(output_path))
        else:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'UNSUPPORTED_FORMAT',
                    'message': f'サポートされていない出力形式です: {output_format}',
                    'details': '対応形式: html, pdf, excel'
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

    except UnicodeDecodeError as e:
        return jsonify({
            'success': False,
            'error': {
                'code': 'ENCODING_ERROR',
                'message': 'ファイルのエンコーディングを読み取れません',
                'details': '対応形式: UTF-8, UTF-8 BOM, Shift-JIS (CP932), Latin-1'
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

@app.route('/upload_async', methods=['POST'])
def upload_file_async():
    """ファイルアップロード・変換処理（非同期、複数ファイル対応）"""
    try:
        # 複数ファイル対応: config_files[] または config_file
        files = request.files.getlist('config_files[]')
        if not files or (len(files) == 1 and files[0].filename == ''):
            # 後方互換性: config_file もチェック
            if 'config_file' in request.files:
                file = request.files['config_file']
                if file.filename != '':
                    files = [file]

        if not files or all(f.filename == '' for f in files):
            return jsonify({
                'success': False,
                'error': {'code': 'NO_FILE', 'message': 'ファイルが選択されていません'}
            }), 400

        # 有効なファイルのみをフィルタリング
        valid_files = [f for f in files if f.filename and allowed_file(f.filename)]
        if not valid_files:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'UNSUPPORTED_FORMAT',
                    'message': 'サポートされていないファイル形式です',
                    'details': '対応形式: .conf (FortiGate), .xml (Palo Alto)'
                }
            }), 400

        output_format = request.form.get('output_format', 'html')
        ha_mode = request.form.get('ha_mode', 'auto')
        sections_json = request.form.get('sections', '[]')
        try:
            sections_list = json.loads(sections_json)
            sections = [s for s in sections_list if isinstance(s, str)] if isinstance(sections_list, list) else None
        except json.JSONDecodeError:
            sections = None

        file_id = str(uuid.uuid4())
        upload_folder = Path(app.config['UPLOAD_FOLDER']).resolve()
        upload_folder.mkdir(parents=True, exist_ok=True)

        # 入力ファイルを保存（リクエスト終了後も処理できるように）
        input_paths: List[Path] = []
        original_filenames: List[str] = []

        for i, file in enumerate(valid_files):
            original_filename = secure_filename(file.filename)
            original_filenames.append(original_filename)

            ext = get_file_extension(original_filename)
            input_path = (upload_folder / f"{file_id}_input_{i}{ext}").resolve()
            if not str(input_path).startswith(str(upload_folder)):
                raise ValueError("Invalid input file path detected")
            file.save(str(input_path))
            input_paths.append(input_path)

        # 出力ファイル名を決定（複数ファイルの場合はclusterを付ける）
        first_filename = original_filenames[0]
        base_name = Path(first_filename).stem
        if len(valid_files) > 1:
            base_name = f"{base_name}_cluster"

        if output_format == 'html':
            output_filename = f"{base_name}_param.html"
        elif output_format == 'pdf':
            output_filename = f"{base_name}_param.pdf"
        elif output_format == 'excel':
            output_filename = f"{base_name}_param.xlsx"
        else:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'UNSUPPORTED_FORMAT',
                    'message': f'サポートされていない出力形式です: {output_format}',
                    'details': '対応形式: html, pdf, excel'
                }
            }), 400

        output_path = (upload_folder / f"{file_id}_{output_filename}").resolve()
        if not str(output_path).startswith(str(upload_folder)):
            raise ValueError("Invalid output file path detected")

        # 初期メタデータ（進捗用）
        save_file_metadata(file_id, {
            "filename": output_filename,
            "path": str(output_path),
            "file_count": len(valid_files),
            "created_at": datetime.now(),
            "status": "processing",
            "progress_percent": 0,
            "progress_message": f"アップロードを受け付けました ({len(valid_files)} ファイル)",
            "progress_stage": "queued",
        })

        # 非同期処理開始
        t = threading.Thread(
            target=_process_job_multi,
            args=(file_id, input_paths, original_filenames, output_format, sections, upload_folder, output_path, output_filename, ha_mode),
            daemon=True
        )
        t.start()

        return jsonify({
            "success": True,
            "file_id": file_id,
            "file_count": len(valid_files),
            "progress_url": f"/api/progress/{file_id}",
            "result_url": f"/result/{file_id}",
        })

    except Exception as e:
        logger.error(f"非同期受付エラー: {e}", exc_info=True)
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

@app.route('/api/progress/<file_id>')
def get_progress(file_id):
    """生成中の進捗を取得（非同期用）"""
    try:
        uuid.UUID(file_id)
    except (ValueError, AttributeError):
        return jsonify({
            'success': False,
            'error': {'code': 'INVALID_FILE_ID', 'message': '無効なファイルIDです'}
        }), 400

    file_info = load_file_metadata(file_id)
    if file_info is None:
        return jsonify({
            'success': False,
            'error': {'code': 'FILE_NOT_FOUND', 'message': 'ファイルが見つかりません'}
        }), 404

    return jsonify({
        "success": True,
        "file_id": file_id,
        "status": file_info.get("status", "processing"),
        "progress": {
            "percent": file_info.get("progress_percent", 0),
            "message": file_info.get("progress_message", ""),
            "stage": file_info.get("progress_stage", ""),
        },
        "error": file_info.get("error"),
        "result_url": f"/result/{file_id}",
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

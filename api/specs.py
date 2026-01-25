#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Swagger 2.0 仕様定義（flasgger 用）
"""

# API仕様の基本情報
API_SPEC = {
    # NOTE: flasgger の Swagger UI は Swagger 2.0 を前提にしているため
    # openapi(3.x) と swagger(2.0) を混在させないこと
    "swagger": "2.0",
    "info": {
        "title": "WallScribe API",
        "description": "ファイアウォール設定ファイルからパラメータシートを生成するREST API",
        "version": "1.1.0",
        "contact": {
            "name": "WallScribe",
        },
    },
    # Swagger 2.0 形式のサーバ指定（必要最低限）
    "schemes": ["http", "https"],
    "basePath": "/",
    "tags": [
        {
            "name": "ファイル処理",
            "description": "設定ファイルのアップロードとパラメータシート生成"
        },
        {
            "name": "進捗・ステータス",
            "description": "処理の進捗状況とステータスの取得"
        },
        {
            "name": "ジョブ管理",
            "description": "生成ジョブの一覧・詳細・削除"
        },
        {
            "name": "ダウンロード",
            "description": "生成されたファイルのダウンロード"
        },
        {
            "name": "システム",
            "description": "システム情報とメトリクス"
        }
    ],
    # Swagger 2.0 のスキーマ定義は definitions を使用
    "definitions": {
        "Error": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean", "example": False},
                "error": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "example": "INTERNAL_ERROR"},
                        "message": {"type": "string", "example": "予期しないエラーが発生しました"},
                        "details": {"type": "string", "example": "詳細はログを確認してください"},
                    },
                },
            },
        },
        "UploadResponse": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean", "example": True},
                "file_id": {
                    "type": "string",
                    "format": "uuid",
                    "example": "550e8400-e29b-41d4-a716-446655440000",
                },
                "file_count": {"type": "integer", "example": 1},
                "progress_url": {
                    "type": "string",
                    "example": "/api/progress/550e8400-e29b-41d4-a716-446655440000",
                },
                "result_url": {"type": "string", "example": "/result/550e8400-e29b-41d4-a716-446655440000"},
            },
        },
        "ProgressResponse": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean", "example": True},
                "file_id": {"type": "string", "format": "uuid"},
                "status": {
                    "type": "string",
                    "enum": ["processing", "done", "error"],
                    "example": "processing",
                },
                "progress": {
                    "type": "object",
                    "properties": {
                        "percent": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 100,
                            "example": 45,
                        },
                        "message": {"type": "string", "example": "設定ファイルを解析しています..."},
                        "stage": {"type": "string", "example": "parsing"},
                    },
                },
                "error": {
                    "type": "object",
                    # Swagger 2.0 には nullable が無いので拡張で表現
                    "x-nullable": True,
                },
                "result_url": {"type": "string"},
            },
        },
        "StatusResponse": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean", "example": True},
                "file_id": {"type": "string", "format": "uuid"},
                "filename": {"type": "string", "example": "fortigate_param.html"},
                "device_type": {
                    "type": "string",
                    "enum": ["fortigate", "paloalto"],
                    "example": "fortigate",
                },
                "hostname": {"type": "string", "example": "FW-PRIMARY"},
                "version": {"type": "string", "example": "7.6.2"},
                "summary": {"type": "object"},
            },
        },
        "Job": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "format": "uuid"},
                "filename": {"type": "string"},
                "status": {"type": "string", "enum": ["processing", "done", "error"]},
                "created_at": {"type": "string", "example": "2026-01-25T09:38:31"},
                "file_count": {"type": "integer", "example": 1},
                "progress_percent": {"type": "integer", "example": 45},
                "progress_message": {"type": "string", "example": "設定ファイルを解析しています..."},
                "progress_stage": {"type": "string", "example": "parsing"},
                "device_type": {"type": "string", "example": "fortigate"},
                "hostname": {"type": "string", "example": "FW-PRIMARY"},
                "version": {"type": "string", "example": "7.6.2"},
                "result_url": {"type": "string", "example": "/result/550e8400-e29b-41d4-a716-446655440000"},
                "download_url": {"type": "string", "example": "/download/550e8400-e29b-41d4-a716-446655440000"},
                "preview_url": {"type": "string", "example": "/preview/550e8400-e29b-41d4-a716-446655440000"},
                "status_url": {"type": "string", "example": "/api/status/550e8400-e29b-41d4-a716-446655440000"},
                "progress_url": {"type": "string", "example": "/api/progress/550e8400-e29b-41d4-a716-446655440000"},
            },
        },
        "JobResponse": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean", "example": True},
                "job": {"$ref": "#/definitions/Job"},
            },
        },
        "JobsResponse": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean", "example": True},
                "jobs": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/Job"},
                },
            },
        },
        "DeleteJobResponse": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean", "example": True},
                "file_id": {"type": "string", "format": "uuid"},
                "deleted_files": {"type": "integer", "example": 3},
            },
        },
    },
}

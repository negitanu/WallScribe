#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenAPI仕様定義
"""

# API仕様の基本情報
API_SPEC = {
    "openapi": "3.0.0",
    "info": {
        "title": "WallScribe API",
        "description": "ファイアウォール設定ファイルからパラメータシートを生成するREST API",
        "version": "1.1.0",
        "contact": {
            "name": "WallScribe",
        },
    },
    "servers": [
        {
            "url": "http://localhost:8080",
            "description": "開発サーバー"
        },
        {
            "url": "https://api.example.com",
            "description": "本番サーバー"
        }
    ],
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
            "name": "ダウンロード",
            "description": "生成されたファイルのダウンロード"
        },
        {
            "name": "システム",
            "description": "システム情報とメトリクス"
        }
    ],
    "components": {
        "schemas": {
            "Error": {
                "type": "object",
                "properties": {
                    "success": {
                        "type": "boolean",
                        "example": False
                    },
                    "error": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "example": "INTERNAL_ERROR"
                            },
                            "message": {
                                "type": "string",
                                "example": "予期しないエラーが発生しました"
                            },
                            "details": {
                                "type": "string",
                                "example": "詳細はログを確認してください"
                            }
                        }
                    }
                }
            },
            "UploadResponse": {
                "type": "object",
                "properties": {
                    "success": {
                        "type": "boolean",
                        "example": True
                    },
                    "file_id": {
                        "type": "string",
                        "format": "uuid",
                        "example": "550e8400-e29b-41d4-a716-446655440000"
                    },
                    "file_count": {
                        "type": "integer",
                        "example": 1
                    },
                    "progress_url": {
                        "type": "string",
                        "example": "/api/progress/550e8400-e29b-41d4-a716-446655440000"
                    },
                    "result_url": {
                        "type": "string",
                        "example": "/result/550e8400-e29b-41d4-a716-446655440000"
                    }
                }
            },
            "ProgressResponse": {
                "type": "object",
                "properties": {
                    "success": {
                        "type": "boolean",
                        "example": True
                    },
                    "file_id": {
                        "type": "string",
                        "format": "uuid"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["processing", "done", "error"],
                        "example": "processing"
                    },
                    "progress": {
                        "type": "object",
                        "properties": {
                            "percent": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 100,
                                "example": 45
                            },
                            "message": {
                                "type": "string",
                                "example": "設定ファイルを解析しています..."
                            },
                            "stage": {
                                "type": "string",
                                "example": "parsing"
                            }
                        }
                    },
                    "error": {
                        "type": "object",
                        "nullable": True
                    },
                    "result_url": {
                        "type": "string"
                    }
                }
            },
            "StatusResponse": {
                "type": "object",
                "properties": {
                    "success": {
                        "type": "boolean",
                        "example": True
                    },
                    "file_id": {
                        "type": "string",
                        "format": "uuid"
                    },
                    "filename": {
                        "type": "string",
                        "example": "fortigate_param.html"
                    },
                    "device_type": {
                        "type": "string",
                        "enum": ["fortigate", "paloalto"],
                        "example": "fortigate"
                    },
                    "hostname": {
                        "type": "string",
                        "example": "FW-PRIMARY"
                    },
                    "version": {
                        "type": "string",
                        "example": "7.6.2"
                    },
                    "summary": {
                        "type": "object"
                    }
                }
            }
        }
    }
}

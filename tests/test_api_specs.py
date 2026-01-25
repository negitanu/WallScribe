#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API仕様のテスト
"""

import pytest
from api.specs import API_SPEC


class TestAPISpecs:
    """API仕様のテスト"""

    def test_api_spec_structure(self):
        """API仕様の構造確認"""
        assert 'openapi' in API_SPEC
        assert 'info' in API_SPEC
        assert 'servers' in API_SPEC
        assert 'tags' in API_SPEC
        assert 'components' in API_SPEC

    def test_api_info(self):
        """API情報の確認"""
        info = API_SPEC['info']
        assert 'title' in info
        assert 'version' in info
        assert 'description' in info
        assert info['title'] == 'WallScribe API'
        assert info['version'] == '1.1.0'

    def test_api_tags(self):
        """APIタグの確認"""
        tags = API_SPEC['tags']
        assert len(tags) > 0
        
        tag_names = [tag['name'] for tag in tags]
        assert 'ファイル処理' in tag_names
        assert '進捗・ステータス' in tag_names
        assert 'ダウンロード' in tag_names
        assert 'システム' in tag_names

    def test_api_schemas(self):
        """APIスキーマの確認"""
        schemas = API_SPEC['components']['schemas']
        assert 'Error' in schemas
        assert 'UploadResponse' in schemas
        assert 'ProgressResponse' in schemas
        assert 'StatusResponse' in schemas

    def test_error_schema(self):
        """エラースキーマの確認"""
        error_schema = API_SPEC['components']['schemas']['Error']
        assert 'type' in error_schema
        assert error_schema['type'] == 'object'
        assert 'properties' in error_schema
        assert 'error' in error_schema['properties']

    def test_upload_response_schema(self):
        """アップロードレスポンススキーマの確認"""
        upload_schema = API_SPEC['components']['schemas']['UploadResponse']
        assert 'properties' in upload_schema
        assert 'file_id' in upload_schema['properties']
        assert 'success' in upload_schema['properties']

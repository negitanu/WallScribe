#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
バリデーション機能のテスト
"""

from utils.validation import (
    validate_file_content,
    validate_file_size,
    validate_ha_mode,
    validate_output_format,
)


class TestValidateFileContent:
    """ファイル内容検証のテスト"""

    def test_fortigate_valid(self):
        """FortiGate設定ファイル（有効）のテスト"""
        content = b"#config-version=FGVM01-6.4.0-FW-build1234\nconfig system global"
        is_valid, error = validate_file_content(content, "test.conf")
        assert is_valid is True
        assert error is None

    def test_fortigate_valid_alternative(self):
        """FortiGate設定ファイル（代替形式）のテスト"""
        content = b"config system global\n    set hostname test"
        is_valid, error = validate_file_content(content, "test.conf")
        assert is_valid is True
        assert error is None

    def test_fortigate_invalid(self):
        """FortiGate設定ファイル（無効）のテスト"""
        content = b"This is not a FortiGate config file"
        is_valid, error = validate_file_content(content, "test.conf")
        assert is_valid is False
        assert error is not None
        assert "FortiGate" in error

    def test_paloalto_valid(self):
        """Palo Alto設定ファイル（有効）のテスト"""
        content = b'<?xml version="1.0"?><config><devices></devices></config>'
        is_valid, error = validate_file_content(content, "test.xml")
        assert is_valid is True
        assert error is None

    def test_paloalto_invalid(self):
        """Palo Alto設定ファイル（無効）のテスト"""
        content = b"This is not valid XML"
        is_valid, error = validate_file_content(content, "test.xml")
        assert is_valid is False
        assert error is not None
        assert "XML" in error

    def test_unsupported_format(self):
        """サポートされていない形式のテスト"""
        content = b"Some content"
        is_valid, error = validate_file_content(content, "test.txt")
        assert is_valid is False
        assert error is not None
        assert "サポートされていない" in error


class TestValidateFileSize:
    """ファイルサイズ検証のテスト"""

    def test_valid_size(self):
        """有効なサイズのテスト"""
        content = b"x" * 1000  # 1KB
        is_valid, error = validate_file_size(content, 1024 * 1024)  # 1MB
        assert is_valid is True
        assert error is None

    def test_invalid_size(self):
        """無効なサイズのテスト"""
        content = b"x" * (2 * 1024 * 1024)  # 2MB
        is_valid, error = validate_file_size(content, 1024 * 1024)  # 1MB
        assert is_valid is False
        assert error is not None
        assert "MB" in error


class TestValidateOutputFormat:
    """出力形式検証のテスト"""

    def test_valid_formats(self):
        """有効な出力形式のテスト"""
        for format_type in ["html", "pdf", "excel"]:
            is_valid, error = validate_output_format(format_type)
            assert is_valid is True, f"{format_type} should be valid"
            assert error is None

    def test_invalid_format(self):
        """無効な出力形式のテスト"""
        is_valid, error = validate_output_format("invalid")
        assert is_valid is False
        assert error is not None
        assert "無効な出力形式" in error


class TestValidateHaMode:
    """HAモード検証のテスト"""

    def test_valid_modes(self):
        """有効なHAモードのテスト"""
        for mode in ["auto", "single", "cluster"]:
            is_valid, error = validate_ha_mode(mode)
            assert is_valid is True, f"{mode} should be valid"
            assert error is None

    def test_invalid_mode(self):
        """無効なHAモードのテスト"""
        is_valid, error = validate_ha_mode("invalid")
        assert is_valid is False
        assert error is not None
        assert "無効なHAモード" in error

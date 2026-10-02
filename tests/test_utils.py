#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ユーティリティ関数のテスト
"""

from parsers.utils import get_nested, ip_to_cidr, parse_proposal, to_list


class TestIPToCIDR:
    """IPアドレスとサブネットマスクからCIDRへの変換テスト"""

    def test_ip_to_cidr_basic(self):
        """基本的なCIDR変換"""
        assert ip_to_cidr("192.168.1.0 255.255.255.0") == "192.168.1.0/24"
        assert ip_to_cidr("10.0.0.0 255.255.0.0") == "10.0.0.0/16"
        assert ip_to_cidr("172.16.0.0 255.240.0.0") == "172.16.0.0/12"

    def test_ip_to_cidr_host(self):
        """ホストアドレス（/32）"""
        assert ip_to_cidr("192.168.1.1 255.255.255.255") == "192.168.1.1/32"
        assert ip_to_cidr("10.0.0.10 255.255.255.255") == "10.0.0.10/32"

    def test_ip_to_cidr_already_cidr(self):
        """既にCIDR表記の場合"""
        assert ip_to_cidr("192.168.1.0/24") == "192.168.1.0/24"
        assert ip_to_cidr("10.0.0.0/16") == "10.0.0.0/16"
        assert ip_to_cidr("2001:db8::1/64") == "2001:db8::1/64"

    def test_ip_to_cidr_list(self):
        """リスト形式の入力"""
        assert ip_to_cidr(["192.168.1.0", "255.255.255.0"]) == "192.168.1.0/24"
        assert ip_to_cidr(["10.0.0.0", "255.255.0.0"]) == "10.0.0.0/16"
        assert ip_to_cidr(["2001:db8::1", "64"]) == "2001:db8::1/64"

    def test_ip_to_cidr_ipv6_prefixlen(self):
        """IPv6: address + prefixlen 形式"""
        assert ip_to_cidr("2001:db8::1 64") == "2001:db8::1/64"

    def test_ip_to_cidr_invalid(self):
        """無効な入力"""
        # 無効な形式の場合は元の値を返す
        result = ip_to_cidr("invalid")
        assert result == "invalid"

    def test_ip_to_cidr_empty(self):
        """空の入力"""
        assert ip_to_cidr("") == ""
        assert ip_to_cidr([]) == ""

    def test_ip_to_cidr_various_masks(self):
        """様々なサブネットマスク"""
        assert ip_to_cidr("192.168.1.0 255.255.255.128") == "192.168.1.0/25"
        assert ip_to_cidr("192.168.1.0 255.255.255.192") == "192.168.1.0/26"
        assert ip_to_cidr("192.168.1.0 255.255.255.224") == "192.168.1.0/27"
        assert ip_to_cidr("192.168.1.0 255.255.255.248") == "192.168.1.0/29"


class TestToList:
    """to_list関数のテスト"""

    def test_list_input(self):
        """リスト入力はそのまま返す"""
        assert to_list([1, 2, 3]) == [1, 2, 3]
        assert to_list(["a", "b"]) == ["a", "b"]

    def test_string_input(self):
        """文字列入力はリストに変換"""
        assert to_list("test") == ["test"]
        assert to_list("") == []

    def test_none_input(self):
        """None入力は空リスト"""
        assert to_list(None) == []

    def test_empty_string(self):
        """空文字列は空リスト"""
        assert to_list("") == []


class TestGetNested:
    """get_nested関数のテスト"""

    def test_simple_key(self):
        """単一キー"""
        data = {"key": "value"}
        assert get_nested(data, "key") == "value"

    def test_nested_keys(self):
        """ネストされたキー"""
        data = {"a": {"b": {"c": "value"}}}
        assert get_nested(data, "a", "b", "c") == "value"

    def test_nonexistent_key(self):
        """存在しないキー"""
        data = {"a": {"b": "value"}}
        assert get_nested(data, "a", "c") is None
        assert get_nested(data, "a", "c", default="default") == "default"

    def test_default_value(self):
        """デフォルト値の使用"""
        data = {}
        assert get_nested(data, "nonexistent", default="default") == "default"

    def test_partial_path(self):
        """部分的なパス"""
        data = {"a": {"b": "value"}}
        assert get_nested(data, "a") == {"b": "value"}


class TestParseProposal:
    """parse_proposal関数のテスト"""

    def test_simple_proposal(self):
        """単純なプロポーザル"""
        encryption, authentication = parse_proposal("aes256-sha256")
        assert encryption == "aes256"
        assert authentication == "sha256"

    def test_list_proposal(self):
        """リスト形式のプロポーザル"""
        encryption, authentication = parse_proposal(["aes256-sha256", "aes128-md5"])
        assert "aes256" in encryption or "aes128" in encryption

    def test_encryption_only(self):
        """暗号化のみ"""
        encryption, authentication = parse_proposal("aes256")
        assert encryption == "aes256"
        assert authentication == ""

    def test_empty_proposal(self):
        """空のプロポーザル"""
        encryption, authentication = parse_proposal("")
        assert encryption == ""
        assert authentication == ""


def test_metadata_read_survives_transient_replacement(tmp_path, monkeypatch):
    import builtins
    from pathlib import Path
    import utils.storage as storage

    monkeypatch.setattr(storage, "_UPLOAD_FOLDER", tmp_path)
    storage.save_file_metadata("temporary-job", {"status": "processing"})
    original = builtins.open
    attempts = []

    def intermittent(path, *args, **kwargs):
        if Path(path) == tmp_path / "temporary-job.meta.json" and not attempts:
            attempts.append(True)
            raise FileNotFoundError("transient bind-mount replacement")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", intermittent)
    assert storage.load_file_metadata("temporary-job")["status"] == "processing"

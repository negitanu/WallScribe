#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
パーサー共通ユーティリティ
FortiGate と Palo Alto パーサーで共通して使用する関数
"""

import csv
import os
import ipaddress
from typing import Any, Dict, List, Optional, Union

# アプリケーションIDマッピングのキャッシュ
_appid_cache: Optional[Dict[str, Dict[str, str]]] = None


def get_appid_mapping() -> Dict[str, Dict[str, str]]:
    """appid.csvからアプリケーションIDマッピングを取得

    Returns:
        Dict[str, Dict[str, str]]: app_id -> {app_name, category, risk, ...}
    """
    global _appid_cache
    if _appid_cache is not None:
        return _appid_cache

    _appid_cache = {}
    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "static", "data", "appid.csv"
    )

    if not os.path.exists(csv_path):
        return _appid_cache

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                app_id = row.get("app_id", "")
                if app_id:
                    _appid_cache[app_id] = {
                        "app_name": row.get("app_name", ""),
                        "category": row.get("category", ""),
                        "risk": row.get("risk", ""),
                        "description": row.get("description", ""),
                    }
    except (IOError, csv.Error):
        pass

    return _appid_cache


def get_app_name(app_id: str) -> str:
    """アプリケーションIDからアプリケーション名を取得

    Args:
        app_id: アプリケーションID

    Returns:
        str: アプリケーション名（見つからない場合はIDをそのまま返す）
    """
    mapping = get_appid_mapping()
    app_info = mapping.get(str(app_id))
    if app_info:
        return app_info.get("app_name", app_id)
    return str(app_id)


def get_app_info(app_id: str) -> Optional[Dict[str, str]]:
    """アプリケーションIDから詳細情報を取得

    Args:
        app_id: アプリケーションID

    Returns:
        Optional[Dict[str, str]]: アプリケーション情報（app_name, category, risk, description）
    """
    mapping = get_appid_mapping()
    return mapping.get(str(app_id))


def to_list(val: Any) -> List:
    """値をリストに変換

    Args:
        val: 変換する値

    Returns:
        List: リスト形式の値
    """
    if isinstance(val, list):
        return val
    elif val:
        return [val]
    return []


def ip_to_cidr(ip_subnet: Union[str, List]) -> str:
    """IPアドレスとサブネットマスクをCIDR表記に変換

    Args:
        ip_subnet: "192.168.1.1 255.255.255.0" 形式、またはリスト形式

    Returns:
        str: CIDR表記 (例: "192.168.1.1/24")
    """
    if isinstance(ip_subnet, list):
        ip_subnet = " ".join(str(x) for x in ip_subnet)

    ip_subnet = str(ip_subnet).strip()
    if not ip_subnet:
        return ""
    if "/" in ip_subnet:
        return ip_subnet

    parts = ip_subnet.strip().split()
    if len(parts) == 2:
        ip_address, subnet_mask = parts
        # IPv4/IPv6: "address prefixlen" 形式（例: "2001:db8::1 64" / "192.168.1.1 24"）
        if subnet_mask.isdigit():
            try:
                prefix_len = int(subnet_mask)
                if ":" in ip_address:
                    if 0 <= prefix_len <= 128:
                        return f"{ip_address}/{prefix_len}"
                else:
                    if 0 <= prefix_len <= 32:
                        return f"{ip_address}/{prefix_len}"
            except ValueError:
                pass

        # IPv6: "address netmask" 形式（例: "2001:db8::1 ffff:ffff:ffff:ffff::"）
        # FortiOS/PANでは通常prefixlenだが、入力揺れ対策として対応しておく
        if ":" in ip_address and ":" in subnet_mask:
            try:
                mask_int = int(ipaddress.IPv6Address(subnet_mask))
                ones = bin(mask_int).count("1")
                # 先頭から1が連続するマスクか検証
                expected = ((1 << ones) - 1) << (128 - ones) if ones > 0 else 0
                if mask_int == expected and 0 <= ones <= 128:
                    return f"{ip_address}/{ones}"
            except (ipaddress.AddressValueError, ValueError):
                pass

        try:
            octets = [int(x) for x in subnet_mask.split(".")]
            if len(octets) == 4:
                mask_int = (octets[0] << 24) | (octets[1] << 16) | (octets[2] << 8) | octets[3]
                cidr = bin(mask_int).count("1")
                return f"{ip_address}/{cidr}"
        except (ValueError, IndexError):
            pass
    return ip_subnet


def get_nested(data: Dict, *keys, default=None) -> Any:
    """ネストされた辞書から値を取得

    Args:
        data: 辞書データ
        *keys: 取得するキーのパス
        default: デフォルト値

    Returns:
        Any: 取得した値、またはデフォルト値
    """
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def parse_proposal(proposals: Union[str, List]) -> tuple:
    """暗号化/認証プロポーザルをパース

    Args:
        proposals: プロポーザル文字列またはリスト (例: "aes256-sha256")

    Returns:
        tuple: (encryption, authentication)
    """
    if isinstance(proposals, list):
        proposals = ", ".join(proposals)

    encryption = ""
    authentication = ""

    if proposals and "-" in proposals:
        proposal_parts = proposals.split("-")
        if len(proposal_parts) >= 2:
            encryption = proposal_parts[0]
            authentication = proposal_parts[1]
        elif len(proposal_parts) == 1:
            encryption = proposal_parts[0]
    elif proposals:
        encryption = proposals

    return encryption, authentication

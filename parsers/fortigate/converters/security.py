#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
セキュリティプロファイルコンバーター
"""

from typing import Dict

from models.config import (
    ConfigModel, SecurityProfile,
    AntivirusProfile, WebFilterProfile, AppControlProfile, AppControlEntry,
    IPSProfile, SSLInspectionProfile
)
from parsers.utils import get_nested, get_app_name, get_app_info


def convert_security_profiles(
    config_model: ConfigModel,
    parsed_config: Dict
) -> None:
    """セキュリティプロファイルを変換

    Args:
        config_model: 変換先のConfigModel
        parsed_config: パース済み設定データ
    """
    # Global profiles
    global_cfg = parsed_config.get("global", {})
    _add_profiles_from_config(config_model, global_cfg, "root")

    # VDOM profiles
    for vdom_name, vdom_cfg in parsed_config.get("vdom", {}).items():
        _add_profiles_from_config(config_model, vdom_cfg, vdom_name)


def _add_profiles_from_config(
    config_model: ConfigModel,
    config: Dict,
    vdom: str
) -> None:
    """プロファイルを追加"""
    _add_basic_profiles(config_model, config, vdom)
    _add_antivirus_profiles(config_model, config, vdom)
    _add_webfilter_profiles(config_model, config, vdom)
    _add_app_control_profiles(config_model, config, vdom)
    _add_ips_profiles(config_model, config, vdom)
    _add_ssl_inspection_profiles(config_model, config, vdom)


def _add_basic_profiles(
    config_model: ConfigModel,
    config: Dict,
    vdom: str
) -> None:
    """基本プロファイル一覧を追加"""
    profile_types = [
        ("antivirus profile", "antivirus"),
        ("webfilter profile", "webfilter"),
        ("ips sensor", "ips"),
        ("firewall ssl-ssh-profile", "ssl-inspection"),
        ("application list", "app-control"),
    ]

    for config_path, profile_type in profile_types:
        profiles = get_nested(config, config_path, default={})
        if isinstance(profiles, dict):
            for profile_name, profile_data in profiles.items():
                if isinstance(profile_data, dict):
                    profile = SecurityProfile(
                        name=profile_data.get("_name", profile_name),
                        profile_type=profile_type,
                        vdom=vdom,
                        description=profile_data.get("comment", "")
                    )
                    config_model.security_profiles.append(profile)


def _add_antivirus_profiles(
    config_model: ConfigModel,
    config: Dict,
    vdom: str
) -> None:
    """アンチウイルスプロファイル詳細を追加"""
    av_profiles = get_nested(config, "antivirus profile", default={})
    if isinstance(av_profiles, dict):
        for profile_name, profile_data in av_profiles.items():
            if isinstance(profile_data, dict):
                protocols = []
                for proto in ["http", "ftp", "imap", "pop3", "smtp", "mapi", "cifs", "ssh"]:
                    proto_config = profile_data.get(proto, {})
                    if isinstance(proto_config, dict):
                        if proto_config.get("options") or proto_config.get("av-scan") == "enable":
                            protocols.append(proto)

                av_profile = AntivirusProfile(
                    name=profile_data.get("_name", profile_name),
                    scan_mode=profile_data.get("scan-mode", ""),
                    protocols=protocols,
                    vdom=vdom
                )
                config_model.security_profiles_detail.antivirus.append(av_profile)


def _add_webfilter_profiles(
    config_model: ConfigModel,
    config: Dict,
    vdom: str
) -> None:
    """Webフィルタプロファイル詳細を追加"""
    wf_profiles = get_nested(config, "webfilter profile", default={})
    if isinstance(wf_profiles, dict):
        for profile_name, profile_data in wf_profiles.items():
            if isinstance(profile_data, dict):
                wf_profile = WebFilterProfile(
                    name=profile_data.get("_name", profile_name),
                    vdom=vdom
                )
                # FortiGuardカテゴリ設定
                ftgd_wf = profile_data.get("ftgd-wf", {})
                if isinstance(ftgd_wf, dict):
                    filters = ftgd_wf.get("filters", {})
                    if isinstance(filters, dict):
                        for cat_data in filters.values():
                            if isinstance(cat_data, dict):
                                cat = cat_data.get("category", "")
                                if cat:
                                    wf_profile.categories.append(str(cat))
                config_model.security_profiles_detail.webfilter.append(wf_profile)


def _add_app_control_profiles(
    config_model: ConfigModel,
    config: Dict,
    vdom: str
) -> None:
    """アプリケーションコントロールプロファイル詳細を追加"""
    app_profiles = get_nested(config, "application list", default={})
    if isinstance(app_profiles, dict):
        for profile_name, profile_data in app_profiles.items():
            if isinstance(profile_data, dict):
                categories = []
                applications = []
                entries = profile_data.get("entries", {})
                if isinstance(entries, dict):
                    for entry_data in entries.values():
                        if isinstance(entry_data, dict):
                            # カテゴリを取得
                            cat = entry_data.get("category", "")
                            if cat:
                                categories.append(str(cat))

                            # アプリケーションIDを取得してアプリケーション名に変換
                            action = entry_data.get("action", "")
                            app_ids = entry_data.get("application", "")
                            if app_ids:
                                # アプリケーションIDは空白区切りで複数指定される場合がある
                                app_id_list = str(app_ids).split()
                                for app_id in app_id_list:
                                    app_info = get_app_info(app_id)
                                    if app_info:
                                        entry = AppControlEntry(
                                            app_id=app_id,
                                            app_name=app_info.get("app_name", ""),
                                            category=app_info.get("category", ""),
                                            risk=app_info.get("risk", ""),
                                            action=action
                                        )
                                    else:
                                        entry = AppControlEntry(
                                            app_id=app_id,
                                            app_name=app_id,
                                            action=action
                                        )
                                    applications.append(entry)

                app_profile = AppControlProfile(
                    name=profile_data.get("_name", profile_name),
                    categories=categories,
                    applications=applications,
                    vdom=vdom
                )
                config_model.security_profiles_detail.app_control.append(app_profile)


def _add_ips_profiles(
    config_model: ConfigModel,
    config: Dict,
    vdom: str
) -> None:
    """IPSプロファイル詳細を追加"""
    ips_profiles = get_nested(config, "ips sensor", default={})
    if isinstance(ips_profiles, dict):
        for profile_name, profile_data in ips_profiles.items():
            if isinstance(profile_data, dict):
                signatures = []
                entries = profile_data.get("entries", {})
                if isinstance(entries, dict):
                    for entry_data in entries.values():
                        if isinstance(entry_data, dict):
                            rule = entry_data.get("rule", "")
                            if rule:
                                signatures.append(str(rule))

                ips_profile = IPSProfile(
                    name=profile_data.get("_name", profile_name),
                    signatures=signatures,
                    action=profile_data.get("action", ""),
                    vdom=vdom
                )
                config_model.security_profiles_detail.ips.append(ips_profile)


def _add_ssl_inspection_profiles(
    config_model: ConfigModel,
    config: Dict,
    vdom: str
) -> None:
    """SSLインスペクションプロファイル詳細を追加"""
    ssl_profiles = get_nested(config, "firewall ssl-ssh-profile", default={})
    if isinstance(ssl_profiles, dict):
        for profile_name, profile_data in ssl_profiles.items():
            if isinstance(profile_data, dict):
                mode = _detect_ssl_inspection_mode(profile_data)

                ssl_profile = SSLInspectionProfile(
                    name=profile_data.get("_name", profile_name),
                    enabled=True,
                    mode=mode,
                    vdom=vdom
                )
                config_model.security_profiles_detail.ssl_inspection.append(ssl_profile)


def _detect_ssl_inspection_mode(profile_data: Dict) -> str:
    """SSLインスペクションモードを検出"""
    mode = "certificate-inspection"  # デフォルト
    profile_name_str = profile_data.get("_name", "")

    # プロファイル名で判定
    if "deep-inspection" in profile_name_str.lower():
        return "deep-inspection"

    # SSL設定を確認
    ssl_data = profile_data.get("ssl", {})
    if isinstance(ssl_data, dict):
        if ssl_data.get("inspect-all") == "enable":
            return "deep-inspection"

    # 各プロトコルのstatusを確認
    protocols = ["https", "ftps", "imaps", "pop3s", "smtps", "dot", "ssh"]
    for protocol in protocols:
        protocol_config = profile_data.get(protocol, {})
        if isinstance(protocol_config, dict):
            status = protocol_config.get("status", "")
            if status == "deep-inspection":
                return "deep-inspection"

    return mode

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FortiGate設定ファイルパーサー
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from models.config import ConfigModel, DeviceType
from parsers.base import BaseConfigParser
from parsers.device_identification import format_fortigate_display_model
from parsers.textfsm_utils import run_textfsm

from .converters import (
    convert_bgp,
    convert_device_info,
    convert_dhcp,
    convert_ha,
    convert_interfaces,
    convert_local_in_policies,
    convert_logging,
    convert_nat,
    convert_objects,
    convert_ospf,
    convert_policies,
    convert_policy_routes,
    convert_routes,
    convert_security_profiles,
    convert_system_settings,
    convert_vpn,
)

logger = logging.getLogger(__name__)


class FortiGateParser(BaseConfigParser):
    """FortiGate設定ファイルパーサー"""

    def __init__(self):
        super().__init__()
        self.raw_config: Dict[str, Any] = {"header": {}, "global": [], "vdom": {}}
        self.parsed_config: Dict[str, Any] = {"header": {}, "global": {}, "vdom": {}}
        self.vdoms: List[str] = []

    @staticmethod
    def detect_file_type(file_path: str) -> bool:
        """ファイル形式を判定"""
        path = Path(file_path)
        return path.suffix.lower() == ".conf"

    @staticmethod
    def detect_content_type(content: str) -> bool:
        """ファイル内容から形式を判定"""
        return "#config-version=" in content or "config system global" in content

    def parse(self, file_path: str) -> ConfigModel:
        """設定ファイルをパース"""
        content = self.read_file(file_path)
        if content is None:
            return self.config_model

        self.config_model.source_file = file_path
        return self.parse_content(content, Path(file_path).name)

    def parse_content(self, content: str, filename: str = "") -> ConfigModel:
        """設定ファイルの内容をパース"""
        self.config_model = ConfigModel()
        self.config_model.source_file = filename
        self.config_model.device_info.device_type = DeviceType.FORTIGATE

        lines = content.splitlines()

        # Phase 1: 設定を分割
        self._separate_config(lines)

        # Phase 2: 各セクションをパース
        self._parse_header()
        self._parse_global_config()
        self._parse_vdom_configs()

        # Phase 3: データモデルに変換（コンバーター使用）
        self._convert_to_model()

        self.config_model.parse_errors = self.errors
        return self.config_model

    def _separate_config(self, lines: List[str]) -> None:
        """設定をglobalとvdomに分割"""
        global_flag = False
        vdom_flag = False
        vdom_name_flag = False
        no_vdom_flag = True
        vdom_name = ""

        for line in lines:
            stripped = line.strip()

            # ヘッダー情報
            if "#config-version=" in line:
                self._parse_header_line(line)
                continue

            if "config global" in stripped:
                global_flag = True
                continue
            elif no_vdom_flag and "config system global" in stripped:
                global_flag = True
                # 以降の行も global として処理する

            if "config vdom" in stripped:
                global_flag = False
                vdom_flag = True
                vdom_name_flag = True
                continue
            elif no_vdom_flag and "config system object-tagging" in stripped:
                global_flag = False
                vdom_flag = True
                self.raw_config["vdom"]["root"] = []
                vdom_name = "root"

            if "vdom-mode multi-vdom" in stripped:
                no_vdom_flag = False

            # 最小構成（config firewall policy だけ等）の場合、
            # 明示的な "config system global" が無くても global として扱う
            if (
                no_vdom_flag
                and (not global_flag)
                and (not vdom_flag)
                and stripped.startswith("config ")
            ):
                global_flag = True

            if global_flag:
                self.raw_config["global"].append(stripped)
                continue

            if vdom_flag:
                if "edit" in stripped and vdom_name_flag:
                    parts = stripped.split()
                    if len(parts) > 1:
                        vdom_name = parts[1].strip('"')
                        vdom_name_flag = False
                        self.raw_config["vdom"][vdom_name] = []
                        self.vdoms.append(vdom_name)
                        continue
                if vdom_name:
                    self.raw_config["vdom"][vdom_name].append(stripped)
                continue

        # 空行を削除
        self.raw_config["global"] = [l for l in self.raw_config["global"] if l]
        for vdom_name in self.raw_config["vdom"]:
            self.raw_config["vdom"][vdom_name] = [
                l for l in self.raw_config["vdom"][vdom_name] if l
            ]

    def _parse_header_line(self, line: str) -> None:
        """ヘッダー行をパース

        ヘッダー行の例:
        #config-version=FG33E1-7.4.8-FW-build2795-250523:opmode=0:vdom=1:user=admin
        #config-version=FGT60F-7.2.5-FW-build1517:opmode=0:vdom=0:user=admin
        """
        if "#config-version=" not in line:
            return

        rows = run_textfsm("fortigate/header_config_version.textfsm", line)
        if rows:
            row = rows[0]
            model_prefix = row.get("model_prefix", "")
            model_code = row.get("model_code", "")
            if model_prefix and model_code:
                self.raw_config["header"]["model"] = format_fortigate_display_model(model_code)
            if row.get("os_version"):
                self.raw_config["header"]["version"] = row["os_version"]
            if row.get("build"):
                self.raw_config["header"]["build"] = row["build"]
            if row.get("opmode"):
                self.raw_config["header"]["opmode"] = row["opmode"]
            if row.get("vdom"):
                self.raw_config["header"]["vdom_enabled"] = row["vdom"] == "1"

        if "model" not in self.raw_config["header"] and self.identification:
            if self.identification.model:
                self.raw_config["header"]["model"] = self.identification.model
            if self.identification.os_version:
                self.raw_config["header"]["version"] = self.identification.os_version

    def _parse_header(self) -> None:
        """ヘッダー情報をパース"""
        self.parsed_config["header"] = self.raw_config.get("header", {})

    def _parse_config_tree(
        self, config_lines: List[str], line_count: int = 0
    ) -> Tuple[Dict[str, Any], int]:
        """設定ツリーを再帰的にパース"""
        result: Dict[str, Any] = {}
        current_name: Optional[str] = None

        while line_count < len(config_lines):
            line = config_lines[line_count]
            line_count += 1

            if not line:
                continue

            parts = line.split(" ", 1)
            if not parts:
                continue

            command = parts[0]

            if command == "config":
                if len(parts) > 1:
                    config_name = parts[1]
                    result[config_name], line_count = self._parse_config_tree(
                        config_lines, line_count
                    )
                continue

            if command == "set":
                if len(parts) > 1:
                    set_parts = parts[1].split(" ", 1)
                    if set_parts:
                        name = set_parts[0]
                        value = set_parts[1] if len(set_parts) > 1 else ""
                        result[name] = self._parse_value(value)
                        current_name = name
                continue

            if command == "unset":
                if len(parts) > 1:
                    name = parts[1].split(" ")[0]
                    result[name] = "unset"
                    current_name = name
                continue

            if command == "edit":
                if len(parts) > 1:
                    edit_table = parts[1].strip('"')
                    sub_result, line_count = self._parse_config_tree(config_lines, line_count)
                    sub_result["_name"] = edit_table
                    if edit_table in result:
                        if not isinstance(result[edit_table], list):
                            result[edit_table] = [result[edit_table]]
                        result[edit_table].append(sub_result)
                    else:
                        result[edit_table] = sub_result
                continue

            if command in ("next", "end"):
                break

            # 継続行
            if current_name and current_name in result:
                if isinstance(result[current_name], str):
                    result[current_name] += line

        return result, line_count

    def _parse_value(self, value_str: str) -> Any:
        """値をパース"""
        if not value_str:
            return ""

        values = []
        current = ""
        in_quotes = False

        for char in value_str:
            if char == '"':
                in_quotes = not in_quotes
            elif char == " " and not in_quotes:
                if current:
                    values.append(current.strip('"'))
                    current = ""
            else:
                current += char

        if current:
            values.append(current.strip('"'))

        if len(values) == 0:
            return ""
        elif len(values) == 1:
            return values[0]
        else:
            return values

    def _parse_global_config(self) -> None:
        """グローバル設定をパース"""
        if self.raw_config["global"]:
            self.parsed_config["global"], _ = self._parse_config_tree(self.raw_config["global"])

    def _parse_vdom_configs(self) -> None:
        """VDOM設定をパース"""
        for vdom_name, vdom_lines in self.raw_config["vdom"].items():
            if vdom_lines:
                self.parsed_config["vdom"][vdom_name], _ = self._parse_config_tree(vdom_lines)

    def _convert_to_model(self) -> None:
        """パース結果をConfigModelに変換"""
        convert_device_info(self.config_model, self.parsed_config, self.vdoms)
        convert_system_settings(self.config_model, self.parsed_config)
        convert_interfaces(self.config_model, self.parsed_config)
        convert_routes(self.config_model, self.parsed_config)
        convert_ospf(self.config_model, self.parsed_config)
        convert_bgp(self.config_model, self.parsed_config)
        convert_policy_routes(self.config_model, self.parsed_config)
        convert_dhcp(self.config_model, self.parsed_config)
        convert_objects(self.config_model, self.parsed_config)
        convert_policies(self.config_model, self.parsed_config)
        convert_local_in_policies(self.config_model, self.parsed_config)
        convert_nat(self.config_model, self.parsed_config)
        convert_vpn(self.config_model, self.parsed_config)
        convert_security_profiles(self.config_model, self.parsed_config)
        convert_ha(self.config_model, self.parsed_config)
        convert_logging(self.config_model, self.parsed_config)

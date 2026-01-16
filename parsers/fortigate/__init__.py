#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FortiGate設定ファイルパーサー
"""

import re
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from parsers.base import BaseConfigParser
from models.config import ConfigModel, DeviceType

from .converters import (
    convert_device_info,
    convert_system_settings,
    convert_interfaces,
    convert_routes,
    convert_dhcp,
    convert_objects,
    convert_policies,
    convert_local_in_policies,
    convert_nat,
    convert_vpn,
    convert_security_profiles,
    convert_ha,
    convert_logging,
)

logger = logging.getLogger(__name__)


class FortiGateParser(BaseConfigParser):
    """FortiGate設定ファイルパーサー"""

    def __init__(self):
        super().__init__()
        self.raw_config: Dict[str, Any] = {
            "header": {},
            "global": [],
            "vdom": {}
        }
        self.parsed_config: Dict[str, Any] = {
            "header": {},
            "global": {},
            "vdom": {}
        }
        self.vdoms: List[str] = []

    @staticmethod
    def detect_file_type(file_path: str) -> bool:
        """ファイル形式を判定"""
        path = Path(file_path)
        return path.suffix.lower() == '.conf'

    @staticmethod
    def detect_content_type(content: str) -> bool:
        """ファイル内容から形式を判定"""
        return '#config-version=' in content or 'config system global' in content

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
        skip_flag = False
        global_flag = False
        vdom_flag = False
        vdom_name_flag = False
        no_vdom_flag = True
        vdom_name = ""

        for line in lines:
            stripped = line.strip()

            # ヘッダー情報
            if '#config-version=' in line:
                self._parse_header_line(line)
                skip_flag = True
                continue

            if 'config global' in stripped:
                global_flag = True
                skip_flag = False
                continue
            elif no_vdom_flag and 'config system global' in stripped:
                global_flag = True
                skip_flag = False

            if 'config vdom' in stripped:
                global_flag = False
                vdom_flag = True
                vdom_name_flag = True
                continue
            elif no_vdom_flag and 'config system object-tagging' in stripped:
                global_flag = False
                vdom_flag = True
                self.raw_config["vdom"]["root"] = []
                vdom_name = "root"

            if 'vdom-mode multi-vdom' in stripped:
                no_vdom_flag = False

            if skip_flag:
                continue

            if global_flag:
                self.raw_config["global"].append(stripped)
                continue

            if vdom_flag:
                if 'edit' in stripped and vdom_name_flag:
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
        """ヘッダー行をパース"""
        if '#config-version=' in line:
            match = re.search(r'FGT(\w+)-(\d+\.\d+\.\d+)-FW-build(\d+)', line)
            if match:
                self.raw_config["header"]["model"] = f"FortiGate-{match.group(1)}"
                self.raw_config["header"]["version"] = match.group(2)
                self.raw_config["header"]["build"] = match.group(3)

            if 'opmode=' in line:
                opmode_match = re.search(r'opmode=(\d+)', line)
                if opmode_match:
                    self.raw_config["header"]["opmode"] = opmode_match.group(1)

            if 'vdom=' in line:
                vdom_match = re.search(r':vdom=(\d+)', line)
                if vdom_match:
                    self.raw_config["header"]["vdom_enabled"] = vdom_match.group(1) == '1'

    def _parse_header(self) -> None:
        """ヘッダー情報をパース"""
        self.parsed_config["header"] = self.raw_config.get("header", {})

    def _parse_config_tree(self, config_lines: List[str], line_count: int = 0) -> Tuple[Dict[str, Any], int]:
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
                    result[config_name], line_count = self._parse_config_tree(config_lines, line_count)
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
            elif char == ' ' and not in_quotes:
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
        convert_dhcp(self.config_model, self.parsed_config)
        convert_objects(self.config_model, self.parsed_config)
        convert_policies(self.config_model, self.parsed_config)
        convert_local_in_policies(self.config_model, self.parsed_config)
        convert_nat(self.config_model, self.parsed_config)
        convert_vpn(self.config_model, self.parsed_config)
        convert_security_profiles(self.config_model, self.parsed_config)
        convert_ha(self.config_model, self.parsed_config)
        convert_logging(self.config_model, self.parsed_config)

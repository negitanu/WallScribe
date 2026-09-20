#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FortiGate設定ファイルパーサー
"""

import logging
import re
import shlex
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
        self.errors = []
        self.raw_config = {"header": {}, "global": [], "vdom": {}}
        self.parsed_config = {"header": {}, "global": {}, "vdom": {}}
        self.vdoms = []
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
        # Parse wrapper blocks with the same nesting rules as ordinary sections.
        pending = ""
        for line in lines:
            stripped = line.strip()
            if not pending and stripped.startswith("#"):
                if stripped.startswith("#config-version="):
                    self._parse_header_line(stripped)
                continue
            pending = pending + "\n" + line if pending else stripped
            try:
                shlex.split(pending)
            except ValueError:
                continue
            if pending.strip():
                self.raw_config["global"].append(pending.strip())
            pending = ""
        if pending:
            self.add_error("FortiGate設定に閉じていない引用符があります")

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
        else:
            # FortiOS 8.x 以降やVM系で config-version の細部が揺れても、
            # モデル/バージョン/VDOM有効化の基本情報は拾えるようにする。
            match = re.search(
                r"#config-version=(?P<model>[A-Z0-9]+)-(?P<version>\d+(?:\.\d+){1,3})-FW"
                r"(?:-build(?P<build>\d+))?.*",
                line,
            )
            if match:
                model_code = match.group("model")
                if model_code.startswith("FGT"):
                    model_code = model_code[3:]
                elif model_code.startswith("FG"):
                    model_code = model_code[2:]
                self.raw_config["header"]["model"] = format_fortigate_display_model(model_code)
                self.raw_config["header"]["version"] = match.group("version")
                if match.group("build"):
                    self.raw_config["header"]["build"] = match.group("build")

            opmode_match = re.search(r":opmode=(\d+)", line)
            if opmode_match:
                self.raw_config["header"]["opmode"] = opmode_match.group(1)
            vdom_match = re.search(r":vdom=(\d+)", line)
            if vdom_match:
                self.raw_config["header"]["vdom_enabled"] = vdom_match.group(1) == "1"

        if "model" not in self.raw_config["header"] and self.identification:
            if self.identification.model:
                self.raw_config["header"]["model"] = self.identification.model
            if self.identification.os_version:
                self.raw_config["header"]["version"] = self.identification.os_version

    def _parse_header(self) -> None:
        """ヘッダー情報をパース"""
        self.parsed_config["header"] = self.raw_config.get("header", {})

    def _parse_config_tree(
        self,
        config_lines: List[str],
        line_count: int = 0,
        terminator: Optional[str] = None,
        initial: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], int]:
        """設定ツリーを再帰的にパース"""
        result: Dict[str, Any] = initial if initial is not None else {}

        while line_count < len(config_lines):
            line = config_lines[line_count]
            line_count += 1

            if not line:
                continue

            parts = line.split(None, 1)
            if not parts:
                continue

            command = parts[0]

            if command == "config":
                if len(parts) > 1:
                    config_name = parts[1]
                    _, line_count = self._parse_config_tree(
                        config_lines, line_count, "end", result.setdefault(config_name, {})
                    )
                continue

            if command == "set":
                if len(parts) > 1:
                    set_parts = parts[1].split(None, 1)
                    if set_parts:
                        name = set_parts[0]
                        value = set_parts[1] if len(set_parts) > 1 else ""
                        result[name] = self._parse_value(value)
                continue

            if command == "unset":
                if len(parts) > 1:
                    name = parts[1].split(" ")[0]
                    result.pop(name, None)
                continue

            if command == "edit":
                if len(parts) > 1:
                    edit_table = str(self._parse_value(parts[1]))
                    sub_result, line_count = self._parse_config_tree(
                        config_lines, line_count, "next", result.setdefault(edit_table, {})
                    )
                    sub_result["_name"] = edit_table
                continue

            if command in ("append", "unselect") and len(parts) > 1:
                arguments = parts[1].split(None, 1)
                if len(arguments) != 2:
                    self.add_error("FortiGateリスト操作に値がありません")
                    continue
                key, raw_value = arguments
                existing = result.get(key, [])
                existing = existing if isinstance(existing, list) else [existing]
                values = self._parse_value(raw_value)
                values = values if isinstance(values, list) else [values]
                if command == "append":
                    result[key] = list(dict.fromkeys(existing + values))
                else:
                    result[key] = [value for value in existing if value not in values]
                continue

            if command in ("next", "end"):
                if command != terminator:
                    self.add_error(f"FortiGate設定のブロック終端が不正です: {command}")
                return result, line_count

            self.add_error(f"FortiGate設定の未対応コマンド ({line_count}行目)")

        if terminator:
            self.add_error(f"FortiGate設定のブロック終端がありません: {terminator}")
        return result, line_count

    def _parse_value(self, value_str: str) -> Any:
        """値をパース"""
        if not value_str:
            return ""

        try:
            values = shlex.split(value_str, comments=False)
        except ValueError:
            self.add_error("FortiGate設定の値を解析できません")
            return value_str
        return values[0] if len(values) == 1 else values if values else ""

    def _parse_global_config(self) -> None:
        """グローバル設定をパース"""
        if self.raw_config["global"]:
            tree, _ = self._parse_config_tree(self.raw_config["global"])
            global_config = tree.pop("global", {})
            vdom_config = tree.pop("vdom", {})
            tree.update(global_config)
            self.parsed_config["global"] = tree
            self.parsed_config["vdom"] = vdom_config
            self.vdoms = list(vdom_config)

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

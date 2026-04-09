#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Palo Alto Networks 設定の CLI set 形式（テキスト）を TextFSM で取り込む。
XML 本体は ElementTree のまま。parsers/paloalto.py から利用する。
"""

from __future__ import annotations

import re
from typing import Dict, Tuple

from models.config import AddressObject, ConfigModel

from .textfsm_utils import run_textfsm
from .utils import ip_to_cidr

# FortiGate の raw .conf と誤判定しないよう、先頭が PAN-OS らしい set パスであること
_SET_CLI_PROBE = re.compile(
    r"^set\s+(deviceconfig|mgt-config|network|vsys|shared|profiles|panorama)\s+",
)


def is_paloalto_set_cli_text(content: str) -> bool:
    """先頭付近に PAN-OS の set 設定らしい行があるか（軽量判定）。"""
    head = content[:65536]
    for line in head.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if _SET_CLI_PROBE.match(s):
            return True
    return False


def _strip_cli_token(name: str) -> str:
    n = (name or "").strip()
    if len(n) >= 2 and n[0] == '"' and n[-1] == '"':
        return n[1:-1]
    return n


def apply_set_cli_textfsm_to_model(config_model: ConfigModel, content: str) -> None:
    """set 形式テキストを paloalto/set_cli.textfsm でパースし、ConfigModel に反映する。"""
    rows = run_textfsm("paloalto/set_cli.textfsm", content)
    addr_by_key: Dict[Tuple[str, str], AddressObject] = {}

    for row in rows:
        hn = (row.get("hostname") or "").strip()
        if hn:
            config_model.device_info.hostname = hn

        name = _strip_cli_token(row.get("name") or "")
        ip_nm = (row.get("ip_netmask") or "").strip()
        ip_range = (row.get("ip_range") or "").strip()
        fqdn = (row.get("fqdn") or "").strip()
        if not name or not (ip_nm or ip_range or fqdn):
            continue

        vsys = (row.get("vsys") or "").strip()
        vdom = vsys if vsys else "shared"

        key = (vdom, name)
        if key not in addr_by_key:
            addr_by_key[key] = AddressObject(name=name, vdom=vdom)

        obj = addr_by_key[key]
        if ip_nm:
            obj.object_type = "subnet"
            obj.value = ip_to_cidr(ip_nm)
        elif ip_range:
            obj.object_type = "iprange"
            obj.value = ip_range
        elif fqdn:
            obj.object_type = "fqdn"
            obj.value = fqdn

    config_model.objects.addresses.extend(addr_by_key.values())

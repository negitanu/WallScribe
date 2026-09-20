#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Palo Alto Networks 設定の CLI set 形式を既知のスキーマに従って XML に変換する。
XML 本体は ElementTree のまま。parsers/paloalto.py から利用する。
"""

from __future__ import annotations

import re

from models.config import ConfigModel

# FortiGate の raw .conf と誤判定しないよう、先頭が PAN-OS らしい set パスであること
_SET_CLI_PROBE = re.compile(
    r"^set\s+(deviceconfig|mgt-config|network|vsys|shared|profiles|panorama|rulebase|address|address-group|service|service-group)\s+",
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


def apply_set_cli_textfsm_to_model(config_model: ConfigModel, content: str) -> None:
    """Compatibility adapter for callers of the original CLI helper."""
    from .paloalto import PaloAltoParser

    parsed = PaloAltoParser().parse_content(content, config_model.source_file)
    config_model.__dict__.update(parsed.__dict__)


def set_cli_to_xml(content: str):
    """Normalize supported set paths to XML, sharing the XML model conversion.

    Only known object/security-rule fields are accepted. Unsupported commands are
    reported by line number without leaking configuration values in diagnostics.
    """
    import shlex
    import xml.etree.ElementTree as ET

    root = ET.Element("config")
    device = ET.SubElement(ET.SubElement(root, "devices"), "entry", name="localhost.localdomain")
    errors = []

    def child(parent, tag, name=None):
        for element in parent.findall(tag):
            if name is None or element.get("name") == name:
                return element
        return ET.SubElement(parent, tag, {} if name is None else {"name": name})

    object_fields = {
        "address": {"ip-netmask", "ip-range", "fqdn", "description", "tag"},
        "address-group": {"static", "dynamic/filter", "description", "tag"},
        "service": {
            "protocol/tcp/port",
            "protocol/udp/port",
            "description",
            "tag",
        },
        "service-group": {"members", "description"},
    }
    rule_members = {
        "from",
        "to",
        "source",
        "destination",
        "service",
        "application",
        "source-user",
        "tag",
        "profile-setting/group",
    }
    rule_scalars = {
        "action",
        "disabled",
        "description",
        "schedule",
        "negate-source",
        "negate-destination",
        "log-start",
        "log-end",
        "log-setting",
    }
    profiles = {
        "virus",
        "spyware",
        "vulnerability",
        "url-filtering",
        "file-blocking",
        "wildfire-analysis",
        "data-filtering",
    }
    rule_members.update("profile-setting/profiles/" + name for name in profiles)

    for number, line in enumerate(content.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            tokens = shlex.split(line, comments=False)
            if not tokens or tokens.pop(0) != "set":
                raise ValueError
            scope = None
            if tokens[:1] == ["shared"]:
                tokens.pop(0)
                scope = child(root, "shared")
            elif tokens[:1] == ["vsys"]:
                tokens.pop(0)
                scope = child(child(device, "vsys"), "entry", tokens.pop(0))
            if tokens[:2] == ["deviceconfig", "system"] and scope is None:
                fields = {
                    "hostname",
                    "ip-address",
                    "netmask",
                    "timezone",
                    "dns-setting/servers/primary",
                    "dns-setting/servers/secondary",
                }
                target = child(child(device, "deviceconfig"), "system")
                tokens = tokens[2:]
                member_fields = set()
            else:
                if scope is None:
                    scope = child(child(device, "vsys"), "entry", "vsys1")
                if tokens[:3] == ["rulebase", "security", "rules"]:
                    target = scope
                    for tag in tokens[:3]:
                        target = child(target, tag)
                    target = child(target, "entry", tokens[3])
                    tokens = tokens[4:]
                    fields = rule_members | rule_scalars
                    member_fields = rule_members
                elif tokens and tokens[0] in object_fields:
                    kind = tokens[0]
                    target = child(child(scope, kind), "entry", tokens[1])
                    tokens = tokens[2:]
                    fields = object_fields[kind]
                    member_fields = {"static", "members", "tag"}
                else:
                    raise ValueError
            field = next(
                (
                    f
                    for f in sorted(fields, key=len, reverse=True)
                    if tokens[: len(f.split("/"))] == f.split("/")
                ),
                None,
            )
            if field is None:
                raise ValueError
            values = tokens[len(field.split("/")) :]
            if values[:1] == ["["]:
                if values[-1:] != ["]"]:
                    raise ValueError
                values = values[1:-1]
            if field == "ip-netmask" and len(values) == 2:
                values = [" ".join(values)]
            if not values or (field not in member_fields and len(values) != 1):
                raise ValueError
            for tag in field.split("/"):
                target = child(target, tag)
            if field in member_fields:
                existing = {m.text for m in target.findall("member")}
                for value in values:
                    if value not in existing:
                        ET.SubElement(target, "member").text = value
                        existing.add(value)
            else:
                target.text = values[0]
        except (ValueError, IndexError):
            errors.append(f"Palo Alto CLI {number}行目: 未対応のパスまたは不正な構文")
    return ET.tostring(root, encoding="unicode"), errors

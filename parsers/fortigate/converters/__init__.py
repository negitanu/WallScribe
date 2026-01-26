#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FortiGate設定コンバーター
パース結果をConfigModelに変換するモジュール群
"""

from .device import convert_device_info, convert_system_settings
from .misc import convert_ha, convert_logging
from .network import (
    convert_bgp,
    convert_dhcp,
    convert_interfaces,
    convert_ospf,
    convert_policy_routes,
    convert_routes,
)
from .objects import convert_objects
from .policies import convert_local_in_policies, convert_nat, convert_policies
from .security import convert_security_profiles
from .vpn import convert_vpn

__all__ = [
    "convert_device_info",
    "convert_system_settings",
    "convert_interfaces",
    "convert_routes",
    "convert_dhcp",
    "convert_ospf",
    "convert_bgp",
    "convert_policy_routes",
    "convert_objects",
    "convert_policies",
    "convert_local_in_policies",
    "convert_nat",
    "convert_vpn",
    "convert_security_profiles",
    "convert_ha",
    "convert_logging",
]

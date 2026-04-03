#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
機器識別とTextFSMユーティリティのテスト
"""

from models.config import DeviceType
from parsers.base import get_parser_for_content
from parsers.device_identification import identify_device
from parsers.textfsm_utils import run_textfsm


def test_identify_fortigate(sample_fortigate_config):
    result = identify_device(sample_fortigate_config)
    assert result is not None
    assert result.device_type == DeviceType.FORTIGATE
    assert result.model == "FortiGate 60F"
    assert result.os_version == "7.2.5"


def test_identify_paloalto(sample_paloalto_config):
    result = identify_device(sample_paloalto_config)
    assert result is not None
    assert result.device_type == DeviceType.PALOALTO
    assert result.model == "PA Series"
    assert result.os_version == "10.2.0"


def test_identify_paloalto_set_cli(sample_paloalto_cli_set):
    result = identify_device(sample_paloalto_cli_set)
    assert result is not None
    assert result.device_type == DeviceType.PALOALTO
    assert result.model == "PA Series"


def test_get_parser_for_file_content_fallback(tmp_path, sample_paloalto_cli_set):
    from parsers.base import get_parser_for_file

    p = tmp_path / "unknown.txt"
    p.write_text(sample_paloalto_cli_set, encoding="utf-8")
    parser = get_parser_for_file(str(p))
    assert parser is not None
    assert parser.identification is not None
    assert parser.identification.device_type == DeviceType.PALOALTO


def test_run_textfsm_template_not_found():
    rows = run_textfsm("identify/not_found.textfsm", "dummy")
    assert rows == []


def test_get_parser_with_identification(sample_fortigate_config):
    parser = get_parser_for_content(sample_fortigate_config)
    assert parser is not None
    assert parser.identification is not None
    assert parser.identification.device_type == DeviceType.FORTIGATE

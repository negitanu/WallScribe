"""Cross-VDOM graph evidence, safe map rendering, and offline path behavior."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from analyzers.topology import infer_topology
from exporters.html import HTMLExporter
from models.config import ConfigModel, Interface
from parsers.fortigate import FortiGateParser

VDOM_CONFIG = """#config-version=FGT60F-7.2.10-FW-build0000-000000:opmode=0:vdom=1:user=admin
config global
 config system global
  set hostname FW-VDOM-DEMO
 end
 config system vdom-link
  edit transit
   set type ethernet
  next
 end
 config system interface
  edit lan
   set vdom branch
   set ip 192.0.2.1 255.255.255.0
  next
  edit transit0
   set vdom branch
   set type vdom-link
   set ip 10.255.0.1 255.255.255.252
  next
  edit transit1
   set vdom root
   set type vdom-link
   set ip 10.255.0.2 255.255.255.252
  next
  edit wan
   set vdom root
   set ip 198.51.100.1 255.255.255.0
  next
 end
end
config vdom
 edit branch
  config router static
   edit 1
    set dst 0.0.0.0 0.0.0.0
    set gateway 10.255.0.2
    set device transit0
   next
  end
  config firewall policy
   edit 1
    set name branch-to-root
    set srcintf lan
    set dstintf transit0
    set srcaddr all
    set dstaddr all
    set service ALL
    set action accept
    set status enable
    set schedule always
    set nat disable
    set logtraffic all
   next
  end
 next
 edit root
  config router static
   edit 1
    set dst 0.0.0.0 0.0.0.0
    set gateway 198.51.100.254
    set device wan
   next
  end
  config firewall policy
   edit 2
    set name root-to-wan
    set srcintf transit1
    set dstintf wan
    set srcaddr all
    set dstaddr all
    set service ALL
    set action accept
    set status enable
    set schedule always
    set nat enable
    set logtraffic all
   next
  end
 next
end
"""


def map_data(config):
    html = HTMLExporter(config, sections=["topology"]).export()
    return json.loads(html.split('class="map-data">', 1)[1].split("</script>", 1)[0])


def test_declared_pair_and_route_interface_evidence():
    config = FortiGateParser().parse_content(VDOM_CONFIG)
    assert not any("/ _name" in path for path in config.unsupported_sections)
    graph = infer_topology(config)
    links = [e for e in graph.edges if e.relation == "VDOM 間リンク"]
    assert len(links) == 1 and links[0].confidence == "configured"
    nodes = {n.id: n for n in graph.nodes}
    assert {nodes[links[0].source].scope, nodes[links[0].target].scope} == {"root", "branch"}
    assert "system vdom-link" in links[0].evidence
    assert all(
        nodes[e.source].kind == "interface" for e in graph.edges if e.relation == "設定ルート"
    )


def test_similar_names_and_same_subnet_do_not_invent_connection():
    config = ConfigModel(
        interfaces=[
            Interface(name="random0", vdom="a", ip_address="10.1.0.1/24"),
            Interface(name="random1", vdom="b", ip_address="10.1.0.2/24"),
        ]
    )
    assert not any(e.relation == "VDOM 間リンク" for e in infer_topology(config).edges)


def test_missing_peer_and_unknown_scope_are_not_linked():
    config = FortiGateParser().parse_content(VDOM_CONFIG)
    config.interfaces = [i for i in config.interfaces if i.name != "transit1"]
    assert not any(e.relation == "VDOM 間リンク" for e in infer_topology(config).edges)


@pytest.mark.parametrize("down, expected", [(False, ["branch", "root"]), (True, None)])
def test_offline_path_uses_only_active_configured_pairs(down, expected):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")
    config = FortiGateParser().parse_content(VDOM_CONFIG)
    if down:
        next(i for i in config.interfaces if i.name == "transit0").status = "down"
    program = "const {scopePath}=require(process.argv[1]);console.log(JSON.stringify(scopePath(JSON.parse(process.argv[2]),'branch','root')));"
    result = json.loads(
        subprocess.check_output(
            [
                node,
                "-e",
                program,
                str(Path("static/js/network_map.js").resolve()),
                json.dumps(map_data(config)),
            ],
            text=True,
        )
    )
    assert (result["scopes"] if result else None) == expected


def test_map_is_single_svg_safe_offline_and_pdf_has_no_controls():
    config = FortiGateParser().parse_content(VDOM_CONFIG)
    config.interfaces[0].description = "</script><script>alert(1)</script>"
    html = HTMLExporter(config, sections=["topology"]).export()
    assert html.count("<svg ") == 1
    assert "区画間の動作を確認" in html
    assert "\\u003c/script\\u003e" in html
    assert 'src="http' not in html
    pdf = HTMLExporter(config, sections=["topology"], for_pdf=True).export()
    assert pdf.count("<svg ") == 1
    assert "map-trace" not in pdf and "<script" not in pdf
    assert "map-node.device rect" in pdf


def test_npu_vlan_pairs_preserve_vlan_id_and_do_not_pair_different_tags():
    source = """config system interface
 edit npu0_vlink0
  set vdom root
 next
 edit npu0_vlink1
  set vdom root
 next
 edit engineering
  set vdom engineering
  set interface npu0_vlink0
  set vlanid 100
 next
 edit marketing
  set vdom marketing
  set interface npu0_vlink1
  set vlanid 100
 next
 edit other
  set vdom other
  set interface npu0_vlink1
  set vlanid 200
 next
end"""
    c = FortiGateParser().parse_content(source)
    interfaces = {i.name: i for i in c.interfaces}
    assert interfaces["engineering"].vdom_link_peer == "marketing"
    assert not interfaces["other"].vdom_link_peer
    links = [e for e in infer_topology(c).edges if e.relation == "VDOM 間リンク"]
    assert len(links) == 1
    assert "100" in links[0].evidence


def test_offline_path_crosses_intermediate_vdom_and_handles_cycles():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")
    data = {
        "nodes": [{"id": s, "scope": s} for s in ["a", "b", "c"]],
        "edges": [
            {"id": "ab", "source": "a", "target": "b", "relation": "VDOM 間リンク", "active": True},
            {"id": "bc", "source": "b", "target": "c", "relation": "VDOM 間リンク", "active": True},
            {"id": "bad", "source": "a", "target": "c", "relation": "IP から推定", "active": True},
        ],
    }
    program = "const {scopePath}=require(process.argv[1]);const d=JSON.parse(process.argv[2]);console.log(JSON.stringify([scopePath(d,'a','c'),scopePath(d,'a','missing'),scopePath(d,'a','a')]));"
    result = json.loads(
        subprocess.check_output(
            [
                node,
                "-e",
                program,
                str(Path("static/js/network_map.js").resolve()),
                json.dumps(data),
            ],
            text=True,
        )
    )
    assert result[0]["scopes"] == ["a", "b", "c"]
    assert result[1] is None
    assert result[2]["scopes"] == ["a"]


def test_same_interface_name_across_scopes_does_not_misattach_routes():
    from models.config import Route

    c = ConfigModel(
        interfaces=[
            Interface(name="ethernet1/1", vdom="a"),
            Interface(name="ethernet1/1", vdom="b"),
        ],
        routes=[Route(name="r", vdom="a", interface="ethernet1/1", destination="0.0.0.0/0")],
    )
    graph = infer_topology(c)
    nodes = {n.id: n for n in graph.nodes}
    edge = next(e for e in graph.edges if e.relation == "設定ルート")
    assert nodes[edge.source].scope == "a"


def test_connection_layout_contains_every_node_without_overlaps():
    from exporters.network_layout import layout_topology
    from models.config import Route

    c = ConfigModel()
    c.interfaces = [Interface(name=f"port{i}", ip_address=f"192.0.{i}.1/24") for i in range(16)]
    c.routes = [Route(destination=f"198.51.{i}.0/24", interface=f"port{i}") for i in range(16)]
    topology = infer_topology(c)
    positions, bounds, width, height = layout_topology(topology)
    assert len(positions) == len(topology.nodes)
    assert layout_topology(topology) == (positions, bounds, width, height)
    for node in topology.nodes:
        x, y, w, h = positions[node.id]
        bx, by, bw, bh = bounds[node.scope]
        assert bx <= x and by + 60 <= y and x + w <= bx + bw and y + h <= by + bh
    rectangles = list(positions.values())
    for index, (x, y, w, h) in enumerate(rectangles):
        for nx, ny, nw, nh in rectangles[index + 1 :]:
            assert x + w <= nx or nx + nw <= x or y + h <= ny or ny + nh <= y


def test_connection_layout_fans_out_interfaces_below_device():
    from exporters.network_layout import layout_topology

    c = FortiGateParser().parse_content(VDOM_CONFIG)
    topology = infer_topology(c)
    positions, bounds, _, _ = layout_topology(topology)
    for scope in bounds:
        device = next(n for n in topology.nodes if n.scope == scope and n.kind == "device")
        interfaces = [n for n in topology.nodes if n.scope == scope and n.kind == "interface"]
        assert len({positions[n.id][0] for n in interfaces}) > 1
        assert all(positions[n.id][1] > positions[device.id][1] for n in interfaces)
    assert bounds["branch"][1] != bounds["root"][1]


def run_policy_flow(config, index=0):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")
    return json.loads(
        subprocess.check_output(
            [
                node,
                "-e",
                "const {policyFlow}=require(process.argv[1]); console.log(JSON.stringify(policyFlow(JSON.parse(process.argv[2]),Number(process.argv[3]))));",
                str(Path("static/js/network_map.js").resolve()),
                json.dumps(map_data(config)),
                str(index),
            ],
            text=True,
        )
    )


def test_policy_animation_scope_and_direction_are_configuration_based():
    config = FortiGateParser().parse_content(VDOM_CONFIG)
    flow = run_policy_flow(config)
    graph = {n["id"]: n for n in map_data(config)["nodes"]}
    assert [graph[s["from"]]["label"] for s in flow["segments"]] == ["lan", "FW-VDOM-DEMO"]
    assert [graph[s["to"]]["label"] for s in flow["segments"]] == ["FW-VDOM-DEMO", "transit0"]
    assert [s["stage"] for s in flow["segments"]] == [0, 1]
    assert all(graph[s["from"]]["scope"] == "branch" for s in flow["segments"])
    assert flow["segments"][1]["reverse"] is True


def test_disabled_deny_unknown_policy_and_interface_do_not_animate_success():
    from models.config import PolicyAction

    config = FortiGateParser().parse_content(VDOM_CONFIG)
    policy = config.firewall_policies[0]
    policy.enabled = False
    assert run_policy_flow(config)["segments"] == []
    policy.enabled = True
    for action in (PolicyAction.DENY, PolicyAction.DROP, PolicyAction.UNKNOWN):
        policy.action = action
        assert all(s["stage"] == 0 for s in run_policy_flow(config)["segments"])
    policy.action = PolicyAction.ALLOW
    next(i for i in config.interfaces if i.name == "transit0").status = "down"
    flow = run_policy_flow(config)
    assert not flow["destinations"]
    assert "特定できません" in flow["reason"]
    assert all(s["stage"] == 0 for s in flow["segments"])


def test_policy_zone_wildcard_and_unknown_names_are_not_cross_scope_guesses():
    config = FortiGateParser().parse_content(VDOM_CONFIG)
    next(i for i in config.interfaces if i.name == "lan").zone = "trust"
    policy = config.firewall_policies[0]
    policy.source_interface = ["trust"]
    assert len(run_policy_flow(config)["sources"]) == 1
    policy.destination_interface = ["any"]
    assert len(run_policy_flow(config)["destinations"]) == 2
    policy.source_interface = ["nonexistent"]
    assert not run_policy_flow(config)["sources"]
    assert not run_policy_flow(config)["segments"]


def test_map_has_separate_inspectors_disabled_control_and_motion_export_cleanup():
    html = HTMLExporter(
        FortiGateParser().parse_content(VDOM_CONFIG), sections=["topology"]
    ).export()
    assert (
        html.index('class="map-inspector map-device-panel"')
        < html.index('class="map-viewport"')
        < html.index('class="map-policy-panel map-inspector"')
    )
    assert "data-map-hide-disabled" in html
    assert "prefers-reduced-motion" in html
    assert "repeatCount', '3'" in html
    assert "clone.querySelectorAll('.map-packet-layer')" in html

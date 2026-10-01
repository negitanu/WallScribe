"""Adversarial lab regression, bounded load, and parser provenance tests."""

import io
import json
import time
from copy import deepcopy

import pytest

from analyzers.network import investigate_flow
from analyzers.topology import infer_topology
from exporters.html import HTMLExporter
from models.config import (
    ApplicationDefinition,
    ConfigModel,
    DeviceType,
    FirewallPolicy,
    Interface,
    PolicyAction,
    Route,
    ServiceObject,
    VirtualRouter,
)
from parsers.fortigate import FortiGateParser
from parsers.paloalto import PaloAltoParser
from services.lab import feeds
from services.lab.engine import generate_cases, route_path, run_case
from services.lab.validation import catalogs, validate_cases

PAN = """<config version="10.0.0"><shared><application><entry name="custom-web"><default><port><member>tcp/8443</member></port></default></entry></application><application-group><entry name="web-group"><members><member>custom-web</member></members></entry></application-group></shared><devices><entry name="localhost.localdomain"><network><interface><ethernet><entry name="ethernet1/1"><layer3><ip><entry name="192.0.2.1/24"/></ip></layer3></entry><entry name="ethernet1/2"><layer3><ip><entry name="198.51.100.1/24"/></ip></layer3></entry></ethernet></interface><virtual-router><entry name="VR-A"><interface><member>ethernet1/1</member></interface><routing-table><ip><static-route><entry name="to-B"><destination>198.51.100.0/24</destination><nexthop><next-vr>VR-B</next-vr></nexthop></entry></static-route></ip><ipv6><static-route><entry name="v6"><destination>2001:db8::/32</destination><nexthop><discard/></nexthop></entry></static-route></ipv6></routing-table></entry><entry name="VR-B"><interface><member>ethernet1/2</member></interface></entry></virtual-router></network><vsys><entry name="vsys1"><visible-vsys><member>vsys2</member></visible-vsys><import><network><interface><member>ethernet1/1</member></interface><virtual-router><member>VR-A</member></virtual-router></network></import><zone><entry name="trust"><network><layer3><member>ethernet1/1</member></layer3></network></entry><entry name="to-vsys2"><network><external><member>vsys2</member></external></network></entry></zone><rulebase><security><rules><entry name="app-web"><from><member>trust</member></from><to><member>to-vsys2</member></to><source><member>any</member></source><destination><member>any</member></destination><service><member>application-default</member></service><application><member>web-group</member></application><action>allow</action><disabled>no</disabled><log-start>no</log-start><log-end>yes</log-end></entry></rules></security></rulebase></entry><entry name="vsys2"><visible-vsys><member>vsys1</member></visible-vsys><zone><entry name="untrust"><network><layer3><member>ethernet1/2</member></layer3></network></entry><entry name="from-vsys1"><network><external><member>vsys1</member></external></network></entry></zone></entry></vsys></entry></devices></config>"""


def model():
    c = ConfigModel()
    c.device_info.device_type = DeviceType.FORTIGATE
    c.device_info.vdom_list = ["root"]
    c.interfaces = [
        Interface(name="lan", ip_address="192.0.2.1/24"),
        Interface(name="wan", ip_address="198.51.100.1/24"),
    ]
    c.firewall_policies = [
        FirewallPolicy(
            policy_id="1",
            name="web",
            source_interface=["lan"],
            destination_interface=["wan"],
            source_address=["all"],
            destination_address=["all"],
            service=["HTTPS"],
            action=PolicyAction.ALLOW,
        )
    ]
    c.objects.services = [ServiceObject(name="HTTPS", protocol="TCP", port="443")]
    c.routes = [
        Route(
            name="default",
            destination="0.0.0.0/0",
            interface="wan",
            gateway="198.51.100.254",
            distance="10",
        )
    ]
    return c


def case(c=None):
    return generate_cases(c or model())[0]


def test_pan_vsys_vr_app_groups_ipv6_and_graph():
    c = PaloAltoParser().parse_content(PAN)
    assert [i.routing_context for i in c.interfaces] == ["VR-A", "VR-B"]
    assert [i.vdom for i in c.interfaces] == ["vsys1", "vsys2"]
    assert all(i.vdom_assignment_known for i in c.interfaces)
    assert c.virtual_routers[0].vsys == ["vsys1"]
    assert c.routes[1].destination == "2001:db8::/32"
    graph = infer_topology(c)
    assert any(n.kind == "router" and n.label == "VR-A" for n in graph.nodes)
    assert sum(e.relation == "vsys 間接続" for e in graph.edges) == 2
    assert any(e.relation == "next-vr" and e.directed for e in graph.edges)
    assert not c.unsupported_sections
    html = HTMLExporter(c, sections=["topology"]).export()
    assert "VR-A" in html and html.count("<svg ") == 1
    q = dict(
        source="192.0.2.10",
        destination="198.51.100.10",
        scope="vsys1",
        source_interface="trust",
        destination_interface="to-vsys2",
        application="custom-web",
    )
    found = investigate_flow(c, port=8443, **q)
    assert found["policies"][0]["status"] == "static_match"
    mismatch = investigate_flow(c, port=443, include_excluded=True, **q)
    assert not mismatch["policies"] and "サービスが不一致" in mismatch["excluded"][0]["mismatches"]
    path = route_path(c, q | {"routing_context": "VR-A"})
    assert path["steps"][0]["route_type"] == "next-vr"
    assert path["status"] == "unknown"  # cross-vsys policy check cannot be skipped
    c.vsys_connections[0].visible = False
    assert sum(e.relation == "vsys 間接続" for e in infer_topology(c).edges) == 1


def test_isdb_src_negation_and_unknown_snapshot():
    content = """#config-version=FGT60F-7.2.10-FW-build1
config firewall policy
edit 1
set srcintf "any"
set dstintf "any"
set srcaddr "all"
set internet-service enable
set internet-service-id 12345
set internet-service-src enable
set internet-service-src-name "Source-Service"
set internet-service-src-negate enable
set schedule "always"
set action accept
set status enable
set logtraffic all
set nat disable
next
end
"""
    c = FortiGateParser().parse_content(content)
    p = c.firewall_policies[0]
    assert p.internet_service_source_name == ["Source-Service"] and p.internet_service_source_negate
    db = {
        "12345": [{"network": "198.51.100.0/24", "ports": ["tcp/443"]}],
        "Source-Service": [{"network": "203.0.113.0/24", "ports": ["tcp/443"]}],
    }
    assert (
        investigate_flow(c, "192.0.2.10", "198.51.100.2", internet_services=db)["policies"][0][
            "status"
        ]
        == "static_match"
    )
    assert not investigate_flow(c, "203.0.113.3", "198.51.100.2", internet_services=db)["policies"]
    assert (
        investigate_flow(c, "192.0.2.10", "198.51.100.2")["policies"][0]["status"] == "needs_review"
    )
    assert not investigate_flow(c, "192.0.2.10", "198.51.100.2", port=8443, internet_services=db)[
        "policies"
    ]


def test_positive_boundary_shadow_and_attack():
    c = model()
    q = case(c)
    assert run_case(c, q)["outcome"] == "allow_candidate"
    deny = deepcopy(c.firewall_policies[0])
    deny.policy_id = "deny-first"
    deny.action = PolicyAction.DENY
    c.firewall_policies.insert(0, deny)
    r = run_case(c, q)
    assert r["outcome"] == "block" and r["attention"]
    assert r["policies"][0]["policy_id"] == "deny-first"
    c.firewall_policies[0].service = ["unresolved"]
    assert run_case(c, q)["outcome"] == "review"  # uncertain earlier denial beats later allow
    c = model()
    c.firewall_policies[0].service = ["ALL"]
    attack = generate_cases(c)[2]
    result = run_case(c, attack)
    assert result["outcome"] == "allow_candidate" and result["attention"]
    assert any("プロファイル" in i for i in result["issues"])


@pytest.mark.parametrize(
    "problem,expected",
    [
        ("missing", "missing"),
        ("down", "drop"),
        ("blackhole", "drop"),
        ("gateway", "unknown"),
        ("egress", "unknown"),
        ("tie", "ambiguous"),
    ],
)
def test_adversarial_routes(problem, expected):
    c = model()
    q = case(c)["query"]
    if problem == "missing":
        c.routes = []
        q["destination"] = "203.0.113.10"
    if problem == "down":
        c.interfaces[1].status = "down"
    if problem == "blackhole":
        c.routes.append(Route(destination="198.51.100.20/32", route_type="blackhole", distance="1"))
    if problem == "gateway":
        c.routes[0].gateway = "203.0.113.254"
        q["destination"] = "203.0.113.10"
    if problem == "egress":
        q["destination_interface"] = "lan"
    if problem == "tie":
        c.routes.append(deepcopy(c.routes[0]))
        q["destination"] = "203.0.113.10"
    assert route_path(c, q)["status"] == expected


def test_nextvr_cycle_and_missing():
    c = model()
    c.virtual_routers = [VirtualRouter("A"), VirtualRouter("B")]
    c.routes = [
        Route(destination="0.0.0.0/0", route_type="next-vr", routing_context="A", gateway="B"),
        Route(destination="0.0.0.0/0", route_type="next-vr", routing_context="B", gateway="A"),
    ]
    q = case()["query"] | {"routing_context": "A"}
    assert route_path(c, q)["status"] == "cycle"
    c.routes[0].gateway = "absent"
    assert route_path(c, q)["status"] == "missing"
    q["routing_context"] = ""
    assert route_path(c, q)["status"] == "unknown"


def test_disabled_nat_and_incomplete_never_false_success():
    c = model()
    q = case(c)
    c.firewall_policies[0].enabled = False
    assert run_case(c, q)["outcome"] == "review"
    c.firewall_policies[0].enabled = True
    c.firewall_policies[0].nat_enabled = True
    assert run_case(c, q)["outcome"] == "review"
    c.firewall_policies[0].nat_enabled = False
    c.unsupported_sections = ["PBR"]
    assert run_case(c, q)["outcome"] == "review"


@pytest.mark.parametrize(
    "bad",
    [
        {"provenance": "x", "applications": {"x": ["tcp/0"]}},
        {"provenance": "x", "applications": {"x": ["tcp/65536"]}},
        {"applications": {"x": ["tcp/443"]}},
        {
            "provenance": "x",
            "internet_services": {"x": [{"network": "invalid", "ports": ["tcp/443"]}]},
        },
    ],
)
def test_hostile_catalogs_rejected(bad):
    with pytest.raises((ValueError, TypeError)):
        catalogs(bad)


@pytest.mark.parametrize(
    "change",
    [
        {"port": True},
        {"port": 65536},
        {"source": "<script>"},
        {"scope": "absent"},
        {"protocol": "ICMP"},
        {"destination": "2001:db8::1"},
        {"routing_context": "absent"},
        {"url": "http://169.254.169.254"},
    ],
)
def test_hostile_cases_rejected(change):
    c = model()
    q = case(c)
    q["query"].update(change)
    with pytest.raises(ValueError):
        validate_cases([q], c)


def test_feed_parsing_freshness_and_no_ip_probes():
    raw = json.dumps(
        {
            "dateReleased": "2026-10-01",
            "vulnerabilities": [
                {"cveID": "CVE-2026-1234", "dateAdded": "2026-10-01", "vendorProject": "Fortinet"}
            ],
        }
    )
    items, _ = feeds.parse_feed("cisa-kev", raw)
    assert items[0]["cveID"] == "CVE-2026-1234"
    csv = "first_seen_utc,dst_ip,dst_port,c2_status,last_online,malware\n2026-01-01,8.8.8.8,443,online,2026-10-01,Example\n2026-01-01,127.0.0.1,443,online,x,Bad\n2026-01-01,1.1.1.1,443,offline,x,Old\n"
    records, _ = feeds.parse_feed("feodo", csv)
    assert len(records) == 1
    feed = {
        "key": "feodo",
        "name": "feed",
        "url": feeds.SOURCES["feodo"][1],
        "status": "ok",
        "fetched_at": "x",
        "items": records,
    }
    assert any(c.get("feed") for c in generate_cases(model(), feeds=[feed]))
    feed["stale"] = True
    assert not any(c.get("feed") for c in generate_cases(model(), feeds=[feed]))
    with pytest.raises(ValueError):
        feeds.fetch_feed("http://127.0.0.1")


def test_feed_response_bounded_error_and_redirect(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, size):
            return b"x" * (feeds.MAX_BYTES + 1)

    class Client:
        def open(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(feeds, "_cache", {})
    assert feeds.fetch_feed("cisa-kev", Client())["status"] == "error"
    with pytest.raises(ValueError):
        feeds.NoRedirect().redirect_request(None, None, None, None, None, "http://127.0.0.1")


def test_bounded_policy_load():
    c = model()
    template = c.firewall_policies[0]
    c.firewall_policies = [deepcopy(template) for _ in range(5000)]
    for i, p in enumerate(c.firewall_policies):
        p.policy_id = str(i)
        p.service = ["UNRESOLVED"]
    start = time.monotonic()
    cases = generate_cases(c)
    assert len(cases) <= 200
    results = [run_case(c, q) for q in cases]
    assert all(r["outcome"] == "review" and len(r["policies"]) <= 10 for r in results)
    assert time.monotonic() - start < 15
    c.firewall_policies.append(deepcopy(template))
    with pytest.raises(ValueError):
        generate_cases(c)


@pytest.fixture
def lab_client(tmp_path, monkeypatch):
    monkeypatch.setenv("WALLSCRIBE_DISABLE_CLEANUP_THREAD", "1")
    monkeypatch.setenv("UPLOAD_FOLDER", str(tmp_path))
    import app

    server = app.create_app()
    server.config["TESTING"] = True
    return server.test_client()


def test_lab_api_stateless_generate_run_invalid_and_injection(lab_client, tmp_path):
    assert lab_client.get("/lab").status_code == 200
    response = lab_client.post(
        "/api/lab/generate", data={"config": (io.BytesIO(PAN.encode()), "x.xml")}
    )
    assert response.status_code == 200
    cases = response.json["cases"]
    assert cases
    response = lab_client.post(
        "/api/lab/run",
        data={"config": (io.BytesIO(PAN.encode()), "x.xml"), "cases": json.dumps(cases)},
    )
    assert response.status_code == 200 and len(response.json["results"]) == len(cases)
    assert (
        lab_client.post(
            "/api/lab/run", data={"config": (io.BytesIO(PAN.encode()), "x.xml"), "cases": "[]"}
        ).status_code
        == 400
    )
    assert (
        lab_client.post(
            "/api/lab/generate",
            data={"config": (io.BytesIO(b"x" * (2 * 1024 * 1024 + 1)), "x.xml")},
        ).status_code
        == 400
    )
    assert lab_client.post("/api/lab/feeds/evil").status_code == 400
    assert (
        lab_client.post(
            "/api/lab/generate",
            data={
                "config": (
                    io.BytesIO(
                        b'<!DOCTYPE x [<!ENTITY a SYSTEM "file:///etc/passwd">]><config>&a;</config>'
                    ),
                    "x.xml",
                )
            },
        ).status_code
        == 400
    )


def test_ipv6_generation_and_negated_address_boundaries():
    from models.config import AddressObject

    c = model()
    c.objects.addresses = [AddressObject(name="v6", object_type="ipv6", value="2001:db8::/64")]
    c.firewall_policies[0].destination_address = ["v6"]
    generated = generate_cases(c)
    validate_cases(generated, c)
    assert ":" in generated[0]["query"]["source"]
    c.firewall_policies[0].destination_negate = True
    result = run_case(c, generated[0])
    assert result["outcome"] == "review"
    assert any("宛先アドレスが不一致" in p["mismatches"] for p in result["excluded"])


def test_nested_app_group_filter_cycle_and_nonstandard_port():
    from analyzers.application import application_match, application_ports

    c = model()
    c.applications = [
        ApplicationDefinition("A", members=["B"]),
        ApplicationDefinition("B", members=["A"]),
        ApplicationDefinition("F", dynamic=True),
        ApplicationDefinition("named", ports=["tcp/10000-10001"]),
    ]
    assert application_match(c, ["A"], "root", "named") is None
    assert application_match(c, ["F"], "root", "named") is None
    assert application_ports(c, "root", "named", "TCP", 10001, {}) is True
    assert application_ports(c, "root", "named", "UDP", 10001, {}) is False
    q = case(c)
    q["query"]["application"] = "F"
    with pytest.raises(ValueError):
        validate_cases([q], c)


def test_cisa_cases_provenance_and_stale_c2_records():
    feed = {
        "key": "cisa-kev",
        "name": "CISA",
        "url": feeds.SOURCES["cisa-kev"][1],
        "status": "ok",
        "fetched_at": "2026-10-01",
        "items": [
            {
                "cveID": "CVE-2026-9999",
                "vendorProject": "Example",
                "vulnerabilityName": "Example issue",
            }
        ],
    }
    generated = generate_cases(model(), feeds=[feed])
    assert any(c.get("feed", {}).get("indicator") == "CVE-2026-9999" for c in generated)
    csv = "dst_ip,dst_port,c2_status,last_online,malware\n8.8.8.8,443,online,2000-01-01,Old\n"
    assert not feeds.parse_feed("feodo", csv)[0]


def test_route_context_input_cannot_leak_other_vr():
    c = PaloAltoParser().parse_content(PAN)
    q = generate_cases(c)[0]
    q["query"]["routing_context"] = "VR-B"
    with pytest.raises(ValueError):
        validate_cases([q], c)


def test_pending_vsys_peer_policy_is_suggested():
    c = PaloAltoParser().parse_content(PAN)
    peer = deepcopy(c.firewall_policies[0])
    peer.vdom = "vsys2"
    peer.policy_id = "peer"
    peer.source_interface = ["from-vsys1"]
    peer.destination_interface = ["untrust"]
    peer.action = PolicyAction.DENY
    c.firewall_policies.append(peer)
    result = run_case(c, generate_cases(c)[0])
    assert result["outcome"] == "review"
    assert result["boundary_policies"][0]["policy_id"] == "peer"


def test_no_success_for_pbr_or_wrong_egress_interface():
    from models.config import PolicyRoute

    c = model()
    q = case(c)
    q["query"]["destination_interface"] = "lan"
    assert run_case(c, q)["outcome"] == "review"
    c.firewall_policies[0].destination_interface = ["any"]
    q["query"]["destination_interface"] = "wan"
    c.routing.policy_routes = [PolicyRoute()]
    assert run_case(c, q)["outcome"] == "review"


def test_worst_case_rejection_load_is_bounded():
    c = model()
    template = c.firewall_policies[0]
    c.firewall_policies = [deepcopy(template) for _ in range(5000)]
    q = case()
    q["query"]["port"] = 444
    batch = [deepcopy(q) for _ in range(200)]
    start = time.monotonic()
    results = [run_case(c, item) for item in batch]
    assert all(not r["policies"] and r["outcome"] == "review" for r in results)
    assert time.monotonic() - start < 20


def test_isdb_incomplete_membership_stays_unknown_and_negates_safely():
    from ipaddress import ip_address

    from analyzers.application import isdb_match

    records = {"known": [{"network": "192.0.2.0/24", "ports": ["tcp/443"]}]}
    assert isdb_match(["known", "missing"], ip_address("198.51.100.1"), "TCP", 443, records) is None
    assert isdb_match(["known"], ip_address("192.0.2.1"), "TCP", 443, records, True) is False
    assert isdb_match(["missing"], ip_address("192.0.2.1"), "TCP", 443, records, True) is None


def test_conflicting_vsys_imports_are_not_assumed_owned():
    xml = PAN.replace(
        '<entry name="vsys2"><visible-vsys>',
        '<entry name="vsys2"><import><network><interface><member>ethernet1/1</member></interface></network></import><visible-vsys>',
    )
    c = PaloAltoParser().parse_content(xml)
    assert not c.interfaces[0].vdom_assignment_known
    assert any("複数 vsys" in e for e in c.parse_errors)


def test_pan_route_metric_is_not_admin_distance():
    xml = PAN.replace(
        "<destination>198.51.100.0/24</destination>",
        "<destination>198.51.100.0/24</destination><admin-dist>10</admin-dist><metric>100</metric>",
        1,
    )
    c = PaloAltoParser().parse_content(xml)
    assert c.routes[0].distance == "10" and c.routes[0].metric == "100"


def test_feed_cache_is_copy_and_failure_not_current(monkeypatch):
    raw = json.dumps(
        {"vulnerabilities": [{"cveID": "CVE-2026-1234", "dateAdded": "2026-10-01"}]}
    ).encode()

    class Response:
        def __init__(self):
            self.stream = io.BytesIO(raw)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, size):
            return self.stream.read(size)

    class Client:
        count = 0

        def open(self, *a, **kw):
            self.count += 1
            return Response()

    client = Client()
    monkeypatch.setattr(feeds, "_cache", {})
    first = feeds.fetch_feed("cisa-kev", client)
    first["items"].clear()
    second = feeds.fetch_feed("cisa-kev", client)
    assert second["items"] and second["cached"] and client.count == 1
    feeds._cache["cisa-kev"]["stamp"] -= 901

    class Broken:
        def open(self, *a, **kw):
            raise OSError("remote private error")

    result = feeds.fetch_feed("cisa-kev", Broken())
    assert (
        result["status"] == "error" and result["fetched_at"] is None and result["last_success_at"]
    )
    assert "remote private error" not in result["error"]


def test_lab_rejects_extra_network_targets_and_duplicate_case_ids():
    q = case()
    with pytest.raises(ValueError):
        validate_cases([q, deepcopy(q)], model())
    with pytest.raises(ValueError):
        catalogs({"provenance": "x", "url": "http://169.254.169.254"})


def test_sheet_exports_preserve_vr_and_isdb_conditions(tmp_path):
    import openpyxl

    from exporters.excel import ExcelExporter

    c = PaloAltoParser().parse_content(PAN)
    html = HTMLExporter(c, sections=["network", "policies"]).export()
    assert "仮想ルーターの所属" in html and "VR-A" in html and "web-group" in html
    out = tmp_path / "pan.xlsx"
    ExcelExporter(c, sections=["network", "policies"]).export(str(out))
    book = openpyxl.load_workbook(out)
    values = [cell.value for sheet in book for row in sheet for cell in row]
    assert "VR-A" in values and "VR-B" in values and "仮想ルーター" in values


def test_diamond_group_graph_does_not_expand_exponentially():
    from ipaddress import ip_address

    from models.config import AddressGroup, ServiceGroup

    c = model()
    c.objects.address_groups = [
        AddressGroup(name="a" + str(i), members=["a" + str(i + 1)] * 2) for i in range(60)
    ]
    c.objects.address_groups.append(AddressGroup(name="a60", members=["missing"]))
    c.objects.service_groups = [
        ServiceGroup(name="s" + str(i), members=["s" + str(i + 1)] * 2) for i in range(60)
    ]
    c.objects.service_groups.append(ServiceGroup(name="s60", members=["missing"]))
    resolver = __import__("analyzers.network", fromlist=["Resolver"]).Resolver(c)
    start = time.monotonic()
    assert resolver.address("a0", "root", ip_address("192.0.2.1")) is None
    assert resolver.service("s0", "root", "TCP", 443) is None
    assert time.monotonic() - start < 1


def test_cyclic_group_partial_cache_does_not_hide_later_match():
    from ipaddress import ip_address

    from analyzers.network import Resolver
    from models.config import AddressGroup

    c = model()
    c.objects.address_groups = [
        AddressGroup(name="A", members=["B", "all"]),
        AddressGroup(name="B", members=["A"]),
    ]
    resolver = Resolver(c)
    assert resolver.address("A", "root", ip_address("192.0.2.1")) is True
    assert resolver.address("B", "root", ip_address("192.0.2.1")) is True


def test_diamond_app_groups_and_generation_have_work_limits():
    from analyzers.application import application_match
    from models.config import AddressGroup

    c = model()
    c.applications = [
        ApplicationDefinition("a" + str(i), members=["a" + str(i + 1)] * 2) for i in range(60)
    ]
    c.objects.address_groups = [
        AddressGroup(name="n" + str(i), members=["n" + str(i + 1)] * 2) for i in range(60)
    ]
    c.firewall_policies[0].source_address = ["n0"]
    start = time.monotonic()
    assert application_match(c, ["a0"], "root", "unresolved") is None
    assert generate_cases(c)
    assert time.monotonic() - start < 1

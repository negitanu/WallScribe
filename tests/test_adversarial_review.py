"""Regressions for bounded graph evaluation and shared application ownership."""

import json
import shutil
import subprocess
from ipaddress import ip_address
from pathlib import Path

import pytest

from analyzers.application import application_match
from analyzers.network import Resolver, flow_snapshot
from models.config import (
    AddressGroup,
    ApplicationDefinition,
    ConfigModel,
    FirewallPolicy,
    PolicyAction,
    ServiceGroup,
)


def graph_model(cyclic):
    config = ConfigModel()
    config.objects.address_groups = [
        AddressGroup(name=f"a{i}", members=[f"a{i + 1}"] * 2) for i in range(60)
    ] + [AddressGroup(name="a60", members=["a60" if cyclic else "missing"])]
    config.objects.service_groups = [
        ServiceGroup(name=f"s{i}", members=[f"s{i + 1}"] * 2) for i in range(60)
    ] + [ServiceGroup(name="s60", members=["s60" if cyclic else "missing"])]
    config.firewall_policies = [
        FirewallPolicy(
            source_address=["a0"],
            destination_address=["all"],
            source_interface=["any"],
            destination_interface=["any"],
            service=["s0"],
            action=PolicyAction.ALLOW,
        )
    ]
    return config


@pytest.mark.parametrize("kind", ["address", "service"])
def test_cyclic_diamond_has_a_total_work_limit(kind):
    resolver = Resolver(graph_model(True))
    if kind == "address":
        result = resolver.address("a0", "root", ip_address("192.0.2.1"))
    else:
        result = resolver.service("s0", "root", "TCP", 443)
    assert result is None
    # 2**60 branches cannot be evaluated by a bounded request.
    assert -200 < resolver.remaining_work < 0


def test_shared_application_group_resolves_members_in_shared_scope():
    config = ConfigModel()
    config.applications = [
        ApplicationDefinition("G", vdom="shared", members=["nested"]),
        ApplicationDefinition("nested", vdom="shared", members=["shared-app"]),
        ApplicationDefinition("nested", vdom="root", members=["local-app"]),
        ApplicationDefinition("shared-app", vdom="shared"),
        ApplicationDefinition("local-app", vdom="root"),
    ]
    assert application_match(config, ["G"], "root", "shared-app") is None
    assert application_match(config, ["G"], "root", "local-app") is None
    config.applications = [a for a in config.applications if a.vdom != "root"]
    assert application_match(config, ["G"], "root", "shared-app") is True
    assert application_match(config, ["G"], "root", "local-app") is False


@pytest.mark.parametrize("cyclic", [False, True])
def test_browser_diamond_graphs_finish_and_stay_unknown(cyclic):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is unavailable")
    script = Path(__file__).resolve().parents[1] / "static/js/network_investigation.js"
    program = """
const flow=require(process.argv[1]);
let input='';process.stdin.on('data',v=>input+=v);process.stdin.on('end',()=>{
 const data=JSON.parse(input);
 const result=flow.investigate(data,{source:'192.0.2.1',destination:'198.51.100.1',protocol:'TCP',port:443,scope:'root'});
 if(result.policies.length!==1||result.policies[0].status!=='needs_review')process.exit(1);
 console.log('bounded unknown');
});
"""
    result = subprocess.run(
        [node, "-e", program, str(script)],
        input=json.dumps(flow_snapshot(graph_model(cyclic))),
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "bounded unknown"


def test_browser_cycle_cache_does_not_hide_a_later_match():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is unavailable")
    config = graph_model(False)
    config.objects.address_groups = [
        AddressGroup(name="A", members=["B", "all"]),
        AddressGroup(name="B", members=["A"]),
    ]
    config.firewall_policies[0].source_address = ["A", "B"]
    config.firewall_policies[0].service = ["ALL"]
    script = Path(__file__).resolve().parents[1] / "static/js/network_investigation.js"
    program = """
const flow=require(process.argv[1]);let text='';process.stdin.on('data',v=>text+=v);
process.stdin.on('end',()=>{const r=flow.investigate(JSON.parse(text),{source:'192.0.2.1',destination:'198.51.100.1',protocol:'TCP',port:443,scope:'root'});if(r.policies[0].status!=='static_match')process.exit(1);});
"""
    result = subprocess.run(
        [node, "-e", program, str(script)],
        input=json.dumps(flow_snapshot(config)),
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "target",
    [
        "hostile",
        None,
        1,
        [],
        {"order": True},
        {"order": -1},
        {"scope": []},
        {"url": "https://example.test"},
    ],
)
def test_hostile_target_annotations_are_rejected(target):
    from services.lab.validation import validate_cases

    config = graph_model(False)
    config.device_info.vdom_list = ["root"]
    case = {
        "id": "x",
        "kind": "custom",
        "expected": "allow",
        "query": {
            "source": "192.0.2.1",
            "destination": "198.51.100.1",
            "protocol": "TCP",
            "port": 443,
            "scope": "root",
        },
        "target": target,
    }
    with pytest.raises(ValueError):
        validate_cases([case], config)


def test_feed_trickle_stream_has_a_total_read_deadline(monkeypatch):
    from services.lab import feeds

    clock = [0.0]
    monkeypatch.setattr(feeds.time, "monotonic", lambda: clock[0])

    class Stream:
        def read(self, size):
            raise AssertionError("HTTP streams must use a single-read primitive")

        def read1(self, size):
            clock[0] += 3
            return b"x"

    with pytest.raises(TimeoutError):
        feeds._read_bounded(Stream(), 8)
    assert clock[0] == 9


def test_feed_short_reads_are_combined_until_eof():
    import time

    from services.lab import feeds

    class Stream:
        def __init__(self):
            self.parts = iter([b"ab", b"c", b""])

        def read(self, size):
            return next(self.parts)

    assert feeds._read_bounded(Stream(), time.monotonic() + 1) == b"abc"


def test_feed_network_io_does_not_block_snapshots(monkeypatch):
    import threading

    from services.lab import feeds

    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    monkeypatch.setattr(feeds, "_cache", {})

    class Client:
        def open(self, *args, **kwargs):
            entered.set()
            release.wait(2)
            raise OSError("expected network failure")

    worker = threading.Thread(target=lambda: feeds.fetch_feed("cisa-kev", Client()), daemon=True)
    worker.start()
    try:
        assert entered.wait(1)
        snapshot = threading.Thread(target=lambda: (feeds.snapshots(), finished.set()), daemon=True)
        snapshot.start()
        assert finished.wait(0.5), "cache snapshots blocked behind network I/O"
        assert feeds.fetch_feed("cisa-kev", Client())["status"] == "error"
    finally:
        release.set()
        worker.join(2)


def test_review_diamond_is_linear_and_cycles_remain_visible():
    import sys

    program = """
from analyzers.review import analyze_review
from models.config import ConfigModel,AddressGroup
c=ConfigModel();c.objects.address_groups=[AddressGroup(name=f'a{i}',members=[f'a{i+1}']*2) for i in range(60)]+[AddressGroup(name='a60',members=['missing'])]
r=analyze_review(c);assert len([i for i in r['items'] if i['kind']=='未解決参照'])==1
c.objects.address_groups[-1].members=['a0'];r=analyze_review(c);assert any(i['kind']=='参照循環' for i in r['items'])
print('bounded review')
"""
    result = subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "bounded review"


def test_fortigate_unclosed_multiline_quote_is_bounded():
    import sys

    program = """
from parsers.fortigate import FortiGateParser
c=FortiGateParser().parse_content('#config-version=FGT60F-7.2.10-FW-build1\\nset password "\\n'+'x\\n'*50000)
assert c.parse_errors and not c.firewall_policies
print('bounded malformed quote')
"""
    result = subprocess.run(
        [sys.executable, "-c", program], capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "bounded malformed quote"


def inherited_model():
    from models.config import AddressObject, DeviceType, ServiceObject

    config = ConfigModel()
    config.device_info.device_type = DeviceType.PALOALTO
    config.objects.address_groups = [AddressGroup(name="G", vdom="shared", members=["overridden"])]
    config.objects.addresses = [
        AddressObject(
            name="overridden", vdom="shared", object_type="subnet", value="203.0.113.0/24"
        ),
        AddressObject(name="overridden", vdom="root", object_type="subnet", value="192.0.2.0/24"),
    ]
    config.objects.service_groups = [
        ServiceGroup(name="S", vdom="shared", members=["overridden-service"])
    ]
    config.objects.services = [
        ServiceObject(name="overridden-service", vdom="shared", protocol="TCP", port="443"),
        ServiceObject(name="overridden-service", vdom="root", protocol="TCP", port="8443"),
    ]
    config.firewall_policies = [
        FirewallPolicy(
            source_address=["G"],
            destination_address=["all"],
            source_interface=["any"],
            destination_interface=["any"],
            service=["S"],
            action=PolicyAction.DENY,
        )
    ]
    return config


def test_inherited_conflicts_cannot_establish_a_policy_mismatch():
    config = inherited_model()
    resolver = Resolver(config)
    assert resolver.address("G", "root", ip_address("192.0.2.1")) is None
    assert resolver.service("S", "root", "TCP", 443) is None
    # Direct references still honor their known local definitions.
    assert resolver.address("overridden", "root", ip_address("192.0.2.1")) is True
    assert resolver.service("overridden-service", "root", "TCP", 8443) is True
    # The same resolver must not reuse a result from another originating scope.
    assert resolver.address("G", "shared", ip_address("192.0.2.1")) is False
    assert resolver.service("S", "shared", "TCP", 443) is True


def test_browser_inherited_conflicts_keep_the_earlier_denial_candidate():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is unavailable")
    script = Path(__file__).resolve().parents[1] / "static/js/network_investigation.js"
    program = """
const flow=require(process.argv[1]);let text='';process.stdin.on('data',v=>text+=v);
process.stdin.on('end',()=>{const r=flow.investigate(JSON.parse(text),{source:'192.0.2.1',destination:'198.51.100.1',protocol:'TCP',port:443,scope:'root'});if(r.policies.length!==1||r.policies[0].status!=='needs_review'||r.policies[0].action!=='deny')process.exit(1);});
"""
    result = subprocess.run(
        [node, "-e", program, str(script)],
        input=json.dumps(flow_snapshot(inherited_model())),
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr


def test_feed_total_timeout_keeps_worker_bounded_and_discards_late_data(monkeypatch):
    import io
    import threading
    import time

    from services.lab import feeds

    entered, release = threading.Event(), threading.Event()
    monkeypatch.setattr(feeds, "_cache", {})
    monkeypatch.setattr(feeds, "MAX_FETCH_SECONDS", 0.03)

    class Response:
        def __init__(self):
            self.body = io.BytesIO(b'{"vulnerabilities": []}')

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, size):
            return self.body.read(size)

    class Client:
        calls = 0

        def open(self, *args, **kwargs):
            self.calls += 1
            entered.set()
            release.wait(2)
            return Response()

    client = Client()
    started = time.monotonic()
    try:
        assert feeds.fetch_feed("cisa-kev", client)["status"] == "error"
        assert entered.is_set()
        assert time.monotonic() - started < 0.5
        # Repeated callers cannot spawn more workers while the first is stalled.
        for _ in range(5):
            assert feeds.fetch_feed("cisa-kev", client)["status"] == "error"
        assert client.calls == 1
        assert feeds.snapshots() == []
    finally:
        release.set()
        assert feeds._fetch_locks["cisa-kev"].acquire(timeout=1)
        feeds._fetch_locks["cisa-kev"].release()
    assert feeds.snapshots() == []


def zone_model():
    from models.config import DeviceType, Interface, Route

    config = ConfigModel()
    config.device_info.device_type = DeviceType.PALOALTO
    config.device_info.vdom_list = ["vsys1"]
    config.interfaces = [
        Interface(name="ethernet1/1", zone="trust", vdom="vsys1", ip_address="192.0.2.1/24"),
        Interface(name="ethernet1/2", zone="untrust", vdom="vsys1", ip_address="198.51.100.1/24"),
    ]
    config.routes = [
        Route(
            destination="0.0.0.0/0", interface="ethernet1/2", gateway="198.51.100.254", vdom="vsys1"
        )
    ]
    config.firewall_policies = [
        FirewallPolicy(
            policy_id="deny-first",
            source_interface=["trust"],
            destination_interface=["untrust"],
            source_address=["any"],
            destination_address=["any"],
            service=["any"],
            action=PolicyAction.DENY,
            vdom="vsys1",
        ),
        FirewallPolicy(
            policy_id="allow-later",
            source_interface=["any"],
            destination_interface=["any"],
            source_address=["any"],
            destination_address=["any"],
            service=["any"],
            action=PolicyAction.ALLOW,
            vdom="vsys1",
        ),
    ]
    return config


def zone_query():
    return {
        "source": "192.0.2.10",
        "destination": "203.0.113.10",
        "protocol": "TCP",
        "port": 443,
        "scope": "vsys1",
        "source_interface": "ethernet1/1",
        "destination_interface": "ethernet1/2",
    }


def test_pan_interface_names_cannot_skip_an_earlier_zone_denial():
    from services.lab.engine import run_case

    config = zone_model()
    case = {"id": "x", "kind": "custom", "expected": "block", "query": zone_query()}
    result = run_case(config, case)
    assert result["outcome"] == "block"
    assert result["policies"][0]["policy_id"] == "deny-first"
    config.interfaces[0].zone = ""
    result = run_case(config, case)
    assert result["outcome"] == "review"
    assert result["policies"][0]["policy_id"] == "deny-first"


def test_lab_rejects_fictitious_or_wildcard_actual_interfaces():
    from services.lab.validation import validate_cases

    for actual in ("not-an-interface", "any", "ALL"):
        case = {
            "id": "x",
            "kind": "custom",
            "expected": "block",
            "query": zone_query() | {"source_interface": actual},
        }
        with pytest.raises(ValueError):
            validate_cases([case], zone_model())


def test_pan_intrazone_compares_zone_identity_for_interface_inputs():
    from analyzers.network import investigate_flow

    config = zone_model()
    config.firewall_policies = config.firewall_policies[:1]
    config.firewall_policies[0].rule_type = "intrazone"
    query = zone_query() | {"destination_interface": "trust"}
    result = investigate_flow(config, **query)
    assert result["policies"][0]["status"] == "static_match"


def test_browser_interface_names_retain_zone_denial_and_unknown_membership():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is unavailable")
    script = Path(__file__).resolve().parents[1] / "static/js/network_investigation.js"
    program = """
const flow=require(process.argv[1]);let text='';process.stdin.on('data',v=>text+=v);
process.stdin.on('end',()=>{const input=JSON.parse(text),data=input.data,q=input.query;
let r=flow.investigate(data,q);if(r.policies[0].policy_id!=='deny-first'||r.policies[0].status!=='static_match')process.exit(1);
data.interfaces[0].zone='';r=flow.investigate(data,q);if(r.policies[0].policy_id!=='deny-first'||r.policies[0].status!=='needs_review')process.exit(2);
});
"""
    result = subprocess.run(
        [node, "-e", program, str(script)],
        input=json.dumps({"data": flow_snapshot(zone_model()), "query": zone_query()}),
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr

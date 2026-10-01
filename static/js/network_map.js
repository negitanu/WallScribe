/* Offline graph exploration. Config-derived content is rendered with textContent. */
(function (root) {
    'use strict';
    function scopePath(data, from, to) {
        const scopes = new Set(data.nodes.map(n => n.scope));
        if (!scopes.has(from) || !scopes.has(to)) return null;
        if (from === to) return {scopes: [from], links: []};
        const nodes = new Map(data.nodes.map(n => [n.id, n]));
        const adjacent = new Map();
        for (const edge of data.edges) {
            if (!['VDOM 間リンク', 'vsys 間接続'].includes(edge.relation) || !edge.active) continue;
            const left = nodes.get(edge.source), right = nodes.get(edge.target);
            if (!left || !right) continue;
            for (const [a, b, local, peer] of (edge.directed ? [[left.scope, right.scope, left, right]] : [[left.scope, right.scope, left, right], [right.scope, left.scope, right, left]])) {
                if (!adjacent.has(a)) adjacent.set(a, []);
                adjacent.get(a).push({scope: b, edge: edge.id, local, peer});
            }
        }
        const queue = [{scopes: [from], links: []}], seen = new Set([from]);
        for (let index = 0; index < queue.length; index++) {
            const path = queue[index], last = path.scopes[path.scopes.length - 1];
            for (const link of adjacent.get(last) || []) {
                if (seen.has(link.scope)) continue;
                const next = {scopes: [...path.scopes, link.scope], links: [...path.links, link]};
                if (link.scope === to) return next;
                seen.add(link.scope); queue.push(next);
            }
        }
        return null;
    }
    // This is a policy direction illustration, never a routing/success verdict.
    function policyFlow(data, index) {
        const p = data.flow.policies[index];
        if (!p || !p.enabled) return {segments: [], sources: [], destinations: [], reason: '無効ポリシーのため流れは表示しません。'};
        const interfaces = data.nodes.filter(n => n.kind === 'interface' && n.scope === p.vdom && n.status !== 'down');
        const matches = (node, names) => names.some(name => ['any', 'all'].includes(name.toLowerCase()) || name === node.label || name === node.zone);
        const sources = interfaces.filter(n => matches(n, p.source_interface));
        const destinations = interfaces.filter(n => matches(n, p.destination_interface));
        const devices = new Set(data.nodes.filter(n => n.scope === p.vdom && n.kind === 'device').map(n => n.id));
        const ownership = data.edges.filter(e => e.active && ['IF 所属', '外部ゾーン所属'].includes(e.relation));
        const segments = [];
        function add(node, incoming) {
            const edge = ownership.find(e => (e.source === node.id && devices.has(e.target)) || (e.target === node.id && devices.has(e.source)));
            if (!edge) return;
            const device = edge.source === node.id ? edge.target : edge.source;
            const from = incoming ? node.id : device, to = incoming ? device : node.id;
            segments.push({edge: edge.id, from, to, reverse: edge.source !== from, stage: incoming ? 0 : 1});
        }
        sources.forEach(n => add(n, true));
        const allowed = ['accept', 'allow'].includes(p.action);
        if (allowed && segments.length) destinations.forEach(n => add(n, false));
        const reason = !sources.length || !destinations.length ? '入口・出口の IF を特定できません。ゾーン所属や未取得の設定を確認してください。' :
            allowed ? 'ポリシーの入口 → 機器 → 出口を表示しています。アドレス・サービス・経路・NAT・先行ルールの評価前です。' :
            ['deny', 'drop', 'reject'].includes(p.action) ? '拒否ポリシーです。入口から機器まで表示し、出口へは進めません。' : '動作が未確定のため、出口への流れは表示しません。';
        return {segments, sources: sources.map(n => n.id), destinations: destinations.map(n => n.id), reason};
    }
    root.WallScribeMap = {scopePath, policyFlow};
    if (typeof module !== 'undefined') module.exports = root.WallScribeMap;
    if (typeof document === 'undefined') return;
    for (const explorer of document.querySelectorAll('[data-network-explorer]')) {
        if (explorer.dataset.initialized) continue;
        explorer.dataset.initialized = 'true';
        const data = JSON.parse(explorer.querySelector('.map-data').textContent);
        const svg = explorer.querySelector('svg'), viewport = explorer.querySelector('.map-viewport');
        const panel = explorer.querySelector('.map-device-panel'), policiesPanel = explorer.querySelector('.map-policy-panel'), result = explorer.querySelector('.map-trace-result');
        const nodeData = new Map(data.nodes.map(n => [n.id, n]));
        const edgeData = new Map(data.edges.map(e => [e.id, e]));
        const peers = new Map(data.nodes.map(n => [n.id, []]));
        for (const edge of data.edges) { peers.get(edge.source).push(edge.target); peers.get(edge.target).push(edge.source); }
        const initial = svg.getAttribute('viewBox').split(' ').map(Number);
        let view = [...initial], drag = null;
        const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
        const apply = () => svg.setAttribute('viewBox', view.join(' '));
        function fit(elements) {
            if (!elements || !elements.length) { view = [...initial]; apply(); return; }
            const boxes = elements.map(e => e.getBBox());
            const x = Math.min(...boxes.map(b => b.x)) - 30, y = Math.min(...boxes.map(b => b.y)) - 30;
            view = [x, y, Math.max(...boxes.map(b => b.x + b.width)) - x + 30, Math.max(...boxes.map(b => b.y + b.height)) - y + 30];
            apply();
        }
        function zoom(factor) {
            const w = view[2] * factor, h = view[3] * factor;
            if (w < 160 || w > initial[2] * 5) return;
            view = [view[0] + (view[2] - w) / 2, view[1] + (view[3] - h) / 2, w, h]; apply();
        }
        function stopPackets() { for (const el of svg.querySelectorAll('.map-packet-layer')) el.remove(); }
        function clearFocus() {
            stopPackets();
            for (const element of svg.querySelectorAll('.map-node,.map-edge')) element.classList.remove('selected', 'traced', 'dimmed');
        }
        function text(tag, value, parent = panel) {
            const element = document.createElement(tag); element.textContent = value; parent.append(element); return element;
        }
        function inspectNode(id) {
            const node = nodeData.get(id); if (!node) return;
            clearFocus(); panel.replaceChildren();
            text('small', node.scope + ' · ' + node.kind); text('h4', node.label);
            for (const detail of node.details) text('p', detail);
            if (node.status === 'down') text('p', '管理設定で無効です。接続追跡には使用しません。');
            const adjacent = new Set([id]);
            for (const edge of data.edges) if (edge.source === id || edge.target === id) {
                adjacent.add(edge.source); adjacent.add(edge.target);
                svg.querySelector('[data-edge="' + edge.id + '"]').classList.add('selected');
                text('p', edge.relation + ' / ' + edge.evidence);
            }
            for (const shape of svg.querySelectorAll('[data-node]')) shape.classList.toggle('dimmed', !adjacent.has(shape.dataset.node));
            svg.querySelector('[data-node="' + id + '"]').classList.add('selected');
            if (node.findings.length) {
                text('h5', '診断・確認事項');
                for (const finding of node.findings) { text('strong', finding.title); text('p', finding.evidence); text('p', finding.recommendation); }
            }
            showPolicies(node);
        }
        function showPolicies(node) {
            policiesPanel.replaceChildren(); text('small', '関連ポリシー', policiesPanel);
            text('h4', node.label + ' · ' + node.policies.length + ' 件', policiesPanel);
            if (!node.policies.length) text('p', '関連するポリシーはありません。', policiesPanel);
            for (const index of node.policies) {
                const p = data.flow.policies[index];
                const card = text('div', '', policiesPanel); card.className = 'map-policy-card';
                const button = text('button', p.policy_id + ': ' + (p.name || '名称なし'), card);
                button.type = 'button'; button.dataset.policy = index; button.setAttribute('aria-pressed', 'false');
                text('small', p.action + (p.enabled ? '' : ' · 無効'), card);
                text('p', p.source_interface.join(', ') + ' → ' + p.destination_interface.join(', '), card);
                button.addEventListener('click', () => selectPolicy(index, card));
            }
        }
        function selectPolicy(index, card) {
            clearFocus();
            for (const el of policiesPanel.querySelectorAll('[data-policy]')) el.setAttribute('aria-pressed', String(Number(el.dataset.policy) === index));
            for (const el of policiesPanel.querySelectorAll('.map-policy-detail')) el.remove();
            const p = data.flow.policies[index], flow = policyFlow(data, index);
            const details = text('div', '', card); details.className = 'map-policy-detail';
            text('p', '送信元: ' + p.source_address.join(', ') + ' / 宛先: ' + p.destination_address.join(', '), details);
            text('p', 'サービス: ' + p.service.join(', ') + ' / アプリ: ' + (p.application.join(', ') || '指定なし'), details);
            text('p', 'NAT: ' + (p.nat_enabled ? '有効・変換後の確認が必要' : 'ポリシー単位では無効'), details);
            text('p', flow.reason, details);
            const findings = data.policy_findings[index] || [];
            if (findings.length) { const checks = text('details', '', details); text('summary', '確認事項 (' + findings.length + ')', checks); for (const finding of findings) { text('strong', finding.title, checks); text('p', finding.recommendation, checks); } }
            const ids = new Set(flow.segments.flatMap(s => [s.from, s.to]));
            const edgeIds = new Set(flow.segments.map(s => s.edge));
            for (const el of svg.querySelectorAll('[data-node]')) { el.classList.toggle('traced', ids.has(el.dataset.node)); el.classList.toggle('dimmed', !ids.has(el.dataset.node)); }
            for (const el of svg.querySelectorAll('[data-edge]')) { el.classList.toggle('traced', edgeIds.has(el.dataset.edge)); el.classList.toggle('dimmed', !edgeIds.has(el.dataset.edge)); }
            if (ids.size) fit([...svg.querySelectorAll('.map-node.traced')]);
            const replay = text('button', '流れを再生', details); replay.type = 'button'; replay.disabled = !flow.segments.length;
            replay.addEventListener('click', () => animatePackets(flow));
            const stop = text('button', '停止', details); stop.type = 'button'; stop.addEventListener('click', stopPackets);
            animatePackets(flow);
        }
        function animatePackets(flow) {
            stopPackets();
            if (motion.matches || document.hidden) return;
            const scheduled = [];
            const ns = 'http://www.w3.org/2000/svg', layer = document.createElementNS(ns, 'g');
            layer.classList.add('map-packet-layer'); layer.setAttribute('aria-hidden', 'true');
            for (const segment of flow.segments) {
                const path = svg.querySelector('[data-edge="' + segment.edge + '"]'); if (!path || path.classList.contains('map-hidden')) continue;
                const dot = document.createElementNS(ns, 'circle'); dot.setAttribute('r', '5');
                const animate = document.createElementNS(ns, 'animateMotion');
                animate.setAttribute('path', path.getAttribute('d')); animate.setAttribute('dur', '1.6s');
                animate.setAttribute('begin', 'indefinite'); animate.setAttribute('repeatCount', '3');
                animate.setAttribute('keyPoints', segment.reverse ? '1;0' : '0;1'); animate.setAttribute('keyTimes', '0;1'); animate.setAttribute('calcMode', 'linear');
                dot.append(animate); layer.append(dot); scheduled.push([animate, segment.stage]);
                dot.style.visibility = 'hidden';
                animate.addEventListener('beginEvent', () => { dot.style.visibility = 'visible'; });
                animate.addEventListener('endEvent', () => { dot.style.visibility = 'hidden'; });
            }
            svg.append(layer);
            for (const [animation, stage] of scheduled) animation.beginElementAt(stage * 1.6);
        }
        document.addEventListener('visibilitychange', () => { if (document.hidden) stopPackets(); });
        motion.addEventListener('change', stopPackets);

        function activate(element) {
            if (element.dataset.node) inspectNode(element.dataset.node);
            else {
                const edge = edgeData.get(element.dataset.edge); if (!edge) return;
                clearFocus(); element.classList.add('selected'); panel.replaceChildren(); policiesPanel.replaceChildren(); text('p', 'IF を選ぶと関連ポリシーを表示します。', policiesPanel);
                text('h4', edge.relation); text('p', edge.evidence); text('p', edge.active ? '設定上の接続です。実際の通信可否はポリシーと経路の確認が必要です。' : '端点に無効な IF が含まれます。');
                for (const id of [edge.source, edge.target]) { const button = text('button', nodeData.get(id).scope + ' / ' + nodeData.get(id).label); button.type = 'button'; button.addEventListener('click', () => inspectNode(id)); }
            }
        }
        svg.addEventListener('click', event => { const target = event.target.closest('[data-node],[data-edge]'); if (target) activate(target); });
        svg.addEventListener('keydown', event => { if (['Enter', ' '].includes(event.key)) { const target = event.target.closest('[data-node],[data-edge]'); if (target) { event.preventDefault(); activate(target); } } });
        explorer.querySelector('[data-map-fit]').addEventListener('click', () => { clearFocus(); fit([...svg.querySelectorAll('.map-node:not(.map-hidden)')]); });
        for (const button of explorer.querySelectorAll('[data-map-zoom]')) button.addEventListener('click', () => zoom(button.dataset.mapZoom === 'in' ? .8 : 1.25));
        explorer.querySelector('[data-map-export]').addEventListener('click', () => {
            const clone = svg.cloneNode(true);
            for (const el of clone.querySelectorAll('.map-packet-layer')) el.remove();
            for (const el of clone.querySelectorAll('.map-hidden')) el.classList.remove('map-hidden'); clone.setAttribute('viewBox', initial.join(' '));
            clone.setAttribute('width', initial[2]); clone.setAttribute('height', initial[3]);
            for (const element of clone.querySelectorAll('.selected,.traced,.dimmed')) element.classList.remove('selected', 'traced', 'dimmed');
            const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(clone)], {type: 'image/svg+xml'}));
            const link = document.createElement('a'); link.href = url; link.download = 'network-map.svg'; link.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        });
        explorer.querySelector('[data-map-fullscreen]').addEventListener('click', async () => { try { if (document.fullscreenElement) await document.exitFullscreen(); else await explorer.requestFullscreen(); } catch (_) { explorer.classList.toggle('expanded'); } });
        svg.addEventListener('pointerdown', event => {
            if (event.target.closest('[data-node],[data-edge]')) return;
            const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(svg.getScreenCTM().inverse());
            drag = {x: point.x, y: point.y, view: [...view]}; svg.setPointerCapture(event.pointerId);
        });
        svg.addEventListener('pointermove', event => { if (!drag) return; const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(svg.getScreenCTM().inverse()); view[0] += drag.x - point.x; view[1] += drag.y - point.y; apply(); });
        svg.addEventListener('pointerup', () => { drag = null; });
        svg.addEventListener('pointercancel', () => { drag = null; });
        viewport.addEventListener('wheel', event => { if (!event.ctrlKey && !event.metaKey) return; event.preventDefault(); zoom(event.deltaY < 0 ? .9 : 1.1); }, {passive: false});
        function filter() {
            clearFocus(); const scope = explorer.querySelector('[data-map-scope]').value, query = explorer.querySelector('[data-map-search]').value.trim().toLowerCase();
            const hideDisabled = explorer.querySelector('[data-map-hide-disabled]').checked;
            const hidden = new Set(data.nodes.filter(n => hideDisabled && n.kind === 'interface' && n.status === 'down').map(n => n.id));
            // Hide only orphaned leaf networks/routes of disabled interfaces, keeping shared nodes.
            for (const n of data.nodes) if (['subnet', 'route', 'discard'].includes(n.kind)) {
                const adjacent = peers.get(n.id);
                if (adjacent.length && adjacent.every(id => hidden.has(id))) hidden.add(n.id);
            }
            for (const el of svg.querySelectorAll('[data-node]')) el.classList.toggle('map-hidden', hidden.has(el.dataset.node));
            for (const el of svg.querySelectorAll('[data-edge]')) { const e = edgeData.get(el.dataset.edge); el.classList.toggle('map-hidden', hidden.has(e.source) || hidden.has(e.target)); }
            const matched = new Set(data.nodes.filter(n => !hidden.has(n.id) && (!scope || n.scope === scope) && (!query || [n.label, n.scope, ...n.details].join(' ').toLowerCase().includes(query))).map(n => n.id));
            const elements = [];
            for (const element of svg.querySelectorAll('[data-node]')) { const match = matched.has(element.dataset.node); element.classList.toggle('dimmed', !match); if (match) elements.push(element); }
            for (const element of svg.querySelectorAll('[data-edge]')) { const edge = edgeData.get(element.dataset.edge); element.classList.toggle('dimmed', !matched.has(edge.source) && !matched.has(edge.target)); }
            fit(elements);
            policiesPanel.replaceChildren(); text('p', 'IF を選ぶと関連ポリシーを表示します。', policiesPanel);
            panel.replaceChildren(); text('h4', matched.size + ' ノードが該当'); text('p', matched.size ? 'ノードを選ぶと設定の詳細を確認できます。' : '該当する設定はありません。検索条件を変更してください。');
        }
        explorer.querySelector('[data-map-hide-disabled]').addEventListener('change', filter);
        explorer.querySelector('[data-map-search]').addEventListener('input', filter);
        explorer.querySelector('[data-map-scope]').addEventListener('change', filter);
        const trace = explorer.querySelector('.map-trace');
        if (trace.elements.to_scope.options.length > 1) trace.elements.to_scope.selectedIndex = 1;
        trace.addEventListener('submit', event => {
            event.preventDefault(); clearFocus(); result.replaceChildren();
            const q = Object.fromEntries(new FormData(trace));
            try {
                // Validate inputs even when no inter-partition connection exists.
                root.WallScribeFlow.investigate(data.flow, {...q, scope: q.from_scope});
                const path = scopePath(data, q.from_scope, q.to_scope);
                if (!path) { text('strong', '設定から追跡できる VDOM 間リンクがありません', result); text('p', '疎通不可の断定ではありません。未取得のリンク・外部機器を経由する接続・無効な IF を確認してください。', result); return; }
                text('strong', '構造上の接続: ' + path.scopes.join(' → '), result);
                text('p', '複数経路がある場合は、リンク数が最少の一例です。実効経路の選択や通信成功を示しません。NAT 変換前の入力を各区画で照合します。', result);
                const ids = new Set(path.links.flatMap(link => [link.local.id, link.peer.id]));
                for (const n of data.nodes) if (n.kind === 'device' && path.scopes.includes(n.scope)) ids.add(n.id);
                const tracedEdges = new Set(path.links.map(link => link.edge));
                for (const edge of data.edges) if (edge.relation === 'IF 所属' && ids.has(edge.source) && ids.has(edge.target)) tracedEdges.add(edge.id);
                for (const shape of svg.querySelectorAll('[data-node]')) { shape.classList.toggle('traced', ids.has(shape.dataset.node)); shape.classList.toggle('dimmed', !ids.has(shape.dataset.node)); }
                for (const shape of svg.querySelectorAll('[data-edge]')) { shape.classList.toggle('traced', tracedEdges.has(shape.dataset.edge)); shape.classList.toggle('dimmed', !tracedEdges.has(shape.dataset.edge)); }
                fit([...svg.querySelectorAll('.map-node.traced')]);
                path.scopes.forEach((scope, index) => {
                    const section = document.createElement('details'); section.open = true; result.append(section); text('summary', (index + 1) + '. ' + scope, section);
                    const input = {...q, scope, source_interface: index ? path.links[index - 1].peer.label : q.source_interface || '', destination_interface: index < path.links.length ? path.links[index].local.label : q.destination_interface || ''};
                    const checks = root.WallScribeFlow.investigate(data.flow, input);
                    if (!checks.policies.length) text('p', '一致候補なし。暗黙ルール・入力不足・未解析設定を確認してください。', section);
                    for (const p of checks.policies) {
                        text('strong', p.policy_id + ': ' + p.name + ' / ' + p.action + ' / ' + (p.status === 'static_match' ? '静的条件が一致' : '追加確認が必要'), section);
                        if (p.nat_enabled) text('p', 'ポリシーの NAT が有効です。後続区画では変換後のパケット条件を再確認してください。', section);
                        for (const note of p.unknown) text('p', note, section);
                        if (p.preceding_candidates.length) text('p', '先行候補: ' + p.preceding_candidates.join(', '), section);
                    }
                    text('p', '宛先に対応する設定ルート候補: ' + checks.routes.map(r => r.destination + ' / ' + (r.interface || 'IF 未指定')).join('; '), section);
                    if (checks.nat.length) text('p', 'NAT 候補あり: ' + checks.nat.map(n => n.name).join(', ') + '。変換後のアドレス・ポート・ゾーンは再確認が必要です。', section);
                });
            } catch (error) { text('p', error.message, result); }
        });
    }
})(typeof globalThis === 'undefined' ? this : globalThis);

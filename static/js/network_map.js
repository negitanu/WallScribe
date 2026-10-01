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
    root.WallScribeMap = {scopePath};
    if (typeof module !== 'undefined') module.exports = root.WallScribeMap;
    if (typeof document === 'undefined') return;
    for (const explorer of document.querySelectorAll('[data-network-explorer]')) {
        if (explorer.dataset.initialized) continue;
        explorer.dataset.initialized = 'true';
        const data = JSON.parse(explorer.querySelector('.map-data').textContent);
        const svg = explorer.querySelector('svg'), viewport = explorer.querySelector('.map-viewport');
        const panel = explorer.querySelector('.map-inspector'), result = explorer.querySelector('.map-trace-result');
        const nodeData = new Map(data.nodes.map(n => [n.id, n]));
        const initial = svg.getAttribute('viewBox').split(' ').map(Number);
        let view = [...initial], drag = null;
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
        function clearFocus() {
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
            if (node.policies.length) {
                text('h5', '関連ポリシー (' + node.policies.length + ')');
                for (const policyIndex of node.policies) {
                    const p = data.flow.policies[policyIndex];
                    const detail = document.createElement('details'); panel.append(detail);
                    text('summary', p.policy_id + ': ' + (p.name || '名称なし') + ' · ' + p.action + (p.enabled ? '' : ' · 無効'), detail);
                    text('p', p.source_interface.join(', ') + ' → ' + p.destination_interface.join(', '), detail);
                    text('p', '送信元: ' + p.source_address.join(', ') + ' / 宛先: ' + p.destination_address.join(', '), detail);
                    text('p', 'サービス: ' + p.service.join(', ') + ' / アプリ: ' + p.application.join(', '), detail);
                    for (const finding of data.policy_findings[policyIndex] || []) { text('strong', finding.title, detail); text('p', finding.recommendation, detail); }
                    text('p', 'NAT: ' + (p.nat_enabled ? '有効・変換後の評価が必要' : 'ポリシー単位では無効'), detail);
                }
            }
        }
        function activate(element) {
            if (element.dataset.node) inspectNode(element.dataset.node);
            else {
                const edge = data.edges.find(e => e.id === element.dataset.edge); if (!edge) return;
                clearFocus(); element.classList.add('selected'); panel.replaceChildren();
                text('h4', edge.relation); text('p', edge.evidence); text('p', edge.active ? '設定上の接続です。実際の通信可否はポリシーと経路の確認が必要です。' : '端点に無効な IF が含まれます。');
                for (const id of [edge.source, edge.target]) { const button = text('button', nodeData.get(id).scope + ' / ' + nodeData.get(id).label); button.type = 'button'; button.addEventListener('click', () => inspectNode(id)); }
            }
        }
        svg.addEventListener('click', event => { const target = event.target.closest('[data-node],[data-edge]'); if (target) activate(target); });
        svg.addEventListener('keydown', event => { if (['Enter', ' '].includes(event.key)) { const target = event.target.closest('[data-node],[data-edge]'); if (target) { event.preventDefault(); activate(target); } } });
        explorer.querySelector('[data-map-fit]').addEventListener('click', () => { clearFocus(); fit(); });
        for (const button of explorer.querySelectorAll('[data-map-zoom]')) button.addEventListener('click', () => zoom(button.dataset.mapZoom === 'in' ? .8 : 1.25));
        explorer.querySelector('[data-map-export]').addEventListener('click', () => {
            const clone = svg.cloneNode(true); clone.setAttribute('viewBox', initial.join(' '));
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
            const matched = new Set(data.nodes.filter(n => (!scope || n.scope === scope) && (!query || [n.label, n.scope, ...n.details].join(' ').toLowerCase().includes(query))).map(n => n.id));
            const elements = [];
            for (const element of svg.querySelectorAll('[data-node]')) { const match = matched.has(element.dataset.node); element.classList.toggle('dimmed', !match); if (match) elements.push(element); }
            for (const element of svg.querySelectorAll('[data-edge]')) { const edge = data.edges.find(e => e.id === element.dataset.edge); element.classList.toggle('dimmed', !matched.has(edge.source) && !matched.has(edge.target)); }
            if (query || scope) fit(elements); else fit();
            panel.replaceChildren(); text('h4', matched.size + ' ノードが該当'); text('p', matched.size ? 'ノードを選ぶと設定の詳細を確認できます。' : '該当する設定はありません。検索条件を変更してください。');
        }
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

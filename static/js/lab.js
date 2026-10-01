/* Tabletop assistance: all configuration and feed text goes through textContent. */
(() => {
    'use strict';
    const form = document.querySelector('#lab-input'), list = document.querySelector('#lab-cases');
    const status = document.querySelector('#lab-status'), run = document.querySelector('#lab-run'), filter = document.querySelector('#lab-filter');
    let cases = [], results = new Map(), scopes = [], routers = [], busy = false, revision = 0;
    const labels = {allow_candidate: '許可候補', block: '明示拒否', route_failure: '経路不備', review: '未確定'};
    function node(tag, text, parent, cls) { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (cls) el.className = cls; if (parent) parent.append(el); return el; }
    function setBusy(value) {busy = value; run.disabled = value || !cases.length; document.querySelector('#lab-add').disabled = value || !cases.length || cases.length >= 200; form.querySelector('button').disabled = value;}
    function packet() { const data = new FormData(form); return data; }
    async function api(path, data) {
        const response = await fetch(path, {method: 'POST', body: data});
        const content = await response.json();
        if (!response.ok) throw new Error(content.error || '処理に失敗しました。時間を置いて再試行してください。');
        return content;
    }
    function invalidate() {revision++; results.clear(); document.querySelector('#lab-summary').replaceChildren(); status.textContent = '条件が変更されました。再実行して最新の結果を確認してください。';}
    function control(parent, title, value, options, onChange) {
        const label = node('label', title, parent), input = node(options ? 'select' : 'input', undefined, label);
        if (options) for (const [key, text] of options) {const opt = node('option', text, input); opt.value = key;}
        input.value = value || ''; input.addEventListener('change', () => {onChange(input.value); invalidate(); render();});
        return input;
    }
    function render() {
        const expanded = new Set([...list.querySelectorAll(".lab-case")].filter(el=>el.querySelector("details")?.open).map(el=>el.dataset.case));
        list.replaceChildren();
        for (const c of cases) {
            const r = results.get(c.id), f = filter.value;
            if (f === 'attention' && !r?.attention || f === 'review' && r?.outcome !== 'review' || ['policy','boundary','attack'].includes(f) && c.kind !== f) continue;
            const card = node('article', undefined, list, 'lab-case' + (r?.attention ? ' attention' : ''));
            card.dataset.case = c.id;
            const head = node('div', undefined, card, 'lab-case-head');
            const check = node('input', undefined, head); check.type = 'checkbox'; check.checked = c.selected !== false; check.setAttribute('aria-label', c.name + ' を選択'); check.addEventListener('change', () => {c.selected = check.checked;});
            const title = node('div', undefined, head); node('strong', c.name, title);
            node('small', c.query.scope + ' · ' + c.query.source + ' → ' + c.query.destination + ' · ' + c.query.protocol + '/' + c.query.port, title);
            node('span', r ? labels[r.outcome] : '未実行', head, 'lab-badge ' + (r?.outcome || ''));
            const detail = node('details', undefined, card); detail.open = expanded.has(c.id); node('summary', r ? '根拠・該当ポリシー・条件の編集' : '条件と期待値を確認・編集', detail);
            node('p', c.reason || '手動のテスト条件です。', detail);
            if (c.feed) node('p', '出典: ' + c.feed.name + ' / 取得: ' + c.feed.fetched_at + ' / 指標: ' + c.feed.indicator, detail);
            const editDetails = node('details', undefined, detail); node('summary','通信条件と期待値を編集',editDetails);
            const edit = node('div', undefined, editDetails, 'lab-edit');
            control(edit, '期待値（検討用）', c.expected, [['allow','許可を期待'],['block','拒否を期待']], v => c.expected = v);
            control(edit, '区画', c.query.scope, scopes.map(v => [v,v]), v => c.query.scope = v);
            for (const [key, label] of [['source','送信元 IP'],['destination','宛先 IP'],['source_interface','入口 IF / ゾーン'],['destination_interface','出口 IF / ゾーン'],['application','App-ID（仮定）']]) control(edit,label,c.query[key],null,v => c.query[key] = v);
            control(edit,'プロトコル',c.query.protocol,[['TCP','TCP'],['UDP','UDP']],v => c.query.protocol = v);
            const port = control(edit,'宛先ポート',c.query.port,null,v => c.query.port = Number(v)); port.type = 'number'; port.min = '1'; port.max = '65535';
            if (routers.length) control(edit,'入口の仮想ルーター',c.query.routing_context,[['','未指定'],...routers.map(v=>[v,v])],v => c.query.routing_context = v);
            if (r) {
                const evidence = node('div', undefined, detail, 'lab-evidence');
                node('h4', r.attention ? '期待値との違いがあります' : '照合の根拠', evidence);
                const issues = node('ul', undefined, evidence); for (const text of [...r.issues,...r.assumptions]) node('li', text, issues);
                node('h4', '該当ポリシー候補（設定順）', evidence);
                for (const p of r.policies) { node('p', '#' + p.order + ' · ' + p.scope + ' / ' + p.policy_id + ' ' + p.name + ' · ' + p.action + ' · ' + (p.status === 'static_match' ? '静的条件一致' : '未確定条件あり'), evidence); const ul=node('ul',undefined,evidence); for (const text of [...p.evidence,...p.unknown]) node('li',text,ul); }
                if (r.candidate_limit_reached || r.candidate_count > r.policies.length) node('p','先頭 10 件を表示しています。先行する未確定候補がある場合、後続の一致だけでは判定しません。',evidence);
                if (r.excluded?.length) {node('h4','条件が一致しないポリシー',evidence); for (const p of r.excluded) node('p', '#' + p.order + ' · ' + p.scope + ' / ' + p.policy_id + ' ' + p.name + ' — ' + p.mismatches.join('・'),evidence);}
                if (r.boundary_policies?.length) {node('h4','接続先 vsys のポリシー候補',evidence);for (const p of r.boundary_policies) node('p','#' + p.order + ' · ' + p.scope + ' / ' + p.policy_id + ' ' + p.name + ' · ' + p.action + ' · ' + p.status,evidence);}
                node('h4','経路: ' + ({found:'設定上の経路あり',missing:'設定上の経路なし',drop:'破棄・無効',cycle:'循環',ambiguous:'競合',unknown:'未確定'}[r.route.status] || r.route.status),evidence);
                for (const step of r.route.steps) node('p',(step.routing_context || c.query.scope) + ' · ' + step.destination + ' → ' + (step.interface || step.gateway || step.route_type),evidence);
            }
        }
        if (!list.children.length) node('p','該当するケースはありません。表示条件を変更してください。',list);
    }
    form.addEventListener('submit', async e => {
        e.preventDefault(); if (busy) return; setBusy(true); status.textContent = '設定からテストを生成しています…';
        try { const data = await api('/api/lab/generate',packet()); cases=data.cases; results.clear(); scopes=[...new Set([...data.scopes,...cases.map(c=>c.query.scope)])]; routers=data.routers; revision++; render(); document.querySelector('#lab-summary').replaceChildren();
            status.textContent = cases.length + ' ケースを生成しました。期待値と条件を確認して実行してください。' + (data.truncated ? ' 大規模設定のため代表ケースを上限内で抽出しています。' : '') + (data.parse_warning_count ? ' 解析範囲の未確定: ' + data.parse_warning_count + ' 件。' : '');
            const issue=document.querySelector('#lab-issues');issue.replaceChildren(); if(data.parameter_issues.length){const d=node('details',undefined,issue,'lab-parameter');node('summary','設定パラメータの確認箇所: ' + data.parameter_issues.length + ' 件',d);const ul=node('ul',undefined,d);for(const i of data.parameter_issues)node('li',i.scope+' / '+i.target+' — '+i.message,ul);}
        } catch(error){status.textContent=error.message;} finally{setBusy(false);}
    });
    run.addEventListener('click',async()=>{
        if(busy)return;const selected=cases.filter(c=>c.selected!==false);if(!selected.length){status.textContent='実行するケースを選択してください。';return;}
        const generation=revision;setBusy(true);status.textContent='机上テストを実行しています…';
        try{const data=packet();data.set('cases',JSON.stringify(selected));const report=await api('/api/lab/run',data);if(generation!==revision){status.textContent='実行中に条件が変更されたため、結果を破棄しました。再実行してください。';return;}results=new Map(report.results.map(r=>[r.id,r]));const summary=document.querySelector('#lab-summary');summary.replaceChildren();for(const [value,label]of[[report.summary.total,'実行ケース'],[report.summary.attention,'期待値と差異'],[report.summary.review,'未確定']]){const box=node('div',undefined,summary);node('strong',String(value),box);node('small',label,box);}status.textContent='実行完了。差異と未確定から確認してください。許可候補は疎通成功や攻撃検知の保証ではありません。';render();}catch(error){status.textContent=error.message;}finally{setBusy(false);}
    });
    form.addEventListener('change',()=>{if(cases.length){cases=[];results.clear();revision++;render();setBusy(busy);status.textContent='設定または補助 DB が変更されました。テストを再生成してください。';}});
    filter.addEventListener('change',render);
    document.querySelector('#lab-select-all').addEventListener('change',e=>{for(const c of cases)c.selected=e.target.checked;render();});
    document.querySelector('#lab-add').addEventListener('click',()=>{if(busy||cases.length>=200)return;const base=cases[0];cases.push({id:'manual-'+Date.now(),kind:'custom',name:'手動条件',expected:'block',query:{...base.query},reason:'業務要件に合わせて条件と期待値を指定してください。'});invalidate();filter.value='all';render();});
    document.querySelector('#lab-fetch').addEventListener('click',async e=>{e.target.disabled=true;const feedStatus=document.querySelector('#lab-feed-status'), items=document.querySelector('#lab-feed-items');feedStatus.replaceChildren();items.replaceChildren();node('small','公開 Feed を取得しています…',feedStatus);try{const feeds=await Promise.all(['cisa-kev','feodo'].map(key=>api('/api/lab/feeds/'+key)));feedStatus.replaceChildren();for(const feed of feeds){node('small',feed.name+' · '+feed.items.length+' 件 · '+new Date(feed.fetched_at).toLocaleString('ja-JP')+(feed.cached?'（15 分以内のキャッシュ）':''),feedStatus);node('h3',feed.name,items);const ul=node('ul',undefined,items);for(const item of feed.items.slice(0,8))node('li',item.cveID ? item.dateAdded+' / '+item.cveID+' / '+item.vendorProject+' / '+item.vulnerabilityName : item.ip+':'+item.port+' / '+item.malware,ul);}node('small','取得した Feed は次のテスト生成に反映されます。KEV の製品該当性とバージョンは担当者が確認してください。',feedStatus);}catch(error){feedStatus.replaceChildren();node('small',error.message+' 取得済みの片方がある場合は次の生成で利用します。',feedStatus);}finally{e.target.disabled=false;}});
})();

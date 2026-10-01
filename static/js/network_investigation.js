/* Offline investigation only. textContent rendering prevents config-driven HTML injection. */
(function (root) {
    'use strict';
    if(typeof document!=='undefined'){if(root.WallScribeInvestigationInitialized)return;root.WallScribeInvestigationInitialized=true;}
    function ip(text) {
        if (text.includes(':')) {
            if (text.includes('.') || text.includes('%')) throw Error('IPv4 埋込/スコープ付き IPv6 は CLI で確認してください');
            const halves = text.split('::');
            if (halves.length > 2) throw Error('IPv6 の形式が不正です');
            const left = halves[0] ? halves[0].split(':') : [];
            const right = halves.length === 2 && halves[1] ? halves[1].split(':') : [];
            const parts = halves.length === 2 ? [...left, ...Array(8-left.length-right.length).fill('0'), ...right] : left;
            if (parts.length !== 8 || parts.some(p => !/^[0-9a-f]{1,4}$/i.test(p)) || (halves.length === 2 && left.length+right.length >= 8)) throw Error('IPv6 の形式が不正です');
            return {bits:128, value:parts.reduce((v,p) => (v<<16n)+BigInt('0x'+p),0n)};
        }
        const parts=text.split('.');
        if (parts.length!==4 || parts.some(p=>!/^\d{1,3}$/.test(p)||Number(p)>255||String(Number(p))!==p)) throw Error('IP アドレスの形式が不正です');
        return {bits:32,value:parts.reduce((v,p)=>(v<<8n)+BigInt(p),0n)};
    }
    function contains(value, target) {
        const parts=value.trim().replace(/\s+/g,'/').split('/'), address=ip(parts[0]);
        let prefix=parts[1]===undefined ? address.bits : Number(parts[1]);
        if (parts[1] && parts[1].includes('.')) {
            const mask=ip(parts[1]).value.toString(2).padStart(32,'0');
            if (!/^1*0*$/.test(mask)) throw Error('不正なマスク');
            prefix=mask.indexOf('0')<0?32:mask.indexOf('0');
        }
        if (!Number.isInteger(prefix)||prefix<0||prefix>address.bits) throw Error('不正なプレフィックス');
        return {match:address.bits===target.bits && (address.value>>BigInt(address.bits-prefix))===(target.value>>BigInt(address.bits-prefix)),prefix};
    }
    function union(values) {return values.includes(true)?true:!values.length||values.includes(null)?null:false;}
    const lookupCache=new WeakMap();
    function lookup(data,name,scope,keys) {
        if(!lookupCache.has(data)){const indexes={};for(const key of ['addresses','address_groups','services','service_groups']){indexes[key]=new Map();for(const obj of data[key]){const id=JSON.stringify([obj.vdom,obj.name]);if(!indexes[key].has(id))indexes[key].set(id,obj);}}lookupCache.set(data,indexes);}
        for(const owner of [...new Set([scope,'shared'])]) for(const key of keys) {
            const obj=lookupCache.get(data)[key].get(JSON.stringify([owner,name])); if(obj) return obj;
        } return null;
    }
    function resolutionState(scope) {return {originScope:scope,remaining:20000,cycles:0,addresses:new Map(),services:new Map()};}
    function inheritedConflict(data,name,scope,keys,state) {
        if(data.vendor!=='Palo Alto'||scope!=='shared'||state.originScope==='shared')return false;
        const shared=lookup(data,name,'shared',keys),local=lookup(data,name,state.originScope,keys);
        if(!shared||!local||local.vdom!==state.originScope)return false;
        const fields=['members','dynamic_filter','object_type','value','protocol','port','source_port'];
        return fields.some(field=>JSON.stringify(shared[field])!==JSON.stringify(local[field]));
    }
    function resolve(state, cache, cacheKey, seen, key, evaluate) {
        if(--state.remaining<0||seen.includes(key)||seen.length>=128){state.cycles++;return null;}
        if(cache.has(cacheKey))return cache.get(cacheKey);
        const before=state.cycles,result=evaluate();
        // A cycle-dependent unknown is contextual; caching it can hide a later match.
        if(result!==null||before===state.cycles)cache.set(cacheKey,result);
        return result;
    }
    function address(data,name,scope,target,seen=[],state=resolutionState(scope)) {
        const key=JSON.stringify([scope,name]),cacheKey=JSON.stringify([scope,name,target.bits,String(target.value)]);
        return resolve(state,state.addresses,cacheKey,seen,key,()=>{
            if(['any','all'].includes(name.toLowerCase()))return true;
            if(inheritedConflict(data,name,scope,['addresses','address_groups'],state))return null;
            const obj=lookup(data,name,scope,['addresses','address_groups']);
            try {
                if(!obj)return contains(name,target).match;
                if(obj.members)return obj.dynamic_filter?null:union(obj.members.map(n=>address(data,n,obj.vdom,target,[...seen,key],state)));
                if(obj.object_type==='iprange') {
                    const range=obj.value.split('-').map(s=>ip(s.trim()));
                    return range.length===2&&range.every(v=>v.bits===target.bits)?range[0].value<=target.value&&target.value<=range[1].value:null;
                }
                return ['subnet','ip-netmask','ipv6'].includes(obj.object_type)?contains(obj.value,target).match:null;
            }catch(_){return null;}
        });
    }
    function service(data,name,scope,protocol,port,seen=[],state=resolutionState(scope)) {
        const key=JSON.stringify([scope,name]),cacheKey=JSON.stringify([scope,name,protocol,port]);
        return resolve(state,state.services,cacheKey,seen,key,()=>{
            if(['any','all'].includes(name.toLowerCase()))return true;
            if(inheritedConflict(data,name,scope,['services','service_groups'],state))return null;
            const obj=lookup(data,name,scope,['services','service_groups']);if(!obj)return null;
            if(obj.members)return union(obj.members.map(n=>service(data,n,obj.vdom,protocol,port,[...seen,key],state)));
            if(obj.protocol.toUpperCase()!==protocol)return obj.protocol.includes('/')||obj.protocol.toUpperCase()==='IP'?null:false;
            if(obj.source_port||obj.port.includes(':')||!obj.port)return null;
            const ranges=obj.port.trim().split(/[,\s]+/);if(ranges.some(p=>!/^\d+(-\d+)?$/.test(p)))return null;
            const parsed=ranges.map(p=>p.split('-').map(Number));if(parsed.some(v=>v[0]<0||v[v.length-1]>65535||v[0]>v[v.length-1]))return null;return parsed.some(v=>v[0]<=port&&port<=v[v.length-1]);
        });
    }
    function interfaceIdentity(data,scope,actual) {
        if(!actual||['any','all'].includes(actual.toLowerCase()))return null;
        const interfaces=data.interfaces.filter(i=>i.name===actual);
        if(!interfaces.length)return actual;
        const owned=interfaces.filter(i=>i.vdom===scope&&i.vdom_assignment_known);
        if(!owned.length)return null;
        const identities=[...new Set(owned.map(i=>i.zone||(data.vendor==='Palo Alto'?'':i.name)))];
        return identities.length===1&&identities[0]?identities[0]:null;
    }
    function interfaceMatch(data,names,scope,actual) {
        if(names.some(n=>['any','all'].includes(n.toLowerCase())))return true;
        const identity=interfaceIdentity(data,scope,actual);
        return identity===null?null:names.includes(identity)||names.includes(actual);
    }
    function investigate(data,query) {
        const src=ip(query.source),dst=ip(query.destination),protocol=query.protocol.toUpperCase(),port=Number(query.port),scope=query.scope;
        if(src.bits!==dst.bits)throw Error('送信元と宛先の IP バージョンを合わせてください');
        if(!['TCP','UDP'].includes(protocol)||!Number.isInteger(port)||port<1||port>65535)throw Error('TCP/UDP と 1〜65535 のポートを指定してください');
        const policies=[],state=resolutionState(scope);
        data.policies.forEach((p,index)=>{
            if(!p.enabled||p.vdom!==scope)return;
            const invert=(v,n)=>v===null?null:n?!v:v;
            const checks={
                '送信元アドレス':invert(union(p.source_address.map(n=>address(data,n,scope,src,[],state))),p.source_negate),
                '宛先アドレス':invert(union(p.destination_address.map(n=>address(data,n,scope,dst,[],state))),p.destination_negate),
                'サービス':union(p.service.map(n=>service(data,n,scope,protocol,port,[],state)))
            };
            for(const [label,names,actual] of [['送信元 IF/ゾーン',p.source_interface,query.source_interface],['宛先 IF/ゾーン',p.destination_interface,query.destination_interface]]) {
                checks[label]=interfaceMatch(data,names,scope,actual);
            }
            if(p.internet_service_source_enabled)checks['送信元アドレス']=null;
            if(p.internet_service_enabled){checks['宛先アドレス']=null;checks['サービス']=null;}
            if(['intrazone','interzone'].includes(p.rule_type)){
                const sourceZone=interfaceIdentity(data,scope,query.source_interface),destinationZone=interfaceIdentity(data,scope,query.destination_interface);
                const same=sourceZone&&destinationZone?sourceZone===destinationZone:null;
                checks['ゾーン種別']=same===null?null:p.rule_type==='intrazone'?same:!same;
                if(p.rule_type==='intrazone')checks['宛先 IF/ゾーン']=checks['ゾーン種別'];
            }else if(p.rule_type&&p.rule_type!=='universal')checks['ゾーン種別']=null;
            if(Object.values(checks).includes(false))return;
            const evidence=[],unknown=[];
            for(const [label,value]of Object.entries(checks)) (value===true?evidence:unknown).push(label+(value===true?'が一致':'を確定できない（未解決参照・動的条件・入力不足）'));
            if(p.schedule&&p.schedule!=='always')unknown.push('スケジュールの実行時条件');
            if(p.application.some(n=>n.toLowerCase()!=='any'))unknown.push('App-ID の実通信判定');
            if(p.source_users.some(n=>n.toLowerCase()!=='any')||p.source_groups.length)unknown.push('ユーザー/グループの実行時情報');
            if((p.url_categories||[]).some(n=>n.toLowerCase()!=='any'))unknown.push('URL カテゴリの実通信判定');
            if(p.internet_service_name.length||p.internet_service_enabled||p.internet_service_source_enabled)unknown.push('Internet Service DB の実行時情報');
            unknown.push(...p.unmodeled_fields);
            if(data.incomplete)unknown.push('未解析設定があり実効ルール順序は未保証');
            policies.push({order:index+1,scope,policy_id:p.policy_id,name:p.name,action:p.action,status:unknown.length?'needs_review':'static_match',evidence,unknown,nat_enabled:p.nat_enabled,preceding_candidates:policies.map(c=>c.policy_id)});
        });
        const routes=[];
        for(const r of data.routes) {
            if(!r.enabled||(r.vdom_assignment_known&&r.vdom!==scope))continue;
            try {const match=contains(r.destination,dst);if(match.match)routes.push({name:r.name,destination:r.destination,gateway:r.gateway,interface:r.interface,prefix_length:match.prefix,distance:r.distance,priority:r.priority,evidence:'宛先が設定プレフィックス内。稼働状態・優先度の確認が必要',scope_known:r.vdom_assignment_known});}
            catch(_){routes.push({name:r.name,destination:r.destination,evidence:'宛先形式を解釈できないため除外できない',prefix_length:-1});}
        }
        for(const i of data.interfaces) {
            if(i.status==='down'||!i.vdom_assignment_known||i.vdom!==scope)continue;
            for(const value of i.ip_address.split(','))try {const match=contains(value,dst);if(match.match)routes.push({name:'直結候補',destination:value,interface:i.name,prefix_length:match.prefix,evidence:'IF 設定から推定。実際の IF/ARP/ND 状態を確認'});}catch(_){}
        }
        return {query,verdict:'human_review_required',policies,routes:routes.sort((a,b)=>b.prefix_length-a.prefix_length),nat:data.nat.filter(n=>n.enabled&&n.vdom===scope).map(n=>{const checks={};for(const[label,raw,target]of [['変換前送信元',n.original_source,src],['変換前宛先',n.original_destination||n.external_ip,dst]])checks[label]=raw?union(raw.split(',').map(v=>address(data,v.trim(),scope,target,[],state))):null;if(Object.values(checks).includes(false))return null;return {...n,evidence:Object.entries(checks).filter(([,v])=>v===true).map(([k])=>k+'アドレスが一致'),unknown:[...Object.entries(checks).filter(([,v])=>v===null).map(([k])=>k+'の選択条件を確定できない'),'IF/ゾーン・サービス・ポート・適用順序・実効ルールを人が確認。アドレス照合だけでは適用を確定しません']};}).filter(Boolean),limitations:data.limitations};
    }
    root.WallScribeFlow={investigate};
    if(typeof module!=='undefined')module.exports=root.WallScribeFlow;
    if(typeof document==='undefined')return;
    const form=document.getElementById('flow-query');
    if(form)form.addEventListener('submit',event=>{
        event.preventDefault();const output=document.getElementById('flow-result');output.replaceChildren();
        try {
            const data=JSON.parse(document.getElementById('flow-data').textContent),query=Object.fromEntries(new FormData(form));
            const result=investigate(data,query);
            const title=document.createElement('p');title.textContent='最終判断: 人による確認が必要。候補は設定順です。先行する不確定候補がある場合、後続ルールの適用は確定できません。';output.append(title);
            for(const [heading,rows]of [['ポリシー候補',result.policies],['ルート候補（長いプレフィックス順。実効経路は未確定）',result.routes],['NAT 候補（変換前アドレスのみ照合。適用は未確定）',result.nat]]) {
                const h=document.createElement('h4');h.textContent=heading;output.append(h);
                if(!rows.length){const p=document.createElement('p');p.textContent='候補なし（疎通不可の証明ではありません）';output.append(p);}
                for(const row of rows){
                    const card=document.createElement('section');card.className='investigation-card';
                    const title=document.createElement('h5');title.textContent=row.policy_id?'ルール '+row.policy_id+' / '+row.name:(row.name||'名前なし');card.append(title);
                    const add=(label,value)=>{const p=document.createElement('p');p.textContent=label+': '+(value||'不明・未記載');card.append(p);};
                    if(row.policy_id){
                        add('照合結果',row.status==='static_match'?'設定上の条件が一致（実通信は未確認）':'追加確認が必要');
                        add('設定の動作',({allow:'許可',deny:'拒否',drop:'破棄'})[row.action]||'不明');
                        add('設定順',String(row.order));add('先行する候補',row.preceding_candidates.join(', ')||'なし');
                        add('ルール内 NAT',row.nat_enabled?'有効（適用条件を確認）':'モデル上は無効（既定値の検証状況を確認）');
                    }else if(row.prefix_length!==undefined){
                        add('宛先ネットワーク',row.destination);add('出力 IF',row.interface);add('ゲートウェイ',row.gateway);add('Distance / Priority',[row.distance,row.priority].filter(Boolean).join(' / '));
                        if(row.scope_known===false)add('所属','vsys 所属未確定');
                    }else{
                        add('NAT 種別',row.nat_type);add('変換前送信元',row.original_source);add('変換前宛先',row.original_destination||row.external_ip);
                        add('変換後送信元',row.translated_source);add('変換後宛先',row.translated_destination||row.internal_ip);
                        add('IF / ゾーン',row.interface||row.external_interface);add('ポート変換',[row.original_port,row.translated_port].filter(Boolean).join(' → '));
                    }
                    for(const [label,values]of [['一致の根拠',Array.isArray(row.evidence)?row.evidence:row.evidence?[row.evidence]:[]],['人に確認してほしいこと',row.unknown||[]]]) {
                        if(!values.length)continue;const h=document.createElement('strong');h.textContent=label;card.append(h);const ul=document.createElement('ul');for(const text of values){const li=document.createElement('li');li.textContent=text;ul.append(li);}card.append(ul);
                    }
                    output.append(card);
                }
            }
        }catch(error){output.textContent=error.message;}
    });

})(typeof globalThis==='undefined'?this:globalThis);

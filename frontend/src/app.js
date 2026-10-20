import { createClient } from 'genlayer-js';
import { studionet } from 'genlayer-js/chains';
import { TransactionHashVariant } from 'genlayer-js/types';
import { keccak256, stringToHex } from 'viem';
import './styles.css';

const ADDRESS = (import.meta.env.VITE_CONTRACT_ADDRESS || '').trim();
const EXPLORER = 'https://explorer-studio.genlayer.com';
const RPC = 'https://studio.genlayer.com/api';
const CHAIN_ID = '0xf22f';
const CHAIN_DEC = 61999;
const addressOk = /^0x[0-9a-fA-F]{40}$/.test(ADDRESS);
const readClient = createClient({ chain: studionet });
const FINAL = TransactionHashVariant.LATEST_FINAL;
const statusText = {
  0: 'PENDING', 1: 'AFFECTED', 2: 'NOT AFFECTED', 3: 'UNCERTAIN',
  4: 'UNDER APPEAL', 5: 'REMEDY REVIEW', 6: 'REMEDIATED', 7: 'STALE'
};
const noticeStates = { 0: 'AWAITING VERIFICATION', 1: 'VERIFIED', 2: 'REJECTED' };
const views = ['Overview', 'Asset registry', 'Recall notices', 'Case adjudication', 'Remediation', 'Network & proofs'];
let active = 'Overview';
let wallet = null;
let chain = null;
let alertMessage = '';
let busy = false;
let data = { stats: null, assets: [], notices: [], cases: [], fetchedAt: null };
let inflight = 0;
const remembered = localStorage.getItem('recallcircuit.wallet');
const $ = (id) => document.getElementById(id);
const safe = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
const short = (s) => s ? `${String(s).slice(0,7)}…${String(s).slice(-5)}` : '—';
const abbr = (s, len=92) => String(s ?? '').length > len ? `${String(s).slice(0,len-1)}…` : String(s ?? '');
const explorerAddress = (a) => `${EXPLORER}/address/${encodeURIComponent(a)}`;
const explorerTx = (h) => `${EXPLORER}/tx/${encodeURIComponent(h)}`;
const badge = (label, mood='neutral') => `<span class="pill pill-${mood}">${safe(label)}</span>`;
const statusPill = (state) => badge(statusText[state] || 'UNKNOWN', state===1?'danger':state===2||state===6?'good':'warn');
const noticePill = (state) => badge(noticeStates[state] || 'UNKNOWN',state===1?'good':'warn');
const stat = (value,label) => `<div class="stat"><b>${safe(value ?? '—')}</b><span>${safe(label)}</span></div>`;
const field = (name,label,type='text',placeholder='',required=true) => `<label>${safe(label)}<input ${required?'required':''} type="${type}" name="${safe(name)}" placeholder="${safe(placeholder)}" autocomplete="off" /></label>`;
const action = (method,title,fields,summary='') => `<form class="form-card" data-method="${safe(method)}"><div class="form-head"><h3>${safe(title)}</h3><p>${safe(summary)}</p></div><div class="form-grid">${fields}</div><button class="primary" ${busy||!wallet||chain!==CHAIN_ID||!addressOk?'disabled':''} type="submit">Submit on StudioNet <span aria-hidden="true">↗</span></button></form>`;

function nav() {
  return `<aside class="sidebar"><div class="brand"><div class="brand-mark">✳</div><div><strong>RecallCircuit</strong><small>INTELLIGENT SAFETY PROTOCOL</small></div></div>
   <div class="nav-label">WORKSPACE</div><nav>${views.map((v,i)=>`<button type="button" data-nav="${safe(v)}" class="nav-item ${v===active?'selected':''}"><span class="nav-dot">${['◈','▦','≋','⚖','✣','⌘'][i]}</span>${safe(v)}</button>`).join('')}</nav>
   <div class="sidebar-bottom"><div class="small-overline">ACTIVE ENVIRONMENT</div><b>StudioNet <span class="inline-dot"></span></b><p>Chain 61999 · Latest final state</p><a href="${EXPLORER}" target="_blank" rel="noopener noreferrer">Open block explorer ↗</a></div></aside>`;
}
function header() {
  const w = wallet ? `<span class="wallet-label">${safe(short(wallet))}</span>` : 'Connect wallet';
  return `<header class="topbar"><div class="breadcrumb">RECALLCIRCUIT <span>/</span> <b>${safe(active.toUpperCase())}</b></div><div class="top-actions">${badge(chain===CHAIN_ID?'StudioNet 61999':wallet?'Wrong chain':'Read-only',chain===CHAIN_ID?'good':'warn')}<button class="wallet-button" id="walletBtn">${w}<span class="chevron">⌄</span></button><button class="icon-btn" id="refreshBtn" title="Refresh finalized chain state" aria-label="Refresh finalized chain state">↻</button></div></header>`;
}
function overview() {
  const s=data.stats||{};
  const held=data.assets.filter(a=>a.release===false).length;
  return `<section class="hero"><div class="hero-copy"><div class="eyebrow"><span class="halo"></span> GENLAYER INTELLIGENT CONTRACT</div><h1>Safety doesn't stop<br/>at the <em>recall notice.</em></h1><p>Independent AI consensus translates official recall notices into enforceable product-level holds. Track every scope decision, component dependency, appeal and remedy—directly from StudioNet.</p><button class="light-btn" data-go="Asset registry">Inspect asset registry <span>↗</span></button></div><div class="hero-art" aria-hidden="true"><div class="outer-orbit"><div class="inner-orbit"><div class="hero-core">✳</div></div></div><div class="orbit-badge one">VERIFIED</div><div class="orbit-badge two">HOLD / CLEAR</div></div></section>
  <div class="metrics">${stat(s.assets,'Registered assets')}${stat(s.notices,'Recall notices')}${stat(s.cases,'Review cases')}${stat(data.fetchedAt?held:'—','Not release-eligible')}</div>
  <div class="two-col"><article class="panel"><div class="section-top"><div><div class="small-overline">CURRENT CHAIN STATE</div><h2>Asset health</h2></div><button class="text-btn" data-go="Asset registry">View all ↗</button></div>${assetRows(data.assets.slice(0,5))}</article>
  <article class="panel"><div class="section-top"><div><div class="small-overline">INDEPENDENT JURY</div><h2>Notice review</h2></div><button class="text-btn" data-go="Recall notices">All notices ↗</button></div>${noticeRows(data.notices.slice(0,5))}</article></div>
  <div class="note"><b>Scope matters.</b> A clearance means only that an asset was found outside a particular verified recall, not that the product is universally safe. Unassessed inventory is not certified.</div>`;
}
function assetRows(items) {
  if(!items.length) return `<div class="empty"><div class="empty-icon">▤</div>No finalized assets found.<p>Register an asset or configure a deployed contract address.</p></div>`;
  return `<div class="list-rows">${items.map(x=>`<div class="list-row"><div class="circle-icon">▦</div><div class="row-main"><b>${safe(x.name)}</b><small>${safe(x.manufacturer)} · ${safe(x.model)} · ${safe(x.batch)}</small></div><div class="row-end">${x.release?badge('ELIGIBLE','good'):badge('HOLD / NO COVERAGE','warn')}<small>Asset #${safe(x.id)}</small></div></div>`).join('')}</div>`;
}
function noticeRows(items) {
 if(!items.length) return `<div class="empty"><div class="empty-icon">≋</div>No finalized recall notices found.<p>Submit a CPSC notice to begin verified assessment.</p></div>`;
 return `<div class="list-rows">${items.map(n=>`<div class="list-row"><div class="circle-icon">≋</div><div class="row-main"><b>${safe(abbr(n.title||n.source_url,48))}</b><small>${safe(n.official_id||'Pending source verification')} · Notice #${safe(n.id)}</small></div><div class="row-end">${noticePill(n.status)}<a href="${safe(n.source_url)}" target="_blank" rel="noopener noreferrer">Official source ↗</a></div></div>`).join('')}</div>`;
}
function caseRows(items){
 if(!items.length) return `<div class="empty"><div class="empty-icon">⚖</div>No adjudicated cases yet.<p>Open an asset-notice case to initiate consensus review.</p></div>`;
 return `<div class="case-grid">${items.map(c=>`<article class="case-card"><div class="case-top"><span>CASE #${safe(c.id)}</span>${statusPill(c.status)}</div><h3>Asset ${safe(c.asset_id)} <span>·</span> Notice ${safe(c.notice_id)}</h3><p>${safe(c.reason||'Awaiting independent validator assessment')}</p><div class="case-bottom"><span>Appeals: ${safe(c.appeal_count)}</span><button class="text-btn" data-copy="${safe(c.decision_hash||'')}" ${!c.decision_hash?'disabled':''}>Copy decision hash ↗</button></div></article>`).join('')}</div>`;
}
function registry() { return `<div class="page-intro"><div class="eyebrow">01 / REGISTER</div><h1>Asset registry</h1><p>Version-locked product identities and component relationships. A product cannot silently change its dependency graph after a case is opened.</p></div>${action('register_asset','Register product or component',[
 field('name','Product name'), field('manufacturer','Manufacturer'),field('model','Model / SKU'),field('batch','Batch identifier'),field('serial','Serial number'),field('made_on','Manufacturing date / range'),field('auditor','Independent auditor address','text','0x...')].join(''),'Auditors must be separate wallet addresses and accept their appointment.')}
 <div class="two-col forms">${action('link_component','Link component',field('parent_id','Assembled product ID','number')+field('component_id','Component asset ID','number'),'Components must share the same owner. Loops are rejected.')}${action('accept_auditor','Accept audit appointment',field('aid','Asset ID','number'),'The configured auditor signs this transaction.')}</div>
 <div class="two-col forms">${action('freeze_asset','Emergency freeze',field('aid','Asset ID','number'),'Immediately blocks release through registered gates.')}${action('unfreeze_asset','Lift owner freeze',field('aid','Asset ID','number'),'Will fail while any recall case or component safety hold remains.')}</div><article class="panel"><div class="section-top"><h2>Registered inventory</h2><span class="muted">Latest finalized state</span></div>${assetRows(data.assets)}</article>`; }
function notices(){ return `<div class="page-intro"><div class="eyebrow">02 / VERIFY</div><h1>Official recall notices</h1><p>Only official CPSC recall URLs are accepted. Validators independently fetch the regulator source and verify structured identifiers before it can be used in cases.</p></div>
 ${action('propose_notice','Submit or revise a notice',field('source_url','Official CPSC recall URL','url','https://www.cpsc.gov/Recalls/...')+field('parent_id','Parent notice ID (0 for new)','number','0'),'Revisions do not supersede earlier evidence until the replacement independently verifies.')}
 ${action('verify_notice','Consensus-verify notice',field('nid','Notice ID','number'),'Triggers live web access and validator agreement.')}
 <article class="panel"><div class="section-top"><h2>Official notice ledger</h2><span class="muted">Auditable source links</span></div>${noticeRows(data.notices)}</article>`; }
function cases(){return `<div class="page-intro"><div class="eyebrow">03 / ADJUDICATE</div><h1>Consensus casework</h1><p>Every applicability result is specific to one asset and one regulator notice. Uncertain outcomes remain blocked until stronger evidence is established.</p></div>
 <div class="two-col forms">${action('open_case','Open a product case',field('aid','Asset ID','number')+field('nid','Verified notice ID','number'),'Immediately places this covered case in a pending hold.')}${action('resolve_case','Run independent assessment',field('cid','Case ID','number'),'Validators re-fetch source data and independently derive the outcome.')}</div>
 ${action('appeal_case','Appeal a verdict',field('cid','Case ID','number')+`<label class="wide">Grounds for appeal<textarea required name="grounds" rows="3" placeholder="Describe the specific model, batch or date issue"></textarea></label>`,'Appeal instantly places the case on hold. Re-run case resolution for a fresh verdict.')}
 <article class="panel"><div class="section-top"><h2>Review ledger</h2><span class="muted">Live verdicts and unresolved holds</span></div>${caseRows(data.cases)}</article>`;}
function remedies(){return `<div class="page-intro"><div class="eyebrow">04 / REMEDIATE</div><h1>Safe return to circulation</h1><p>A manufacturer cannot self-certify a repaired recalled product. An accepted independent auditor must attest to the evidence commitment, and validators must verify the remedy against the official notice.</p></div>
 ${action('propose_remedy','Submit remediation evidence',field('cid','Affected case ID','number')+field('proof_url','Public HTTPS evidence URL','url'),'This enters a safety hold until an auditor attests and validators agree.')}
 ${action('attest_remedy','Auditor attestation',field('cid','Case ID','number')+field('proof_hash','Committed evidence URL hash','text','0x...')+`<label class="wide"><span>Auditor decision</span><select name="approved" required><option value="true">Approve attestation</option><option value="false">Reject</option></select></label>`,'Auditor only: the hash is Keccak-256 of the canonical JSON string of the exact proof URL.')}
 <div class="helper"><b>Generate the URL commitment</b><div class="hash-tools"><input id="hashUrl" type="url" placeholder="https://example.com/remedy/product-123"/><button type="button" id="hashBtn" class="outline-btn">Generate and copy hash</button></div><code id="hashOut">No commitment generated</code></div>
 ${action('resolve_remedy','Adjudicate proposed remedy',field('cid','Remedy case ID','number'),'Even with auditor approval, consensus can reject insufficient evidence.')}`;}
function network(){return `<div class="page-intro"><div class="eyebrow">05 / VERIFY</div><h1>Network & proofs</h1><p>Every finalized decision should have a verifiable transaction hash and onchain state readback. This interface never treats a wallet popup as finalized proof.</p></div>
 <div class="two-col"><article class="panel"><h2>Chain configuration</h2><dl class="facts"><dt>Network</dt><dd>StudioNet</dd><dt>Chain ID</dt><dd>61999 (0xF22F)</dd><dt>RPC</dt><dd><code>${RPC}</code></dd><dt>Contract</dt><dd><code>${safe(ADDRESS || 'Not configured')}</code></dd><dt>Final-state policy</dt><dd>Latest final only</dd><dt>Wallet</dt><dd>${safe(wallet || 'Disconnected')}</dd></dl><button class="outline-btn" id="switchBtn">Switch injected wallet to StudioNet</button></article>
 <article class="panel"><h2>Production proofs</h2><p class="muted">Only real finalized receipts count. Deployment and lifecycle proof will be recorded by Claude after live deployment. No sample proof is presented as fact.</p><a class="outline-link" href="${EXPLORER}" target="_blank" rel="noopener noreferrer">Open StudioNet explorer ↗</a><a class="outline-link" href="https://github.com/Chinny070/RecallCircuit" target="_blank" rel="noopener noreferrer">Source repository ↗</a></article></div><article class="panel caution-panel"><h2>Safety boundaries</h2><p>RecallCircuit is an onchain scope and release-gating prototype, not an official CPSC service, universal product-safety certification, or proof of a physical repair. Registering or clearing a case never guarantees that no other recalls apply. Only downstream integrations actually enforce release restrictions.</p></article>`;}
function content(){return ({'Overview':overview,'Asset registry':registry,'Recall notices':notices,'Case adjudication':cases,'Remediation':remedies,'Network & proofs':network})[active]();}
function walletMenu(){return `<div class="wallet-menu" id="walletMenu" role="dialog" aria-label="Wallet actions"><h3>Injected wallet</h3><p>${safe(wallet||'Not connected')}</p>${wallet?`<button id="copyWallet">Copy address</button><button id="switchNetwork">Switch to StudioNet</button><button id="disconnectWallet">Disconnect from app</button>`:`<button id="connectInjected">Connect injected wallet</button>`}</div>`;}
function render(){
 $('app').innerHTML = `<div class="shell">${nav()}<div class="workspace">${header()}<main class="main">${!addressOk?`<div class="config-alert">No deployed contract is configured. Set <code>VITE_CONTRACT_ADDRESS</code> to a verified StudioNet contract address. This interface will not fabricate ledger data.</div>`:''}${wallet&&chain!==CHAIN_ID?`<div class="config-alert">Your injected wallet is not on StudioNet 61999. Switch networks before writing. <button class="text-btn" id="inlineSwitch">Switch now ↗</button></div>`:''}${alertMessage?`<div class="info-alert" role="status">${safe(alertMessage)}<button id="clearAlert" aria-label="Dismiss message">×</button></div>`:''}${content()}<footer>RecallCircuit · GenLayer StudioNet · No mock chain data · Source-scoped decisions</footer></main></div></div>${walletMenu()}`;
 bind();
}
function toggleWalletMenu(){ $('walletMenu')?.classList.toggle('open'); }
function bind(){
 document.querySelectorAll('[data-nav],[data-go]').forEach(el=>el.addEventListener('click',()=>{active=el.dataset.nav||el.dataset.go;render();window.scrollTo(0,0);}));
 $('walletBtn')?.addEventListener('click',toggleWalletMenu);
 $('connectInjected')?.addEventListener('click',connectWallet);
 $('disconnectWallet')?.addEventListener('click',disconnect);
 $('copyWallet')?.addEventListener('click',()=>navigator.clipboard.writeText(wallet||'').then(()=>show('Wallet address copied.')).catch(()=>show('Could not copy.')));
 ['switchNetwork','switchBtn','inlineSwitch'].forEach(id=>$(id)?.addEventListener('click',switchNetwork));
 $('refreshBtn')?.addEventListener('click',refresh);
 $('clearAlert')?.addEventListener('click',()=>{alertMessage='';render();});
 $('hashBtn')?.addEventListener('click',()=>{const url=($('hashUrl')?.value||'').trim();if(!url.startsWith('https://'))return show('Enter a public HTTPS evidence URL.');const hash=keccak256(stringToHex(JSON.stringify(url)));$('hashOut').textContent=hash;navigator.clipboard?.writeText(hash).catch(()=>{});});
 document.querySelectorAll('[data-copy]').forEach(el=>el.addEventListener('click',()=>navigator.clipboard.writeText(el.dataset.copy).then(()=>show('Decision hash copied.'))));
 document.querySelectorAll('form[data-method]').forEach(el=>el.addEventListener('submit',submit));
}
function show(message){alertMessage=message;render();}
async function syncWallet(silent=true){
 try{
   const e=window.ethereum;
   if(!e){wallet=null;chain=null; if(!silent)show('No injected wallet found. Install MetaMask or Rabby.');return;}
   const addresses=await e.request({method:'eth_accounts'});
   chain=String(await e.request({method:'eth_chainId'})).toLowerCase();
   wallet=addresses.length ? String(addresses[0]) : null;
   if(!wallet) localStorage.removeItem('recallcircuit.wallet');
   else localStorage.setItem('recallcircuit.wallet',wallet);
   render();
 }catch(err){wallet=null;chain=null;if(!silent)show(`Wallet error: ${err.message||err}`);}
}
async function connectWallet(){
 if(!window.ethereum){show('No injected wallet found. Please install a compatible wallet.');return;}
 try{const arr=await window.ethereum.request({method:'eth_requestAccounts'});wallet=arr[0]||null;localStorage.setItem('recallcircuit.wallet',wallet||'');await syncWallet();}catch(e){show(`Wallet connection was not completed: ${e.message||e}`);}
}
function disconnect(){wallet=null;localStorage.removeItem('recallcircuit.wallet');render();}
async function switchNetwork(){
 if(!window.ethereum){show('No injected wallet found.');return;}
 try{await window.ethereum.request({method:'wallet_switchEthereumChain',params:[{chainId:CHAIN_ID}]});await syncWallet();}
 catch(err){
   if(err.code!==4902){show(`Network switch failed: ${err.message||err}`);return;}
   try{await window.ethereum.request({method:'wallet_addEthereumChain',params:[{chainId:CHAIN_ID,chainName:'GenLayer StudioNet',nativeCurrency:{name:'GEN',symbol:'GEN',decimals:18},rpcUrls:[RPC],blockExplorerUrls:[EXPLORER]}]});await syncWallet();}
   catch(e){show(`Network addition failed: ${e.message||e}`);}
 }
}
const uintMethods = {
  link_component:['parent_id','component_id'],accept_auditor:['aid'],freeze_asset:['aid'],
  unfreeze_asset:['aid'],propose_notice:['parent_id'],verify_notice:['nid'],
  open_case:['aid','nid'],resolve_case:['cid'],appeal_case:['cid'],
  propose_remedy:['cid'],attest_remedy:['cid'],resolve_remedy:['cid']
};
const methodKeys = {
 register_asset:['name','manufacturer','model','batch','serial','made_on','auditor'],
 link_component:['parent_id','component_id'],accept_auditor:['aid'],
 freeze_asset:['aid'],unfreeze_asset:['aid'], propose_notice:['source_url','parent_id'],
 verify_notice:['nid'],open_case:['aid','nid'],resolve_case:['cid'],
 appeal_case:['cid','grounds'],propose_remedy:['cid','proof_url'],
 attest_remedy:['cid','approved','proof_hash'],resolve_remedy:['cid']
};
async function submit(event){
 event.preventDefault();
 if(busy)return;
 const form=event.currentTarget,method=form.dataset.method;
 if(!methodKeys[method])return show('Unsupported contract method.');
 if(!addressOk)return show('Configure the StudioNet contract address first.');
 if(!wallet)return show('Connect an injected wallet first.');
 if(chain!==CHAIN_ID)return show('Switch your wallet to StudioNet 61999 first.');
 const values=Object.fromEntries(new FormData(form).entries());
 let args;
 try{args=methodKeys[method].map(k=>{
   const value=String(values[k]||'').trim();
   if((uintMethods[method]||[]).includes(k)){
     if(!/^\d+$/.test(value))throw Error(`${k} must be a positive integer (or 0 for a new notice).`);
     return BigInt(value);
   }
   if(method==='attest_remedy'&&k==='approved')return value==='true';
   if(!value)throw Error(`Missing field: ${k}`);
   return value;
 });}catch(err){return show(err.message);}
 busy=true;render();
 try{
   await syncWallet();
   if(!wallet||chain!==CHAIN_ID)throw Error('Wallet state changed. Reconnect or switch network.');
   const client=createClient({chain:studionet,account:wallet,provider:window.ethereum});
   const call={address:ADDRESS,functionName:method,args};
   const estimate=await client.estimateTransactionFeesForWrite(call);
   await syncWallet();
   if(!wallet||chain!==CHAIN_ID)throw Error('Wallet or chain changed before signing.');
   const tx=await client.writeContract({...call, fees:{distribution:estimate.distribution,feeValue:estimate.feeValue}});
   alertMessage=`Transaction submitted: ${tx}. Awaiting finalization; no verdict has been assumed.`;render();
   await readClient.waitForFinalization({hash:tx});
   alertMessage=`Finalization returned for ${tx}. Refreshing latest-final state; inspect explorer execution result as well.`;
   await refresh();
 }catch(err){alertMessage=`${method} was not confirmed: ${err?.shortMessage||err?.message||err}`;render();}
 finally{busy=false;render();}
}
async function read(method,id){return readClient.readContract({address:ADDRESS,functionName:method,args:id===undefined?[]:[BigInt(id)],transactionHashVariant:FINAL,jsonSafeReturn:true});}
async function refresh(){
 if(!addressOk)return;
 const token=++inflight;
 try{
   const stats=await read('get_stats');
   const cap=(n,max)=>Math.min(Number(n)||0,max);
   const ids=(n)=>Array.from({length:n},(_,i)=>i+1);
   const [assets,notices,cases]=await Promise.all([
     Promise.all(ids(cap(stats.assets,256)).map(async id=>{const obj=await read('get_asset',id);let release=false;try{release=Boolean(await read('is_release_allowed',id));}catch{}return {...obj,release};})),
     Promise.all(ids(cap(stats.notices,64)).map(id=>read('get_notice',id))),
     Promise.all(ids(cap(stats.cases,512)).map(id=>read('get_case',id))),
   ]);
   if(token!==inflight)return;
   data={stats,assets,notices,cases,fetchedAt:Date.now()};render();
 }catch(err){if(token===inflight){alertMessage=`Could not read finalized contract state: ${err.message||err}`;render();}}
}
render();
if(window.ethereum){
 window.ethereum.on?.('accountsChanged',()=>{syncWallet();});
 window.ethereum.on?.('chainChanged',()=>{syncWallet();});
 if(remembered)syncWallet();
}
refresh();

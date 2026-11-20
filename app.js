/* ====== កែ ២ បន្ទាត់នេះ ====== */
var API = 'https://webseit-top-up.onrender.com/api';
var BOT = 'webseit_topup_game_bot';                      
/* ============================== */

var T=null,U=null,G=[],sel=null,msg='',slide=0,poll=null;
try{T=localStorage.getItem('gt')}catch(e){}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function $(n){return '$'+Number(n).toFixed(2)}
function gm(id){return G.filter(function(x){return x.id==id})[0]}
async function api(p,o){o=o||{};var h={'Content-Type':'application/json'};if(T)h.Authorization='Bearer '+T;
 var r=await fetch(API+p,{method:o.method||'GET',headers:h,body:o.body?JSON.stringify(o.body):undefined});
 var d={};try{d=await r.json()}catch(e){}
 if(r.status==401&&T){T=null;U=null;try{localStorage.removeItem('gt')}catch(e){}}
 if(!r.ok){var er=new Error(d.error||'HTTP '+r.status);er.status=r.status;throw er}return d}

window.onTg=async function(u){try{var d=await api('/auth/telegram',{method:'POST',body:u});T=d.token;U=d.user;try{localStorage.setItem('gt',T)}catch(e){}go('#shop')}catch(e){msg='<span class="er">'+esc(e.message)+'</span>';render()}};
function tgWidget(){var el=document.getElementById('tg');if(!el)return;var s=document.createElement('script');s.async=true;s.src='https://telegram.org/js/telegram-widget.js?22';
 s.setAttribute('data-telegram-login',BOT);s.setAttribute('data-size','large');s.setAttribute('data-radius','12');s.setAttribute('data-onauth','onTg(user)');s.setAttribute('data-request-access','write');el.appendChild(s)}
var LOCAL=/localhost|127\.0\.0\.1/.test(API);
async function devLogin(a){try{var d=await api('/dev/login',{method:'POST',body:{admin:a}});T=d.token;U=d.user;try{localStorage.setItem('gt',T)}catch(e){}go(a?'#admin':'#shop')}catch(e){msg='<span class="er">'+esc(e.message)+'</span>';render()}}
async function devCredit(){var d=await api('/dev/credit',{method:'POST'});U.wallet=d.wallet;render()}
function logout(){T=null;U=null;try{localStorage.removeItem('gt')}catch(e){}go('#shop')}
function go(h){if(location.hash==h)render();else location.hash=h}

function art(g){return '<div class="art" style="background:linear-gradient(135deg,'+g.colors+')">'+g.emoji+(g.flag?'<span class="flag">'+g.flag+'</span>':'')+(g.maint?'<span class="mt">កំពុងថែទាំ</span>':'')+'</div>'}
function banner(){
 var s=[['⚔️','តម្លៃសមរម្យ សុវត្ថិភាព រហ័សទាន់ចិត្ត','Mobile Legends · Free Fire · PUBG','#2742c9,#6a3df0'],['💎','បញ្ចូល Diamond ក្នុងរយៈពេលតែប៉ុន្មានវិនាទី','Top-up ស្វ័យប្រវត្តិ ២៤/៧','#0b6e99,#2742c9'],['🎁','បញ្ចូលលុយតាម KHQR','ABA · Bakong · គ្រប់ធនាគារ','#8e24aa,#2742c9']];
 return '<div class="banner" id="bn">'+s.map(function(x,i){return '<div class="sl'+(i?'':' on')+'" style="background:linear-gradient(120deg,'+x[3]+')"><span class="big">'+x[0]+'</span><b>'+x[1]+'</b><span>'+x[2]+'</span></div>'}).join('')+'<div class="acc">WE ACCEPT <em>ABA PAY</em> <em>KHQR</em></div><div class="dots">'+s.map(function(x,i){return '<u'+(i?'':' class="on"')+'></u>'}).join('')+'</div></div>'}
setInterval(function(){var b=document.getElementById('bn');if(!b)return;var a=b.querySelectorAll('.sl'),d=b.querySelectorAll('u');slide=(slide+1)%a.length;for(var i=0;i<a.length;i++){a[i].className='sl'+(i==slide?' on':'');d[i].className=i==slide?'on':''}},4000);

async function render(){
 var h=location.hash||'#shop',t=[['#shop','ទំព័រដើម'],['#wallet','កាបូប'],['#orders','ប្រវត្តិ']];
 if(U&&U.admin)t.push(['#admin','Admin']);
 document.getElementById('nav').innerHTML=t.map(function(x){return '<a href="'+x[0]+'"'+(h.indexOf(x[0])==0?' class="on"':'')+'>'+x[1]+'</a>'}).join('');
 document.getElementById('who').innerHTML=U?'<b style="color:var(--gd)">'+$(U.wallet)+'</b>':'<a class="btn" style="text-decoration:none;padding:8px 14px" href="#login">ចូលគណនី</a>';
 var a=document.getElementById('app'),m=msg?'<div class="msg">'+msg+'</div>':'';msg='';clearInterval(poll);
 try{
  if(!U&&(h=='#wallet'||h=='#orders'||h=='#admin'||h=='#login')){a.innerHTML=m+login();tgWidget();return}
  var b;
  if(h=='#wallet')b=wallet();else if(h=='#orders')b=await orders();else if(h=='#admin'&&U.admin)b=await admin();
  else if(h.indexOf('#g-')==0&&gm(h.slice(3)))b=detail(gm(h.slice(3)));else b=home();
  a.innerHTML=m+b;
 }catch(e){a.innerHTML=m+'<div class="msg er">'+esc(e.message)+'</div>'}}
function login(){return '<div class="pnl" style="max-width:420px;margin:40px auto;text-align:center"><div style="font-size:56px">⚡</div><h2 style="justify-content:center">ចូលប្រើប្រាស់</h2><p class="muted">ចូលតាម Telegram ដើម្បីទិញ Diamond និងគ្រប់គ្រងកាបូប។</p><div id="tg" style="display:flex;justify-content:center;min-height:44px"></div>'+(LOCAL?'<p><button class="btn alt" onclick="devLogin(false)">Dev login (user)</button> <button class="btn alt" onclick="devLogin(true)">Dev login (admin)</button></p>':'')+'</div>'}

function home(){
 if(!G.length)return banner()+'<div class="msg er" style="margin-top:20px">មិនទាន់ទទួលបានបញ្ជីហ្គេមពី backend។ សូមពិនិត្យថា <b>python app.py</b> កំពុងរត់ ហើយ API នៅ <b>'+esc(API)+'</b> ត្រឹមត្រូវ។ (ចុច F12 &rarr; Console ដើម្បីមើលកំហុស)</div>';
 return banner()+'<h2>ព្រឹត្តិការណ៍ពិសេស</h2><div class="ev">'+G.slice(0,3).map(function(g){return '<a href="#g-'+g.id+'" style="text-decoration:none">'+art(g)+'</a>'}).join('')+'</div><h2>ហ្គេមពេញនិយម</h2><div class="grid">'+G.map(function(g){return '<div class="card">'+art(g)+'<h3>'+esc(g.name)+'</h3><button class="btn"'+(g.maint?' disabled':'')+' onclick="sel=null;go(\'#g-'+g.id+'\')">⚡ '+(g.maint?'កំពុងថែទាំ':'បញ្ចូលទឹកប្រាក់')+'</button></div>'}).join('')+'</div>'}
function detail(g){
 return '<h2>'+esc(g.name)+'</h2><div class="pnl"><label for="uid">User ID ហ្គេម</label><input id="uid" placeholder="ឧ. 12345678 (1234)"></div><div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(230px,1fr))">'+g.packs.map(function(p,i){return '<button class="pk'+(sel===i?' sel':'')+'" onclick="pickPack('+i+')"><span>'+esc(p.name)+'</span><b class="pe">'+$(p.price)+'</b></button>'}).join('')+'</div><p><button class="btn" onclick="buy(\''+g.id+'\')"'+(sel===null||g.maint?' disabled':'')+'>ទិញឥឡូវ</button> <button class="btn alt" onclick="go(\'#shop\')">ត្រឡប់ក្រោយ</button></p>'}
function pickPack(i){var v=document.getElementById('uid').value;sel=i;render().then(function(){document.getElementById('uid').value=v})}
async function buy(id){
 if(!U){msg='<span class="pe">សូមចូលគណនីមុនពេលទិញ</span>';go('#login');return}
 var uid=document.getElementById('uid').value.trim();
 if(!uid){msg='<span class="er">សូមបញ្ចូល User ID</span>';render();return}
 try{var d=await api('/orders',{method:'POST',body:{game_id:id,pack:sel,player_id:uid}});U.wallet=d.wallet;sel=null;msg='កំពុងដំណើរការ #'+d.order_id+' ...';go('#orders')}
 catch(e){msg='<span class="er">'+esc(e.message)+'</span>';if(e.status==402)go('#wallet');else render()}}

function wallet(){return '<h2>កាបូបរបស់ខ្ញុំ</h2><div class="pnl row"><div><div class="muted">សមតុល្យ</div><div class="bal">'+$(U.wallet)+'</div></div><button class="btn alt" style="margin-left:auto" onclick="logout()">ចាកចេញ</button></div><h2>បញ្ចូលលុយតាម KHQR</h2><div class="pnl"><label for="amt">ចំនួនទឹកប្រាក់ (USD)</label><div class="row"><input id="amt" type="number" min="1" value="5" style="max-width:160px"><button class="btn" onclick="showQR()">បង្កើត KHQR</button></div><div id="qr"></div>'+(LOCAL?'<p><button class="btn alt" onclick="devCredit()">Dev: +$10 ក្លែង</button></p>':'')+'</div>'}
async function showQR(){
 var a=parseFloat(document.getElementById('amt').value);if(!(a>=1))return;var q=document.getElementById('qr');q.textContent='កំពុងបង្កើត...';
 try{var d=await api('/wallet/khqr',{method:'POST',body:{amount:a}});
  q.innerHTML=(d.qr_url?'<p class="qr"><img src="'+esc(d.qr_url)+'" width="220" alt="KHQR"></p>':'')+(d.payment_url?'<p><a class="btn" style="display:inline-block;text-decoration:none" target="_blank" rel="noopener" href="'+esc(d.payment_url)+'">បើកទំព័របង់ប្រាក់</a></p>':'')+'<p class="muted">ស្កេនជាមួយ ABA / Bakong។ ប្រព័ន្ធនឹងបញ្ចូលលុយដោយស្វ័យប្រវត្តិ។</p>';
  var n=0;clearInterval(poll);poll=setInterval(async function(){try{var s=await api('/wallet/deposit/'+d.txn);
   if(s.status=='paid'){clearInterval(poll);U.wallet=s.wallet;msg='<span class="ok">បញ្ចូលបាន '+$(a)+'</span>';render()}else if(s.status=='expired'||++n>150)clearInterval(poll)}catch(e){}},4000)}
 catch(e){q.innerHTML='<p class="er">'+esc(e.message)+'</p>'}}

var ST={pending:['រង់ចាំ','pe'],processing:['កំពុងដំណើរការ','pe'],success:['ជោគជ័យ','ok'],failed:['បរាជ័យ (សងលុយវិញ)','er'],review:['កំពុងត្រួតពិនិត្យ','pe']};
async function orders(){
 var d=await api('/orders'),me=await api('/me');U=me.user;
 if(d.orders.some(function(o){return o.status=='pending'||o.status=='processing'}))poll=setInterval(render,4000);
 return '<h2>ប្រវត្តិទិញ</h2>'+(d.orders.length?'<div class="pnl scroll"><table><tr><th>លេខ</th><th>ហ្គេម</th><th>កញ្ចប់</th><th>ID</th><th>តម្លៃ</th><th>ស្ថានភាព</th><th>ពេល</th></tr>'+d.orders.map(function(o){var s=ST[o.status]||[o.status,''];return '<tr><td>#'+o.id+'</td><td>'+esc(o.game)+'</td><td>'+esc(o.pack)+'</td><td>'+esc(o.player_id)+'</td><td>'+$(o.price)+'</td><td><span class="tag '+s[1]+'">'+s[0]+'</span></td><td>'+new Date(o.created*1000).toLocaleString()+'</td></tr>'}).join('')+'</table></div>':'<p class="muted">មិនទាន់មានការបញ្ជាទិញ។ ទៅទំព័រដើមដើម្បីទិញលើកដំបូង។</p>')}

async function admin(){
 var s=await api('/admin/stats'),p=await api('/admin/pricing');
 var h='<h2>Admin Dashboard</h2><div class="grid"><div class="pnl"><div class="muted">ការបញ្ជាទិញជោគជ័យ</div><div class="bal">'+s.orders+'</div></div><div class="pnl"><div class="muted">ចំណូល</div><div class="bal">'+$(s.revenue)+'</div></div><div class="pnl"><div class="muted">ប្រាក់ចំណេញ</div><div class="bal ok">'+$(s.profit)+'</div></div>'+(s.review?'<div class="pnl"><div class="muted">ត្រូវត្រួតពិនិត្យ</div><div class="bal er">'+s.review+'</div></div>':'')+'</div><h2>គ្រប់គ្រងតម្លៃ និងប្រាក់ចំណេញ</h2>';
 p.games.forEach(function(g){h+='<div class="pnl"><div class="row"><b>'+g.emoji+' '+esc(g.name)+'</b><span class="muted" style="margin-left:auto">ចំណេញ %</span><input type="number" min="0" value="'+g.margin+'" style="width:80px" onchange="setP(\''+g.id+'\',{margin:this.value})"></div><div class="scroll"><table><tr><th>កញ្ចប់</th><th>តម្លៃដើម $</th><th>តម្លៃលក់</th><th>ចំណេញ</th></tr>'+g.packs.map(function(k,i){return '<tr><td>'+esc(k.name)+'</td><td><input type="number" step="0.01" value="'+k.cost+'" onchange="setP(\''+g.id+'\',{index:'+i+',cost:this.value})"></td><td><b>'+$(k.price)+'</b></td><td class="ok">'+$(k.price-k.cost)+'</td></tr>'}).join('')+'</table></div></div>'});
 return h}
async function setP(id,o){o.game_id=id;try{await api('/admin/pricing',{method:'PUT',body:o});G=(await api('/games')).games}catch(e){msg='<span class="er">'+esc(e.message)+'</span>'}render()}

async function init(){
 try{G=(await api('/games')).games}catch(e){msg='<span class="er">ភ្ជាប់ server មិនបាន: '+esc(e.message)+'</span>'}
 if(T){try{U=(await api('/me')).user}catch(e){}}
 render()}
window.addEventListener('hashchange',render);init();
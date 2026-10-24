// Set API to your FastAPI base URL (e.g. "http://localhost:8000"). If it is unreachable, demo data is used.
var API = "";
var INTERESTS = [["ml","Machine learning"],["bio","Biology"],["physics","Physics"],["econ","Economics"],["oss","Open source"],["eng","Engineering"]];
var DEMO = [
 {id:1,title:"DAAD WISE Research Internship",org:"Germany",funding:"Stipend and travel grant",due:"2026-12-01",base:84,tags:["ml","eng","physics"],why:"Your Python and machine learning projects match what host labs ask for.",docs:["CV","Transcript","Recommendation letter","Statement of purpose"],url:"https://www.daad.de"},
 {id:2,title:"Mitacs Globalink Research Internship",org:"Canada",funding:"Funded, 12 weeks",due:"2026-11-20",base:80,tags:["ml","bio","eng","econ"],why:"Open to undergraduates in your field, with a start window that fits your semester.",docs:["CV","Transcript","Project ranking form","Supervisor ranking"],url:"https://www.mitacs.ca"},
 {id:3,title:"Summer Research Fellowship",org:"India",funding:"Monthly stipend",due:"2026-11-12",base:76,tags:["physics","bio","ml"],why:"A fellowship open to students from smaller colleges, with no prior publication needed.",docs:["CV","Marksheets","Recommendation letter"],url:"https://www.ias.ac.in"},
 {id:4,title:"Open Source Summer Programme",org:"Remote",funding:"Stipend",due:"2027-03-25",base:70,tags:["oss","ml","eng"],why:"Your GitHub activity shows the contribution history reviewers look for.",docs:["CV","Project proposal","GitHub profile"],url:"https://summerofcode.withgoogle.com"},
 {id:5,title:"OIST Research Internship",org:"Japan",funding:"Funded",due:"2026-10-15",base:88,tags:["bio","physics","ml"],why:"Strong match, but the application window has closed. We will watch for the next cycle.",docs:["CV","Transcript","Recommendation letter"],url:"https://www.oist.jp"}
];
var sel = {ml:true}, data = [];
var $ = function(id){return document.getElementById(id)};

INTERESTS.forEach(function(it){
  var b = document.createElement("button");
  b.className="chip"; b.type="button"; b.textContent=it[1];
  b.setAttribute("aria-pressed", !!sel[it[0]]);
  b.onclick=function(){ sel[it[0]]=!sel[it[0]]; b.setAttribute("aria-pressed", !!sel[it[0]]); if(data.length) render(); };
  $("chips").appendChild(b);
});

$("cv").onchange=function(e){
  var f=e.target.files[0]; if(!f) return;
  $("fname").textContent=f.name; $("fhint").textContent=Math.max(1,Math.round(f.size/1024))+" KB, ready to scan";
};

function daysLeft(d){ var t=new Date(); t.setHours(0,0,0,0); return Math.round((new Date(d+"T00:00:00")-t)/864e5); }
function score(o){
  var keys=Object.keys(sel).filter(function(k){return sel[k]});
  var m=o.tags.filter(function(t){return sel[t]}).length;
  var s=o.base+m*5-(keys.length&&!m?14:0);
  return Math.max(30,Math.min(99,s));
}
function ranked(){
  return data.map(function(o){var c=Object.assign({},o); c.score=score(o); c.left=daysLeft(o.due); c.closed=c.left<0; return c;})
   .sort(function(a,b){return (a.closed-b.closed)||(b.score-a.score)});
}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}

function render(){
  var items=ranked(), list=$("list"), blips=$("blips");
  list.innerHTML=""; blips.innerHTML="";
  items.forEach(function(o,i){
    var dueTxt=o.closed?"Closed":(o.left===0?"Today":o.left+" days");
    var card=document.createElement("article");
    card.className="card"+(o.closed?" closed":"");
    card.id="c"+o.id;
    card.innerHTML=
     '<div class="score" style="--s:'+o.score+'"><span>'+o.score+'</span></div>'+
     '<div><h3>'+esc(o.title)+'</h3><div class="meta">'+esc(o.org)+' · '+esc(o.funding)+'</div><p class="why">'+esc(o.why)+'</p>'+
     '<button class="more" type="button" aria-expanded="false">Documents and link</button></div>'+
     '<div class="due'+((!o.closed&&o.left<=14)?' soon':'')+'"><b>'+dueTxt+'</b><small>'+(o.closed?'ended '+o.due:'until '+o.due)+'</small></div>'+
     '<div class="extra"><ul>'+o.docs.map(function(d,k){return '<li><label><input type="checkbox"> '+esc(d)+'</label></li>'}).join("")+'</ul>'+
     '<a href="'+o.url+'" target="_blank" rel="noopener">Open the source page</a></div>';
    var btn=card.querySelector(".more");
    btn.onclick=function(){var open=card.classList.toggle("open"); btn.setAttribute("aria-expanded",open);};
    card.onmouseenter=function(){hl(o.id,true)}; card.onmouseleave=function(){hl(o.id,false)};
    list.appendChild(card);

    var r=48*(1-(o.score-30)/80)*0.9+4, a=(i*137.5+20)*Math.PI/180;
    var b=document.createElement("button");
    b.className="blip"+(o.closed?" closed":""); b.id="b"+o.id; b.type="button"; b.setAttribute("aria-label",o.title+", "+o.score+" percent match");
    b.style.left=(50+r*Math.cos(a))+"%"; b.style.top=(50+r*Math.sin(a))+"%";
    b.onclick=function(){card.scrollIntoView({behavior:"smooth",block:"center"});hl(o.id,true);setTimeout(function(){hl(o.id,false)},1600)};
    blips.appendChild(b);
    setTimeout(function(){b.classList.add("on")},300+i*350);
  });
}
function hl(id,on){ var c=$("c"+id), b=$("b"+id); if(c)c.classList.toggle("hl",on); if(b)b.classList.toggle("hl",on); }

$("scan").onclick=function(){
  var radar=$("radar"), st=$("status"), btn=$("scan");
  btn.disabled=true; radar.classList.remove("idle"); data=[]; $("blips").innerHTML="";
  st.textContent="Searching the web…";
  var get = API ? fetch(API+"/api/opportunities").then(function(r){return r.json()}) : Promise.reject();
  get.catch(function(){return DEMO}).then(function(d){
    setTimeout(function(){st.textContent="Reading pages…"},900);
    setTimeout(function(){
      data=d; render(); st.textContent=d.length+" opportunities ranked";
      radar.classList.add("idle"); btn.disabled=false;
      $("feed").scrollIntoView({behavior:"smooth"});
    },1900);
  });
};

$("theme").onclick=function(){
  var root=document.documentElement, dark=getComputedStyle(root).getPropertyValue("color-scheme").indexOf("dark")>-1;
  root.setAttribute("data-theme", dark?"light":"dark");
};

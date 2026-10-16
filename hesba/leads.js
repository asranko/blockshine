(function(){
"use strict";
const $=id=>document.getElementById(id);
const STORAGE_KEY="hesba-leads-v1";
const statusNames={new:"جديد",contacted:"تم التواصل",quote:"عرض سعر",negotiation:"تفاوض",won:"فاز",lost:"خسر",paused:"مؤجل"};
const sourceNames={referral:"إحالة",search:"بحث على الإنترنت",website:"موقع",platform:"منصة عمل حر",social:"وسائل اجتماعية",past:"عميل سابق",other:"أخرى"};
const activeStatuses=new Set(["new","contacted","quote","negotiation"]);
const money=n=>new Intl.NumberFormat("ar-EG",{style:"currency",currency:"EGP",maximumFractionDigits:0}).format(Number.isFinite(Number(n))?Number(n):0);
const esc=v=>String(v==null?"":v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const today=()=>{const d=new Date();return d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"+String(d.getDate()).padStart(2,"0")};
let leads=[],editingId=null;
try{const parsed=JSON.parse(localStorage.getItem(STORAGE_KEY)||"[]");leads=Array.isArray(parsed)?parsed.filter(x=>x&&typeof x==="object"&&typeof x.id==="string"):[]}catch(e){leads=[]}
function save(next){try{localStorage.setItem(STORAGE_KEY,JSON.stringify(next));leads=next;return true}catch(e){$("leadSaveStatus").textContent="تعذّر الحفظ على هذا الجهاز. حرّر مساحة في المتصفح أو صدّر نسخة احتياطية.";return false}}
function id(){try{return crypto.randomUUID()}catch(e){return Date.now().toString(36)+"-"+Math.random().toString(36).slice(2,12)}}
function toast(s){$("leadSaveStatus").textContent=s}
function getForm(){return{id:editingId||id(),company:$("leadCompany").value.trim(),service:$("leadService").value.trim(),source:$("leadSource").value,value:Math.max(0,Number($("leadValue").value)||0),status:$("leadStatus").value,followUp:$("leadFollowUp").value,nextStep:$("leadNextStep").value.trim(),notes:$("leadNotes").value.trim(),updatedAt:new Date().toISOString(),createdAt:editingId?(leads.find(x=>x.id===editingId)||{}).createdAt||new Date().toISOString():new Date().toISOString()}}
function clearForm(){editingId=null;$("leadForm").reset();$("leadValue").value="0";$("leadFormTitle").textContent="سجّل فرصة جديدة";$("saveLead").textContent="حفظ الفرصة";$("cancelLeadEdit").hidden=true;toast("")}
function enterEdit(item){editingId=item.id;$("leadCompany").value=item.company||"";$("leadService").value=item.service||"";$("leadSource").value=item.source||"other";$("leadValue").value=String(item.value||0);$("leadStatus").value=item.status||"new";$("leadFollowUp").value=item.followUp||"";$("leadNextStep").value=item.nextStep||"";$("leadNotes").value=item.notes||"";$("leadFormTitle").textContent="تعديل فرصة مسجلة";$("saveLead").textContent="حفظ التعديلات";$("cancelLeadEdit").hidden=false;toast("أنت بتعدّل سجلًا موجودًا.");$("lead-manager").scrollIntoView({behavior:"smooth",block:"start"});$("leadCompany").focus()}
function render(){
 const q=$("leadSearch").value.trim().toLocaleLowerCase("ar"),state=$("leadStatusFilter").value;
 const filtered=leads.filter(x=>(state==="all"||x.status===state)&&(!q||[x.company,x.service,x.notes,x.nextStep,sourceNames[x.source]].some(v=>String(v||"").toLocaleLowerCase("ar").includes(q))));
 const due=leads.filter(x=>x.followUp&&x.followUp<=today()&&activeStatuses.has(x.status)).length;
 const pipeline=leads.filter(x=>activeStatuses.has(x.status)).reduce((s,x)=>s+(Number(x.value)||0),0);
 $("leadCount").textContent=leads.length.toLocaleString("ar-EG");
 $("quoteCount").textContent=leads.filter(x=>["quote","negotiation"].includes(x.status)).length.toLocaleString("ar-EG");
 $("wonCount").textContent=leads.filter(x=>x.status==="won").length.toLocaleString("ar-EG");
 $("dueCount").textContent=due.toLocaleString("ar-EG");
 $("pipelineValue").textContent=money(pipeline);
 $("leadRowsCount").textContent=filtered.length.toLocaleString("ar-EG")+" من "+leads.length.toLocaleString("ar-EG")+" فرصة";
 $("leadsEmpty").hidden=filtered.length>0;
 $("leadsTableBody").innerHTML=filtered.sort((a,b)=>(a.followUp||"9999-99-99").localeCompare(b.followUp||"9999-99-99")).map(x=>'<tr><td><b>'+esc(x.company)+'</b><small>'+esc(sourceNames[x.source]||"أخرى")+'</small></td><td>'+esc(x.service||"غير محددة")+'</td><td class="lead-money">'+money(x.value)+'</td><td><span class="lead-status status-'+esc(x.status)+'">'+esc(statusNames[x.status]||"جديد")+'</span></td><td>'+esc(x.followUp||"غير محدد")+'</td><td>'+esc(x.nextStep||"لم تُحدد بعد")+'</td><td><div class="lead-row-actions"><button type="button" data-edit="'+esc(x.id)+'" aria-label="تعديل '+esc(x.company)+'">تعديل</button><button type="button" class="danger" data-delete="'+esc(x.id)+'" aria-label="حذف '+esc(x.company)+'">حذف</button></div></td></tr>').join("");
 $("leadsTableBody").querySelectorAll("[data-edit]").forEach(b=>b.addEventListener("click",()=>{const item=leads.find(x=>x.id===b.dataset.edit);if(item)enterEdit(item)}));
 $("leadsTableBody").querySelectorAll("[data-delete]").forEach(b=>b.addEventListener("click",()=>{const item=leads.find(x=>x.id===b.dataset.delete);if(!item)return;if(!confirm("تحذف فرصة «"+item.company+"» من هذا المتصفح؟"))return;const next=leads.filter(x=>x.id!==item.id);if(save(next)){if(editingId===item.id)clearForm();render();toast("تم حذف السجل.")}}));
}
$("leadForm").addEventListener("submit",e=>{e.preventDefault();const item=getForm();if(!item.company){$("leadCompany").focus();toast("اكتب اسم العميل أو الشركة.");return}const wasEditing=Boolean(editingId);const next=wasEditing?leads.map(x=>x.id===editingId?item:x):[item,...leads];if(save(next)){render();clearForm();toast(wasEditing?"تم تحديث السجل.":"تم حفظ الفرصة على جهازك.")}});
$("cancelLeadEdit").addEventListener("click",clearForm);
$("resetLeadForm").addEventListener("click",()=>{clearForm();$("leadCompany").focus()});
$("leadSearch").addEventListener("input",render);$("leadStatusFilter").addEventListener("change",render);
$("clearLeads").addEventListener("click",()=>{if(!leads.length){toast("لا توجد سجلات لمسحها.");return}if(!confirm("هتمسح كل فرص العملاء المحفوظة على هذا الجهاز. هل تريد المتابعة؟"))return;if(save([])){clearForm();render();toast("تم مسح كل السجلات.")}});
function csvCell(value){const s=String(value==null?"":value);return '"'+s.replace(/"/g,'""')+'"'}
$("exportLeads").addEventListener("click",()=>{if(!leads.length){toast("أضف فرصة واحدة على الأقل قبل التصدير.");return}const headers=["تاريخ الإنشاء","العميل / الشركة","الخدمة المطلوبة","مصدر العميل","القيمة المحتملة (ج.م)","الخطوة التالية","موعد المتابعة","الحالة","ملاحظات"];const rows=leads.map(x=>[String(x.createdAt||"").slice(0,10),x.company,x.service,sourceNames[x.source]||"أخرى",x.value,x.nextStep,x.followUp,statusNames[x.status]||"جديد",x.notes]);const body="\uFEFF"+[headers,...rows].map(r=>r.map(csvCell).join(",")).join("\r\n");const blob=new Blob([body],{type:"text/csv;charset=utf-8"});const url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="hesba-client-pipeline-"+today()+".csv";document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);toast("تم تجهيز نسخة CSV على جهازك.")});
render();
})();
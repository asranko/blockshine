(function(){
"use strict";
const API="https://hesba-payments-api.onrender.com";
const $=id=>document.getElementById(id);
let downloadToken=null;
function statusText(message){const node=$("checkoutStatus");if(node)node.textContent=message}
function setDownloadToken(token,message){
 downloadToken=token;
 const area=$("downloadArea"),link=$("downloadLink"),holder=$("paypalButtons");
 if(area)area.hidden=false;
 if(link)link.hidden=false;
 if(holder)holder.hidden=true;
 statusText(message||"تم التحقق من الطلب. رمز التنزيل صالح لمدة 15 دقيقة.");
}
async function downloadCurrentToken(){
 const link=$("downloadLink"),area=$("downloadArea");
 if(!downloadToken){statusText("انتهت صلاحية رمز التنزيل. استخدم استعادة التنزيل للتحقق من الطلب مرة أخرى.");return;}
 if(link)link.setAttribute("aria-disabled","true");
 statusText("جارٍ تجهيز ملف التنزيل الآمن…");
 try{
  const response=await fetch(API+"/api/download",{method:"POST",headers:{"Authorization":"Bearer "+downloadToken}});
  if(!response.ok)throw new Error("download_failed");
  const blob=await response.blob();
  const objectUrl=URL.createObjectURL(blob);
  const a=document.createElement("a");
  a.href=objectUrl;a.download="hesba-freelancer-desk-kit-v1.zip";
  document.body.appendChild(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(objectUrl),30000);
  downloadToken=null;
  if(link)link.hidden=true;
  if(area)area.hidden=true;
  statusText("بدأ تنزيل الحزمة. احفظ نسخة احتياطية في مكان آمن.");
  const recoveryStatus=$("recoveryStatus");
  if(recoveryStatus)recoveryStatus.textContent="تم بدء التنزيل. احتفظ بنسختك في مكان آمن.";
 }catch(e){
  statusText("تعذر تنزيل الحزمة. تحقّق من اتصالك؛ لن يتم تحصيل مبلغ إضافي بسبب محاولة التنزيل.");
 }finally{if(link)link.removeAttribute("aria-disabled");}
}
function bindDownloadLink(){
 const link=$("downloadLink");
 if(!link||link.dataset.bound==="yes")return;
 link.dataset.bound="yes";
 link.addEventListener("click",event=>{event.preventDefault();downloadCurrentToken();});
}
async function start(){
 const status=$("checkoutStatus"),holder=$("paypalButtons");
 if(!status||!holder)return;
 bindDownloadLink();
 try{
  const response=await fetch(API+"/api/config",{headers:{Accept:"application/json"}});
  if(!response.ok)throw new Error("config");
  const config=await response.json();
  if(!config.checkout_enabled||!config.paypal_client_id){
   status.textContent="الشراء الإلكتروني غير متاح حاليًا. لن يتم تحصيل أي مبلغ ولن يُفتح التنزيل حتى يكتمل ربط حساب التاجر واختبار الدفع.";
   status.setAttribute("data-state","disabled");
   holder.hidden=true;
   const recovery=$("recoverySection");if(recovery)recovery.hidden=true;
   return;
  }
  holder.hidden=false;
  status.textContent="الدفع الآمن متاح عبر PayPal. لن نطلب بيانات البطاقة داخل حِسبة.";
  const recovery=$("recoverySection");
  if(recovery)recovery.hidden=false;
  bindRecoveryForm();
  const script=document.createElement("script");
  script.src="https://www.paypal.com/sdk/js?client-id="+encodeURIComponent(config.paypal_client_id)+"&currency="+encodeURIComponent(config.currency)+"&intent=capture&components=buttons";
  script.async=true;
  script.onload=()=>renderButtons(config);
  script.onerror=()=>{status.textContent="تعذر تحميل PayPal حاليًا. لم يتم خصم أي مبلغ.";};
  document.head.appendChild(script);
 }catch(e){
  status.textContent="خدمة الدفع لا تستجيب حاليًا. الأدوات المجانية تعمل، ولن يتم تحصيل أي مبلغ.";
  const recovery=$("recoverySection");if(recovery)recovery.hidden=true;
 }
}
function bindRecoveryForm(){
 const button=$("recoveryBtn");
 if(!button||button.dataset.bound==="yes")return;
 button.dataset.bound="yes";
 button.addEventListener("click",async()=>{
  const orderId=($("recoveryOrderId")?.value||"").trim().toUpperCase();
  const email=($("recoveryEmail")?.value||"").trim();
  const result=$("recoveryStatus");
  if(!/^[A-Z0-9]{8,40}$/.test(orderId)){if(result)result.textContent="راجع رقم الطلب كما يظهر في PayPal.";return;}
  if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)){if(result)result.textContent="أدخل البريد الإلكتروني الذي استخدمته في الدفع.";return;}
  button.disabled=true;
  if(result)result.textContent="جارٍ التحقق من الطلب مع PayPal…";
  try{
   const response=await fetch(API+"/api/orders/reissue-download",{
    method:"POST",
    headers:{"Content-Type":"application/json","Accept":"application/json"},
    body:JSON.stringify({order_id:orderId,payer_email:email})
   });
   const payload=await response.json().catch(()=>({}));
   if(!response.ok||payload.status!=="COMPLETED"||!payload.download_token){
    if(result)result.textContent="تعذر التحقق من الطلب. تأكد من رقم الطلب والبريد وأن الدفع مكتمل.";
    return;
   }
   setDownloadToken(payload.download_token,"تم التحقق من عملية الشراء. اضغط على زر التنزيل؛ رمز الاستعادة صالح لمدة 15 دقيقة.");
   if(result)result.textContent="تم التحقق بنجاح. زر التنزيل أصبح متاحًا أعلى هذا النموذج.";
   $("downloadArea")?.scrollIntoView({behavior:"smooth",block:"center"});
  }catch(e){
   if(result)result.textContent="تعذر الاتصال بخدمة الاستعادة. حاول مجددًا بعد قليل.";
  }finally{button.disabled=false;}
 });
}
function renderButtons(config){
 const status=$("checkoutStatus"),holder=$("paypalButtons");
 if(!window.paypal||!holder)return;
 status.textContent="اختر الدفع عبر PayPal لإتمام الشراء. لا تتابع إذا لم تكن متأكدًا من المبلغ.";
 window.paypal.Buttons({
  style:{layout:"vertical",shape:"rect",label:"paypal",color:"gold",tagline:false},
  createOrder:async()=>{
   const response=await fetch(API+"/api/orders",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:"hesba-freelancer-kit-v1"})});
   const payload=await response.json().catch(()=>({}));
   if(!response.ok||!payload.id)throw new Error(payload.detail||"لم نستطع إنشاء طلب الدفع.");
   return payload.id;
  },
  onApprove:async data=>{
   status.textContent="جارٍ التحقق من الدفع مع PayPal. لا تغلق الصفحة.";
   try{
    const response=await fetch(API+"/api/orders/capture",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({order_id:data.orderID})});
    const payload=await response.json().catch(()=>({}));
    if(!response.ok||payload.status!=="COMPLETED"||!payload.download_token)throw new Error(payload.detail||"لم يتم تأكيد الدفع. لم يُصدر رمز التنزيل.");
    setDownloadToken(payload.download_token,"تم تأكيد الدفع. رمز التنزيل صالح لمدة 15 دقيقة. اضغط لتنزيل الحزمة.");
    holder.hidden=true;
   }catch(e){
    status.textContent="لم نستطع تأكيد الدفع وإصدار التنزيل. لن نعرض رمزًا قبل التحقق من عملية الدفع. افحص حالة العملية في PayPal قبل إعادة المحاولة.";
   }
  },
  onCancel:()=>{status.textContent="ألغيت عملية الدفع. لم يتم إنشاء رمز تنزيل.";},
  onError:()=>{status.textContent="حدث خطأ أثناء الدفع. تحقق من حساب PayPal قبل المحاولة مجددًا، ولا تكرر الدفع إذا ظهر خصم.";},
 }).render("#paypalButtons");
}
start();
})();
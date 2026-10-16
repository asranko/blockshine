(function(){
"use strict";
const API="https://hesba-payments-api.onrender.com";
const $=id=>document.getElementById(id);
async function start(){
 const status=$("checkoutStatus"), holder=$("paypalButtons"), area=$("downloadArea");
 if(!status||!holder)return;
 try{
  const response=await fetch(API+"/api/config",{headers:{Accept:"application/json"}});
  if(!response.ok)throw new Error("config");
  const config=await response.json();
  if(!config.checkout_enabled||!config.paypal_client_id){
   status.textContent="الشراء الإلكتروني لم يُفعّل بعد. المنتج معروض، لكن الدفع والتنزيل مقفولان حتى يكتمل ربط حساب التاجر.";
   status.setAttribute("data-state","disabled");
   return;
  }
  holder.hidden=false;
  status.textContent="الدفع الآمن متاح عبر PayPal. لن نطلب بيانات البطاقة داخل حِسبة.";
  const script=document.createElement("script");
  script.src="https://www.paypal.com/sdk/js?client-id="+encodeURIComponent(config.paypal_client_id)+"&currency="+encodeURIComponent(config.currency)+"&intent=capture&components=buttons";
  script.async=true;
  script.onload=()=>renderButtons(config);
  script.onerror=()=>{status.textContent="تعذر تحميل PayPal حاليًا. لم يتم خصم أي مبلغ.";};
  document.head.appendChild(script);
 }catch(e){
  status.textContent="خدمة الدفع لا تستجيب حاليًا. الأدوات المجانية تعمل، ولن يتم تحصيل أي مبلغ.";
 }
}
function renderButtons(config){
 const status=$("checkoutStatus"),holder=$("paypalButtons"),area=$("downloadArea"),link=$("downloadLink");
 if(!window.paypal||!holder)return;
 status.textContent="اختر الدفع عبر PayPal لإتمام الشراء. لا تتابع إذا لم تكن متأكدًا من المبلغ.";
 window.paypal.Buttons({
  style:{layout:"vertical",shape:"rect",label:"paypal",color:"gold",tagline:false},
  createOrder:async()=>{
   const r=await fetch(API+"/api/orders",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({product_id:"hesba-freelancer-kit-v1"})});
   const d=await r.json().catch(()=>({}));
   if(!r.ok||!d.id)throw new Error(d.detail||"لم نستطع إنشاء طلب الدفع.");
   return d.id;
  },
  onApprove:async data=>{
   status.textContent="جارٍ التحقق من الدفع مع PayPal. لا تغلق الصفحة.";
   try{
    const r=await fetch(API+"/api/orders/capture",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({order_id:data.orderID})});
    const d=await r.json().catch(()=>({}));
    if(!r.ok||d.status!=="COMPLETED"||!d.download_url)throw new Error(d.detail||"لم يتم تأكيد الدفع. لم يُصدر رابط التنزيل.");
    link.href=API+d.download_url;link.hidden=false;area.hidden=false;status.textContent="تم تأكيد الدفع. رابط التنزيل صالح لمدة 15 دقيقة. احفظ نسخة احتياطية بعد التنزيل.";holder.hidden=true;
   }catch(e){
    status.textContent="لم نستطع تأكيد الدفع وإصدار التنزيل. لن نعرض رابطًا قبل التحقق من عملية الدفع. افحص حالة العملية في PayPal قبل إعادة المحاولة.";
   }
  },
  onCancel:()=>{status.textContent="ألغيت عملية الدفع. لم يتم إنشاء رابط تنزيل.";},
  onError:()=>{status.textContent="حدث خطأ أثناء الدفع. تحقق من حساب PayPal قبل المحاولة مجددًا، ولا تكرر الدفع إذا ظهر خصم.";},
 }).render("#paypalButtons");
}
start();
})();
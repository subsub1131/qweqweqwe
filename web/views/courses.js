import {courseApi,errorMessage} from '../api/courses.js';
import {courseStore} from '../stores/courses.js';
import {courseCard,money} from '../components/course-card.js';
import {startRouter} from '../router/index.js';
import {startPayments} from './payments.js';
const $=id=>document.getElementById(id);
const dialog=$('course-dialog');
let detailLoading=false;
function renderCards(target,items){$(target).replaceChildren(...items.map((course,index)=>courseCard(course,openDetail,index)));}
async function loadCatalog(){ $('catalog-message').textContent='강의를 불러오고 있어요…';$('catalog-retry').hidden=true;try {courseStore.items=await courseApi.list();renderCards('course-list',courseStore.items);$('course-count').textContent=courseStore.items.length+'개의 배움';$('catalog-message').textContent=courseStore.items.length?'':'아직 등록된 강의가 없어요.';}catch(error){$('catalog-message').textContent=errorMessage(error);$('catalog-retry').hidden=false;}}
async function loadMine(){ $('my-courses').replaceChildren();$('my-message').textContent='내 강의를 불러오고 있어요…';try{const items=await courseApi.mine();renderCards('my-courses',items);$('my-message').textContent=items.length?'':'아직 구매한 강의가 없어요. 마음에 드는 수업을 테스트 결제로 만나보세요.';}catch(error){$('my-message').textContent=errorMessage(error);}}
async function openDetail(id){if(detailLoading)return;detailLoading=true;try{const course=await courseApi.detail(id);courseStore.selected=course;$('detail-title').textContent=course.title;$('detail-category').textContent=course.category;$('detail-instructor').textContent=course.instructor;$('detail-description').textContent=course.description;$('detail-duration').textContent=`${course.duration_minutes}분 · ${course.lesson_count}개 수업`;$('detail-price').textContent=money(course.price);$('detail-message').textContent='';$('purchase-button').textContent='PortOne 테스트 결제 →';dialog.showModal();}catch(error){const target=location.hash==='#my'?'my-message':'catalog-message';$(target).textContent=errorMessage(error);}finally{detailLoading=false;}}
$('detail-close').addEventListener('click',()=>dialog.close());
const payments = startPayments({onMessage:text=>{$('detail-message').textContent=text;},onPaid:async()=>{if(location.hash==='#my')await loadMine();}});
$('purchase-button').addEventListener('click',()=>payments.purchase(courseStore.selected.id));
$('register-form').addEventListener('submit',async event=>{event.preventDefault();const form=event.currentTarget;if(!form.reportValidity())return;const button=form.querySelector('button[type="submit"]');button.disabled=true;const values=Object.fromEntries(new FormData(form));for(const key of ['title','description','category'])values[key]=values[key].trim();if(!values.title||!values.description||!values.category){$('register-message').textContent='공백 없이 제목·소개·분류를 입력해 주세요.';button.disabled=false;return;}for(const key of ['price','duration_minutes','lesson_count'])values[key]=Number(values[key]);$('register-message').textContent='등록 중이에요…';try{await courseApi.register(values);form.reset();$('register-message').textContent='데모 강의가 등록됐어요. 모든 강의에서 확인해 보세요.';await loadCatalog();}catch(error){$('register-message').textContent=errorMessage(error);}finally{button.disabled=false;}});
$('catalog-retry').addEventListener('click',loadCatalog);
startRouter(route=>{if(route==='my')loadMine();});
loadCatalog();

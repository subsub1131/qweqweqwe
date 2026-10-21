export const money=value=>new Intl.NumberFormat('ko-KR').format(value)+'원';
export function courseCard(course,onDetail,index=0) {
  const card=document.createElement('article');card.className='course-card';card.dataset.testid='course-card';
  const artwork=document.createElement('div');artwork.className='course-art art-'+index%4;artwork.setAttribute('aria-hidden','true');artwork.textContent=['✿','◌','✧','⌁'][index%4];
  const body=document.createElement('div');body.className='course-body';
  for(const [tag,cls,text] of [['p','category',course.category],['h3','',course.title],['p','muted',course.instructor],['p','course-meta',`${course.lesson_count}개 수업 · ${course.duration_minutes}분`],['p','price',money(course.price)]]){const el=document.createElement(tag);el.className=cls;el.textContent=text;body.append(el);}
  const button=document.createElement('button');button.type='button';button.className='detail-link';button.dataset.testid='course-detail';button.textContent='강의 살펴보기 ↗';button.setAttribute('aria-label',course.title+' 강의 살펴보기');button.addEventListener('click',()=>onDetail(course.id));body.append(button);card.append(artwork,body);return card;
}

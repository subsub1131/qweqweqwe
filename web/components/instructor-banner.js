import {element, button} from './dom.js';

export function instructorBanner({eyebrow = 'MEET YOUR GUIDE', title = '함께 시작하면, 조금 더 가벼워요.', description = '한 명의 강사와 차근차근. 오늘의 작은 호기심을 내일의 즐거움으로 이어가세요.', actionLabel = '수업 둘러보기', onAction = () => {}} = {}) {
  const root = element('aside', 'bloom-banner');
  const art = element('div', 'bloom-banner__art', '✿'); art.setAttribute('aria-hidden', 'true');
  const content = element('div', 'bloom-banner__content');
  const action = button('bloom-banner__action', `${actionLabel} ↗`);
  action.addEventListener('click', onAction);
  content.append(element('p', 'bloom-banner__eyebrow', eyebrow), element('h2', '', title), element('p', 'bloom-banner__description', description), action);
  root.append(art, content); return root;
}

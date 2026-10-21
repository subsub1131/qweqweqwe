import {element, button} from './dom.js';

/** Presentation-only course card. Favorite state belongs to the caller. */
export function courseTile({course, saved = false, onFavorite = () => {}, onOpen = () => {}}) {
  const lessonCount = course.lesson_count ?? course.lessonCount;
  const durationMinutes = course.duration_minutes ?? course.durationMinutes;
  const root = element('article', 'bloom-tile');
  const art = element('div', 'bloom-tile__art');
  const tones = ['rose', 'sage', 'sand', 'lilac'];
  art.dataset.tone = tones.includes(course.tone) ? course.tone : 'rose';
  const illustration = element('span', 'bloom-tile__illustration', course.symbol || '✿');
  illustration.setAttribute('aria-hidden', 'true');
  const category = element('span', 'bloom-tile__badge', course.category);
  const favorite = button('bloom-tile__favorite');
  let isSaved = Boolean(saved);
  function updateFavorite() {
    favorite.textContent = isSaved ? '♥' : '♡';
    favorite.setAttribute('aria-pressed', String(isSaved));
    favorite.setAttribute('aria-label', `${course.title} 찜하기`);
  }
  favorite.addEventListener('click', () => {isSaved = !isSaved; updateFavorite(); onFavorite(course, isSaved);});
  updateFavorite(); art.append(illustration, category, favorite);
  const body = element('div', 'bloom-tile__body');
  const title = element('h3');
  const open = button('bloom-tile__title', course.title);
  open.addEventListener('click', () => onOpen(course)); title.append(open);
  const price = new Intl.NumberFormat('ko-KR', {style: 'currency', currency: 'KRW', maximumFractionDigits: 0}).format(course.price);
  body.append(element('p', 'bloom-tile__eyebrow', '작은 배움, 새로운 계절'), title,
    element('p', 'bloom-tile__description', course.description),
    element('p', 'bloom-tile__meta', `${lessonCount}개 수업 · ${durationMinutes}분`),
    element('p', 'bloom-tile__price', price));
  root.append(art, body); return root;
}

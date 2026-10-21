import {courseSearch, categoryChips, courseTile, instructorBanner} from '../components/index.js';

const categories = [
  {value: '', label: '모든 배움', symbol: '✿'},
  {value: '코딩', label: '코딩', symbol: '⌘'},
  {value: '디자인', label: '디자인', symbol: '◒'},
  {value: '일상', label: '일상', symbol: '☷'},
  {value: '취미', label: '취미', symbol: '✧'},
];
const courses = [
  {id: 1, title: '한 줄씩 시작하는 파이썬', category: '코딩', description: '처음 만나는 코드도, 내 속도에 맞춰 차근차근.', price: 39000, lesson_count: 8, duration_minutes: 120, symbol: '⌘', tone: 'rose'},
  {id: 2, title: '나만의 색을 찾는 디자인', category: '디자인', description: '작은 화면에 나다운 감각을 담는 시간.', price: 29000, lesson_count: 6, duration_minutes: 90, symbol: '◒', tone: 'sage'},
  {id: 3, title: '차분하게 정리하는 하루', category: '일상', description: '복잡한 생각을 비우고, 소중한 일상을 기록해요.', price: 19000, lesson_count: 4, duration_minutes: 60, symbol: '☷', tone: 'sand'},
  {id: 4, title: '봄을 그리는 드로잉', category: '취미', description: '연필 한 자루로 발견하는 평범한 날의 아름다움.', price: 25000, lesson_count: 5, duration_minutes: 75, symbol: '✿', tone: 'lilac'},
];
const state = {query: '', category: '', saved: new Set()};
const message = document.querySelector('#interaction-message');
const grid = document.querySelector('#tiles-mount');
function render() {
  const query = state.query.toLocaleLowerCase('ko-KR');
  const filtered = courses.filter(course => (!state.category || course.category === state.category) && `${course.title} ${course.description} ${course.category}`.toLocaleLowerCase('ko-KR').includes(query));
  grid.replaceChildren(...filtered.map(course => courseTile({
    course, saved: state.saved.has(course.id),
    onFavorite(item, saved) {
      if (saved) state.saved.add(item.id); else state.saved.delete(item.id);
      message.textContent = `${item.title}${saved ? ' 강의를 찜했어요.' : ' 강의의 찜을 해제했어요.'} · 관심 강의 ${state.saved.size}개`;
    },
    onOpen(item) {message.textContent = `${item.title} · ${item.lesson_count}개 수업, ${item.duration_minutes}분. 실제 강의는 상단의 ‘강의 목록으로’에서 확인하세요.`;},
  })));
  document.querySelector('#result-count').textContent = `${filtered.length}개의 작은 시작`;
  document.querySelector('#empty-message').hidden = filtered.length !== 0;
}
const search = courseSearch({categories, onSearch({query, category}) {
  state.query = query; state.category = category; chips.setValue(category); render();
}});
const chips = categoryChips({items: categories, onChange(category) {
  state.category = category; search.setCategory(category); render();
}});
document.querySelector('#search-mount').append(search.element);
document.querySelector('#categories-mount').append(chips.element);
document.querySelector('#banner-mount').append(instructorBanner({onAction() {
  document.querySelector('#tiles-title').scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start'});
  const firstCourse = grid.querySelector('.bloom-tile__title');
  if (firstCourse) firstCourse.focus({preventScroll: true});
  else search.element.querySelector('input').focus();
}}));
render();

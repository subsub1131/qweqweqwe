import {element, button} from './dom.js';

/** onSearch receives {query, category}; categories are {value, label}. */
export function courseSearch({categories = [], onSearch = () => {}} = {}) {
  const root = element('form', 'bloom-search');
  root.setAttribute('role', 'search');
  root.setAttribute('aria-label', '배우고 싶은 강의 찾기');
  const queryLabel = element('label', 'bloom-search__field');
  const query = element('input');
  query.type = 'search'; query.name = 'query'; query.maxLength = 120;
  query.placeholder = '새로운 관심사를 찾아보세요';
  queryLabel.append(element('span', '', '어떤 배움을 찾으세요?'), query);
  const categoryLabel = element('label', 'bloom-search__field bloom-search__category');
  const category = element('select'); category.name = 'category';
  for (const item of categories) {
    const option = element('option', '', item.label); option.value = item.value;
    category.append(option);
  }
  categoryLabel.append(element('span', '', '관심 분야'), category);
  const submit = button('bloom-search__submit', '↗');
  submit.type = 'submit'; submit.setAttribute('aria-label', '강의 검색');
  root.append(queryLabel, categoryLabel, submit);
  root.addEventListener('submit', event => {
    event.preventDefault(); onSearch({query: query.value.trim(), category: category.value});
  });
  return {element: root, setCategory(value) {category.value = value;}};
}

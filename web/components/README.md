# Bloom components

벚꽃·크림·로즈 테마의 vanilla ES module 컴포넌트입니다. Airbnb의 검색, 카테고리 선택, 카드 탐색 패턴을 온라인 강의에 맞춰 구성했습니다. 기존 로그인·강의·결제 페이지에 자동 적용되지 않습니다.

미리보기: 프론트 서버의 `/components.html`. 검색, 분야 선택, 찜 토글이 동작합니다. 샘플 강의와 찜 상태는 화면 내 메모리만 사용하고 API·결제·계정 정보에 접근하지 않습니다.

## 사용

```html
<link rel="stylesheet" href="components/bloom.css">
<div id="search"></div>
<script type="module">
  import {courseSearch, categoryChips, courseTile, instructorBanner} from './components/index.js';
  const categories = [{value: '', label: '모든 배움'}, {value: '코딩', label: '코딩'}];
  const search = courseSearch({categories, onSearch: ({query, category}) => console.log(query, category)});
  document.querySelector('#search').append(search.element);
</script>
```

- `courseSearch({categories, onSearch})` → `{element, setCategory(value)}`. `categories`: `{value, label}[]`. 제출 시 `{query, category}` 전달. 전체 분야용 빈 값 옵션은 호출자가 제공합니다.
- `categoryChips({items, value, onChange})` → `{element, setValue(value)}`. `items`: `{value, label, symbol?}[]`. 선택 버튼은 `aria-pressed` 사용. `setValue`는 콜백을 호출하지 않습니다.
- `courseTile({course, saved, onFavorite, onOpen})` → `<article>`. `course`: `{id, title, category, description, price, lesson_count, duration_minutes, symbol?, tone?}`. 현재 강의 API 객체를 그대로 전달할 수 있으며 `lessonCount`, `durationMinutes`도 지원합니다. `tone`: `rose | sage | sand | lilac`. `onFavorite(course, saved)`, `onOpen(course)` 콜백. 상위에서 찜 상태를 보관하여 재렌더 시 `saved`로 전달하세요. 가격은 원 단위 숫자입니다.
- `instructorBanner({eyebrow?, title?, description?, actionLabel?, onAction?})` → `<aside>`. 안내 문구와 동작을 교체할 수 있습니다.

기존 API 데이터 사용 예시:

```js
const course = {id: 1, title: '파이썬 입문', category: '코딩', description: '기초부터 차근차근', price: 39000, lesson_count: 8, duration_minutes: 120};
const tile = courseTile({course, onOpen: item => openCourseDetail(item.id)});
document.querySelector('#course-grid').append(tile);
```

모든 문구는 `textContent`로 렌더링하며 임의 HTML은 받지 않습니다. CSS는 `bloom-` 접두어로 분리했고 외부 이미지·폰트·CDN 의존성이 없습니다. 카드 그리드는 호스트 화면에서 정합니다. 예시는 `assets/components-preview.css`의 `.preview-grid`를 참고하세요. API 연동이 필요하면 현재 프로젝트의 `api` 계층에서 Axios로 백엔드를 직접 호출한 결과를 전달하세요.

import {element, button} from './dom.js';

/** Single-selection buttons use aria-pressed; standard Tab/Enter navigation. */
export function categoryChips({items = [], value = '', onChange = () => {}} = {}) {
  const root = element('div', 'bloom-categories');
  root.setAttribute('role', 'group'); root.setAttribute('aria-label', '관심 분야 선택');
  const controls = new Map();
  function setValue(selected) {
    for (const [key, control] of controls) control.setAttribute('aria-pressed', String(key === selected));
  }
  for (const item of items) {
    const control = button('bloom-chip');
    const symbol = element('span', 'bloom-chip__symbol', item.symbol || '✿');
    symbol.setAttribute('aria-hidden', 'true');
    control.append(symbol, element('span', '', item.label));
    control.addEventListener('click', () => {setValue(item.value); onChange(item.value);});
    controls.set(item.value, control); root.append(control);
  }
  setValue(value);
  return {element: root, setValue};
}

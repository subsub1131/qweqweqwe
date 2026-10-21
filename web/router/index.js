export function startRouter(onRoute) {
  function render(){const next=['my','register'].includes(location.hash.slice(1))?location.hash.slice(1):'catalog';for(const id of ['catalog','my','register'])document.getElementById(id).hidden=id!==next;for(const link of document.querySelectorAll('nav a')){if(link.hash==='#'+next)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');}onRoute(next);}
  addEventListener('hashchange',render);render();
}

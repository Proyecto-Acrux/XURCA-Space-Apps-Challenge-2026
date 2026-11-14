import { media } from './media.js';
import { db, authReady } from './firebase.js';
import {
  addDoc,
  collection,
  onSnapshot,
  orderBy,
  query,
  serverTimestamp
} from 'https://www.gstatic.com/firebasejs/11.10.0/firebase-firestore.js';

// =========================================
// NAVEGACIÓN ENTRE SECCIONES
// =========================================

const views = [...document.querySelectorAll('[data-view]')];
const nav = document.querySelector('#navegacion');
const menuToggle = document.querySelector('.menu-toggle');
const mobile = window.matchMedia('(max-width: 760px)');

function closeMenu() {
  nav.classList.remove('is-open');
  menuToggle.setAttribute('aria-expanded', 'false');
}

function syncNavigation() {
  menuToggle.hidden = !mobile.matches;
  if (!mobile.matches) closeMenu();
}

function showView(route, updateHistory = true) {
  const target = views.find(view => view.dataset.view === route) || views[0];

  views.forEach(view => {
    const active = view === target;
    view.hidden = !active;
    view.classList.toggle('is-active', active);
  });

  document.querySelectorAll('#navegacion [data-route]').forEach(link => {
    if (link.dataset.route === target.dataset.view) {
      link.setAttribute('aria-current', 'page');
    } else {
      link.removeAttribute('aria-current');
    }
  });

  if (updateHistory && location.hash !== `#${target.dataset.view}`) {
    history.pushState({ route: target.dataset.view }, '', `#${target.dataset.view}`);
  }

  closeMenu();
  window.scrollTo({ top: 0, behavior: 'smooth' });
  target.setAttribute('tabindex', '-1');
  target.focus({ preventScroll: true });
}

document.addEventListener('click', event => {
  const link = event.target.closest('[data-route]');
  if (!link) return;
  event.preventDefault();
  showView(link.dataset.route);
});

window.addEventListener('popstate', () => {
  showView(location.hash.slice(1) || 'inicio', false);
});

menuToggle.addEventListener('click', () => {
  const open = menuToggle.getAttribute('aria-expanded') !== 'true';
  menuToggle.setAttribute('aria-expanded', String(open));
  nav.classList.toggle('is-open', open);
});

nav.addEventListener('click', event => {
  if (event.target.closest('a')) closeMenu();
});

document.addEventListener('keydown', event => {
  if (event.key === 'Escape') closeMenu();
});

mobile.addEventListener('change', syncNavigation);
syncNavigation();

if (media.downloadUrl) {
  const downloadLink = document.querySelector('[data-download-link]');
  const downloadStatus = document.querySelector('[data-download-status]');
  downloadLink.href = media.downloadUrl;
  downloadLink.hidden = false;
  downloadStatus.hidden = true;
}

// =========================================
// COMUNIDAD XURCA — FIRESTORE
// =========================================

const publicationForm = document.querySelector('#publication-form');
const publicationFeedback = document.querySelector('#publication-feedback');
const publicationSubmit = document.querySelector('#publication-submit');
const publicationsList = document.querySelector('#publications-list');

const categoryNames = {
  general: 'General',
  temperatura: 'Temperatura',
  precipitacion: 'Precipitación',
  humedad: 'Humedad',
  atmosfera: 'Atmósfera y ozono',
  otros: 'Otros fenómenos'
};

function showFeedback(message, type = '') {
  if (!publicationFeedback) return;
  publicationFeedback.textContent = message;
  publicationFeedback.dataset.type = type;
}

function formatDate(timestamp) {
  if (!timestamp?.toDate) return 'Fecha no disponible';

  return new Intl.DateTimeFormat('es-AR', {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(timestamp.toDate());
}

function renderPublication(publication) {
  const article = document.createElement('article');
  article.className = 'publication-card';

  const header = document.createElement('div');
  header.className = 'publication-header';

  const category = document.createElement('span');
  category.className = 'publication-category';
  category.textContent = categoryNames[publication.categoria] || 'Otros';

  const date = document.createElement('time');
  date.className = 'publication-date';
  date.textContent = formatDate(publication.fecha);

  const title = document.createElement('h3');
  title.textContent = publication.titulo || 'Publicación sin título';

  const content = document.createElement('p');
  content.className = 'publication-content';
  content.textContent = publication.contenido || '';

  const author = document.createElement('p');
  author.className = 'publication-author';
  author.textContent = 'Publicado por la comunidad XURCA';

  header.append(category, date);
  article.append(header, title, content, author);

  return article;
}

function listenToPublications() {
  if (!publicationsList) return;

  const publicationsQuery = query(
    collection(db, 'publicaciones'),
    orderBy('fecha', 'desc')
  );

  onSnapshot(publicationsQuery, snapshot => {
    publicationsList.replaceChildren();

    if (snapshot.empty) {
      const emptyMessage = document.createElement('p');
      emptyMessage.className = 'muted';
      emptyMessage.textContent = 'Todavía no hay publicaciones. ¡Podés ser la primera persona en compartir una investigación!';
      publicationsList.append(emptyMessage);
      return;
    }

    snapshot.forEach(documentSnapshot => {
      const publication = renderPublication(documentSnapshot.data());
      publicationsList.append(publication);
    });
  }, error => {
    console.error('Error al cargar publicaciones:', error);
    publicationsList.textContent = 'No pudimos cargar las publicaciones. Revisá tu conexión e intentá nuevamente.';
  });
}

if (publicationForm) {
  publicationForm.addEventListener('submit', async event => {
    event.preventDefault();

    const title = publicationForm.elements.title.value.trim();
    const category = publicationForm.elements.category.value;
    const content = publicationForm.elements.content.value.trim();

    if (!title || !category || !content) {
      showFeedback('Completá todos los campos antes de publicar.', 'error');
      return;
    }

    if (title.length > 120 || content.length > 3000) {
      showFeedback('El título o el contenido superan el límite permitido.', 'error');
      return;
    }

    publicationSubmit.disabled = true;
    publicationSubmit.textContent = 'Publicando...';
    showFeedback('Estamos publicando tu aporte...');

    try {
      await authReady;

      await addDoc(collection(db, 'publicaciones'), {
        titulo: title,
        contenido: content,
        categoria: category,
        autor: 'Comunidad XURCA',
        estado: 'publicado',
        fecha: serverTimestamp()
      });

      publicationForm.reset();
      showFeedback('¡Tu investigación se publicó correctamente!', 'success');
    } catch (error) {
      console.error('Error al publicar:', error);
      showFeedback('No pudimos publicar tu aporte. Intentá nuevamente en unos minutos.', 'error');
    } finally {
      publicationSubmit.disabled = false;
      publicationSubmit.textContent = 'Publicar investigación →';
    }
  });
}

async function initializeCommunity() {
  if (!publicationForm || !publicationsList) return;

  try {
    await authReady;
    listenToPublications();
  } catch (error) {
    console.error('No se pudo iniciar la sesión anónima:', error);
    showFeedback('No pudimos conectar con la comunidad. Recargá la página e intentá nuevamente.', 'error');
    publicationsList.textContent = 'La comunidad no está disponible en este momento.';
  }
}

initializeCommunity();

// Abrir la sección indicada en la URL al cargar la página.
showView(location.hash.slice(1) || 'inicio', false);
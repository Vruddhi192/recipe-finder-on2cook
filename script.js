let recipes = [];

// Desktop elements
const dietTypeChipGroup = document.getElementById('dietTypeChipGroup');
const cookingTime = document.getElementById('cookingTime');
const cookingTimeLabel = document.getElementById('cookingTimeLabel');
const cookingModeRadioGroup = document.getElementById('cookingModeRadioGroup');
const cuisineRadioGroup = document.getElementById('cuisineRadioGroup');
const categoryRadioGroup = document.getElementById('categoryRadioGroup');
const accessoryRadioGroup = document.getElementById('accessoryRadioGroup');
const clearBtn = document.getElementById('clearBtn');
const recipesGrid = document.getElementById('recipesGrid');
const recipeCountEl = document.getElementById('recipeCount');
const popupPDF = document.getElementById('popupPDF');

const searchBarDesktop = document.getElementById('searchBarDesktop');
const sortTimeAsc = document.getElementById('sortTimeAsc');
const sortTimeDesc = document.getElementById('sortTimeDesc');

// Mobile elements
const mobileFilterBtn = document.getElementById('mobileFilterBtn');
const mobileFilterModal = document.getElementById('mobileFilterModal');
const closeMobileFilter = document.getElementById('closeMobileFilter');
const searchBarMobile = document.getElementById('searchBarMobile');
const dietTypeMobile = document.getElementById('dietTypeMobile');
const cookingModeMobile = document.getElementById('cookingModeMobile');
const cuisineMobile = document.getElementById('cuisineMobile');
const categoryMobile = document.getElementById('categoryMobile');
const accessoryMobile = document.getElementById('accessoryMobile');
const cookingTimeMobile = document.getElementById('cookingTimeMobile');
const cookingTimeLabelMobile = document.getElementById('cookingTimeLabelMobile');
const clearBtnMobile = document.getElementById('clearBtnMobile');

const sortTimeAscMobile = document.getElementById('sortTimeAscMobile');
const sortTimeDescMobile = document.getElementById('sortTimeDescMobile');

// Popup elements
const popupModal = document.getElementById('popupModal');
const popupImage = document.getElementById('popupImage');
const popupCloseBtn = document.getElementById('popupCloseBtn');

// New recipes banner elements
const newRecipesBanner = document.getElementById('newRecipesBanner');
const newRecipesCloseBtn = document.getElementById('newRecipesCloseBtn');
const newRecipesSub = document.getElementById('newRecipesSub');
const exploreNewRecipesBtn = document.getElementById('exploreNewRecipesBtn');
const backToAllBtn = document.getElementById('backToAllBtn');

// ===============================
// NEW RECIPES BANNER CONFIG
// ===============================
// How many of the most-recently-modified recipes count as "new".
const NEW_RECIPES_COUNT = 20;
// The field name written into recipes_fix.json by the pipeline that holds
// the Smartsheet "modified" date for each recipe. Update this if the
// pipeline writes a different key (e.g. "lastModified", "Modified Date").
const MODIFIED_DATE_FIELD = 'Modified';
// How many random photos to show in the banner's image stack.
const NEW_RECIPES_BANNER_IMAGE_COUNT = 5;

let newRecipeNames = new Set(); // Recipe Names currently flagged as "new", used by the grid filter

/** Tries a handful of common date formats/shapes so the pipeline's exact
 *  Smartsheet export format doesn't have to match exactly. Returns a Date
 *  or null if unparseable. */
function parseModifiedDate(value) {
  if (!value) return null;
  if (value instanceof Date) return isNaN(value) ? null : value;
  const d = new Date(value);
  if (!isNaN(d)) return d;
  // Fallback: DD/MM/YYYY or DD-MM-YYYY style strings
  const m = String(value).match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})/);
  if (m) {
    const [, dd, mm, yyyy] = m;
    const year = yyyy.length === 2 ? `20${yyyy}` : yyyy;
    const alt = new Date(`${year}-${mm.padStart(2, '0')}-${dd.padStart(2, '0')}`);
    if (!isNaN(alt)) return alt;
  }
  return null;
}

/** Returns the N most-recently-modified recipes (visible ones only),
 *  sorted newest first. Recipes without a parseable date are excluded. */
function getNewestRecipes(count) {
  return recipes
    .filter(r => !r.hidden)
    .map(r => ({ recipe: r, date: parseModifiedDate(r[MODIFIED_DATE_FIELD]) }))
    .filter(x => x.date)
    .sort((a, b) => b.date - a.date)
    .slice(0, count)
    .map(x => x.recipe);
}

/** Returns `count` random visible recipes (used only for the banner's
 *  decorative photo stack — has no bearing on which recipes are flagged
 *  "new" for the grid filter). */
// Put your own image paths/URLs here — as many as you like, 3 will be
// picked at random on each page load. Local files just need to sit in
// the same folder as index.html (or a subfolder), e.g. "banner/photo1.jpg".
const NEW_RECIPES_BANNER_CUSTOM_IMAGES = [
  './assets/banner-images/photo1.jpg',
  './assets/banner-images/photo2.jpg',
  './assets/banner-images/photo3.jpg',
  './assets/banner-images/photo4.jpg',
  './assets/banner-images/photo5.jpg',
];

function getRandomBannerImages(count) {
  const pool = [...NEW_RECIPES_BANNER_CUSTOM_IMAGES];
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  return pool.slice(0, count);
}

/** Builds and shows the "New Recipes" banner. This always runs on every
 *  page load/visit — there's no dismissal memory, so closing the banner
 *  only hides it for the current page view; it reappears on the next
 *  visit or reload. */
function initNewRecipesBanner() {
  if (!newRecipesBanner) return;

  const newest = getNewestRecipes(NEW_RECIPES_COUNT);
  if (newest.length === 0) {
    // No recipe has a Modified date yet (pipeline not updated) — stay
    // hidden rather than show an empty/incorrect banner.
    newRecipesBanner.style.display = 'none';
    newRecipeNames = new Set();
    return;
  }

  newRecipeNames = new Set(newest.map(r => r['Recipe Name']));

  // Sub-line shows however many recipes actually qualified (could be
  // fewer than NEW_RECIPES_COUNT if the catalogue itself is smaller).
  const countEl = document.getElementById('newRecipesCount');
  if (countEl) {
    countEl.textContent = newest.length;
  }
  if (newRecipesSub) {
    newRecipesSub.textContent = 'Transform simple ingredients into extraordinary meals.';
  }

  // Photo stack: random images, NOT tied to which recipes are "new".
  const imagesContainer = document.getElementById('newRecipesImages');
  if (imagesContainer) {
    imagesContainer.innerHTML = '';
    const randomPicks = getRandomBannerImages(NEW_RECIPES_BANNER_IMAGE_COUNT);
    randomPicks.forEach(src => {
      const img = document.createElement('img');
      img.src = src;
      img.alt = 'Recipe photo';
      imagesContainer.appendChild(img);
    });
  }

  newRecipesBanner.style.display = 'flex';
}

// Dismiss only hides the banner for the current page view — no
// localStorage, so it always comes back on the next visit/reload.
newRecipesCloseBtn?.addEventListener('click', () => {
  newRecipesBanner.style.display = 'none';
});

exploreNewRecipesBtn?.addEventListener('click', () => {
  filterState.onlyNew = true;
  resetOtherFiltersForNewView();
  writeFiltersToURL();
  showRecipes();
  document.getElementById('recipesGrid')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
});

// "Back to All Recipes" — exits the new-recipes filtered view, restoring
// the full grid with default filters.
backToAllBtn?.addEventListener('click', () => {
  filterState.onlyNew = false;
  resetOtherFiltersForNewView();
  writeFiltersToURL();
  showRecipes();
});

/** Clears the other filters when jumping into "new recipes" view so the
 *  user sees the full new batch rather than an intersection with whatever
 *  filters happened to be active. */
function resetOtherFiltersForNewView() {
  filterState.searchTerm = '';
  filterState.dietVal = 'All';
  filterState.cookingModeVal = 'All';
  filterState.cuisineVal = 'All';
  filterState.categoryVal = 'All';
  filterState.accessoryVal = 'All';
  filterState.flavorVal = 'All';
  filterState.consistencyVal = 'All';
  filterState.maxCookingTime = 35;

  if (searchBarDesktop) searchBarDesktop.value = '';
  if (searchBarMobile) searchBarMobile.value = '';
  document.querySelectorAll('.diet-chip').forEach(c => c.classList.toggle('active', c.dataset.value === 'All'));
  document.querySelectorAll('.mini-chip').forEach(c => c.classList.toggle('active', c.dataset.value === 'All'));
  ['cookingMode', 'cuisine', 'category', 'accessory'].forEach(name => {
    const allInput = document.querySelector(`input[name="${name}"][value="All"]`);
    if (allInput) allInput.checked = true;
  });
  if (cookingTime) { cookingTime.value = 35; cookingTimeLabel.textContent = '35 min'; }
  if (cookingTimeMobile) { cookingTimeMobile.value = 35; cookingTimeLabelMobile.textContent = '35'; }
}

// FILTER STATE
const filterState = {
  searchTerm: '',
  sortBy: 'time-asc',
  dietVal: 'All',
  cookingModeVal: 'All',
  cuisineVal: 'All',
  categoryVal: 'All',
  accessoryVal: 'All',
  flavorVal: 'All',
  consistencyVal: 'All',
  maxCookingTime: 35,
  onlyNew: false // true while viewing the "Explore New Recipes" filtered grid
};

// ─── URL STATE ────────────────────────────────────────────────────────────────

/**
 * Reads current URL search params and returns a filterState-shaped object.
 * Only keys that exist in the URL are returned; the rest stay as defaults.
 */
function readFiltersFromURL() {
  const params = new URLSearchParams(window.location.search);
  const result = {};
  if (params.has('q'))         result.searchTerm     = params.get('q');
  if (params.has('sort'))      result.sortBy          = params.get('sort');
  if (params.has('diet'))      result.dietVal         = params.get('diet');
  if (params.has('mode'))      result.cookingModeVal  = params.get('mode');
  if (params.has('cuisine'))   result.cuisineVal      = params.get('cuisine');
  if (params.has('category'))  result.categoryVal     = params.get('category');
  if (params.has('accessory')) result.accessoryVal    = params.get('accessory');
  if (params.has('time'))      result.maxCookingTime  = parseInt(params.get('time'), 10);
  if (params.has('new'))       result.onlyNew         = params.get('new') === '1';
  return result;
}

/**
 * Pushes the current filterState into the URL as search params.
 * Params that are at their default value are omitted to keep URLs clean.
 */
function writeFiltersToURL() {
  const params = new URLSearchParams();
  if (filterState.searchTerm)                    params.set('q',         filterState.searchTerm);
  if (filterState.sortBy !== 'time-asc')         params.set('sort',      filterState.sortBy);
  if (filterState.dietVal !== 'All')             params.set('diet',      filterState.dietVal);
  if (filterState.cookingModeVal !== 'All')      params.set('mode',      filterState.cookingModeVal);
  if (filterState.cuisineVal !== 'All')          params.set('cuisine',   filterState.cuisineVal);
  if (filterState.categoryVal !== 'All')         params.set('category',  filterState.categoryVal);
  if (filterState.accessoryVal !== 'All')        params.set('accessory', filterState.accessoryVal);
  if (filterState.maxCookingTime !== 35)         params.set('time',      filterState.maxCookingTime);
  if (filterState.onlyNew)                       params.set('new',       '1');

  const newSearch = params.toString();
  const newURL = newSearch
    ? `${window.location.pathname}?${newSearch}`
    : window.location.pathname;

  // Use replaceState so every filter tweak doesn't pollute browser history
  window.history.replaceState(null, '', newURL);
}

/**
 * Applies URL params to filterState and then syncs all UI controls to match.
 * Call this once after recipes are loaded (controls must exist in the DOM).
 */
function applyURLFiltersToUI() {
  const fromURL = readFiltersFromURL();
  Object.assign(filterState, fromURL);

  // ── Desktop search bar ──
  if (searchBarDesktop) searchBarDesktop.value = filterState.searchTerm;

  // ── Sort buttons ──
  updateSortButtons();
  updateMobileSortButtons();

  // ── Cooking time slider ──
  cookingTime.value = filterState.maxCookingTime;
  cookingTimeLabel.textContent = `${filterState.maxCookingTime} min`;
  cookingTimeMobile.value = filterState.maxCookingTime;
  cookingTimeLabelMobile.textContent = `${filterState.maxCookingTime}`;

  // ── Diet chips (desktop) ──
  document.querySelectorAll('.diet-chip').forEach(c => {
    c.classList.toggle('active', c.dataset.value === filterState.dietVal);
  });

  // ── Radio groups (desktop) ──
  syncRadioGroup('cookingMode', filterState.cookingModeVal);
  syncRadioGroup('cuisine',     filterState.cuisineVal);
  syncRadioGroup('category',    filterState.categoryVal);
  syncRadioGroup('accessory',   filterState.accessoryVal);

  // ── Mobile selects ──
  if (searchBarMobile)    searchBarMobile.value    = filterState.searchTerm;
  dietTypeMobile.value     = filterState.dietVal;
  cookingModeMobile.value  = filterState.cookingModeVal;
  cuisineMobile.value      = filterState.cuisineVal;
  categoryMobile.value     = filterState.categoryVal;
  accessoryMobile.value    = filterState.accessoryVal;
}

/** Checks the correct radio for a given filter group name. */
function syncRadioGroup(name, value) {
  const inputs = document.querySelectorAll(`input[name="${name}"]`);
  inputs.forEach(input => {
    if (input.value === value) input.checked = true;
  });
}

// ─────────────────────────────────────────────────────────────────────────────

searchBarDesktop?.addEventListener('input', debounce((e) => {
  filterState.searchTerm = e.target.value.toLowerCase().trim();
  filterState.onlyNew = false;
  writeFiltersToURL();
  showRecipes();
}, 250));

sortTimeAscMobile?.addEventListener('click', () => {
  filterState.sortBy = 'time-asc';
  updateMobileSortButtons();
  writeFiltersToURL();
  applyMobileFilters();
});

sortTimeDescMobile?.addEventListener('click', () => {
  filterState.sortBy = 'time-desc';
  updateMobileSortButtons();
  writeFiltersToURL();
  applyMobileFilters();
});

// Helpers
function getUniqueValues(key) {
  const set = new Set(recipes.map(r => r[key]).filter(Boolean));
  return Array.from(set).sort();
}
function getUniqueAccessories() {
  const s = new Set();
  recipes.forEach(r => {
    if (r['Accessories']) {
      r['Accessories'].split(',').forEach(a => s.add(a.trim()));
    }
  });
  return Array.from(s).sort();
}

function setupSortButtons() {
  sortTimeAsc?.addEventListener('click', () => {
    filterState.sortBy = 'time-asc';
    updateSortButtons();
    writeFiltersToURL();
    showRecipes();
  });
  
  sortTimeDesc?.addEventListener('click', () => {
    filterState.sortBy = 'time-desc';
    updateSortButtons();
    writeFiltersToURL();
    showRecipes();
  });
}

function updateSortButtons() {
  sortTimeAsc?.classList.toggle('active', filterState.sortBy === 'time-asc');
  sortTimeDesc?.classList.toggle('active', filterState.sortBy === 'time-desc');
}

function updateMobileSortButtons() {
  sortTimeAscMobile?.classList.toggle('active', filterState.sortBy === 'time-asc');
  sortTimeDescMobile?.classList.toggle('active', filterState.sortBy === 'time-desc');
}

// Build chips/radios
function buildDietChips(values) {
  dietTypeChipGroup.innerHTML = '';
  const allValues = ['All', ...values];
  allValues.forEach(val => {
    const btn = document.createElement('button');
    btn.className = 'diet-chip' + (val === filterState.dietVal ? ' active' : '');
    btn.dataset.value = val;
    btn.innerHTML =
      val === 'All'
      ? '<span class="diet-chip-icon">🍽</span><span>All</span>'
      : val === 'VEG'
      ? '<span class="diet-chip-icon veg-dot"></span><span>Veg</span>'
      : val === 'EGG'
      ? '<span class="diet-chip-icon egg-dot"></span><span>Egg</span>'
      : '<span class="diet-chip-icon nonveg-dot"></span><span>Non Veg</span>';
    btn.addEventListener('click', () => {
      document.querySelectorAll('.diet-chip').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      filterState.dietVal = val;
      filterState.onlyNew = false;
      writeFiltersToURL();
      showRecipes();
    });
    dietTypeChipGroup.appendChild(btn);
  });
}

function buildRadioGroup(container, values, name) {
  container.innerHTML = '';
  const allValues = ['All', ...values];
  allValues.forEach(val => {
    const label = document.createElement('label');
    label.className = 'radio-pill';
    const currentVal = filterState[`${name}Val`];
    label.innerHTML = `
      <input type="radio" name="${name}" value="${val}" ${val === currentVal ? 'checked' : ''}>
      <span>${val}</span>
    `;
    const input = label.querySelector('input');
    input.addEventListener('change', () => {
      filterState[`${name}Val`] = val;
      filterState.onlyNew = false;
      writeFiltersToURL();
      showRecipes();
    });
    container.appendChild(label);
  });
}

// Build mini flavor/consistency chip filters
function buildMiniChips(containerId, values, stateKey, configMap) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';
  const allValues = ['All', ...values];
  allValues.forEach(val => {
    const btn = document.createElement('button');
    btn.className = 'mini-chip' + (val === filterState[stateKey] ? ' active' : '');
    btn.dataset.value = val;
    const cfg = configMap[val];
    btn.innerHTML = val === 'All' ? 'All' : `${cfg ? cfg.emoji + ' ' : ''}${val}`;
    btn.addEventListener('click', () => {
      container.querySelectorAll('.mini-chip').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      filterState[stateKey] = val;
      filterState.onlyNew = false;
      writeFiltersToURL();
      showRecipes();
    });
    container.appendChild(btn);
  });
}

// Populate mobile selects
function populateMobileFilters() {
  const setOptions = (select, values) => {
    select.innerHTML = '<option value="All">All</option>';
    values.forEach(v => {
      const opt = document.createElement('option');
      opt.value = v;
      opt.textContent = v;
      select.appendChild(opt);
    });
  };
  setOptions(dietTypeMobile, getUniqueValues('Veg/Non Veg'));
  setOptions(cookingModeMobile, getUniqueValues('Cooking Mode'));
  setOptions(cuisineMobile, getUniqueValues('Cuisine'));
  setOptions(categoryMobile, getUniqueValues('Category'));
  setOptions(accessoryMobile, getUniqueAccessories());
  const flavorMobile = document.getElementById('flavorMobile');
  const consistencyMobile = document.getElementById('consistencyMobile');
  if (flavorMobile) setOptions(flavorMobile, getUniqueValues('Flavor Profile'));
  if (consistencyMobile) setOptions(consistencyMobile, getUniqueValues('Consistency'));
}

// Load recipes
function loadRecipes() {
  fetch('recipes_fix.json')
    .then(r => r.json())
    .then(data => {
      recipes = data;

      // Build UI controls
      buildDietChips(getUniqueValues('Veg/Non Veg'));
      buildRadioGroup(cookingModeRadioGroup, getUniqueValues('Cooking Mode'), 'cookingMode');
      buildRadioGroup(cuisineRadioGroup, getUniqueValues('Cuisine'), 'cuisine');
      buildRadioGroup(categoryRadioGroup, getUniqueValues('Category'), 'category');
      buildRadioGroup(accessoryRadioGroup, getUniqueAccessories(), 'accessory');
      buildMiniChips('flavorChipGroup', getUniqueValues('Flavor Profile'), 'flavorVal', FLAVOUR_CONFIG);
      buildMiniChips('consistencyChipGroup', getUniqueValues('Consistency'), 'consistencyVal', CONSISTENCY_CONFIG);
      populateMobileFilters();

      // Build the "new recipes" banner before applying URL filters, since
      // a `?new=1` URL needs newRecipeNames already populated.
      initNewRecipesBanner();

      // ← Apply any filters baked into the shared URL
      applyURLFiltersToUI();

      showRecipes();
      setupSortButtons();
      updateSortButtons();
      updateMobileSortButtons();
    })
    .catch(() => {
      recipesGrid.innerHTML = '<p class="error-text">Failed to load recipes.</p>';
    });
}

// Add this function before downloadRecipe
function showDownloadToast(message) {
  // Remove existing toasts
  document.querySelectorAll('.download-toast').forEach(t => t.remove());
  
  const toast = document.createElement('div');
  toast.className = 'download-toast';
  toast.innerHTML = `
    <div class="icon">✓</div>
    <span>${message}</span>
  `;
  
  // Ultra-modern glassmorphism styling
  toast.style.cssText = `
    position: fixed; top: 24px; right: 24px; max-width: 320px;
    background: rgba(16, 185, 129, 0.95); 
    backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.2);
    color: white; padding: 16px 20px; border-radius: 16px; 
    font-size: 14px; font-weight: 500; z-index: 9999;
    box-shadow: 0 20px 40px rgba(0,0,0,0.15), 0 0 0 1px rgba(255,255,255,0.1);
    display: flex; align-items: center; gap: 12px;
    transform: translateX(400px); opacity: 0;
    transition: all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
  `;
  
  const icon = toast.querySelector('.icon');
  icon.style.cssText = `
    width: 20px; height: 20px; border-radius: 50%; 
    background: rgba(255,255,255,0.3); display: flex; align-items: center;
    justify-content: center; font-size: 14px; font-weight: bold;
  `;
  
  document.body.appendChild(toast);
  
  // Slide in animation
  requestAnimationFrame(() => {
    toast.style.transform = 'translateX(0)';
    toast.style.opacity = '1';
  });
  
  // Slide out + remove
  setTimeout(() => {
    toast.style.transform = 'translateX(400px)';
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 400);
  }, 3200);
}

async function downloadSingleRecipeZip(recipe) {
  const popupPath = recipe.PopupImage.split('?')[0];
  const fileNameWithExt = popupPath.split('/').pop();
  let baseName = fileNameWithExt.replace(/\.pdf$/i, '');
  const zipUrl = `/updated_zips/${baseName}.zip`;
  console.log('Trying:', zipUrl);

  const headResponse = await fetch(zipUrl, { method: 'HEAD' });
  if (!headResponse.ok) throw new Error(`Server error: ${headResponse.status}`);
  const contentType = headResponse.headers.get('Content-Type');
  if (!contentType || (!contentType.includes('zip') && !contentType.includes('application/octet-stream'))) {
    throw new Error('Not a ZIP file');
  }
  const getResponse = await fetch(zipUrl);
  const blob = await getResponse.blob();
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `${baseName}.zip`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
  return baseName;
}

async function downloadRecipe(recipe, event) {
  event.stopPropagation();

  // Collect all recipes to download: linked (clubbed) first, then main
  const toDownload = [];
  if (recipe.clubbedWith) {
    const linked = recipes.find(r => r['Recipe Name'] === recipe.clubbedWith);
    if (linked) toDownload.push(linked);
  }
  toDownload.push(recipe);

  const downloaded = [];
  for (const r of toDownload) {
    try {
      const name = await downloadSingleRecipeZip(r);
      downloaded.push(name);
    } catch (e) {
      console.error(e);
      const popupPath = r.PopupImage.split('?')[0];
      const baseName = popupPath.split('/').pop().replace(/\.pdf$/i, '');
      alert(`ZIP not available: /updated_zips/${baseName}.zip (${e.message})`);
    }
  }

  if (downloaded.length > 0) {
    showDownloadToast(downloaded.join(' + ') + ' ZIP' + (downloaded.length > 1 ? 's' : ''));
  }
}


// Filtering
function filterRecipes() {
  return recipes.filter(r => {
    if (r.hidden) return false;

    if (filterState.onlyNew) {
      return newRecipeNames.has(r['Recipe Name']);
    }

    const searchOk =
      !filterState.searchTerm ||
      (r['Recipe Name'] || '').toLowerCase().includes(filterState.searchTerm);

    const dietOk =
      filterState.dietVal === 'All' || r['Veg/Non Veg'] === filterState.dietVal;

    const modeOk =
      filterState.cookingModeVal === 'All' || r['Cooking Mode'] === filterState.cookingModeVal;

    const cuisineOk =
      filterState.cuisineVal === 'All' || r['Cuisine'] === filterState.cuisineVal;

    const catOk =
      filterState.categoryVal === 'All' || r['Category'] === filterState.categoryVal;

    const accOk =
      filterState.accessoryVal === 'All' ||
      (r['Accessories'] &&
        r['Accessories'].split(',').map(a => a.trim()).includes(filterState.accessoryVal));

    const timeOk =
      r['On2Cook Cooking Time'] &&
      parseInt(r['On2Cook Cooking Time'], 10) <= filterState.maxCookingTime;

    const flavorOk =
      filterState.flavorVal === 'All' || r['Flavor Profile'] === filterState.flavorVal;

    const consistencyOk =
      filterState.consistencyVal === 'All' || r['Consistency'] === filterState.consistencyVal;

    return searchOk && dietOk && modeOk && cuisineOk && catOk && accOk && timeOk && flavorOk && consistencyOk;
  });
}

// Render recipes

// ===============================
// FLAVOUR PROFILE & CONSISTENCY HELPERS
// ===============================

const FLAVOUR_CONFIG = {
  'Sweet':        { emoji: '🍬', color: '#f9a8d4', text: '#9d174d' },
  'Sour':         { emoji: '🍋', color: '#fef08a', text: '#713f12' },
  'Medium Spicy': { emoji: '🌶️', color: '#fca5a5', text: '#991b1b' },
  'Less Spicy':   { emoji: '🫑', color: '#bbf7d0', text: '#14532d' },
  'Extra Spicy':  { emoji: '🔥', color: '#fb923c', text: '#7c2d12' },
};

const CONSISTENCY_CONFIG = {
  'Dry':          { emoji: '🍢', color: '#e5e7eb', text: '#374151' },
  'Semi-Dry':     { emoji: '🍛', color: '#dbeafe', text: '#1e3a8a' },
  'Semi - Gravy': { emoji: '🍛', color: '#fed7aa', text: '#7c2d12' },
  'Gravy':        { emoji: '🍲', color: '#fde68a', text: '#78350f' },
  'Base Gravy':   { emoji: '🥘', color: '#d1fae5', text: '#065f46' },
  'Base Sauce':   { emoji: '🥫', color: '#fecdd3', text: '#881337' },
  'Liquid':       { emoji: '🍵', color: '#bfdbfe', text: '#1e40af' },
};

function buildProfileStrip(flavour, consistency) {
  const fp = flavour ? FLAVOUR_CONFIG[flavour] : null;
  const con = consistency ? CONSISTENCY_CONFIG[consistency] : null;

  if (!fp && !con) return '';

  const parts = [];
  if (fp) {
    parts.push(`<span class="profile-item">${fp.emoji} ${flavour}</span>`);
  }
  if (fp && con) {
    parts.push(`<span class="profile-divider">|</span>`);
  }
  if (con) {
    parts.push(`<span class="profile-item">${con.emoji} ${consistency}</span>`);
  }
  return `<div class="profile-strip">${parts.join('')}</div>`;
}

// ── Prerequisite Recipe ──────────────────────────────────────────────────
// "Prerequisite Recipe" is a Smartsheet column: the name of a recipe that
// needs to be prepared first (e.g. "Manchurian Fry" requires "Paneer Fry"
// to already be made). We look the name up against the full recipes list
// to grab its thumbnail and to make the row clickable.

function findRecipeByName(name) {
  if (!name) return null;
  const target = name.trim().toUpperCase();
  return recipes.find(r => (r['Recipe Name'] || '').trim().toUpperCase() === target) || null;
}

function buildPrerequisiteRow(recipe) {
  const raw = (recipe['Prerequisite Recipe'] || '').trim();
  if (!raw) return '';

  // Comma-separated in the sheet — each one is its own prerequisite and
  // gets its own row/thumbnail/tap target, not lumped into one string.
  const prereqNames = raw.split(',').map(n => n.trim()).filter(Boolean);
  if (!prereqNames.length) return '';

  const rows = prereqNames.map(prereqName => {
    const prereqRecipe = findRecipeByName(prereqName);
    const thumbSrc = prereqRecipe ? prereqRecipe.Image : '';
    const safeName = prereqName.replace(/"/g, '&quot;');

    return `
      <div class="prereq-row" data-prereq-name="${safeName}" title="Tap to view ${safeName}">
        <div class="prereq-thumb-wrap">
          ${thumbSrc
            ? `<img src="${thumbSrc}" alt="${safeName}" class="prereq-thumb" />`
            : `<div class="prereq-thumb prereq-thumb-placeholder">🍳</div>`}
        </div>
        <div class="prereq-info">
          <span class="prereq-label">Prerequisite Recipe</span>
          <span class="prereq-name">${prereqName}</span>
        </div>
        <span class="prereq-chevron">&rsaquo;</span>
      </div>
    `;
  }).join('');

  return `<div class="prereq-group">${rows}</div>`;
}

function showRecipes() {
  let filtered = filterRecipes();

  // Apply sorting based on filterState.sortBy.
  // In the "new recipes" view, keep newest-first ordering instead of
  // re-sorting by cooking time, so the explore view matches the banner.
  if (filterState.onlyNew) {
    filtered = filtered.sort((a, b) => {
      const da = parseModifiedDate(a[MODIFIED_DATE_FIELD]) || 0;
      const db = parseModifiedDate(b[MODIFIED_DATE_FIELD]) || 0;
      return db - da;
    });
  } else {
    filtered = filtered.sort((a, b) => {
      const ta = parseInt(a['On2Cook Cooking Time'], 10) || 999;
      const tb = parseInt(b['On2Cook Cooking Time'], 10) || 999;

      if (filterState.sortBy === 'time-asc') {
        return ta - tb;
      } else {
        return tb - ta;
      }
    });
  }

  recipeCountEl.textContent = filterState.onlyNew
    ? `${filtered.length} new recipes`
    : `${filtered.length} recipes found`;

  if (backToAllBtn) {
    backToAllBtn.style.display = filterState.onlyNew ? 'inline-flex' : 'none';
  }

  recipesGrid.innerHTML = '';

  if (filtered.length === 0) {
  recipesGrid.innerHTML = `
    <div class="empty-state">
      <div class="empty-illustration">
        <span class="empty-emoji">🍽️</span>
        <span class="empty-sparkle">✨</span>
      </div>
      <h3 class="empty-title">No recipes on this plate…</h3>
      <p class="empty-text">
        Try relaxing a filter or two, or switch cuisines to discover more delicious ideas.
      </p>
      <button class="empty-btn" type="button" onclick="document.getElementById('clearBtn').click()">
        Clear filters & explore
      </button>
    </div>
  `;
  return;
}

  filtered.forEach(r => {
    const card = document.createElement('div');
    card.className = 'recipe-card';

    const cleanTime = r['Normal Cooking Time']?.replace(/[,;!?'"]/g, '') || '';
    const isNew = filterState.onlyNew && newRecipeNames.has(r['Recipe Name']);

    card.innerHTML = `
  <div class="recipe-card-image-wrap">
    ${isNew ? '<span class="recipe-new-tag">NEW</span>' : ''}
    <img src="${r.Image}" alt="${r['Recipe Name']}" class="recipe-image" data-zip-url="${r.ZipURL || r.PopupImage || r.Image}" />
    <div class="recipe-time-pill">${r['Total Output']}</div>
    <!-- Download button - HIDDEN by default -->
    <button class="download-btn" title="Download Recipe ZIP">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
        <polyline points="7 10 12 15 17 10"></polyline>
        <line x1="12" y1="15" x2="12" y2="3"></line>
      </svg>
    </button>
  </div>

      <div class="recipe-card-body">
        <div class="recipe-title-row">
          <h3 class="recipe-name">${r['Recipe Name']}</h3>
        <span class="diet-icon 
          ${
            r['Veg/Non Veg'] === 'VEG' 
              ? 'veg' 
              : r['Veg/Non Veg'] === 'EGG' 
                ? 'egg' 
                : 'non-veg'
          }">
        </span>
        </div>
        <p class="recipe-meta">${r['Cuisine']} • ${r['Cooking Mode']} • ${r['Category']}</p>
        ${buildProfileStrip(r['Flavor Profile'] || '', r['Consistency'] || '')}
        <div class="badge-row">
          <div class="badge on2cook">
            <span class="badge-icon">⚡</span>
              <span class="badge-text">
                On2Cook ${r['On2Cook Cooking Time']} ${parseInt(r['On2Cook Cooking Time'], 10) === 1 ? 'min' : 'mins'}
              </span>
          </div>
          <div class="badge normal">
            <span class="badge-icon">⏱</span>
            <span class="badge-text">Normal  ${cleanTime}</span>
          </div>
        </div>
        ${buildPrerequisiteRow(r)}
      </div>
    `;

    // Add click handler for card (excluding download/save buttons and the
    // prerequisite row, which navigates to a different recipe's popup)
    card.addEventListener('click', (e) => {
      const prereqEl = e.target.closest('.prereq-row');
      if (prereqEl) {
        e.stopPropagation();
        const target = findRecipeByName(prereqEl.getAttribute('data-prereq-name'));
        if (target) openPopup(target);
        return;
      }
      if (!e.target.closest('.download-btn') && !e.target.closest('.save-recipe-btn')) {
        openPopup(r);
      }
    });

    // Add download button handler
    const downloadBtn = card.querySelector('.download-btn');
    downloadBtn.addEventListener('click', (e) => {
      downloadRecipe(r, e);
    });

    recipesGrid.appendChild(card);
  });
}

// Desktop interactions
cookingTime.addEventListener('input', () => {
  filterState.maxCookingTime = parseInt(cookingTime.value, 10);
  cookingTimeLabel.textContent = `${cookingTime.value} min`;
  filterState.onlyNew = false;
  writeFiltersToURL();
  showRecipes();
});

clearBtn.addEventListener('click', () => {
  filterState.searchTerm = '';
  filterState.dietVal = 'All';
  filterState.cookingModeVal = 'All';
  filterState.cuisineVal = 'All';
  filterState.categoryVal = 'All';
  filterState.accessoryVal = 'All';
  filterState.maxCookingTime = 35;
  filterState.sortBy = 'time-asc';
  filterState.onlyNew = false;
  cookingTime.value = 35;
  cookingTimeLabel.textContent = '35 min';

  document.querySelectorAll('.diet-chip').forEach(c => {
    c.classList.toggle('active', c.dataset.value === 'All');
  });
  filterState.flavorVal = 'All';
  filterState.consistencyVal = 'All';
  document.querySelectorAll('.mini-chip').forEach(c => {
    c.classList.toggle('active', c.dataset.value === 'All');
  });
  const flavorMobile = document.getElementById('flavorMobile');
  const consistencyMobile = document.getElementById('consistencyMobile');
  if (flavorMobile) flavorMobile.value = 'All';
  if (consistencyMobile) consistencyMobile.value = 'All';
  ['cookingMode', 'cuisine', 'category','accessory'].forEach(name => {
    const allInput = document.querySelector(`input[name="${name}"][value="All"]`);
    if (allInput) allInput.checked = true;
  });

  dietTypeMobile.value = 'All';
  cookingModeMobile.value = 'All';
  cuisineMobile.value = 'All';
  categoryMobile.value = 'All';
  accessoryMobile.value = 'All';
  cookingTimeMobile.value = 35;
  cookingTimeLabelMobile.textContent = '35';

  if (searchBarDesktop) searchBarDesktop.value = '';
  if (searchBarMobile)  searchBarMobile.value  = '';

  updateSortButtons();
  updateMobileSortButtons();
  writeFiltersToURL();
  showRecipes();
});

// Mobile modal controls
mobileFilterBtn.addEventListener('click', () => {
  mobileFilterModal.classList.add('active');
});
closeMobileFilter.addEventListener('click', () => {
  mobileFilterModal.classList.remove('active');
});
mobileFilterModal.addEventListener('click', e => {
  if (e.target === mobileFilterModal) {
    mobileFilterModal.classList.remove('active');
  }
});

// Mobile filter handlers
function applyMobileFilters() {
  filterState.searchTerm = (searchBarMobile.value || '').toLowerCase().trim();
  filterState.dietVal = dietTypeMobile.value;
  filterState.cookingModeVal = cookingModeMobile.value;
  filterState.cuisineVal = cuisineMobile.value;
  filterState.categoryVal = categoryMobile.value;
  filterState.accessoryVal = accessoryMobile.value;
  filterState.maxCookingTime = parseInt(cookingTimeMobile.value, 10);
  const flavorMobile = document.getElementById('flavorMobile');
  const consistencyMobile = document.getElementById('consistencyMobile');
  if (flavorMobile) filterState.flavorVal = flavorMobile.value;
  if (consistencyMobile) filterState.consistencyVal = consistencyMobile.value;
  cookingTimeLabelMobile.textContent = cookingTimeMobile.value;
  filterState.onlyNew = false;
  writeFiltersToURL();
  showRecipes();
}

cookingTimeMobile.addEventListener('input', () => {
  cookingTimeLabelMobile.textContent = cookingTimeMobile.value;
});

searchBarMobile.addEventListener('input', () => {
});

dietTypeMobile.addEventListener('change', () => {
});
cookingModeMobile.addEventListener('change', () => {
});
cuisineMobile.addEventListener('change', () => {
});
categoryMobile.addEventListener('change', () => {
});
accessoryMobile.addEventListener('change', () => {
});

document.getElementById('applyBtnMobile').addEventListener('click', () => {
  applyMobileFilters();
  mobileFilterModal.classList.remove('active');
});

sortTimeAscMobile?.addEventListener('click', () => {
  filterState.sortBy = 'time-asc';
  updateMobileSortButtons();
  writeFiltersToURL();
  applyMobileFilters();
});

sortTimeDescMobile?.addEventListener('click', () => {
  filterState.sortBy = 'time-desc';
  updateMobileSortButtons();
  writeFiltersToURL();
  applyMobileFilters();
});

clearBtnMobile.addEventListener('click', () => {
  searchBarMobile.value = '';
  dietTypeMobile.value = 'All';
  cookingModeMobile.value = 'All';
  cuisineMobile.value = 'All';
  categoryMobile.value = 'All';
  accessoryMobile.value = 'All';
  cookingTimeMobile.value = 35;
  cookingTimeLabelMobile.textContent = '35';
  filterState.sortBy = 'time-asc';
  filterState.onlyNew = false;
  updateMobileSortButtons();
  writeFiltersToURL();
  applyMobileFilters();
});

// Popup linked-recipe navigation state
let popupPages = [];
let popupPageIndex = 0;

// Inject prev/next arrows into .popup-container once
function injectNavArrows() {
  if (document.getElementById('popupNavPrev')) return;
  const container = document.querySelector('.popup-container');

  const styleBase = `
    position: absolute; top: 50%; transform: translateY(-50%);
    background: rgba(255,255,255,0.15); backdrop-filter: blur(8px);
    border: 1px solid rgba(255,255,255,0.3); color: #fff;
    width: 44px; height: 44px; border-radius: 50%;
    font-size: 22px; font-weight: bold; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    z-index: 10010; transition: background 0.2s;
  `;

  const prevBtn = document.createElement('button');
  prevBtn.id = 'popupNavPrev';
  prevBtn.innerHTML = '&#8592;';
  prevBtn.title = 'Previous recipe';
  prevBtn.style.cssText = styleBase + 'left: -56px;';
  prevBtn.addEventListener('mouseover', () => prevBtn.style.background = 'rgba(255,255,255,0.3)');
  prevBtn.addEventListener('mouseout',  () => prevBtn.style.background = 'rgba(255,255,255,0.15)');
  prevBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    if (popupPageIndex > 0) { popupPageIndex--; renderPopupPage(); updateNavArrows(); }
  });

  const nextBtn = document.createElement('button');
  nextBtn.id = 'popupNavNext';
  nextBtn.innerHTML = '&#8594;';
  nextBtn.title = 'Next recipe';
  nextBtn.style.cssText = styleBase + 'right: -56px;';
  nextBtn.addEventListener('mouseover', () => nextBtn.style.background = 'rgba(255,255,255,0.3)');
  nextBtn.addEventListener('mouseout',  () => nextBtn.style.background = 'rgba(255,255,255,0.15)');
  nextBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    if (popupPageIndex < popupPages.length - 1) { popupPageIndex++; renderPopupPage(); updateNavArrows(); }
  });

  container.appendChild(prevBtn);
  container.appendChild(nextBtn);
}

function updateNavArrows() {
  const prevBtn = document.getElementById('popupNavPrev');
  const nextBtn = document.getElementById('popupNavNext');
  if (!prevBtn || !nextBtn) return;
  prevBtn.style.display = (popupPages.length > 1 && popupPageIndex > 0)  ? 'flex' : 'none';
  nextBtn.style.display = (popupPages.length > 1 && popupPageIndex < popupPages.length - 1) ? 'flex' : 'none';
}

function renderPopupPage() {
  const { src, alt } = popupPages[popupPageIndex];
  const isPDF = src.toLowerCase().endsWith('.pdf');
  if (isPDF) {
    popupImage.style.display = 'none';
    popupPDF.style.display = 'block';
    popupPDF.src = src;
    resetPDFZoom();
  } else {
    popupPDF.style.display = 'none';
    popupImage.style.display = 'block';
    popupImage.src = src;
    popupImage.alt = alt || 'Recipe Image';
    resetZoom();
  }
}

// Popup
let zoomState = {
  scale: 1,
  minScale: 0.5,
  maxScale: 4,
  translateX: 0,
  translateY: 0,
  isDragging: false,
  startX: 0,
  startY: 0
};

function openPopup(recipe) {
  injectNavArrows();

  // Build pages: if clubbedWith, prepend the linked recipe's PDF
  popupPages = [];
  if (recipe.clubbedWith) {
    const linked = recipes.find(r => r['Recipe Name'] === recipe.clubbedWith);
    if (linked) {
      popupPages.push({ src: linked.PopupImage || linked.Image, alt: linked['Recipe Name'] });
    }
  }
  popupPages.push({ src: recipe.PopupImage || recipe.Image, alt: recipe['Recipe Name'] });

  popupPageIndex = 0;
  renderPopupPage();
  updateNavArrows();
  popupModal.style.display = 'flex';
}

function resetZoom() {
  zoomState.scale = 1;
  zoomState.translateX = 0;
  zoomState.translateY = 0;
  updateImageTransform();
}

function updateImageTransform() {
  const transform = `translate(${zoomState.translateX}px, ${zoomState.translateY}px) scale(${zoomState.scale})`;
  popupImage.style.transform = transform;
}

function zoomImage(factor) {
  zoomState.scale = Math.max(zoomState.minScale, Math.min(zoomState.maxScale, zoomState.scale * factor));
  updateImageTransform();
}

document.querySelector('.popup-container').addEventListener('click', e => {
  e.stopPropagation();
});

popupModal.addEventListener('click', e => {
  if (e.target === popupModal) {
    popupModal.style.display = 'none';
    popupPDF.src = '';
  }
});

popupCloseBtn.addEventListener('click', () => {
  popupModal.style.display = 'none';
  popupPDF.src = '';
});

function isImageVisible() {
  return popupImage.style.display !== 'none';
}
function isPDFVisible() {
  return popupPDF.style.display !== "none";
}

function updateZoomButtons() {
  const disabled = !isImageVisible();
  zoomInBtn.disabled = disabled;
  zoomOutBtn.disabled = disabled;
  zoomResetBtn.disabled = disabled;
}
let pdfScale = 1;

function zoomPDF(factor) {
  pdfScale *= factor;
  popupPDF.style.transform = `scale(${pdfScale})`;
  popupPDF.style.transformOrigin = "center center";
}

function resetPDFZoom() {
  pdfScale = 1;
  popupPDF.style.transform = "scale(1)";
}

// Zoom controls
const zoomInBtn = document.querySelector('.zoom-in');
const zoomOutBtn = document.querySelector('.zoom-out');
const zoomResetBtn = document.querySelector('.zoom-reset');
const wrapper = document.querySelector('.popup-image-wrapper');

zoomInBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  if (isImageVisible()) {
    zoomImage(1.25);
  } else if (isPDFVisible()) {
    zoomPDF(1.25);
  }
});

zoomOutBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  if (isImageVisible()) {
    zoomImage(0.8);
  } else if (isPDFVisible()) {
    zoomPDF(0.8);
  }
});

zoomResetBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  if (isImageVisible()) {
    resetZoom();
  } else if (isPDFVisible()) {
    resetPDFZoom();
  }
});

// Image interaction events
popupImage.addEventListener('dblclick', resetZoom);

wrapper.addEventListener('wheel', (e) => {
  if (!isImageVisible()) return;
  e.preventDefault();
  const factor = e.deltaY > 0 ? 0.9 : 1.15;
  zoomImage(factor);
});

// Drag to pan
wrapper.addEventListener('mousedown', (e) => {
  if (zoomState.scale > 1.01) {
    zoomState.isDragging = true;
    zoomState.startX = e.clientX - zoomState.translateX;
    zoomState.startY = e.clientY - zoomState.translateY;
    wrapper.style.cursor = 'grabbing';
  }
});

document.addEventListener('mousemove', (e) => {
  if (zoomState.isDragging) {
    zoomState.translateX = e.clientX - zoomState.startX;
    zoomState.translateY = e.clientY - zoomState.startY;
    updateImageTransform();
  }
});

document.addEventListener('mouseup', () => {
  zoomState.isDragging = false;
  if (wrapper && zoomState.scale <= 1.01) {
    wrapper.style.cursor = 'zoom-in';
  } else {
    wrapper.style.cursor = 'grab';
  }
});

// Touch support for mobile
let lastTouchDistance = 0;

wrapper.addEventListener('touchstart', (e) => {
  if (e.touches.length === 1 && zoomState.scale > 1.01) {
    zoomState.isDragging = true;
    zoomState.startX = e.touches[0].clientX - zoomState.translateX;
    zoomState.startY = e.touches[0].clientY - zoomState.translateY;
  } else if (e.touches.length === 2) {
    const touch1 = e.touches[0];
    const touch2 = e.touches[1];
    lastTouchDistance = Math.hypot(
      touch1.clientX - touch2.clientX,
      touch1.clientY - touch2.clientY
    );
  }
});

wrapper.addEventListener('touchmove', (e) => {
  if (e.touches.length === 1 && zoomState.isDragging) {
    e.preventDefault();
    zoomState.translateX = e.touches[0].clientX - zoomState.startX;
    zoomState.translateY = e.touches[0].clientY - zoomState.startY;
    updateImageTransform();
  } else if (e.touches.length === 2) {
    e.preventDefault();
    const touch1 = e.touches[0];
    const touch2 = e.touches[1];
    const currentDistance = Math.hypot(
      touch1.clientX - touch2.clientX,
      touch1.clientY - touch2.clientY
    );
    
    if (lastTouchDistance > 0) {
      const factor = currentDistance / lastTouchDistance;
      zoomImage(factor);
    }
    
    lastTouchDistance = currentDistance;
  }
});

wrapper.addEventListener('touchend', () => {
  zoomState.isDragging = false;
  lastTouchDistance = 0;
});

wrapper.style.cursor = 'zoom-in';

// Debounce
function debounce(fn, delay) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn.apply(this, args), delay);
  };
}

// Init
window.addEventListener('load', loadRecipes);

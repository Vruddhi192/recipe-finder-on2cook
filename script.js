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

// FILTER STATE
const filterState = {
  searchTerm: '',
  sortBy: 'time-asc',
  dietVal: 'All',
  cookingModeVal: 'All',
  cuisineVal: 'All',
  categoryVal: 'All',
  accessoryVal: 'All',
  maxCookingTime: 35
};

searchBarDesktop?.addEventListener('input', debounce((e) => {
  filterState.searchTerm = e.target.value.toLowerCase().trim();
  showRecipes();
}, 250));

sortTimeAscMobile?.addEventListener('click', () => {
  filterState.sortBy = 'time-asc';
  updateMobileSortButtons();
  applyMobileFilters();
});

sortTimeDescMobile?.addEventListener('click', () => {
  filterState.sortBy = 'time-desc';
  updateMobileSortButtons();
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
    showRecipes();
  });
  
  sortTimeDesc?.addEventListener('click', () => {
    filterState.sortBy = 'time-desc';
    updateSortButtons();
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
    btn.className = 'diet-chip' + (val === 'All' ? ' active' : '');
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
    label.innerHTML = `
      <input type="radio" name="${name}" value="${val}" ${val === 'All' ? 'checked' : ''}>
      <span>${val}</span>
    `;
    const input = label.querySelector('input');
    input.addEventListener('change', () => {
      filterState[`${name}Val`] = val;
      showRecipes();
    });
    container.appendChild(label);
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
}

// Load recipes
function loadRecipes() {
  fetch('recipes_fix.json')
    .then(r => r.json())
    .then(data => {
      recipes = data;
      buildDietChips(getUniqueValues('Veg/Non Veg'));
      buildRadioGroup(cookingModeRadioGroup, getUniqueValues('Cooking Mode'), 'cookingMode');
      buildRadioGroup(cuisineRadioGroup, getUniqueValues('Cuisine'), 'cuisine');
      buildRadioGroup(categoryRadioGroup, getUniqueValues('Category'), 'category');
      buildRadioGroup(accessoryRadioGroup, getUniqueAccessories(), 'accessory');
      populateMobileFilters();
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

    return searchOk && dietOk && modeOk && cuisineOk && catOk && accOk && timeOk;
  });
}

// Render recipes
function showRecipes() {
  let filtered = filterRecipes();
  
  // Apply sorting based on filterState.sortBy
  filtered = filtered.sort((a, b) => {
    const ta = parseInt(a['On2Cook Cooking Time'], 10) || 999;
    const tb = parseInt(b['On2Cook Cooking Time'], 10) || 999;
    
    if (filterState.sortBy === 'time-asc') {
      return ta - tb;
    } else {
      return tb - ta;
    }
  });
  recipeCountEl.textContent = `${filtered.length} recipes found`;
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

    const cleanTime =
      r['Normal Cooking Time']?.replace(/[.,;!?'"()-]/g, '') || '';

    card.innerHTML = `
  <div class="recipe-card-image-wrap">
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
        <div class="badge-row">
          <div class="badge on2cook">
            <span class="badge-icon">⚡</span>
            <span class="badge-text">On2Cook  ${r['On2Cook Cooking Time']} mins</span>
          </div>
          <div class="badge normal">
            <span class="badge-icon">⏱</span>
            <span class="badge-text">Normal  ${cleanTime}</span>
          </div>
        </div>
      </div>
    `;

    // Add click handler for card (excluding download button)
    card.addEventListener('click', (e) => {
      if (!e.target.closest('.download-btn')) {
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
  cookingTime.value = 35;
  cookingTimeLabel.textContent = '35 min';

  document.querySelectorAll('.diet-chip').forEach(c => {
    c.classList.toggle('active', c.dataset.value === 'All');
  });
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

  updateSortButtons();
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
  cookingTimeLabelMobile.textContent = cookingTimeMobile.value;
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
  applyMobileFilters();
});

sortTimeDescMobile?.addEventListener('click', () => {
  filterState.sortBy = 'time-desc';
  updateMobileSortButtons();
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
  updateMobileSortButtons();
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
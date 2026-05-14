let recipes = [];
let selectedIngredients = [];
let selectedDiet = 'all'; // 'all', 'Veg', 'Non Veg', 'Egg'

fetch('recipes_fix.json')
  .then(res => res.json())
  .then(data => {
    recipes = data;
    renderSelectedIngredients();
    displayRecipes();
  })
  .catch(() => {
    document.getElementById('recipeResults').innerHTML =
      "<p style='color:red'>Failed to load recipes.</p>";
  });

document.getElementById('addIngredientBtn').onclick = function () {
  const input = document.getElementById('ingredientInput');
  const val = input.value.trim().toLowerCase();
  if (val && !selectedIngredients.includes(val)) {
    selectedIngredients.push(val);
    input.value = '';
    renderSelectedIngredients();
    displayRecipes();
  }
};

document
  .getElementById('ingredientInput')
  .addEventListener('keydown', function (e) {
    if (e.key === 'Enter') document.getElementById('addIngredientBtn').click();
  });

document.getElementById('backBtn').onclick = function () {
  window.location.href = 'index.html';
};

// Diet filter chip logic
document.querySelectorAll('.diet-chip').forEach(chip => {
  chip.addEventListener('click', function () {
    document.querySelectorAll('.diet-chip').forEach(c => c.classList.remove('active'));
    this.classList.add('active');
    selectedDiet = this.dataset.diet;
    displayRecipes();
  });
});

function renderSelectedIngredients() {
  const tagsDiv = document.getElementById('ingredientTags');
  const box = document.getElementById('selectedIngredientsBox');

  tagsDiv.innerHTML = '';
  selectedIngredients.forEach((ing, idx) => {
    const tag = document.createElement('span');
    tag.textContent = ing;
    const btn = document.createElement('button');
    btn.textContent = '×';
    btn.onclick = function () {
      selectedIngredients.splice(idx, 1);
      renderSelectedIngredients();
      displayRecipes();
    };
    tag.appendChild(btn);
    tagsDiv.appendChild(tag);
  });

  box.style.display = selectedIngredients.length ? 'block' : 'none';
}

function displayRecipes() {
  const resultsDiv = document.getElementById('recipeResults');
  const countDiv = document.getElementById('recipesCount');
  const emptyInner = document.querySelector('.empty-inner');

  if (selectedIngredients.length === 0) {
    emptyInner.style.visibility = 'visible';
    countDiv.textContent = '';
    resultsDiv.innerHTML = '';
    return;
  }

  emptyInner.style.visibility = 'hidden';

  let filtered = recipes.filter(
    r =>
      Array.isArray(r.Ingredients) &&
      selectedIngredients.every(ing =>
        r.Ingredients.some(recipeIng =>
          recipeIng.toLowerCase().includes(ing.toLowerCase())
        )
      )
  );

  // Apply diet type filter if not 'all'
  if (selectedDiet !== 'all') {
    filtered = filtered.filter(
      r => r['Veg/Non Veg'].toUpperCase() === selectedDiet.toUpperCase()
    );
  }

  countDiv.textContent = filtered.length
    ? `${filtered.length} Recipes Found`
    : 'These ingredients don\'t get along. Try different ones.';

  resultsDiv.innerHTML = '';
  filtered.forEach(r => {
    const card = document.createElement('div');
    card.innerHTML = `
      <img src="${r.Image}" alt="${r['Recipe Name']}" />
      <div>${r['Recipe Name']}</div>
      <div>
        <span>${r['Veg/Non Veg']}</span>
        <span>${r['Cooking Time']} min</span>
      </div>
      <div>${r['Category']} | ${r['Cooking Mode']} | ${r['Cuisine']}</div>
      <div>Ingredients: ${r.Ingredients.join(', ')}</div>
    `;
    card.addEventListener('click', function () {
      openPopup(r.PopupImage, r['Recipe Name']);
    });
    resultsDiv.appendChild(card);
  });
}

function openPopup(fileSrc, altText) {
  const modal = document.getElementById('popupModal');
  const popupImg = document.getElementById('popupImage');
  const popupPDF = document.getElementById('popupPDF');

  const isPDF = fileSrc.toLowerCase().endsWith('.pdf');

  if (isPDF) {
    popupImg.style.display = 'none';
    popupPDF.style.display = 'block';
    popupPDF.src = fileSrc;
  } else {
    popupPDF.style.display = 'none';
    popupImg.style.display = 'block';
    popupImg.src = fileSrc;
    popupImg.alt = altText || 'Recipe Image';
  }

  modal.classList.add('show');
}

document.getElementById('popupCloseBtn').onclick = function () {
  const modal = document.getElementById('popupModal');
  const popupImg = document.getElementById('popupImage');
  const popupPDF = document.getElementById('popupPDF');

  popupImg.src = '';
  popupPDF.src = '';
  modal.classList.remove('show');
};

document.getElementById('popupModal').onclick = function (e) {
  if (e.target === this) {
    const popupImg = document.getElementById('popupImage');
    const popupPDF = document.getElementById('popupPDF');

    popupImg.src = '';
    popupPDF.src = '';
    this.classList.remove('show');
  }
};
/**
 * HUGNESTLE - Admin Panel Interactions
 * Real-time Stock Adjuster, Image Upload Preview, Responsive Sidebar
 */

// Mobile Sidebar Toggle
function toggleAdminSidebar() {
  const sidebar = document.getElementById('adminSidebar');
  if (sidebar) sidebar.classList.toggle('open');
}

// Quick Stock Adjustment (+ / -)
async function adjustStock(productId, delta) {
  const input = document.getElementById(`stockInput_${productId}`);
  const statusBadge = document.getElementById(`stockBadge_${productId}`);
  if (!input) return;

  const currentVal = parseInt(input.value) || 0;
  const newVal = Math.max(0, currentVal + delta);
  input.value = newVal;

  try {
    const res = await fetch(`/api/admin/products/${productId}/stock`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ delta: delta })
    });
    const data = await res.json();

    if (data.success) {
      input.value = data.stock;
      if (statusBadge) {
        if (data.stock === 0) {
          statusBadge.className = 'status-pill status-out-of-stock';
          statusBadge.innerHTML = '● Out of Stock';
        } else if (data.stock <= 5) {
          statusBadge.className = 'status-pill status-low-stock';
          statusBadge.innerHTML = '● Low Stock';
        } else {
          statusBadge.className = 'status-pill status-in-stock';
          statusBadge.innerHTML = '● In Stock';
        }
      }
    } else {
      alert(data.message || 'Error updating stock');
      input.value = currentVal;
    }
  } catch (err) {
    console.error('Stock adjustment error:', err);
    input.value = currentVal;
  }
}

// Direct input stock change on blur or Enter
async function setStockExact(productId, inputElem) {
  const val = parseInt(inputElem.value);
  if (isNaN(val) || val < 0) {
    alert('Please enter a valid stock quantity.');
    return;
  }

  const statusBadge = document.getElementById(`stockBadge_${productId}`);

  try {
    const res = await fetch(`/api/admin/products/${productId}/stock`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_stock: val })
    });
    const data = await res.json();
    if (data.success) {
      inputElem.value = data.stock;
      if (statusBadge) {
        if (data.stock === 0) {
          statusBadge.className = 'status-pill status-out-of-stock';
          statusBadge.innerHTML = '● Out of Stock';
        } else if (data.stock <= 5) {
          statusBadge.className = 'status-pill status-low-stock';
          statusBadge.innerHTML = '● Low Stock';
        } else {
          statusBadge.className = 'status-pill status-in-stock';
          statusBadge.innerHTML = '● In Stock';
        }
      }
    }
  } catch (e) {
    console.error(e);
  }
}

// Open Add Product Modal
function openAddProductModal() {
  const modal = document.getElementById('addProductModal');
  if (modal) modal.classList.add('active');
}

function closeAddProductModal() {
  const modal = document.getElementById('addProductModal');
  if (modal) modal.classList.remove('active');
}

// Open Edit Product Modal
function openEditProductModal(product) {
  const modal = document.getElementById('editProductModal');
  if (!modal) return;

  document.getElementById('editProductId').value = product.id;
  document.getElementById('editForm').action = `/admin/products/edit/${product.id}`;
  document.getElementById('editName').value = product.name;
  document.getElementById('editCategory').value = product.category_id || '';
  document.getElementById('editPrice').value = product.price;
  document.getElementById('editOriginalPrice').value = product.original_price || '';
  document.getElementById('editStock').value = product.stock;
  document.getElementById('editTag').value = product.tag || '';
  document.getElementById('editDimensions').value = product.dimensions || '';
  document.getElementById('editMaterial').value = product.material || '';
  document.getElementById('editDescription').value = product.description || '';
  document.getElementById('editFeatured').checked = product.is_featured === 1;

  modal.classList.add('active');
}

function closeEditProductModal() {
  const modal = document.getElementById('editProductModal');
  if (modal) modal.classList.remove('active');
}

// Drag & Drop Image Uploader Preview
function setupImageDropzone(dropzoneId, inputId, previewId) {
  const dropzone = document.getElementById(dropzoneId);
  const input = document.getElementById(inputId);
  const preview = document.getElementById(previewId);

  if (!dropzone || !input || !preview) return;

  dropzone.addEventListener('click', () => input.click());

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('dragover');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
    }, false);
  });

  dropzone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    input.files = dt.files;
    showImagePreviews(input.files, preview);
  });

  input.addEventListener('change', () => {
    showImagePreviews(input.files, preview);
  });
}

function showImagePreviews(files, container) {
  container.innerHTML = '';
  if (!files || files.length === 0) return;

  Array.from(files).forEach((file, idx) => {
    if (!file.type.startsWith('image/')) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = document.createElement('img');
      img.src = e.target.result;
      img.className = 'preview-thumb';
      img.title = file.name;
      container.appendChild(img);
    };
    reader.readAsDataURL(file);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  setupImageDropzone('addDropzone', 'addImagesInput', 'addImagesPreview');
  setupImageDropzone('editDropzone', 'editImagesInput', 'editImagesPreview');
});

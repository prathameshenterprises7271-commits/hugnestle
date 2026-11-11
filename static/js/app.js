/**
 * HUGNESTLE - Client Side Application JS
 * Cart Management, Drawer, Toast, UI Interactions
 */

const CART_STORAGE_KEY = 'hugnestle_cart_v1';

// Get Cart from LocalStorage
function getCart() {
  try {
    const raw = localStorage.getItem(CART_STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    console.error('Cart parse error:', e);
    return [];
  }
}

// Save Cart to LocalStorage
function saveCart(cart) {
  localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(cart));
  updateCartBadge();
  renderCartDrawer();
}

// Add Item to Cart
function addToCart(product, quantity = 1) {
  if (product.stock <= 0) {
    showToast('Sorry! This cute plushie is currently Out of Stock.', '❌');
    return;
  }

  const cart = getCart();
  const existing = cart.find(item => item.id === product.id);

  if (existing) {
    if (existing.quantity + quantity > product.stock) {
      showToast(`Only ${product.stock} units available in stock!`, '⚠️');
      return;
    }
    existing.quantity += quantity;
  } else {
    cart.push({
      id: product.id,
      name: product.name,
      slug: product.slug,
      price: parseFloat(product.price),
      original_price: product.original_price ? parseFloat(product.original_price) : null,
      image: product.main_image || product.image,
      stock: product.stock,
      quantity: quantity
    });
  }

  saveCart(cart);
  showToast(`Added "${product.name}" to your cart! 🧸`, '✨');
  openCartDrawer();
}

// Update Quantity
function updateCartQty(productId, newQty) {
  let cart = getCart();
  const item = cart.find(i => i.id === productId);
  if (!item) return;

  if (newQty <= 0) {
    removeFromCart(productId);
    return;
  }

  if (newQty > item.stock) {
    showToast(`Sorry! Only ${item.stock} available in stock.`, '⚠️');
    return;
  }

  item.quantity = newQty;
  saveCart(cart);
}

// Remove Item from Cart
function removeFromCart(productId) {
  let cart = getCart();
  cart = cart.filter(i => i.id !== productId);
  saveCart(cart);
  showToast('Item removed from cart.', '🗑️');
}

// Update Badge in Navbar
function updateCartBadge() {
  const cart = getCart();
  const count = cart.reduce((acc, item) => acc + item.quantity, 0);
  document.querySelectorAll('.cart-badge').forEach(badge => {
    badge.textContent = count;
    badge.style.display = count > 0 ? 'flex' : 'none';
  });
}

// Render Cart Drawer
function renderCartDrawer() {
  const container = document.getElementById('cartDrawerItems');
  const totalElem = document.getElementById('cartDrawerTotal');
  const subtotalElem = document.getElementById('cartDrawerSubtotal');
  const progressElem = document.getElementById('freeShippingBar');
  const progressText = document.getElementById('freeShippingText');
  const checkoutBtn = document.getElementById('cartCheckoutBtn');

  if (!container) return;

  const cart = getCart();

  if (cart.length === 0) {
    container.innerHTML = `
      <div class="cart-empty-state">
        <div class="icon">🧸</div>
        <h4 style="font-weight: 800; margin-bottom: 8px;">Your cart is empty!</h4>
        <p style="color: var(--color-text-muted); font-size: 0.9rem; margin-bottom: 20px;">
          Find your new favorite cuddly companion today.
        </p>
        <a href="/shop" class="btn-cute-primary" onclick="closeCartDrawer()">Explore Hugs ✨</a>
      </div>
    `;
    if (subtotalElem) subtotalElem.textContent = '₹0.00';
    if (totalElem) totalElem.textContent = '₹0.00';
    if (progressElem) progressElem.style.width = '0%';
    if (progressText) progressText.textContent = 'Add ₹999 more for FREE Cute Gift Packaging!';
    if (checkoutBtn) checkoutBtn.classList.add('btn-disabled');
    return;
  }

  if (checkoutBtn) checkoutBtn.classList.remove('btn-disabled');

  let subtotal = 0;
  let html = '';

  cart.forEach(item => {
    const itemTotal = item.price * item.quantity;
    subtotal += itemTotal;
    html += `
      <div class="cart-item">
        <img src="${item.image}" alt="${item.name}" class="cart-item-img">
        <div class="cart-item-info">
          <div class="cart-item-name">${item.name}</div>
          <div class="cart-item-price">₹${item.price.toFixed(2)}</div>
          <div class="cart-qty-ctrl">
            <button class="qty-btn" onclick="updateCartQty(${item.id}, ${item.quantity - 1})">-</button>
            <span class="qty-val">${item.quantity}</span>
            <button class="qty-btn" onclick="updateCartQty(${item.id}, ${item.quantity + 1})">+</button>
          </div>
        </div>
        <button class="cart-item-remove" onclick="removeFromCart(${item.id})" title="Remove item">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18m-2 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
        </button>
      </div>
    `;
  });

  container.innerHTML = html;
  if (subtotalElem) subtotalElem.textContent = `₹${subtotal.toFixed(2)}`;
  if (totalElem) totalElem.textContent = `₹${subtotal.toFixed(2)}`;

  // Free gift wrap threshold: ₹999
  const threshold = 999;
  const pct = Math.min(100, Math.round((subtotal / threshold) * 100));
  if (progressElem) progressElem.style.width = `${pct}%`;
  if (progressText) {
    if (subtotal >= threshold) {
      progressText.innerHTML = '🎉 <strong>Woohoo!</strong> You unlocked FREE Cute Gift Packaging &amp; Ribbon!';
    } else {
      const remaining = threshold - subtotal;
      progressText.innerHTML = `Add <strong>₹${remaining.toFixed(2)}</strong> more for FREE Cute Gift Packaging! 🎀`;
    }
  }
}

// Drawer Controls
function openCartDrawer() {
  const overlay = document.getElementById('cartDrawerOverlay');
  if (overlay) overlay.classList.add('active');
  document.body.style.overflow = 'hidden';
  renderCartDrawer();
}

function closeCartDrawer() {
  const overlay = document.getElementById('cartDrawerOverlay');
  if (overlay) overlay.classList.remove('active');
  document.body.style.overflow = '';
}

// Toast System
function showToast(message, icon = '💖') {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.innerHTML = `
    <span style="font-size: 1.25rem;">${icon}</span>
    <span>${message}</span>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3200);
}

// Global initialization
document.addEventListener('DOMContentLoaded', () => {
  updateCartBadge();
  renderCartDrawer();

  // Close drawer on overlay click
  const overlay = document.getElementById('cartDrawerOverlay');
  if (overlay) {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeCartDrawer();
    });
  }

  // Bind cart toggles
  document.querySelectorAll('.btn-cart-toggle').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      openCartDrawer();
    });
  });
});

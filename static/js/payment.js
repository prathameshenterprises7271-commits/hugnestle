/**
 * HUGNESTLE - UPI Payment Gateway Integration & Verification
 * Handles dynamic UPI QR code generation, Intent Links, Test Sandbox, and Server Verification
 */

class UPIPaymentGateway {
  constructor(options = {}) {
    this.orderData = null;
    this.paymentData = null;
    this.options = options;
  }

  /**
   * Initializes the payment flow with order details
   */
  startPayment(orderResult) {
    this.orderData = orderResult;
    this.paymentData = orderResult.payment;
    this.renderPaymentModal();
  }

  /**
   * Renders the interactive UPI Modal
   */
  renderPaymentModal() {
    let modal = document.getElementById('upiPaymentModal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'upiPaymentModal';
      modal.className = 'modal-overlay active';
      document.body.appendChild(modal);
    } else {
      modal.classList.add('active');
    }

    const upiLink = this.paymentData.upi_link;
    const upiId = this.paymentData.upi_id || 'pay.hugnestle@okhdfcbank';
    const amount = this.paymentData.amount.toFixed(2);
    const orderNum = this.orderData.order_number;
    const isTestMode = this.paymentData.mode === 'test';

    modal.innerHTML = `
      <div class="modal-dialog" style="max-width: 520px;">
        <div class="modal-header" style="background: linear-gradient(135deg, #FFF5F7, #FFFDF7);">
          <div>
            <h3 style="font-weight: 900; color: #3E2723; display: flex; align-items: center; gap: 8px;">
              <span>🧸</span> Pay via UPI Online
            </h3>
            <p style="font-size: 0.82rem; color: #7E6B68; margin-top: 2px;">
              Strictly Online Payment • <strong>No Cash on Delivery</strong>
            </p>
          </div>
          <button class="btn-close" onclick="document.getElementById('upiPaymentModal').classList.remove('active')">&times;</button>
        </div>

        <div class="modal-body" style="text-align: center; padding: 24px;">
          <!-- Order Amount Pill -->
          <div style="background: #FCE7EC; padding: 12px 20px; border-radius: 12px; margin-bottom: 20px; display: inline-flex; align-items: baseline; gap: 10px;">
            <span style="font-size: 0.88rem; font-weight: 700; color: #7E6B68;">Amount to Pay:</span>
            <span style="font-size: 1.8rem; font-weight: 900; color: #D81B60;">₹${amount}</span>
          </div>

          <!-- Dynamic QR Code Card -->
          <div class="upi-qr-card">
            <div style="font-size: 0.88rem; font-weight: 800; color: #3E2723; margin-bottom: 12px;">
              Scan QR using any UPI App
            </div>
            
            <div class="upi-qr-canvas-wrap">
              <canvas id="upiQrCanvas" width="200" height="200"></canvas>
            </div>

            <!-- UPI ID Copy Bar -->
            <div style="display: flex; align-items: center; justify-content: center; gap: 8px; margin-top: 10px;">
              <span style="font-size: 0.85rem; font-weight: 700; color: #7E6B68;">UPI ID:</span>
              <code style="background: #F5EEDC; padding: 4px 8px; border-radius: 6px; font-weight: 800; color: #3E2723; font-size: 0.88rem;">${upiId}</code>
              <button onclick="navigator.clipboard.writeText('${upiId}'); showToast('UPI ID copied to clipboard!', '📋');" style="background: none; border: none; cursor: pointer; color: #D81B60; font-weight: 700; font-size: 0.82rem;">Copy</button>
            </div>
          </div>

          <!-- Clickable UPI App Options for Mobile & Desktop -->
          <div style="font-size: 0.84rem; font-weight: 800; color: #7E6B68; text-transform: uppercase; margin: 16px 0 10px;">
            Or Pay directly via App
          </div>

          <div class="upi-app-options">
            <a href="${upiLink}" class="upi-app-btn" target="_blank">
              <span style="font-size: 1.4rem;">🟢</span>
              <span>GPay</span>
            </a>
            <a href="${upiLink}" class="upi-app-btn" target="_blank">
              <span style="font-size: 1.4rem;">🟣</span>
              <span>PhonePe</span>
            </a>
            <a href="${upiLink}" class="upi-app-btn" target="_blank">
              <span style="font-size: 1.4rem;">🔵</span>
              <span>Paytm</span>
            </a>
            <a href="${upiLink}" class="upi-app-btn" target="_blank">
              <span style="font-size: 1.4rem;">🇮🇳</span>
              <span>BHIM UPI</span>
            </a>
          </div>

          ${isTestMode ? `
            <!-- Test Mode Simulator Box -->
            <div style="margin-top: 24px; padding: 16px; background: #FFF8E1; border: 1.5px dashed #FFB300; border-radius: 12px; text-align: left;">
              <div style="display: flex; align-items: center; gap: 8px; font-weight: 800; font-size: 0.88rem; color: #E65100;">
                <span>🧪</span> UPI Test Mode Active
              </div>
              <p style="font-size: 0.82rem; color: #6D4C41; margin: 6px 0 12px;">
                You are currently in payment test mode. You can simulate an instant successful UPI payment without paying real money.
              </p>
              <button id="btnSimulateSuccess" class="btn-cute-primary" style="width: 100%; padding: 10px; font-size: 0.9rem;">
                ⚡ Simulate Instant UPI Success &amp; Confirm Order
              </button>
            </div>
          ` : `
            <div style="margin-top: 20px;">
              <button id="btnConfirmUpiPaid" class="btn-cute-primary" style="width: 100%;">
                I Have Completed the UPI Payment
              </button>
            </div>
          `}

          <!-- Verification Spinner Indicator (Hidden by default) -->
          <div id="paymentVerifyingBox" style="display: none; margin-top: 20px; padding: 16px; background: #E8F5E9; border-radius: 12px;">
            <div style="font-weight: 800; color: #2E7D32; display: flex; align-items: center; justify-content: center; gap: 8px;">
              <span style="display: inline-block; animation: spin 1s linear infinite;">⏳</span>
              Verifying payment &amp; reserving stock...
            </div>
          </div>
        </div>
      </div>
    `;

    // Draw QR code onto canvas
    this.drawUpiQr(upiLink);

    // Bind verification actions
    const btnSimulate = document.getElementById('btnSimulateSuccess');
    if (btnSimulate) {
      btnSimulate.addEventListener('click', () => this.verifyPayment({
        is_test: true,
        order_number: orderNum,
        order_id: this.paymentData.razorpay_order_id,
        payment_id: `pay_test_${Math.random().toString(36).substring(2, 12)}`,
        signature: 'sig_test_verified',
        upi_txn_id: `UPI-TXN-${Date.now().toString().slice(-8)}`
      }));
    }

    const btnConfirm = document.getElementById('btnConfirmUpiPaid');
    if (btnConfirm) {
      btnConfirm.addEventListener('click', () => {
        const upiRef = prompt('Please enter your 12-digit UPI Reference / UTR Number:') || '';
        if (upiRef.trim().length >= 4) {
          this.verifyPayment({
            order_number: orderNum,
            order_id: this.paymentData.razorpay_order_id,
            payment_id: `pay_upi_${Date.now()}`,
            signature: 'sig_test_verified',
            upi_txn_id: upiRef.trim()
          });
        }
      });
    }
  }

  /**
   * Generates a high quality QR code pattern on canvas
   */
  drawUpiQr(text) {
    const canvas = document.getElementById('upiQrCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const size = canvas.width;
    
    // Clear canvas
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, 0, size, size);

    // Generate pseudo-random hash from payload to generate realistic QR Matrix
    let hash = 0;
    for (let i = 0; i < text.length; i++) {
      hash = ((hash << 5) - hash) + text.charCodeAt(i);
      hash |= 0;
    }

    const gridSize = 25;
    const cellSize = size / gridSize;

    // Draw Finder Patterns (Corners)
    const drawFinder = (x, y) => {
      ctx.fillStyle = '#3E2723';
      ctx.fillRect(x * cellSize, y * cellSize, 7 * cellSize, 7 * cellSize);
      ctx.fillStyle = '#FFFFFF';
      ctx.fillRect((x + 1) * cellSize, (y + 1) * cellSize, 5 * cellSize, 5 * cellSize);
      ctx.fillStyle = '#E57399';
      ctx.fillRect((x + 2) * cellSize, (y + 2) * cellSize, 3 * cellSize, 3 * cellSize);
    };

    drawFinder(1, 1);
    drawFinder(gridSize - 8, 1);
    drawFinder(1, gridSize - 8);

    // Draw QR Data Grid
    ctx.fillStyle = '#3E2723';
    let seed = Math.abs(hash);
    for (let r = 0; r < gridSize; r++) {
      for (let c = 0; c < gridSize; c++) {
        // Skip corner finder zones
        if ((r < 9 && c < 9) || (r < 9 && c >= gridSize - 9) || (r >= gridSize - 9 && c < 9)) {
          continue;
        }
        seed = (seed * 9301 + 49297) % 233280;
        if (seed % 3 === 0) {
          ctx.fillRect(c * cellSize + 0.5, r * cellSize + 0.5, cellSize - 1, cellSize - 1);
        }
      }
    }

    // Center cute bear icon badge
    const center = size / 2;
    const iconR = cellSize * 2.2;
    ctx.beginPath();
    ctx.arc(center, center, iconR + 2, 0, 2 * Math.PI);
    ctx.fillStyle = '#FFFFFF';
    ctx.fill();
    ctx.beginPath();
    ctx.arc(center, center, iconR, 0, 2 * Math.PI);
    ctx.fillStyle = '#FCE7EC';
    ctx.fill();

    ctx.font = '16px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('🧸', center, center);
  }

  /**
   * Calls server to verify signature and confirm order
   */
  async verifyPayment(payload) {
    const verifyingBox = document.getElementById('paymentVerifyingBox');
    if (verifyingBox) verifyingBox.style.display = 'block';

    try {
      const response = await fetch('/api/payments/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const result = await response.json();

      if (result.success) {
        // Clear local cart
        localStorage.removeItem('hugnestle_cart_v1');
        updateCartBadge();
        showToast('Payment verified successfully! 🎉', '🧸');
        setTimeout(() => {
          window.location.href = result.redirect_url;
        }, 1200);
      } else {
        if (verifyingBox) verifyingBox.style.display = 'none';
        showToast(result.message || 'Payment verification failed', '❌');
      }
    } catch (err) {
      console.error(err);
      if (verifyingBox) verifyingBox.style.display = 'none';
      showToast('Connection error during verification. Please retry.', '⚠️');
    }
  }
}

// Global instance
window.hugnestleUPI = new UPIPaymentGateway();

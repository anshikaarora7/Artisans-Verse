/* ==========================================================================
   Artisans-Verse Motion & Interactive UI Controller
   ========================================================================== */

(function () {
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // 1. Sticky Header Scroll Shadow
  const header = document.querySelector('.av-header');
  if (header) {
    const onScroll = () => {
      header.classList.toggle('is-scrolled', window.scrollY > 12);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  // 2. Scroll-Reveal with IntersectionObserver & Stagger
  const revealEls = document.querySelectorAll('[data-reveal]');
  if (revealEls.length) {
    if (prefersReducedMotion || !('IntersectionObserver' in window)) {
      revealEls.forEach((el) => el.classList.add('is-visible'));
    } else {
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add('is-visible');
              observer.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.1, rootMargin: '0px 0px -30px 0px' }
      );
      revealEls.forEach((el) => observer.observe(el));
    }
  }

  // 3. Mobile Nav Drawer & Dashboard Sidebar Drawer
  const backdrop = document.querySelector('[data-drawer-backdrop]');
  const openDrawerBtns = document.querySelectorAll('[data-drawer-open]');
  const closeDrawerBtns = document.querySelectorAll('[data-drawer-close]');

  function closeAllDrawers() {
    document.querySelectorAll('.av-drawer.is-open, .av-sidebar.is-open').forEach((el) => {
      el.classList.remove('is-open');
    });
    if (backdrop) backdrop.classList.remove('is-open');
    document.body.style.overflow = '';
  }

  openDrawerBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const targetSelector = btn.getAttribute('data-drawer-open');
      const target = document.querySelector(targetSelector);
      if (!target) return;
      target.classList.add('is-open');
      if (backdrop) backdrop.classList.add('is-open');
      document.body.style.overflow = 'hidden';
    });
  });

  closeDrawerBtns.forEach((btn) => btn.addEventListener('click', closeAllDrawers));
  if (backdrop) backdrop.addEventListener('click', closeAllDrawers);

  // 4. Modals
  document.querySelectorAll('[data-modal-open]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const modal = document.querySelector(btn.getAttribute('data-modal-open'));
      if (modal) {
        modal.classList.add('is-open');
        document.body.style.overflow = 'hidden';
      }
    });
  });

  document.querySelectorAll('[data-modal-close]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const modal = btn.closest('.av-modal');
      if (modal) {
        modal.classList.remove('is-open');
        document.body.style.overflow = '';
      }
    });
  });

  document.querySelectorAll('.av-modal').forEach((modal) => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.classList.remove('is-open');
        document.body.style.overflow = '';
      }
    });
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeAllDrawers();
      document.querySelectorAll('.av-modal.is-open').forEach((m) => m.classList.remove('is-open'));
      document.body.style.overflow = '';
    }
  });

  // 5. Dismissible Alerts
  document.querySelectorAll('.av-alert-close').forEach((btn) => {
    btn.addEventListener('click', () => {
      const alertEl = btn.closest('.av-alert');
      if (alertEl) {
        alertEl.style.opacity = '0';
        alertEl.style.transform = 'translateY(-6px)';
        setTimeout(() => alertEl.remove(), prefersReducedMotion ? 0 : 180);
      }
    });
  });

  // 6. Password Visibility Toggle
  document.querySelectorAll('[data-toggle-password]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-toggle-password');
      const input = document.getElementById(targetId);
      if (!input) return;
      const isPassword = input.getAttribute('type') === 'password';
      input.setAttribute('type', isPassword ? 'text' : 'password');
      const icon = btn.querySelector('i');
      if (icon) {
        icon.classList.toggle('fa-eye', !isPassword);
        icon.classList.toggle('fa-eye-slash', isPassword);
      }
      btn.setAttribute('aria-label', isPassword ? 'Hide password' : 'Show password');
    });
  });

  // 7. Animated KPI Counters
  document.querySelectorAll('[data-count-up]').forEach((el) => {
    const raw = el.getAttribute('data-count-up') || '0';
    const target = parseFloat(raw);
    if (isNaN(target) || prefersReducedMotion || target === 0) return;

    const prefix = el.getAttribute('data-prefix') || '';
    const isDecimal = raw.includes('.');
    const duration = 650;
    const start = performance.now();

    function tick(now) {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = target * eased;
      el.textContent = prefix + (isDecimal ? current.toFixed(2) : Math.round(current).toLocaleString());
      if (progress < 1) {
        requestAnimationFrame(tick);
      } else {
        el.textContent = prefix + (isDecimal ? target.toFixed(2) : target.toLocaleString());
      }
    }
    requestAnimationFrame(tick);
  });

  // 8. Dashboard Live Search & Stock Pill Filtering
  const filterInputs = document.querySelectorAll('[data-filter-table]');
  filterInputs.forEach((input) => {
    const tableId = input.getAttribute('data-filter-table');
    const table = document.getElementById(tableId);
    if (!table) return;

    let activeState = 'all';

    const applyFilter = () => {
      const q = (input.value || '').trim().toLowerCase();
      const rows = table.querySelectorAll('tbody tr[data-filter-row]');
      let visibleCount = 0;
      rows.forEach((row) => {
        const text = (row.textContent || '').toLowerCase();
        const rowState = row.getAttribute('data-stock-state') || 'all';
        const matchText = !q || text.includes(q);
        const matchState = activeState === 'all' || rowState === activeState;
        const match = matchText && matchState;
        row.style.display = match ? '' : 'none';
        if (match) visibleCount++;
      });
      const emptyRow = table.querySelector('tbody tr[data-filter-empty]');
      if (emptyRow) {
        emptyRow.style.display = visibleCount === 0 ? '' : 'none';
      }
    };

    input.addEventListener('input', applyFilter);

    const pills = document.querySelectorAll(`[data-pill-target="${tableId}"]`);
    pills.forEach((pill) => {
      pill.addEventListener('click', () => {
        activeState = pill.getAttribute('data-filter-pill') || 'all';
        pills.forEach((p) => {
          p.classList.toggle('av-btn-primary', p === pill);
          p.classList.toggle('av-btn-ghost', p !== pill);
        });
        applyFilter();
      });
    });
  });

  // 9. Storefront Dynamic Category Nav (if present)
  const dynamicMenu = document.getElementById('av-dynamic-cats');
  if (dynamicMenu) {
    fetch('/show_nav/')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data || !Array.isArray(data.menu_items)) return;
        data.menu_items.slice(0, 4).forEach((item) => {
          const li = document.createElement('li');
          const a = document.createElement('a');
          a.className = 'av-nav-link';
          a.href = `/shop/${item.parent.id}/`;
          a.textContent = item.parent.name;
          li.appendChild(a);
          dynamicMenu.appendChild(li);
        });
      })
      .catch(() => {});
  }
  // 10. Real-time Toast & Live Cart Interactions
  function showToast(message, actionHref, actionLabel) {
    let container = document.getElementById('av-toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'av-toast-container';
      container.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:300;display:grid;gap:10px;max-width:340px;';
      document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = 'av-alert av-alert-success';
    toast.style.cssText = 'margin:0;box-shadow:var(--av-shadow-md);background:#fff;border:1px solid var(--av-success);';
    toast.innerHTML = `<span><i class="fas fa-check-circle" style="margin-right:6px;"></i>${message}</span>` +
      (actionHref ? `<a href="${actionHref}" style="font-weight:700;text-decoration:underline;margin-left:8px;white-space:nowrap;">${actionLabel || 'View'}</a>` : '');
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 220);
    }, 3200);
  }

  function updateCartBadge(count) {
    document.querySelectorAll('[data-cart-badge]').forEach((badge) => {
      badge.textContent = count;
      badge.style.display = count > 0 ? 'inline-flex' : 'none';
    });
  }

  document.querySelectorAll('form[data-ajax-cart]').forEach((form) => {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;

      fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data && data.ok) {
            updateCartBadge(data.cart_count);
            showToast(data.message || 'Added to cart', '/cart/', 'View Cart');
          } else {
            form.submit();
          }
        })
        .catch(() => form.submit())
        .finally(() => {
          if (submitBtn) submitBtn.disabled = false;
        });
    });
  });

  function getCookie(name) {
    const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return match ? decodeURIComponent(match[2]) : '';
  }

  function syncCartSummary(data) {
    const subEl = document.getElementById('av-cart-subtotal');
    const shipEl = document.getElementById('av-cart-shipping');
    const totalEl = document.getElementById('av-cart-total');
    if (subEl) subEl.innerHTML = '&#8377;' + data.sub_total;
    if (shipEl) shipEl.innerHTML = '&#8377;' + data.shipping;
    if (totalEl) totalEl.innerHTML = '&#8377;' + data.total;
    updateCartBadge(data.cart_count);
    if (data.cart_count === 0) {
      window.location.reload();
    }
  }

  document.querySelectorAll('[data-cart-action]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const url = btn.getAttribute('data-url');
      const action = btn.getAttribute('data-cart-action');
      const row = btn.closest('tr[data-cart-row]');
      const fd = new FormData();
      fd.append('action', action);

      fetch(url, {
        method: 'POST',
        body: fd,
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': getCookie('csrftoken'),
        },
      })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (!data || !data.ok) return;
          if (data.removed && row) {
            row.remove();
          } else if (row) {
            const qtyEl = row.querySelector('[data-item-qty]');
            const subEl = row.querySelector('[data-item-subtotal]');
            if (qtyEl) qtyEl.textContent = data.item_qty;
            if (subEl) subEl.innerHTML = '&#8377;' + data.item_subtotal;
          }
          syncCartSummary(data);
        });
    });
  });

  document.querySelectorAll('[data-cart-remove]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const row = btn.closest('tr[data-cart-row]');
      fetch(btn.href, {
        method: 'GET',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (!data || !data.ok) {
            window.location.href = btn.href;
            return;
          }
          if (row) row.remove();
          syncCartSummary(data);
        })
        .catch(() => {
          window.location.href = btn.href;
        });
    });
  });
})();

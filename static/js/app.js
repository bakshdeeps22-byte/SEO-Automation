/**
 * Interactive features for SEO Automation Webapp.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Auto-dismiss flash messages
  document.querySelectorAll('.flash-message').forEach(msg => {
    setTimeout(() => {
      msg.style.opacity = '0';
      msg.style.transform = 'translateY(-10px)';
      setTimeout(() => msg.remove(), 300);
    }, 5000);
  });

  // Flash close buttons
  document.querySelectorAll('.flash-close').forEach(btn => {
    btn.addEventListener('click', () => {
      const msg = btn.closest('.flash-message');
      msg.style.opacity = '0';
      setTimeout(() => msg.remove(), 300);
    });
  });

  // Upload zone drag & drop
  const uploadZone = document.getElementById('upload-zone');
  const fileInput = document.getElementById('file-input');

  if (uploadZone && fileInput) {
    uploadZone.addEventListener('click', () => fileInput.click());
    
    uploadZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
      uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
      e.preventDefault();
      uploadZone.classList.remove('dragover');
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        fileInput.files = files;
        document.getElementById('upload-form').submit();
      }
    });

    fileInput.addEventListener('change', () => {
      if (fileInput.files.length > 0) {
        const name = fileInput.files[0].name;
        uploadZone.querySelector('.upload-zone-title').textContent = name;
        uploadZone.querySelector('.upload-zone-subtitle').textContent = 'Click "Upload" to proceed';
      }
    });
  }

  // Table sorting
  document.querySelectorAll('th[data-sort]').forEach(th => {
    th.style.cursor = 'pointer';
    th.addEventListener('click', () => {
      const table = th.closest('table');
      const tbody = table.querySelector('tbody');
      const col = th.cellIndex;
      const isAsc = th.dataset.order !== 'asc';
      th.dataset.order = isAsc ? 'asc' : 'desc';

      // Reset other headers
      table.querySelectorAll('th').forEach(h => {
        if (h !== th) delete h.dataset.order;
      });

      const rows = Array.from(tbody.querySelectorAll('tr'));
      rows.sort((a, b) => {
        let valA = a.cells[col]?.textContent.trim() || '';
        let valB = b.cells[col]?.textContent.trim() || '';
        
        // Try numeric sort
        const numA = parseFloat(valA.replace(/[^0-9.-]/g, ''));
        const numB = parseFloat(valB.replace(/[^0-9.-]/g, ''));
        if (!isNaN(numA) && !isNaN(numB)) {
          return isAsc ? numA - numB : numB - numA;
        }
        
        return isAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
      });

      rows.forEach(row => tbody.appendChild(row));
    });
  });

  // Filter chips
  document.querySelectorAll('.filter-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const group = chip.closest('.filter-bar');
      const isMulti = group?.dataset.multi === 'true';
      
      if (!isMulti) {
        group?.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
      }
      
      chip.classList.toggle('active');
      
      // Apply filter
      const filterValue = chip.dataset.filter;
      const table = document.querySelector('.filterable-table');
      if (table && filterValue) {
        const activeFilters = Array.from(group.querySelectorAll('.filter-chip.active'))
          .map(c => c.dataset.filter);
        
        table.querySelectorAll('tbody tr').forEach(row => {
          if (activeFilters.length === 0 || activeFilters.includes('all')) {
            row.style.display = '';
          } else {
            const cellValue = row.dataset.filterValue || '';
            row.style.display = activeFilters.includes(cellValue) ? '' : 'none';
          }
        });
      }
    });
  });

  // Confirm actions
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', (e) => {
      if (!confirm(el.dataset.confirm)) {
        e.preventDefault();
      }
    });
  });

  // Loading state for buttons
  document.querySelectorAll('form[data-loading]').forEach(form => {
    form.addEventListener('submit', () => {
      const btn = form.querySelector('button[type="submit"], .btn-primary');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="loading">⏳</span> Running...';
      }
    });
  });

  // Copy share link
  document.querySelectorAll('.copy-link-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = btn.closest('.flex')?.querySelector('.share-link-input');
      if (input) {
        navigator.clipboard.writeText(input.value).then(() => {
          const original = btn.textContent;
          btn.textContent = '✓ Copied!';
          setTimeout(() => btn.textContent = original, 2000);
        });
      }
    });
  });

  // Select all checkbox for bulk approve
  const selectAll = document.getElementById('select-all');
  if (selectAll) {
    selectAll.addEventListener('change', () => {
      document.querySelectorAll('.issue-checkbox').forEach(cb => {
        cb.checked = selectAll.checked;
      });
    });
  }

  // Countdown timer for next run
  const countdownEl = document.getElementById('next-run-countdown');
  if (countdownEl) {
    const targetTime = new Date(countdownEl.dataset.target);
    
    function updateCountdown() {
      const now = new Date();
      const diff = targetTime - now;
      
      if (diff <= 0) {
        countdownEl.textContent = 'Running now...';
        return;
      }
      
      const days = Math.floor(diff / 86400000);
      const hours = Math.floor((diff % 86400000) / 3600000);
      const mins = Math.floor((diff % 3600000) / 60000);
      
      let parts = [];
      if (days > 0) parts.push(`${days}d`);
      parts.push(`${hours}h`);
      parts.push(`${mins}m`);
      
      countdownEl.textContent = parts.join(' ');
    }
    
    updateCountdown();
    setInterval(updateCountdown, 60000);
  }

  // Animate stat card values on scroll
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('animate-in');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('.stat-card, .job-card, .card').forEach(el => {
    observer.observe(el);
  });

  // Copy link buttons with instant visual feedback
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.copy-link-btn');
    if (btn) {
      e.preventDefault();
      const container = btn.closest('.flex') || btn.parentElement;
      const input = container ? (container.querySelector('.share-link-input') || container.querySelector('input')) : null;
      if (input && input.value) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(input.value).then(() => {
            const orig = btn.innerHTML;
            btn.innerHTML = '✓';
            btn.classList.add('copy-success');
            setTimeout(() => {
              btn.innerHTML = orig;
              btn.classList.remove('copy-success');
            }, 2000);
          }).catch(() => {
            input.select();
            document.execCommand('copy');
            const orig = btn.innerHTML;
            btn.innerHTML = '✓';
            setTimeout(() => { btn.innerHTML = orig; }, 2000);
          });
        } else {
          input.select();
          document.execCommand('copy');
          const orig = btn.innerHTML;
          btn.innerHTML = '✓';
          setTimeout(() => { btn.innerHTML = orig; }, 2000);
        }
      }
    }
  });

  // Account menu toggle
  window.toggleAccountMenu = function(e) {
    if (e) e.stopPropagation();
    const menu = document.getElementById('account-dropdown-menu');
    if (menu) {
      menu.style.display = menu.style.display === 'none' || !menu.style.display ? 'block' : 'none';
    }
  };

  // Close account menu on click outside
  window.addEventListener('click', (e) => {
    const menu = document.getElementById('account-dropdown-menu');
    if (menu && menu.style.display === 'block' && !e.target.closest('.account-selector-bar')) {
      menu.style.display = 'none';
    }
  });
});

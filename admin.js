/* ==========================================================================
   CyberTube AI - Admin Dashboard Client Controller & Metrics Engine
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Metrics Elements
  const serverUptime = document.getElementById('serverUptime');
  const diskUsedVal = document.getElementById('diskUsedVal');
  const diskBarFill = document.getElementById('diskBarFill');
  const diskFreeSub = document.getElementById('diskFreeSub');
  const activeDownloadsVal = document.getElementById('activeDownloadsVal');
  const activeSub = document.getElementById('activeSub');
  const totalDownloadsVal = document.getElementById('totalDownloadsVal');
  const totalSub = document.getElementById('totalSub');
  const cacheSizeVal = document.getElementById('cacheSizeVal');
  const cacheFilesSub = document.getElementById('cacheFilesSub');

  // Controls & Table Elements
  const btnAutoRefresh = document.getElementById('btnAutoRefresh');
  const btnManualRefresh = document.getElementById('btnManualRefresh');
  const btnClearCache = document.getElementById('btnClearCache');
  const btnClearLogs = document.getElementById('btnClearLogs');
  const filterChips = document.querySelectorAll('.filter-chip');
  const logCountBadge = document.getElementById('logCountBadge');
  const logsTableBody = document.getElementById('logsTableBody');
  const logsEmptyState = document.getElementById('logsEmptyState');

  // State
  let allLogs = [];
  let currentFilter = 'all';
  let autoRefreshEnabled = true;
  let autoRefreshTimer = null;

  /* ==========================================================================
     Admin Stats & System Load Fetcher
     ========================================================================== */
  async function fetchAdminStats() {
    try {
      const res = await fetch('/api/admin/stats');
      if (!res.ok) return;

      const data = await res.json();
      
      // Server Uptime & Storage Metrics
      serverUptime.textContent = data.uptime || '--';
      diskUsedVal.textContent = `${data.disk_used_gb} GB / ${data.disk_total_gb} GB`;
      diskBarFill.style.width = `${Math.min(data.disk_percent, 100)}%`;
      diskFreeSub.textContent = `${data.disk_free_gb} GB Free Space (${data.disk_percent}% Used)`;

      // Active Downloads & Totals
      activeDownloadsVal.textContent = `${data.active_downloads} Active Streams`;
      activeSub.textContent = data.active_downloads > 0 ? 'Downloading in Background' : 'All Threads Idle';

      totalDownloadsVal.textContent = `${data.total_downloads} Files`;
      totalSub.textContent = `${data.video_count} Video • ${data.audio_count} MP3 Audio`;

      // Cache Storage
      cacheSizeVal.textContent = data.cache_total_size;
      cacheFilesSub.textContent = `${data.cache_files_count} Files Cached on Disk`;

    } catch (err) {
      console.warn('Failed to fetch admin stats:', err);
    }
  }

  /* ==========================================================================
     Download History Logs Fetcher & Table Renderer
     ========================================================================== */
  async function fetchAdminLogs() {
    try {
      const res = await fetch('/api/admin/logs');
      if (!res.ok) return;

      const data = await res.json();
      allLogs = data.logs || [];
      renderFilteredLogs();

    } catch (err) {
      console.warn('Failed to fetch admin logs:', err);
    }
  }

  function renderFilteredLogs() {
    const filtered = allLogs.filter(log => {
      if (currentFilter === 'all') return true;
      if (currentFilter === 'completed') return log.status === 'completed';
      if (currentFilter === 'failed') return log.status === 'failed';
      if (currentFilter === 'audio') return log.is_audio;
      if (currentFilter === 'video') return !log.is_audio;
      return true;
    });

    logCountBadge.textContent = `${filtered.length} Logs`;
    logsTableBody.innerHTML = '';

    if (filtered.length === 0) {
      logsEmptyState.classList.remove('hidden');
      return;
    } else {
      logsEmptyState.classList.add('hidden');
    }

    filtered.forEach(log => {
      const tr = document.createElement('tr');
      
      const statusBadgeClass = log.status === 'completed' ? 'status-tag completed' : 'status-tag failed';
      const statusIcon = log.status === 'completed' ? '✓ Completed' : '✕ Failed';
      const thumbHtml = log.thumbnail ? `<img src="${log.thumbnail}" class="log-thumb" alt="thumb">` : `<div class="log-thumb-placeholder">Video</div>`;

      tr.innerHTML = `
        <td class="cell-time">${log.timestamp}</td>
        <td>
          <div class="log-title-cell">
            ${thumbHtml}
            <div class="title-meta">
              <a href="${log.url}" target="_blank" class="log-video-link" title="${log.title}">${log.title}</a>
              <span class="log-filename">${log.download_name || '--'}</span>
            </div>
          </div>
        </td>
        <td><span class="badge-format ${log.is_audio ? 'audio' : 'video'}">${log.format_label}</span></td>
        <td class="cell-size">${log.file_size_str}</td>
        <td class="cell-duration">${log.duration_sec}</td>
        <td><span class="${statusBadgeClass}">${statusIcon}</span></td>
        <td class="cell-ip">${log.client_ip || '127.0.0.1'}</td>
        <td>
          <div class="log-actions">
            ${log.status === 'completed' ? `
              <a href="/api/file/${log.id}" class="action-btn-sm download" title="Download File">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="7 10 12 15 17 10"></polyline>
                  <line x1="12" y1="15" x2="12" y2="3"></line>
                </svg>
              </a>
            ` : ''}
            <button type="button" class="action-btn-sm delete" data-id="${log.id}" title="Delete Record">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
            </button>
          </div>
        </td>
      `;

      const deleteBtn = tr.querySelector('.action-btn-sm.delete');
      if (deleteBtn) {
        deleteBtn.addEventListener('click', () => deleteLogEntry(log.id));
      }

      logsTableBody.appendChild(tr);
    });
  }

  async function deleteLogEntry(logId) {
    try {
      const res = await fetch(`/api/admin/delete-log/${logId}`, { method: 'DELETE' });
      if (res.ok) {
        refreshAll();
      }
    } catch (err) {
      console.error('Delete log error:', err);
    }
  }

  /* ==========================================================================
     Clear Server Cache & Clear Logs Handlers
     ========================================================================== */
  btnClearCache.addEventListener('click', async () => {
    if (!confirm('Are you sure you want to clear all downloaded cached files from the server disk?')) return;

    try {
      const res = await fetch('/api/admin/clear-cache', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        alert(data.message);
        refreshAll();
      }
    } catch (err) {
      alert('Failed to clear cache.');
      console.error(err);
    }
  });

  if (btnClearLogs) {
    btnClearLogs.addEventListener('click', async () => {
      if (!confirm('Are you sure you want to permanently clear all download history logs? This cannot be undone.')) return;

      try {
        const res = await fetch('/api/admin/clear-logs', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          alert(data.message);
          refreshAll();
        }
      } catch (err) {
        alert('Failed to clear logs.');
        console.error(err);
      }
    });
  }

  /* ==========================================================================
     Filter Chips & Auto Refresh Controls
     ========================================================================== */
  filterChips.forEach(chip => {
    chip.addEventListener('click', () => {
      filterChips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      currentFilter = chip.dataset.filter;
      renderFilteredLogs();
    });
  });

  btnManualRefresh.addEventListener('click', () => {
    refreshAll();
  });

  btnAutoRefresh.addEventListener('click', () => {
    autoRefreshEnabled = !autoRefreshEnabled;
    if (autoRefreshEnabled) {
      btnAutoRefresh.classList.add('active');
      btnAutoRefresh.innerHTML = '<span class="pulse-dot"></span> Auto Refresh: ON';
      startAutoRefresh();
    } else {
      btnAutoRefresh.classList.remove('active');
      btnAutoRefresh.innerHTML = '<span class="pulse-dot muted"></span> Auto Refresh: OFF';
      stopAutoRefresh();
    }
  });

  function refreshAll() {
    fetchAdminStats();
    fetchAdminLogs();
  }

  function startAutoRefresh() {
    stopAutoRefresh();
    autoRefreshTimer = setInterval(() => {
      if (autoRefreshEnabled) {
        refreshAll();
      }
    }, 4000);
  }

  function stopAutoRefresh() {
    if (autoRefreshTimer) clearInterval(autoRefreshTimer);
  }

  // Initial Load
  refreshAll();
  startAutoRefresh();
});

/* ==========================================================================
   CyberTube AI - Client-Side App Controller & Progress Engine
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const urlForm = document.getElementById('urlForm');
  const ytUrlInput = document.getElementById('ytUrlInput');
  const btnFetch = document.getElementById('btnFetch');
  const btnPaste = document.getElementById('btnPaste');
  const btnClearInput = document.getElementById('btnClearInput');

  const loadingSkeleton = document.getElementById('loadingSkeleton');
  const errorBanner = document.getElementById('errorBanner');
  const errorText = document.getElementById('errorText');

  const videoResultCard = document.getElementById('videoResultCard');
  const videoThumb = document.getElementById('videoThumb');
  const videoTitle = document.getElementById('videoTitle');
  const videoChannel = document.getElementById('videoChannel');
  const videoViews = document.getElementById('videoViews');
  const videoDuration = document.getElementById('videoDuration');

  const tabBtns = document.querySelectorAll('.tab-btn');
  const videoFormatGrid = document.getElementById('videoFormatGrid');
  const audioFormatGrid = document.getElementById('audioFormatGrid');
  const btnStartDownload = document.getElementById('btnStartDownload');
  const downloadBtnLabel = document.getElementById('downloadBtnLabel');

  const progressCard = document.getElementById('progressCard');
  const progressStatusText = document.getElementById('progressStatusText');
  const progressPercentage = document.getElementById('progressPercentage');
  const progressBarFill = document.getElementById('progressBarFill');
  const statDownloaded = document.getElementById('statDownloaded');
  const statSpeed = document.getElementById('statSpeed');
  const statEta = document.getElementById('statEta');
  const completeActionArea = document.getElementById('completeActionArea');
  const btnSaveFile = document.getElementById('btnSaveFile');

  // Application State
  let currentVideoData = null;
  let selectedFormat = null;
  let activeTab = 'video';
  let pollInterval = null;

  /* ==========================================================================
     Input Event Listeners & Clipboard Handlers
     ========================================================================== */
  ytUrlInput.addEventListener('input', () => {
    if (ytUrlInput.value.trim().length > 0) {
      btnClearInput.classList.remove('hidden');
    } else {
      btnClearInput.classList.add('hidden');
    }
  });

  btnClearInput.addEventListener('click', () => {
    ytUrlInput.value = '';
    btnClearInput.classList.add('hidden');
    hideResultCard();
    hideError();
  });

  btnPaste.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        ytUrlInput.value = text.trim();
        btnClearInput.classList.remove('hidden');
        triggerFetch();
      }
    } catch (err) {
      console.warn('Clipboard read error:', err);
    }
  });

  urlForm.addEventListener('submit', (e) => {
    e.preventDefault();
    triggerFetch();
  });

  function triggerFetch() {
    const url = ytUrlInput.value.trim();
    if (!url) return;
    fetchVideoMetadata(url);
  }

  /* ==========================================================================
     API Video Metadata Fetcher
     ========================================================================== */
  async function fetchVideoMetadata(url) {
    showSkeleton();
    hideError();
    hideResultCard();
    hideProgressCard();

    try {
      const res = await fetch('/api/info', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });

      const data = await res.json();
      hideSkeleton();

      if (!res.ok || !data.success) {
        showError(data.error || 'Failed to parse YouTube video link.');
        return;
      }

      currentVideoData = data;
      renderVideoDetails(data);
    } catch (err) {
      hideSkeleton();
      showError('Network error connecting to downloader server.');
      console.error(err);
    }
  }

  function renderVideoDetails(data) {
    videoThumb.src = data.thumbnail;
    videoTitle.textContent = data.title;
    videoChannel.textContent = data.channel;
    videoViews.textContent = `${data.views} views`;
    videoDuration.textContent = data.duration;

    // Render Video & MP3 Audio Options Grids
    renderVideoOptions(data.video_options);
    renderAudioOptions(data.audio_options);

    videoResultCard.classList.remove('hidden');
    videoResultCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  /* ==========================================================================
     Format Selection Grids & Tabs (Video vs MP3 Audio)
     ========================================================================== */
  function renderVideoOptions(videoOpts) {
    videoFormatGrid.innerHTML = '';
    selectedFormat = null;

    videoOpts.forEach((opt, idx) => {
      const card = document.createElement('div');
      card.className = `option-card ${idx === 0 ? 'selected' : ''}`;
      card.dataset.type = 'video';
      card.dataset.height = opt.height;

      card.innerHTML = `
        <div class="option-info">
          <span class="option-title">${opt.label}</span>
          <span class="option-badge">${opt.badge}</span>
        </div>
        <div class="option-radio"></div>
      `;

      card.addEventListener('click', () => selectFormatOption(card, {
        is_audio: false,
        height: opt.height,
        label: opt.label
      }));

      videoFormatGrid.appendChild(card);

      if (idx === 0) {
        selectedFormat = { is_audio: false, height: opt.height, label: opt.label };
        updateDownloadBtnLabel(`Download ${opt.label}`);
      }
    });
  }

  function renderAudioOptions(audioOpts) {
    audioFormatGrid.innerHTML = '';

    audioOpts.forEach((opt) => {
      const card = document.createElement('div');
      card.className = 'option-card';
      card.dataset.type = 'audio';
      card.dataset.id = opt.id;

      card.innerHTML = `
        <div class="option-info">
          <span class="option-title">${opt.label}</span>
          <span class="option-badge">${opt.badge}</span>
        </div>
        <div class="option-radio"></div>
      `;

      card.addEventListener('click', () => selectFormatOption(card, {
        is_audio: true,
        ext: opt.ext,
        bitrate: opt.bitrate,
        label: opt.label
      }));

      audioFormatGrid.appendChild(card);
    });
  }

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      activeTab = btn.dataset.tab;
      if (activeTab === 'video') {
        videoFormatGrid.classList.remove('hidden');
        audioFormatGrid.classList.add('hidden');
        
        const firstVideo = videoFormatGrid.querySelector('.option-card');
        if (firstVideo) firstVideo.click();
      } else {
        videoFormatGrid.classList.add('hidden');
        audioFormatGrid.classList.remove('hidden');

        const firstAudio = audioFormatGrid.querySelector('.option-card');
        if (firstAudio) firstAudio.click();
      }
    });
  });

  function selectFormatOption(cardElem, formatData) {
    const parent = cardElem.parentElement;
    parent.querySelectorAll('.option-card').forEach(c => c.classList.remove('selected'));
    cardElem.classList.add('selected');

    selectedFormat = formatData;
    updateDownloadBtnLabel(`Download ${formatData.label}`);
  }

  function updateDownloadBtnLabel(text) {
    downloadBtnLabel.textContent = text;
  }

  /* ==========================================================================
     Download Process & Real-Time Polling Engine
     ========================================================================== */
  btnStartDownload.addEventListener('click', () => {
    if (!currentVideoData || !selectedFormat) return;
    initiateDownload();
  });

  async function initiateDownload() {
    hideError();
    showProgressCard();

    const payload = {
      url: currentVideoData.url,
      is_audio: selectedFormat.is_audio,
      height: selectedFormat.height || 720,
      bitrate: selectedFormat.bitrate || '320',
      ext: selectedFormat.ext || 'mp3'
    };

    try {
      const res = await fetch('/api/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        showError(data.error || 'Failed to start download process.');
        hideProgressCard();
        return;
      }

      startProgressPolling(data.download_id);
    } catch (err) {
      showError('Failed to communicate with download process.');
      hideProgressCard();
      console.error(err);
    }
  }

  function startProgressPolling(downloadId) {
    if (pollInterval) clearInterval(pollInterval);

    pollInterval = setInterval(async () => {
      try {
        const res = await fetch(`/api/progress/${downloadId}`);
        if (!res.ok) return;

        const data = await res.json();
        updateProgressUI(data, downloadId);

        if (data.status === 'completed' || data.status === 'error') {
          clearInterval(pollInterval);
        }
      } catch (err) {
        console.error('Progress poll error:', err);
      }
    }, 750);
  }

  function updateProgressUI(data, downloadId) {
    if (data.status === 'starting') {
      progressStatusText.textContent = data.status_msg || 'Initializing Stream...';
      updateBar(5);
    } else if (data.status === 'downloading') {
      progressStatusText.textContent = selectedFormat.is_audio ? 'Extracting Audio Stream...' : 'Downloading Video Stream...';
      updateBar(data.percent);
      statDownloaded.textContent = `${data.downloaded_str} / ${data.total_str}`;
      statSpeed.textContent = data.speed_str;
      statEta.textContent = data.eta_str;
    } else if (data.status === 'processing') {
      progressStatusText.textContent = selectedFormat.is_audio ? 'Converting Audio to MP3 Format...' : 'Processing Video Stream...';
      updateBar(98);
    } else if (data.status === 'completed') {
      progressStatusText.textContent = 'Download Complete!';
      updateBar(100);
      
      const fileUrl = `/api/file/${downloadId}`;
      btnSaveFile.href = fileUrl;
      completeActionArea.classList.remove('hidden');

      // Auto trigger browser download
      setTimeout(() => {
        window.location.href = fileUrl;
      }, 500);

    } else if (data.status === 'error') {
      showError(data.error_msg || 'Download failed.');
      hideProgressCard();
    }
  }

  function updateBar(pct) {
    const val = Math.min(Math.max(pct, 0), 100);
    progressBarFill.style.width = `${val}%`;
    progressPercentage.textContent = `${Math.round(val)}%`;
  }

  /* ==========================================================================
     UI State Helpers
     ========================================================================== */
  function showSkeleton() {
    loadingSkeleton.classList.remove('hidden');
  }

  function hideSkeleton() {
    loadingSkeleton.classList.add('hidden');
  }

  function showError(msg) {
    errorText.textContent = msg;
    errorBanner.classList.remove('hidden');
  }

  function hideError() {
    errorBanner.classList.add('hidden');
  }

  function hideResultCard() {
    videoResultCard.classList.add('hidden');
  }

  function showProgressCard() {
    completeActionArea.classList.add('hidden');
    updateBar(0);
    progressStatusText.textContent = 'Initializing Stream...';
    statDownloaded.textContent = '0 MB / 0 MB';
    statSpeed.textContent = '0 MB/s';
    statEta.textContent = '--';
    progressCard.classList.remove('hidden');
    progressCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function hideProgressCard() {
    progressCard.classList.add('hidden');
    if (pollInterval) clearInterval(pollInterval);
  }
});

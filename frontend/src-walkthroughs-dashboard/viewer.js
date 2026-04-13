(function () {
  'use strict';

  // ---------- Persistent UI prefs (size + gallery view mode) ----------

  var LS_SIZE_KEY = 'evidence.tileSize';
  var LS_VIEW_KEY = 'evidence.galleryView';
  // Snap stops in px for the tile-size slider. Wide range so strip frames
  // can go from thumbnail (160) to nearly full-viewport (1200).
  var SIZE_STOPS = [160, 240, 320, 480, 640, 800, 1000, 1200];
  var SIZE_DEFAULT = 320;
  // Legacy string-keyed values from earlier rounds, migrated on read.
  var LEGACY_SIZE_MAP = { small: 240, medium: 320, large: 480 };

  function clampToStop(n) {
    var best = SIZE_STOPS[0];
    var bestD = Math.abs(n - best);
    for (var i = 1; i < SIZE_STOPS.length; i++) {
      var d = Math.abs(n - SIZE_STOPS[i]);
      if (d < bestD) { best = SIZE_STOPS[i]; bestD = d; }
    }
    return best;
  }

  function readSize() {
    try {
      var v = localStorage.getItem(LS_SIZE_KEY);
      if (v == null) return SIZE_DEFAULT;
      if (Object.prototype.hasOwnProperty.call(LEGACY_SIZE_MAP, v)) {
        var migrated = LEGACY_SIZE_MAP[v];
        try { localStorage.setItem(LS_SIZE_KEY, String(migrated)); } catch (e) { /* ignore */ }
        return migrated;
      }
      var n = parseInt(v, 10);
      if (Number.isFinite(n) && n > 0) return clampToStop(n);
    } catch (e) { /* ignore */ }
    return SIZE_DEFAULT;
  }
  function writeSize(n) {
    try { localStorage.setItem(LS_SIZE_KEY, String(n)); } catch (e) { /* ignore */ }
  }
  function readGalleryView() {
    try {
      var v = localStorage.getItem(LS_VIEW_KEY);
      if (v === 'gif' || v === 'strip') return v;
    } catch (e) { /* ignore */ }
    return 'gif';
  }
  function writeGalleryView(v) {
    try { localStorage.setItem(LS_VIEW_KEY, v); } catch (e) { /* ignore */ }
  }

  function applyTileSize(n) {
    document.documentElement.style.setProperty('--tile-size', n + 'px');
  }

  var state = {
    scenarios: [],
    generatedAt: '',
    selectedFeature: '__all__',
    search: '',
    tileSize: readSize(),
    galleryView: readGalleryView(),
    // Lightbox
    lbSlug: null,
    lbIndex: 0,
    // Non-screenshot lightbox mode: 'screenshots' | 'gif' | 'video'
    lbMode: 'screenshots',
    lbMediaSrc: null,
    lbMediaTitle: '',
  };

  applyTileSize(state.tileSize);

  function escapeHtml(str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function statusClass(s) {
    if (s === 'passed') return 'status-passed';
    if (s === 'failed') return 'status-failed';
    return 'status-other';
  }

  function pad2(n) { return String(n).padStart(2, '0'); }

  function stepScreenshotUrl(slug, step) {
    return 'screenshots/' + slug + '/' + pad2(step.index) + '-' + step.slug + '.png';
  }

  function findScenario(slug) {
    for (var i = 0; i < state.scenarios.length; i++) {
      if (state.scenarios[i].slug === slug) return state.scenarios[i];
    }
    return null;
  }

  function features() {
    var set = {};
    state.scenarios.forEach(function (s) { set[s.feature] = true; });
    return Object.keys(set).sort();
  }

  function filtered() {
    var q = state.search.trim().toLowerCase();
    return state.scenarios.filter(function (s) {
      if (state.selectedFeature !== '__all__' && s.feature !== state.selectedFeature) return false;
      if (!q) return true;
      return (s.name + ' ' + s.feature + ' ' + s.slug).toLowerCase().indexOf(q) !== -1;
    });
  }

  // ---------- Routing ----------

  function parseRoute() {
    var h = window.location.hash || '#/';
    var m = h.match(/^#\/scenario\/([^/]+)(?:\/(screenshots|flow))?\/?$/);
    if (m) {
      return { name: 'scenario', slug: decodeURIComponent(m[1]), view: m[2] || 'detail' };
    }
    return { name: 'gallery' };
  }

  function navigate(hash) {
    if (window.location.hash === hash) {
      render();
    } else {
      window.location.hash = hash;
    }
  }

  // ---------- Toolbar (size + view mode) ----------

  function sizeControlHtml(includeViewToggle) {
    var minStop = SIZE_STOPS[0];
    var maxStop = SIZE_STOPS[SIZE_STOPS.length - 1];
    // Datalist provides visual snap marks; step=1 with JS snap-to-stop on input.
    var datalistOpts = SIZE_STOPS.map(function (s) { return '<option value="' + s + '"></option>'; }).join('');
    var sizeSlider =
      '<div class="toolbar-group size-group"><span class="toolbar-label">Size</span>' +
        '<input type="range" class="size-slider" min="' + minStop + '" max="' + maxStop + '" step="1" value="' + state.tileSize + '" list="size-stops" aria-label="Tile size" />' +
        '<datalist id="size-stops">' + datalistOpts + '</datalist>' +
        '<span class="size-readout"><span class="size-px">' + state.tileSize + '</span>px</span>' +
      '</div>';
    var viewToggle = '';
    if (includeViewToggle) {
      viewToggle =
        '<div class="toolbar-group"><span class="toolbar-label">View</span>' +
          '<button type="button" class="toolbar-btn' + (state.galleryView === 'gif' ? ' active' : '') + '" data-view="gif">GIF cards</button>' +
          '<button type="button" class="toolbar-btn' + (state.galleryView === 'strip' ? ' active' : '') + '" data-view="strip">Screenshot strips</button>' +
        '</div>';
    }
    return (
      '<div class="toolbar">' +
        sizeSlider +
        viewToggle +
      '</div>'
    );
  }

  function wireToolbar(root, onChange) {
    if (!root) return;
    var slider = root.querySelector('.size-slider');
    var readout = root.querySelector('.size-px');
    if (slider) {
      // During drag, update readout live without committing localStorage.
      slider.addEventListener('input', function () {
        var raw = parseInt(slider.value, 10);
        var snapped = clampToStop(Number.isFinite(raw) ? raw : SIZE_DEFAULT);
        if (readout) readout.textContent = String(snapped);
        state.tileSize = snapped;
        applyTileSize(snapped);
        if (onChange) onChange('size');
      });
      slider.addEventListener('change', function () {
        // Commit final snapped value on release.
        slider.value = String(state.tileSize);
        writeSize(state.tileSize);
      });
    }
    root.querySelectorAll('[data-view]').forEach(function (b) {
      b.addEventListener('click', function () {
        state.galleryView = b.getAttribute('data-view');
        writeGalleryView(state.galleryView);
        root.querySelectorAll('[data-view]').forEach(function (x) {
          x.classList.toggle('active', x.getAttribute('data-view') === state.galleryView);
        });
        if (onChange) onChange('view');
      });
    });
  }

  // ---------- Gallery view ----------

  function renderGallery() {
    var app = document.getElementById('app');
    app.innerHTML = (
      '<div class="layout">' +
        '<aside class="sidebar">' +
          '<section>' +
            '<h2>Search</h2>' +
            '<input id="search" type="search" placeholder="Search scenarios..." />' +
          '</section>' +
          '<section>' +
            '<h2>Feature</h2>' +
            '<ul id="feature-list"></ul>' +
          '</section>' +
        '</aside>' +
        '<main class="main-col">' +
          sizeControlHtml(true) +
          '<div class="grid" id="grid"></div>' +
        '</main>' +
      '</div>'
    );

    var searchEl = document.getElementById('search');
    searchEl.value = state.search;
    searchEl.addEventListener('input', function (e) {
      state.search = e.target.value || '';
      renderGrid();
    });

    wireToolbar(app.querySelector('.toolbar'), function (kind) {
      if (kind === 'view') renderGrid();
    });

    renderSidebar();
    renderGrid();
  }

  function renderSidebar() {
    var el = document.getElementById('feature-list');
    if (!el) return;
    var html = '';
    html += '<li data-feature="__all__" class="' + (state.selectedFeature === '__all__' ? 'active' : '') + '">All (' + state.scenarios.length + ')</li>';
    features().forEach(function (f) {
      var count = state.scenarios.filter(function (s) { return s.feature === f; }).length;
      html += '<li data-feature="' + escapeHtml(f) + '" class="' + (state.selectedFeature === f ? 'active' : '') + '">' + escapeHtml(f) + ' (' + count + ')</li>';
    });
    el.innerHTML = html;
    el.querySelectorAll('li').forEach(function (li) {
      li.addEventListener('click', function () {
        state.selectedFeature = li.getAttribute('data-feature');
        renderSidebar();
        renderGrid();
      });
    });
  }

  function cardLinks(s) {
    var parts = [];
    parts.push('<a class="pill" href="#/scenario/' + encodeURIComponent(s.slug) + '/screenshots" data-nav="1">Screenshots</a>');
    parts.push('<a class="pill" href="#/scenario/' + encodeURIComponent(s.slug) + '/flow" data-nav="1">Flow</a>');
    if (s.motionGifPath) {
      parts.push('<a class="pill" href="' + escapeHtml(s.motionGifPath) + '" target="_blank" rel="noopener" data-stop="1">Motion GIF</a>');
    }
    if (s.videoGalleryPath) {
      parts.push('<a class="pill" href="' + escapeHtml(s.videoGalleryPath) + '" target="_blank" rel="noopener" data-stop="1">Video</a>');
    }
    return '<div class="pills">' + parts.join('') + '</div>';
  }

  function renderGifCard(s) {
    var thumb;
    if (s.gifPath) {
      thumb = '<img class="thumb" src="' + escapeHtml(s.gifPath) + '" alt="" loading="lazy" />';
    } else if (s.steps && s.steps.length) {
      var lastStep = s.steps[s.steps.length - 1];
      thumb = '<img class="thumb" src="' + escapeHtml(stepScreenshotUrl(s.slug, lastStep)) + '" alt="" loading="lazy" />';
    } else {
      thumb = '<div class="thumb"></div>';
    }
    return (
      '<article class="card" data-slug="' + escapeHtml(s.slug) + '">' +
      thumb +
      '<div class="body">' +
      '<div class="title">' + escapeHtml(s.name) + '</div>' +
      '<div class="sub"><span class="' + statusClass(s.status) + '">' + escapeHtml(s.status) + '</span> &middot; ' + (s.steps ? s.steps.length : 0) + ' steps &middot; ' + (s.durationMs || 0) + ' ms</div>' +
      cardLinks(s) +
      '</div></article>'
    );
  }

  function renderStripCard(s) {
    var steps = s.steps || [];
    var frames = steps.map(function (st) {
      var url = stepScreenshotUrl(s.slug, st);
      return (
        '<button type="button" class="strip-frame" data-strip-idx="' + (st.index - 1) + '" aria-label="Step ' + st.index + ': ' + escapeHtml(st.name) + '">' +
          '<img src="' + escapeHtml(url) + '" alt="" loading="lazy" />' +
          '<span class="strip-n">' + pad2(st.index) + '</span>' +
        '</button>'
      );
    }).join('');
    return (
      '<article class="card card-strip" data-slug="' + escapeHtml(s.slug) + '">' +
        '<div class="strip-scroll">' + (frames || '<div class="empty">No steps</div>') + '</div>' +
        '<div class="body">' +
          '<div class="title">' + escapeHtml(s.name) + '</div>' +
          '<div class="sub"><span class="' + statusClass(s.status) + '">' + escapeHtml(s.status) + '</span> &middot; ' + steps.length + ' steps &middot; ' + (s.durationMs || 0) + ' ms</div>' +
          cardLinks(s) +
        '</div>' +
      '</article>'
    );
  }

  function renderStripRow(s) {
    var steps = s.steps || [];
    var frames = steps.map(function (st) {
      var url = stepScreenshotUrl(s.slug, st);
      return (
        '<button type="button" class="strip-frame strip-frame-row" data-strip-idx="' + (st.index - 1) + '" aria-label="Step ' + st.index + ': ' + escapeHtml(st.name) + '">' +
          '<img src="' + escapeHtml(url) + '" alt="" loading="lazy" />' +
          '<span class="strip-n">' + pad2(st.index) + '</span>' +
        '</button>'
      );
    }).join('');
    return (
      '<section class="strip-row" data-slug="' + escapeHtml(s.slug) + '">' +
        '<header class="strip-row-header">' +
          '<div class="strip-row-heading">' +
            '<div class="strip-row-title">' + escapeHtml(s.name) + '</div>' +
            '<div class="strip-row-sub">' +
              '<span class="' + statusClass(s.status) + '">' + escapeHtml(s.status) + '</span>' +
              '<span class="strip-row-meta-line">' + escapeHtml(s.feature) + '</span>' +
              '<span class="strip-row-meta-line">' + steps.length + ' steps &middot; ' + (s.durationMs || 0) + ' ms</span>' +
            '</div>' +
          '</div>' +
          cardLinks(s) +
        '</header>' +
        '<div class="strip-row-scroll-wrap">' +
          '<button type="button" class="strip-scroll-btn strip-scroll-prev" aria-label="Scroll left" data-scroll="prev">&#10094;</button>' +
          '<div class="strip-row-scroll">' + (frames || '<div class="empty">No steps</div>') + '</div>' +
          '<button type="button" class="strip-scroll-btn strip-scroll-next" aria-label="Scroll right" data-scroll="next">&#10095;</button>' +
        '</div>' +
      '</section>'
    );
  }

  function renderGrid() {
    var el = document.getElementById('grid');
    if (!el) return;
    var list = filtered();
    if (list.length === 0) {
      el.innerHTML = '<div class="empty">No scenarios match.</div>';
      return;
    }
    var stripMode = state.galleryView === 'strip';
    el.classList.toggle('grid-strip', stripMode);
    el.classList.toggle('strip-rows', stripMode);
    el.innerHTML = list.map(function (s) {
      return stripMode ? renderStripRow(s) : renderGifCard(s);
    }).join('');

    function wireContainer(container) {
      container.addEventListener('click', function (e) {
        var t = e.target;
        var walker = t;
        // Chevron scroll buttons
        while (walker && walker !== container) {
          if (walker.getAttribute && walker.getAttribute('data-scroll')) {
            e.preventDefault();
            e.stopPropagation();
            var dir = walker.getAttribute('data-scroll');
            var scroller = container.querySelector('.strip-row-scroll');
            if (scroller) {
              var delta = Math.round(scroller.clientWidth * 0.8) * (dir === 'next' ? 1 : -1);
              scroller.scrollBy({ left: delta, behavior: 'smooth' });
            }
            return;
          }
          walker = walker.parentNode;
        }
        walker = t;
        // Strip-frame clicks → jump to that step in screenshots lightbox
        while (walker && walker !== container) {
          if (walker.getAttribute && walker.getAttribute('data-strip-idx') != null) {
            e.preventDefault();
            e.stopPropagation();
            openScreenshotsLightbox(container.getAttribute('data-slug'), Number(walker.getAttribute('data-strip-idx')));
            return;
          }
          walker = walker.parentNode;
        }
        // Ignore pill/nav clicks
        walker = t;
        while (walker && walker !== container) {
          if (walker.getAttribute && (walker.getAttribute('data-nav') === '1' || walker.getAttribute('data-stop') === '1')) return;
          walker = walker.parentNode;
        }
        // Only GIF cards navigate on body click; strip rows don't.
        if (container.classList.contains('card') && !container.classList.contains('card-strip')) {
          var slug = container.getAttribute('data-slug');
          navigate('#/scenario/' + encodeURIComponent(slug));
        }
      });
    }

    el.querySelectorAll('.card').forEach(wireContainer);
    el.querySelectorAll('.strip-row').forEach(wireContainer);
  }

  // ---------- Scenario detail view ----------

  function renderScenarioDetail(s) {
    var app = document.getElementById('app');
    var flipbook = s.gifPath
      ? '<figure class="gif-figure clickable-media" data-media="gif" data-src="' + escapeHtml(s.gifPath) + '" data-title="Flipbook GIF" tabindex="0" role="button" aria-label="Open flipbook GIF fullscreen">' +
          '<figcaption>Flipbook GIF (one frame per step) &middot; click to enlarge</figcaption>' +
          '<img class="detail-gif" src="' + escapeHtml(s.gifPath) + '" alt="" />' +
        '</figure>'
      : '';
    var motion = s.motionGifPath
      ? '<figure class="gif-figure clickable-media" data-media="gif" data-src="' + escapeHtml(s.motionGifPath) + '" data-title="Motion GIF" tabindex="0" role="button" aria-label="Open motion GIF fullscreen">' +
          '<figcaption>Motion GIF (slowed 2x) &middot; click to enlarge</figcaption>' +
          '<img class="detail-gif" src="' + escapeHtml(s.motionGifPath) + '" alt="" />' +
        '</figure>'
      : '';
    var video = s.videoGalleryPath
      ? '<figure class="gif-figure clickable-media" data-media="video" data-src="' + escapeHtml(s.videoGalleryPath) + '" data-title="Playwright recording" tabindex="0" role="button" aria-label="Open video fullscreen">' +
          '<figcaption>Playwright recording &middot; click to enlarge</figcaption>' +
          '<video class="detail-video" src="' + escapeHtml(s.videoGalleryPath) + '" preload="metadata" muted></video>' +
          '<div class="detail-video-links"><a href="' + escapeHtml(s.videoGalleryPath) + '" download data-stop-click="1">Download .webm</a></div>' +
        '</figure>'
      : '';
    // Screenshots preview (small filmstrip, clickable → screenshots page)
    var firstFew = (s.steps || []).slice(0, 5).map(function (st) {
      return '<img src="' + escapeHtml(stepScreenshotUrl(s.slug, st)) + '" alt="" loading="lazy" />';
    }).join('');
    var screenshotsPreview = (s.steps && s.steps.length > 0)
      ? '<figure class="gif-figure clickable-media" data-media="screenshots" tabindex="0" role="button" aria-label="Open screenshots grid">' +
          '<figcaption>Screenshots (' + s.steps.length + ' steps) &middot; click to view all</figcaption>' +
          '<div class="screenshots-preview">' + firstFew + '</div>' +
        '</figure>'
      : '';
    var trace = s.tracePath
      ? '<a href="' + escapeHtml('../' + s.tracePath) + '" target="_blank" rel="noopener">trace.zip</a>'
      : '&mdash;';
    var stepsList = (s.steps || []).map(function (st) {
      return '<li><strong>' + escapeHtml(st.name) + '</strong> &mdash; ' + (st.durationMs || 0) + ' ms <span class="' + statusClass(st.status) + '">' + escapeHtml(st.status) + '</span></li>';
    }).join('');
    app.innerHTML = (
      '<div class="detail">' +
        '<nav class="breadcrumb"><a href="#/">&larr; Back to gallery</a></nav>' +
        '<h2>' + escapeHtml(s.name) + '</h2>' +
        '<p class="hint">Click any preview below to view it fullscreen.</p>' +
        '<div class="gifs-row">' + screenshotsPreview + flipbook + motion + video + '</div>' +
        '<dl class="kv">' +
          '<dt>Status</dt><dd class="' + statusClass(s.status) + '">' + escapeHtml(s.status) + '</dd>' +
          '<dt>Feature</dt><dd>' + escapeHtml(s.feature) + '</dd>' +
          '<dt>Correlation ID</dt><dd><code>' + escapeHtml(s.correlationId) + '</code></dd>' +
          '<dt>Started</dt><dd>' + escapeHtml(s.startedAt) + '</dd>' +
          '<dt>Duration</dt><dd>' + escapeHtml(String(s.durationMs || 0)) + ' ms</dd>' +
          '<dt>Spec file</dt><dd><code>' + escapeHtml(s.specFile) + '</code></dd>' +
          '<dt>Trace</dt><dd>' + trace + '</dd>' +
        '</dl>' +
        '<section class="steps"><h3>Steps</h3><ol>' + stepsList + '</ol></section>' +
      '</div>'
    );

    function handleMediaActivation(fig, e) {
      var t = e.target;
      // Let download links work without hijack.
      while (t && t !== fig) {
        if (t.getAttribute && t.getAttribute('data-stop-click') === '1') return;
        t = t.parentNode;
      }
      if (e && e.preventDefault) e.preventDefault();
      var media = fig.getAttribute('data-media');
      if (media === 'screenshots') {
        navigate('#/scenario/' + encodeURIComponent(s.slug) + '/screenshots');
        return;
      }
      var src = fig.getAttribute('data-src');
      var title = fig.getAttribute('data-title') || '';
      if (media === 'gif') openMediaLightbox('gif', src, title);
      else if (media === 'video') openMediaLightbox('video', src, title);
    }

    app.querySelectorAll('.clickable-media').forEach(function (fig) {
      fig.addEventListener('click', function (e) { handleMediaActivation(fig, e); });
      fig.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handleMediaActivation(fig, e);
        }
      });
    });
  }

  // ---------- Screenshots page ----------

  function renderScreenshotsPage(s) {
    var app = document.getElementById('app');
    var steps = s.steps || [];
    var tiles = steps.map(function (st) {
      var url = stepScreenshotUrl(s.slug, st);
      return (
        '<figure class="shot-tile" data-idx="' + (st.index - 1) + '" tabindex="0">' +
          '<img src="' + escapeHtml(url) + '" alt="Step ' + st.index + ': ' + escapeHtml(st.name) + '" loading="lazy" />' +
          '<figcaption><span class="step-n">' + pad2(st.index) + '</span> ' + escapeHtml(st.name) + '</figcaption>' +
        '</figure>'
      );
    }).join('');
    app.innerHTML = (
      '<div class="detail">' +
        '<nav class="breadcrumb">' +
          '<a href="#/">&larr; Back to gallery</a> / ' +
          '<a href="#/scenario/' + encodeURIComponent(s.slug) + '">' + escapeHtml(s.name) + '</a> / ' +
          'Screenshots' +
        '</nav>' +
        '<h2>Screenshots: ' + escapeHtml(s.name) + '</h2>' +
        '<div class="pills"><a class="pill" href="#/scenario/' + encodeURIComponent(s.slug) + '/flow">Flow overview</a></div>' +
        sizeControlHtml(false) +
        '<div class="shot-grid">' + tiles + '</div>' +
      '</div>'
    );
    wireToolbar(app.querySelector('.toolbar'));
    app.querySelectorAll('.shot-tile').forEach(function (tile) {
      tile.addEventListener('click', function () {
        openScreenshotsLightbox(s.slug, Number(tile.getAttribute('data-idx')));
      });
      tile.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          openScreenshotsLightbox(s.slug, Number(tile.getAttribute('data-idx')));
        }
      });
    });
  }

  // ---------- Flow overview page ----------

  function renderFlowPage(s) {
    var app = document.getElementById('app');
    var steps = s.steps || [];
    var frames = steps.map(function (st) {
      var url = stepScreenshotUrl(s.slug, st);
      return (
        '<figure class="flow-frame" data-idx="' + (st.index - 1) + '" tabindex="0">' +
          '<div class="flow-n">' + pad2(st.index) + '</div>' +
          '<img src="' + escapeHtml(url) + '" alt="Step ' + st.index + ': ' + escapeHtml(st.name) + '" loading="lazy" />' +
          '<figcaption>' + escapeHtml(st.name) + '</figcaption>' +
        '</figure>'
      );
    }).join('');
    app.innerHTML = (
      '<div class="detail">' +
        '<nav class="breadcrumb">' +
          '<a href="#/">&larr; Back to gallery</a> / ' +
          '<a href="#/scenario/' + encodeURIComponent(s.slug) + '">' + escapeHtml(s.name) + '</a> / ' +
          'Flow overview' +
        '</nav>' +
        '<h2>Flow: ' + escapeHtml(s.name) + '</h2>' +
        '<p class="hint">All ' + steps.length + ' steps in reading order. Click any frame to open full-size.</p>' +
        '<div class="pills"><a class="pill" href="#/scenario/' + encodeURIComponent(s.slug) + '/screenshots">Screenshot grid</a></div>' +
        sizeControlHtml(false) +
        '<div class="flow-strip">' + frames + '</div>' +
      '</div>'
    );
    wireToolbar(app.querySelector('.toolbar'));
    app.querySelectorAll('.flow-frame').forEach(function (frame) {
      frame.addEventListener('click', function () {
        openScreenshotsLightbox(s.slug, Number(frame.getAttribute('data-idx')));
      });
      frame.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          openScreenshotsLightbox(s.slug, Number(frame.getAttribute('data-idx')));
        }
      });
    });
  }

  // ---------- Lightbox (screenshots) ----------

  function openScreenshotsLightbox(slug, idx) {
    var s = findScenario(slug);
    if (!s || !s.steps || s.steps.length === 0) return;
    state.lbMode = 'screenshots';
    state.lbSlug = slug;
    state.lbIndex = Math.max(0, Math.min(idx, s.steps.length - 1));
    state.lbMediaSrc = null;
    state.lbMediaTitle = '';
    renderLightbox();
  }

  function openMediaLightbox(mode, src, title) {
    state.lbMode = mode;
    state.lbMediaSrc = src;
    state.lbMediaTitle = title || '';
    state.lbSlug = null;
    renderLightbox();
  }

  function closeLightbox() {
    var lb = document.getElementById('lightbox');
    // Pause any playing video before hiding so audio/decoding stops.
    var v = lb.querySelector('video');
    if (v) { try { v.pause(); } catch (e) { /* ignore */ } }
    lb.classList.add('hidden');
    lb.innerHTML = '';
    state.lbSlug = null;
    state.lbMode = 'screenshots';
    state.lbMediaSrc = null;
  }

  function renderLightbox() {
    var lb = document.getElementById('lightbox');
    lb.classList.remove('hidden');
    if (state.lbMode === 'screenshots') {
      var s = findScenario(state.lbSlug);
      if (!s) { closeLightbox(); return; }
      var st = s.steps[state.lbIndex];
      lb.innerHTML = (
        '<button class="lightbox-close" data-lb-close="1" aria-label="Close">&times;</button>' +
        '<button class="lightbox-nav lightbox-prev" data-lb-prev="1" aria-label="Previous">&#10094;</button>' +
        '<button class="lightbox-nav lightbox-next" data-lb-next="1" aria-label="Next">&#10095;</button>' +
        '<figure class="lightbox-figure">' +
          '<img class="lightbox-media" src="' + escapeHtml(stepScreenshotUrl(s.slug, st)) + '" alt="Step ' + st.index + ': ' + escapeHtml(st.name) + '" />' +
          '<figcaption>' + pad2(st.index) + ' / ' + pad2(s.steps.length) + ' &mdash; ' + escapeHtml(st.name) + '</figcaption>' +
        '</figure>'
      );
    } else if (state.lbMode === 'gif') {
      lb.innerHTML = (
        '<button class="lightbox-close" data-lb-close="1" aria-label="Close">&times;</button>' +
        '<figure class="lightbox-figure">' +
          '<img class="lightbox-media" src="' + escapeHtml(state.lbMediaSrc) + '" alt="' + escapeHtml(state.lbMediaTitle) + '" />' +
          '<figcaption>' + escapeHtml(state.lbMediaTitle) + '</figcaption>' +
        '</figure>'
      );
    } else if (state.lbMode === 'video') {
      var speedOpts = [0.1, 0.15, 0.25, 0.5, 1, 1.5, 2].map(function (r) {
        var sel = r === 1 ? ' selected' : '';
        return '<option value="' + r + '"' + sel + '>' + r + 'x</option>';
      }).join('');
      lb.innerHTML = (
        '<button class="lightbox-close" data-lb-close="1" aria-label="Close">&times;</button>' +
        '<figure class="lightbox-figure lightbox-figure-video">' +
          '<div class="video-toolbar">' +
            '<label>Speed <select id="lb-speed">' + speedOpts + '</select></label>' +
            '<a class="pill" href="' + escapeHtml(state.lbMediaSrc) + '" download>Download .webm</a>' +
          '</div>' +
          '<video class="lightbox-media lightbox-video" src="' + escapeHtml(state.lbMediaSrc) + '" controls autoplay preload="metadata"></video>' +
          '<figcaption>' + escapeHtml(state.lbMediaTitle) + '</figcaption>' +
        '</figure>'
      );
      var sel = lb.querySelector('#lb-speed');
      var vid = lb.querySelector('video');
      if (sel && vid) {
        sel.addEventListener('change', function () {
          vid.playbackRate = parseFloat(sel.value);
        });
      }
    }
    // Focus the lightbox so the document-level keydown doesn't bubble to buttons (no beep).
    try { lb.focus(); } catch (e) { /* ignore */ }
  }

  function lbNext() {
    if (state.lbMode !== 'screenshots') return;
    var s = findScenario(state.lbSlug);
    if (!s) return;
    state.lbIndex = (state.lbIndex + 1) % s.steps.length;
    renderLightbox();
  }
  function lbPrev() {
    if (state.lbMode !== 'screenshots') return;
    var s = findScenario(state.lbSlug);
    if (!s) return;
    state.lbIndex = (state.lbIndex - 1 + s.steps.length) % s.steps.length;
    renderLightbox();
  }

  // ---------- Render dispatch ----------

  function render() {
    document.getElementById('meta').textContent = state.generatedAt ? 'Generated ' + state.generatedAt : '';
    // Close any open lightbox when routing.
    var lb = document.getElementById('lightbox');
    if (lb && !lb.classList.contains('hidden')) closeLightbox();
    var route = parseRoute();
    if (route.name === 'scenario') {
      var s = findScenario(route.slug);
      if (!s) {
        document.getElementById('app').innerHTML = '<div class="empty">Scenario not found: ' + escapeHtml(route.slug) + '. <a href="#/">Back to gallery</a></div>';
        return;
      }
      if (route.view === 'screenshots') renderScreenshotsPage(s);
      else if (route.view === 'flow') renderFlowPage(s);
      else renderScenarioDetail(s);
    } else {
      renderGallery();
    }
  }

  // ---------- Init ----------

  function init() {
    fetch('./manifest.json', { cache: 'no-cache' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        state.generatedAt = data.generatedAt || '';
        state.scenarios = data.scenarios || [];
        render();
      })
      .catch(function (err) {
        document.getElementById('app').innerHTML = '<div class="empty">Failed to load manifest.json: ' + escapeHtml(err && err.message) + '</div>';
      });

    window.addEventListener('hashchange', render);

    var lb = document.getElementById('lightbox');
    lb.addEventListener('click', function (e) {
      var t = e.target;
      if (!t || !t.getAttribute) return;
      if (t.getAttribute('data-lb-close') === '1') closeLightbox();
      else if (t.getAttribute('data-lb-prev') === '1') lbPrev();
      else if (t.getAttribute('data-lb-next') === '1') lbNext();
      else if (t === lb) closeLightbox();
    });

    // Keyboard handler attached to document in capture phase; preventDefault
    // stops macOS Chrome/Safari from emitting the "invalid action" beep that
    // fires when arrow keys hit a focused button inside the lightbox.
    document.addEventListener('keydown', function (e) {
      var lbOpen = !document.getElementById('lightbox').classList.contains('hidden');
      if (!lbOpen) return;
      var key = e.key;
      if (key === 'Escape' || key === 'ArrowRight' || key === 'ArrowLeft' || key === 'ArrowUp' || key === 'ArrowDown') {
        // Tag event as handled even for modes that ignore arrow navigation,
        // so no default browser behaviour / system beep fires.
        e.preventDefault();
        e.stopPropagation();
        if (key === 'Escape') closeLightbox();
        else if (key === 'ArrowRight') lbNext();
        else if (key === 'ArrowLeft') lbPrev();
      }
    }, true);
  }

  document.addEventListener('DOMContentLoaded', init);
})();

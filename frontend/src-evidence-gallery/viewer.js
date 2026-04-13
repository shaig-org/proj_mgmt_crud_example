(function () {
  'use strict';

  var state = {
    scenarios: [],
    generatedAt: '',
    selectedFeature: '__all__',
    search: '',
    // Lightbox
    lbSlug: null,
    lbIndex: 0,
  };

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
    // supported: #/, #/scenario/<slug>/screenshots, #/scenario/<slug>/flow, #/scenario/<slug>
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
        '<main class="grid" id="grid"></main>' +
      '</div>'
    );

    var searchEl = document.getElementById('search');
    searchEl.value = state.search;
    searchEl.addEventListener('input', function (e) {
      state.search = e.target.value || '';
      renderGrid();
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

  function renderGrid() {
    var el = document.getElementById('grid');
    if (!el) return;
    var list = filtered();
    if (list.length === 0) {
      el.innerHTML = '<div class="empty">No scenarios match.</div>';
      return;
    }
    el.innerHTML = list.map(function (s) {
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
    }).join('');
    // Card body (non-pill) click → detail view.
    el.querySelectorAll('.card').forEach(function (card) {
      card.addEventListener('click', function (e) {
        var t = e.target;
        while (t && t !== card) {
          if (t.getAttribute && (t.getAttribute('data-nav') === '1' || t.getAttribute('data-stop') === '1')) return;
          t = t.parentNode;
        }
        var slug = card.getAttribute('data-slug');
        navigate('#/scenario/' + encodeURIComponent(slug));
      });
    });
  }

  // ---------- Scenario detail view ----------

  function renderScenarioDetail(s) {
    var app = document.getElementById('app');
    var flipbook = s.gifPath
      ? '<figure class="gif-figure"><figcaption>Flipbook GIF (one frame per step, 5 fps)</figcaption><img class="detail-gif" src="' + escapeHtml(s.gifPath) + '" alt="" /></figure>'
      : '';
    var motion = s.motionGifPath
      ? '<figure class="gif-figure"><figcaption>Motion GIF (video, 5 fps)</figcaption><img class="detail-gif" src="' + escapeHtml(s.motionGifPath) + '" alt="" /></figure>'
      : '';
    var video = s.videoGalleryPath
      ? '<figure class="gif-figure"><figcaption>Original Playwright video</figcaption><video class="detail-video" src="' + escapeHtml(s.videoGalleryPath) + '" controls preload="metadata"></video><div><a href="' + escapeHtml(s.videoGalleryPath) + '" download>Download .webm</a></div></figure>'
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
        '<div class="pills pills-lg">' +
          '<a class="pill" href="#/scenario/' + encodeURIComponent(s.slug) + '/screenshots">Screenshots</a>' +
          '<a class="pill" href="#/scenario/' + encodeURIComponent(s.slug) + '/flow">Flow overview</a>' +
          (s.videoGalleryPath ? '<a class="pill" href="' + escapeHtml(s.videoGalleryPath) + '" target="_blank" rel="noopener">Play video</a>' : '') +
          (s.motionGifPath ? '<a class="pill" href="' + escapeHtml(s.motionGifPath) + '" target="_blank" rel="noopener">Motion GIF</a>' : '') +
        '</div>' +
        '<div class="gifs-row">' + flipbook + motion + video + '</div>' +
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
        '<div class="shot-grid">' + tiles + '</div>' +
      '</div>'
    );
    app.querySelectorAll('.shot-tile').forEach(function (tile) {
      tile.addEventListener('click', function () {
        openLightbox(s.slug, Number(tile.getAttribute('data-idx')));
      });
      tile.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          openLightbox(s.slug, Number(tile.getAttribute('data-idx')));
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
        '<div class="flow-strip">' + frames + '</div>' +
      '</div>'
    );
    app.querySelectorAll('.flow-frame').forEach(function (frame) {
      frame.addEventListener('click', function () {
        openLightbox(s.slug, Number(frame.getAttribute('data-idx')));
      });
      frame.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          openLightbox(s.slug, Number(frame.getAttribute('data-idx')));
        }
      });
    });
  }

  // ---------- Lightbox ----------

  function openLightbox(slug, idx) {
    var s = findScenario(slug);
    if (!s || !s.steps || s.steps.length === 0) return;
    state.lbSlug = slug;
    state.lbIndex = Math.max(0, Math.min(idx, s.steps.length - 1));
    updateLightbox();
    document.getElementById('lightbox').classList.remove('hidden');
  }

  function closeLightbox() {
    document.getElementById('lightbox').classList.add('hidden');
    state.lbSlug = null;
  }

  function updateLightbox() {
    var s = findScenario(state.lbSlug);
    if (!s) return;
    var st = s.steps[state.lbIndex];
    var img = document.getElementById('lightbox-img');
    img.src = stepScreenshotUrl(s.slug, st);
    img.alt = 'Step ' + st.index + ': ' + st.name;
    document.getElementById('lightbox-cap').textContent =
      pad2(st.index) + ' / ' + pad2(s.steps.length) + ' — ' + st.name;
  }

  function lbNext() {
    var s = findScenario(state.lbSlug);
    if (!s) return;
    state.lbIndex = (state.lbIndex + 1) % s.steps.length;
    updateLightbox();
  }
  function lbPrev() {
    var s = findScenario(state.lbSlug);
    if (!s) return;
    state.lbIndex = (state.lbIndex - 1 + s.steps.length) % s.steps.length;
    updateLightbox();
  }

  // ---------- Render dispatch ----------

  function render() {
    document.getElementById('meta').textContent = state.generatedAt ? 'Generated ' + state.generatedAt : '';
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

    document.addEventListener('keydown', function (e) {
      var lbOpen = !document.getElementById('lightbox').classList.contains('hidden');
      if (!lbOpen) return;
      if (e.key === 'Escape') closeLightbox();
      else if (e.key === 'ArrowRight') lbNext();
      else if (e.key === 'ArrowLeft') lbPrev();
    });
  }

  document.addEventListener('DOMContentLoaded', init);
})();

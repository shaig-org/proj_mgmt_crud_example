(function () {
  'use strict';

  var state = {
    scenarios: [],
    generatedAt: '',
    selectedFeature: '__all__',
    search: '',
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

  function renderSidebar() {
    var el = document.getElementById('feature-list');
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
        render();
      });
    });
  }

  function renderGrid() {
    var el = document.getElementById('grid');
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
        thumb = '<img class="thumb" src="' + escapeHtml(lastStep.screenshot) + '" alt="" loading="lazy" />';
      } else {
        thumb = '<div class="thumb"></div>';
      }
      return (
        '<article class="card" data-slug="' + escapeHtml(s.slug) + '">' +
        thumb +
        '<div class="body">' +
        '<div class="title">' + escapeHtml(s.name) + '</div>' +
        '<div class="sub"><span class="' + statusClass(s.status) + '">' + escapeHtml(s.status) + '</span> &middot; ' + (s.steps ? s.steps.length : 0) + ' steps &middot; ' + (s.durationMs || 0) + ' ms</div>' +
        '</div></article>'
      );
    }).join('');
    el.querySelectorAll('.card').forEach(function (card) {
      card.addEventListener('click', function () {
        var slug = card.getAttribute('data-slug');
        openModal(slug);
      });
    });
  }

  function openModal(slug) {
    var s = state.scenarios.filter(function (x) { return x.slug === slug; })[0];
    if (!s) return;
    var body = document.getElementById('modal-body');
    var gif = s.gifPath ? '<img class="detail-gif" src="' + escapeHtml(s.gifPath) + '" alt="" />' : '<div class="empty">No GIF.</div>';
    var strip = (s.steps || []).map(function (st) {
      return '<div class="frame"><img src="' + escapeHtml('screenshots/' + s.slug + '/' + String(st.index).padStart(2, '0') + '-' + st.slug + '.png') + '" alt="" /><div class="cap">' + escapeHtml(String(st.index) + '. ' + st.name) + '</div></div>';
    }).join('');
    var trace = s.tracePath ? '<a href="' + escapeHtml('../' + s.tracePath) + '" target="_blank" rel="noopener">trace.zip</a>' : '—';
    body.innerHTML = (
      '<h2>' + escapeHtml(s.name) + '</h2>' +
      gif +
      '<div class="filmstrip">' + strip + '</div>' +
      '<dl class="kv">' +
      '<dt>Status</dt><dd class="' + statusClass(s.status) + '">' + escapeHtml(s.status) + '</dd>' +
      '<dt>Feature</dt><dd>' + escapeHtml(s.feature) + '</dd>' +
      '<dt>Correlation ID</dt><dd><code>' + escapeHtml(s.correlationId) + '</code></dd>' +
      '<dt>Started</dt><dd>' + escapeHtml(s.startedAt) + '</dd>' +
      '<dt>Duration</dt><dd>' + escapeHtml(String(s.durationMs || 0)) + ' ms</dd>' +
      '<dt>Spec file</dt><dd><code>' + escapeHtml(s.specFile) + '</code></dd>' +
      '<dt>Trace</dt><dd>' + trace + '</dd>' +
      '</dl>' +
      '<div class="steps"><h3>Steps</h3><ol>' + (s.steps || []).map(function (st) {
        return '<li><strong>' + escapeHtml(st.name) + '</strong> — ' + (st.durationMs || 0) + ' ms <span class="' + statusClass(st.status) + '">' + escapeHtml(st.status) + '</span></li>';
      }).join('') + '</ol></div>'
    );
    document.getElementById('modal').classList.remove('hidden');
  }

  function closeModal() {
    document.getElementById('modal').classList.add('hidden');
  }

  function render() {
    document.getElementById('meta').textContent = state.generatedAt ? 'Generated ' + state.generatedAt : '';
    renderSidebar();
    renderGrid();
  }

  function init() {
    fetch('./manifest.json', { cache: 'no-cache' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        state.generatedAt = data.generatedAt || '';
        state.scenarios = data.scenarios || [];
        render();
      })
      .catch(function (err) {
        document.getElementById('grid').innerHTML = '<div class="empty">Failed to load manifest.json: ' + escapeHtml(err && err.message) + '</div>';
      });

    document.getElementById('search').addEventListener('input', function (e) {
      state.search = e.target.value || '';
      renderGrid();
    });

    document.getElementById('modal').addEventListener('click', function (e) {
      var t = e.target;
      if (t && t.getAttribute && t.getAttribute('data-close') === '1') closeModal();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeModal();
    });
  }

  document.addEventListener('DOMContentLoaded', init);
})();

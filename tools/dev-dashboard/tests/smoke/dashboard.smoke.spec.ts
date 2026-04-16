import { test, expect, withArtifacts, withRealTraceArtifacts } from './fixtures';

test.describe.configure({ mode: 'serial' });


test('dashboard_boots_and_shows_aspect_tabs', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: true, traces: true });
  await page.goto('/');
  await expect(page.getByTestId('rail-scenarios')).toBeVisible();
  await expect(page.getByTestId('rail-capabilities')).toBeVisible();
  await expect(page.getByTestId('rail-traces')).toBeVisible();
  await expect(page.getByTestId('rail-screens')).toBeVisible();
});

test('clicking_each_aspect_tab_renders_its_panel_header', async ({ page }) => {
  const logs: string[] = [];
  page.on('console', (m) => {
    if (m.type() === 'error' || m.type() === 'warning') {
      logs.push(`[${m.type()}] ${m.text()}`);
    }
  });
  page.on('pageerror', (e) => logs.push(`[pageerror] ${String(e)}`));
  await withArtifacts({ scenarios: true, capabilities: true, traces: true, e2eTraces: true });
  await page.goto('/', { timeout: 5000 });

  for (const id of ['scenarios', 'capabilities', 'traces', 'screens'] as const) {
    await page.getByTestId(`rail-${id}`).click({ timeout: 3000 });
    await expect(
      page.getByTestId(`aspect-${id}`),
      `id=${id} logs=${logs.join('||')}`,
    ).toBeVisible({ timeout: 3000 });
    await expect(
      page.getByTestId(`aspect-${id}`).getByTestId('refresh-modal-open'),
    ).toBeVisible();
  }
});

test('empty_state_appears_when_artifacts_are_missing', async ({ page }) => {
  await withArtifacts({ scenarios: false, capabilities: false, traces: false });
  await page.goto('/#/scenarios');
  await expect(page.getByTestId('empty-state')).toBeVisible();
  await expect(page.getByTestId('cmd-block')).toBeVisible();

  await page.getByTestId('rail-capabilities').click();
  await expect(page.getByTestId('empty-state')).toBeVisible();

  await page.getByTestId('rail-traces').click();
  // Traces primary artifact is a directory; when absent, empty state shows.
  await expect(page.getByTestId('empty-state')).toBeVisible();
});

test('stale_badge_appears_when_source_file_newer_than_artifact', async ({ page }) => {
  await withArtifacts(
    { scenarios: true, capabilities: true, traces: true },
    'scenarios',
  );
  await page.goto('/#/scenarios');
  await expect(page.getByTestId('stale-badge')).toBeVisible();
  await expect(page.getByTestId('rail-dot-scenarios')).toBeVisible();
});

test('fresh_state_when_artifact_is_newer_than_all_sources', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: true, traces: true });
  await page.goto('/#/scenarios');
  await expect(page.getByTestId('fresh-badge')).toBeVisible();
  await expect(page.getByTestId('stale-badge')).toHaveCount(0);
});

test('refresh_command_block_copies_only_the_command_to_clipboard', async ({
  page,
  context,
}) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await withArtifacts({ scenarios: true, capabilities: true, traces: true });
  await page.goto('/#/scenarios');
  await page.getByTestId('refresh-modal-open').click();
  const cmdText = await page.getByTestId('cmd-block-command').innerText();
  await page.getByTestId('cmd-block-copy').click();
  const pasted = await page.evaluate(() => navigator.clipboard.readText());
  expect(pasted).toBe(cmdText);
  expect(pasted).not.toContain('<repo-root>');
});

test('scenarios_panel_renders_card_grid_from_manifest', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');
  await expect(page.getByTestId('scenario-grid')).toBeVisible();
  await expect(page.getByTestId('scenario-card-org-create-1776000000000-w0')).toBeVisible();
  await expect(page.getByTestId('scenario-card-project-create-1776000000001-w1')).toBeVisible();
  await expect(page.getByTestId('scenario-card-member-invite-1776000000002-w2')).toBeVisible();
});

test('scenarios_card_click_opens_detail_view_with_video_and_steps', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');
  await page.getByTestId('scenario-card-org-create-1776000000000-w0').click();
  await expect(page.getByTestId('scenario-detail')).toBeVisible();
  await expect(page.getByTestId('scenario-video')).toBeVisible();
  await expect(page.getByTestId('scenario-steps')).toBeVisible();
});

test('capabilities_panel_renders_route_table_from_baseline_and_report', async ({
  page,
}) => {
  await withArtifacts({
    scenarios: false,
    capabilities: true,
    capabilitiesMode: 'full',
    traces: false,
  });
  await page.goto('/#/capabilities');
  const table = page.getByTestId('cap-table');
  await expect(table).toBeVisible();
  await expect(
    page.getByTestId('cap-row-GET-/api/unchanged'),
  ).toHaveAttribute('data-status', 'unchanged');
  await expect(
    page.getByTestId('cap-row-POST-/api/expanded'),
  ).toHaveAttribute('data-status', 'expanded');
  await expect(
    page.getByTestId('cap-row-PUT-/api/reduced'),
  ).toHaveAttribute('data-status', 'reduced');
  await expect(page.getByTestId('cap-row-GET-/api/new')).toHaveAttribute(
    'data-status',
    'new',
  );
  await expect(
    page.getByTestId('cap-row-DELETE-/api/removed'),
  ).toHaveAttribute('data-status', 'removed');
});

test('capabilities_diff_toggle_filters_to_changed_rows', async ({ page }) => {
  await withArtifacts({
    scenarios: false,
    capabilities: true,
    capabilitiesMode: 'full',
    traces: false,
  });
  await page.goto('/#/capabilities');
  await page.getByTestId('cap-diff').selectOption('diff');
  await expect(page.getByTestId('cap-row-GET-/api/unchanged')).toHaveCount(0);
  await expect(page.getByTestId('cap-row-POST-/api/expanded')).toBeVisible();
});

test('capabilities_falls_back_to_baseline_only_when_report_missing', async ({
  page,
}) => {
  await withArtifacts({
    scenarios: false,
    capabilities: true,
    capabilitiesMode: 'baseline-only',
    traces: false,
  });
  await page.goto('/#/capabilities');
  await expect(page.getByTestId('baseline-only-banner')).toBeVisible();
  await expect(page.getByTestId('cap-diff')).toBeDisabled();
  await expect(page.getByTestId('cap-row-GET-/api/unchanged')).toBeVisible();
});

test('traces_panel_lists_scenarios_with_artifacts', async ({ page }) => {
  await withArtifacts({ scenarios: false, capabilities: false, traces: true });
  await page.goto('/#/traces');
  await expect(page.getByTestId('trace-item-org-create-1776000000000-w0')).toBeVisible();
  await expect(page.getByTestId('trace-item-project-create-1776000000001-w1')).toBeVisible();
});

test('traces_selecting_scenario_renders_mermaid_and_flame_iframe', async ({
  page,
}) => {
  await withArtifacts({ scenarios: false, capabilities: false, traces: true });
  await page.goto('/#/traces');
  await page.getByTestId('trace-item-org-create-1776000000000-w0').click();
  // mermaid render may take a tick.
  await expect(page.getByTestId('mermaid-svg')).toBeVisible();
  const iframe = page.getByTestId('flame-iframe');
  await expect(iframe).toBeVisible();
  await expect(iframe).toHaveAttribute('src', /flame\.html$/);
});

test('traces_folded_stacks_collapsed_by_default', async ({ page }) => {
  await withArtifacts({ scenarios: false, capabilities: false, traces: true });
  await page.goto('/#/traces');
  await page.getByTestId('trace-item-org-create-1776000000000-w0').click();
  await expect(page.getByTestId('folded-content')).toHaveCount(0);
  await page.getByTestId('folded-expand').click();
  await expect(page.getByTestId('folded-content')).toBeVisible();
});

test('traces_search_covering_file_filters_scenarios', async ({ page }) => {
  await withArtifacts({ scenarios: false, capabilities: false, traces: true });
  await page.goto('/#/traces');
  const search = page.getByTestId('trace-search');
  // With coveredFiles present in fixture, search is enabled.
  await expect(search).toBeEnabled();
  await search.fill('projects_api.py');
  await expect(page.getByTestId('trace-item-project-create-1776000000001-w1')).toHaveAttribute(
    'aria-selected',
    'true',
  );
});


test('cross_link_scenario_to_trace_appears_only_when_trace_exists', async ({
  page,
}) => {
  // Case A: trace dir exists for org-create-1776000000000-w0 → button visible.
  await withArtifacts({ scenarios: true, capabilities: false, traces: true });
  await page.goto('/#/scenarios');
  await page.getByTestId('scenario-card-org-create-1776000000000-w0').click();
  await expect(page.getByTestId('view-trace-link')).toBeVisible();

  // Case B: no traces → no button. Navigate to the gallery explicitly then
  // reload so the aspect re-runs `load()` against the updated fixtures.
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');
  await page.reload();
  await page.getByTestId('scenario-card-org-create-1776000000000-w0').click();
  await expect(page.getByTestId('scenario-detail')).toBeVisible();
  await expect(page.getByTestId('view-trace-link')).toHaveCount(0);
});

test('top_bar_summarises_aggregate_freshness', async ({ page }) => {
  await withArtifacts(
    { scenarios: true, capabilities: true, traces: true },
    'capabilities',
  );
  await page.goto('/');
  await expect(page.getByTestId('freshness-summary')).toContainText('4 aspects');
  await expect(page.getByTestId('freshness-summary')).toContainText('1 stale');
});

test('unknown_aspect_id_in_url_hash_falls_back_to_first_aspect', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: true, traces: true });
  await page.goto('/#/nonsense');
  await expect(page.getByTestId('aspect-scenarios')).toBeVisible();
  await expect.poll(() => page.url()).toMatch(/#\/scenarios$/);
});

test('user_ask_5_traces_aspect_renders_real_artifacts', async ({ page }) => {
  // Guards against the regression where TracesAspect looked for
  // `folded.txt` but the real producer writes `folded-compact.txt`.
  const picked = await withRealTraceArtifacts();
  expect(picked.length).toBeGreaterThan(0);
  await page.goto('/#/traces');

  // Scenario list is non-empty with real artifact names.
  const first = picked[0]!;
  const item = page.getByTestId(`trace-item-${first}`);
  await expect(item).toBeVisible();
  await item.click();

  // Mermaid SVG renders (real artifacts include mermaid.md). Some real
  // diagrams may hit mermaid parser limits — accept the visible fallback
  // block as an alternative pass condition.
  await expect(
    page
      .getByTestId('mermaid-svg')
      .or(page.getByTestId('mermaid-fallback')),
  ).toBeVisible();

  // Flame iframe is present.
  await expect(page.getByTestId('flame-iframe')).toHaveAttribute(
    'src',
    /flame\.html$/,
  );

  // Folded stacks: expand → content appears (loads folded-compact.txt).
  await page.getByTestId('folded-expand').click();
  await expect(page.getByTestId('folded-content')).toBeVisible();
});

test('user_ask_2_dark_is_default_and_toggle_persists_across_reload', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: true, traces: true });

  // Fresh session: default is dark.
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');

  // Toggle → light, persisted to localStorage.
  await page.getByTestId('theme-toggle').click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  const stored = await page.evaluate(() =>
    localStorage.getItem('dev-dashboard.theme'),
  );
  expect(stored).toBe('light');

  // Reload: still light.
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');

  // Toggle back → dark, persists.
  await page.getByTestId('theme-toggle').click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
});

test('user_ask_4_rail_collapses_to_icons_and_persists', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: true, traces: true });

  // Expanded by default — full aspect labels visible.
  await page.goto('/');
  const rail = page.locator('nav.rail');
  await expect(rail).toHaveAttribute('data-collapsed', '0');
  await expect(page.getByTestId('rail-scenarios')).toContainText('Scenarios');

  // Click hamburger → collapses; stored to localStorage.
  await page.getByTestId('rail-hamburger').click();
  await expect(rail).toHaveAttribute('data-collapsed', '1');
  const stored = await page.evaluate(() =>
    localStorage.getItem('dev-dashboard.railCollapsed'),
  );
  expect(stored).toBe('1');

  // Reload → still collapsed.
  await page.reload();
  await expect(page.locator('nav.rail')).toHaveAttribute('data-collapsed', '1');

  // Expand again and confirm persistence.
  await page.getByTestId('rail-hamburger').click();
  await expect(page.locator('nav.rail')).toHaveAttribute('data-collapsed', '0');
  await page.reload();
  await expect(page.locator('nav.rail')).toHaveAttribute('data-collapsed', '0');
});

test('user_ask_1_rail_shows_feature_subgroups_and_filters_grid', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');

  // Sub-items derived from manifest `feature` field: fixture has "org" and
  // "project".
  const orgGroup = page.getByTestId('rail-group-org');
  const projectGroup = page.getByTestId('rail-group-project');
  await expect(orgGroup).toBeVisible();
  await expect(projectGroup).toBeVisible();

  // Grid starts with all three scenarios visible.
  await expect(
    page.getByTestId('scenario-card-org-create-1776000000000-w0'),
  ).toBeVisible();
  await expect(
    page.getByTestId('scenario-card-project-create-1776000000001-w1'),
  ).toBeVisible();
  await expect(
    page.getByTestId('scenario-card-member-invite-1776000000002-w2'),
  ).toBeVisible();

  // Click "project" sub-item → only project-create shows.
  await projectGroup.click();
  await expect(page).toHaveURL(/#\/scenarios\?group=project$/);
  await expect(
    page.getByTestId('scenario-card-project-create-1776000000001-w1'),
  ).toBeVisible();
  await expect(
    page.getByTestId('scenario-card-org-create-1776000000000-w0'),
  ).toHaveCount(0);
  await expect(projectGroup).toHaveAttribute('aria-selected', 'true');

  // Click "org" sub-item → org scenarios show, project hidden.
  await orgGroup.click();
  await expect(
    page.getByTestId('scenario-card-org-create-1776000000000-w0'),
  ).toBeVisible();
  await expect(
    page.getByTestId('scenario-card-member-invite-1776000000002-w2'),
  ).toBeVisible();
  await expect(
    page.getByTestId('scenario-card-project-create-1776000000001-w1'),
  ).toHaveCount(0);
});

test('old_feature_27_hash_routes_deep_link_to_scenario_detail', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  // Deep link directly to a scenario's detail via hash path segment.
  await page.goto('/#/scenarios/org-create-1776000000000-w0');
  await expect(page.getByTestId('scenario-detail')).toBeVisible();
  await expect(page.getByTestId('scenario-video')).toBeVisible();
  await expect(page.getByTestId('breadcrumb')).toBeVisible();
});

test('old_feature_07_breadcrumb_links_from_detail_back_to_gallery', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');
  await page.getByTestId('scenario-card-org-create-1776000000000-w0').click();
  await expect(page).toHaveURL(/#\/scenarios\/org-create-1776000000000-w0$/);
  await expect(page.getByTestId('scenario-detail')).toBeVisible();

  await page.getByTestId('breadcrumb-gallery').click();
  await expect(page).toHaveURL(/#\/scenarios$/);
  await expect(page.getByTestId('scenario-grid')).toBeVisible();
});

test('old_feature_29_top_bar_shows_generated_at_timestamp_from_manifest', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: true, traces: true });
  await page.goto('/');
  // Fixture manifest has generatedAt: "2026-04-14T04:02:41.793Z".
  const stamp = page.getByTestId('generated-at');
  await expect(stamp).toBeVisible();
  await expect(stamp).toContainText('2026-04-14');
});

test('old_feature_08_09_11_detail_shows_flipbook_motion_and_screenshot_strip', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios/org-create-1776000000000-w0');

  await expect(page.getByTestId('detail-flipbook')).toBeVisible();
  await expect(page.getByTestId('detail-motion')).toBeVisible();
  await expect(page.getByTestId('screenshot-strip')).toBeVisible();
  // Fixture has three steps — all three thumbs show.
  await expect(page.getByTestId('strip-thumb-0')).toBeVisible();
  await expect(page.getByTestId('view-all-screenshots')).toHaveAttribute(
    'href',
    '#/scenarios/org-create-1776000000000-w0/screenshots',
  );

  // Click flipbook → GIF lightbox opens.
  await page.getByTestId('detail-flipbook').click();
  await expect(page.getByTestId('lightbox-gif')).toBeVisible();
});

test('old_feature_10_video_speed_selector_changes_playbackRate', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios/org-create-1776000000000-w0');

  const speed = page.getByTestId('video-speed');
  await expect(speed).toBeVisible();
  await speed.selectOption('0.5');
  const rateAtHalf = await page.evaluate(() => {
    const v = document.querySelector(
      '[data-testid="scenario-video"]',
    ) as HTMLVideoElement | null;
    return v?.playbackRate ?? null;
  });
  expect(rateAtHalf).toBe(0.5);

  await speed.selectOption('2');
  const rateAt2x = await page.evaluate(() => {
    const v = document.querySelector(
      '[data-testid="scenario-video"]',
    ) as HTMLVideoElement | null;
    return v?.playbackRate ?? null;
  });
  expect(rateAt2x).toBe(2);
});

test('old_feature_25_download_webm_link_present', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios/org-create-1776000000000-w0');

  const link = page.getByTestId('download-webm');
  await expect(link).toBeVisible();
  await expect(link).toHaveAttribute('href', /\.webm$/);
  // The link has a `download` attribute.
  await expect(link).toHaveAttribute('download', /.*/);
});

test('old_feature_12_13_14_detail_shows_metadata_kv_with_correlation_id_and_trace_link', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: true });
  await page.goto('/#/scenarios/org-create-1776000000000-w0');

  await expect(page.getByTestId('metadata-kv')).toBeVisible();
  await expect(page.getByTestId('metadata-status')).toContainText('passing');
  await expect(page.getByTestId('metadata-feature')).toContainText('org');
  await expect(page.getByTestId('metadata-correlation-id')).toContainText(
    'org-create-1776000000000-w0',
  );
  await expect(page.getByTestId('metadata-duration')).toContainText('427');
  await expect(page.getByTestId('metadata-spec')).toContainText(
    'org-create.scenario.spec.ts',
  );
  await expect(page.getByTestId('metadata-trace-link')).toBeVisible();

  // When no traces present, the trace row shows "—".
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');
  await page.reload();
  await page.goto('/#/scenarios/org-create-1776000000000-w0');
  await expect(page.getByTestId('metadata-trace-link')).toHaveText('—');
});

test('old_feature_15_detail_shows_step_list_with_timings', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios/org-create-1776000000000-w0');

  await expect(page.getByTestId('scenario-steps')).toBeVisible();
  await expect(page.getByTestId('step-1')).toContainText('Open signup');
  await expect(page.getByTestId('step-ms-1')).toContainText('258');
  await expect(page.getByTestId('step-status-1')).toHaveClass(/pill--passing/);
});

test('old_feature_22_screenshot_lightbox_prev_next_keyboard_nav', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios/org-create-1776000000000-w0');

  await page.getByTestId('strip-thumb-0').click();
  await expect(page.getByTestId('lightbox')).toBeVisible();
  await expect(page.getByTestId('lightbox-counter')).toContainText('1 of 3');

  await page.getByTestId('lightbox-next').click();
  await expect(page.getByTestId('lightbox-counter')).toContainText('2 of 3');

  await page.keyboard.press('ArrowRight');
  await expect(page.getByTestId('lightbox-counter')).toContainText('3 of 3');

  await page.keyboard.press('ArrowLeft');
  await expect(page.getByTestId('lightbox-counter')).toContainText('2 of 3');

  await page.keyboard.press('Escape');
  await expect(page.getByTestId('lightbox')).toHaveCount(0);
});

test('old_feature_23_gif_lightbox_closes_on_escape', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios/org-create-1776000000000-w0');

  await page.getByTestId('detail-motion').click();
  await expect(page.getByTestId('lightbox-gif')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('lightbox')).toHaveCount(0);
});

test('old_feature_24_video_lightbox_speed_and_download', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios/org-create-1776000000000-w0');

  await page.getByTestId('video-lightbox-open').click();
  await expect(page.getByTestId('lightbox-video')).toBeVisible();

  const speed = page.getByTestId('lightbox-video-speed');
  await speed.selectOption('0.25');
  const rate = await page.evaluate(() => {
    const v = document.querySelector(
      '[data-testid="lightbox-video"]',
    ) as HTMLVideoElement | null;
    return v?.playbackRate ?? null;
  });
  expect(rate).toBe(0.25);

  const dl = page.getByTestId('lightbox-download-webm');
  await expect(dl).toHaveAttribute('href', /\.webm$/);
});

test('old_feature_16_17_screenshots_page_shows_full_grid_and_crosslinks', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios/org-create-1776000000000-w0/screenshots');

  await expect(page.getByTestId('screenshots-page')).toBeVisible();
  await expect(page.getByTestId('screenshots-grid')).toBeVisible();
  await expect(page.getByTestId('screenshots-cell-0')).toBeVisible();
  await expect(page.getByTestId('screenshots-cell-2')).toBeVisible();

  // Cross-links to detail and flow.
  await expect(page.getByTestId('page-link-detail')).toHaveAttribute(
    'href',
    '#/scenarios/org-create-1776000000000-w0',
  );
  await expect(page.getByTestId('page-link-flow')).toHaveAttribute(
    'href',
    '#/scenarios/org-create-1776000000000-w0/flow',
  );

  // Cell opens lightbox.
  await page.getByTestId('screenshots-cell-1').click();
  await expect(page.getByTestId('lightbox-counter')).toContainText('2 of 3');
});

test('old_feature_18_21_flow_page_shows_compact_strip_with_labels', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios/org-create-1776000000000-w0/flow');

  await expect(page.getByTestId('flow-page')).toBeVisible();
  await expect(page.getByTestId('flow-strip')).toBeVisible();
  await expect(page.getByTestId('flow-cell-1')).toBeVisible();
  await expect(page.getByTestId('flow-cell-3')).toBeVisible();

  // Breadcrumb leaf shows "flow".
  await expect(page.getByTestId('breadcrumb-leaf')).toHaveText('flow');
});

test('old_feature_03_tile_size_slider_changes_grid_size_and_persists', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');

  const grid = page.getByTestId('scenario-grid');
  await expect(grid).toBeVisible();

  // Default is 320px per the gallery lib default.
  await expect(page.getByTestId('tile-size-readout')).toContainText('320');
  const initialTile = await grid.evaluate(
    (el) => getComputedStyle(el).getPropertyValue('--tile-size').trim(),
  );
  expect(initialTile).toBe('320px');

  // Move the slider to 640. Use the native value setter so React's
  // synthetic event system picks it up.
  const slider = page.getByTestId('tile-size-slider');
  await slider.evaluate((el) => {
    const input = el as HTMLInputElement;
    const proto = Object.getPrototypeOf(input) as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
    setter?.call(input, '640');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await expect(page.getByTestId('tile-size-readout')).toContainText('640');
  const afterMove = await grid.evaluate(
    (el) => getComputedStyle(el).getPropertyValue('--tile-size').trim(),
  );
  expect(afterMove).toBe('640px');

  // Persisted to localStorage.
  const stored = await page.evaluate(() =>
    localStorage.getItem('dev-dashboard.tileSize'),
  );
  expect(stored).toBe('640');

  // Reload: still 640px.
  await page.reload();
  await expect(page.getByTestId('tile-size-readout')).toContainText('640');
  const afterReload = await page
    .getByTestId('scenario-grid')
    .evaluate((el) =>
      getComputedStyle(el).getPropertyValue('--tile-size').trim(),
    );
  expect(afterReload).toBe('640px');
});

test('old_feature_02_view_toggle_switches_between_gif_cards_and_strip_cards', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');

  // Default: GIF cards — grid visible, strip rows absent.
  await expect(page.getByTestId('scenario-grid')).toBeVisible();
  await expect(page.getByTestId('view-toggle-gif')).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await expect(
    page.getByTestId('scenario-card-org-create-1776000000000-w0'),
  ).toBeVisible();
  await expect(
    page.getByTestId('scenario-strip-org-create-1776000000000-w0'),
  ).toHaveCount(0);

  // Click strip toggle.
  await page.getByTestId('view-toggle-strip').click();
  await expect(page.getByTestId('view-toggle-strip')).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await expect(
    page.getByTestId('scenario-strip-org-create-1776000000000-w0'),
  ).toBeVisible();
  await expect(page.getByTestId('scenario-grid')).toHaveCount(0);

  // Persisted.
  const stored = await page.evaluate(() =>
    localStorage.getItem('dev-dashboard.galleryView'),
  );
  expect(stored).toBe('strip');

  // Reload: still strip mode.
  await page.reload();
  await expect(
    page.getByTestId('scenario-strip-org-create-1776000000000-w0'),
  ).toBeVisible();
  await expect(page.getByTestId('scenario-grid')).toHaveCount(0);
});

test('old_feature_05_strip_frame_click_opens_screenshot_lightbox_at_step_index', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');

  await page.getByTestId('view-toggle-strip').click();
  await expect(
    page.getByTestId('scenario-strip-org-create-1776000000000-w0'),
  ).toBeVisible();

  // Click frame index 1 (the second step) — lightbox opens at "2 of 3".
  await page
    .getByTestId('strip-frame-org-create-1776000000000-w0-1')
    .click();
  await expect(page.getByTestId('lightbox')).toBeVisible();
  await expect(page.getByTestId('lightbox-counter')).toContainText('2 of 3');
});

test('repo_root_is_displayed_in_top_bar', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: true, traces: true });
  await page.goto('/');
  const text = await page.getByTestId('repo-root').innerText();
  expect(text).toContain('.tmp-repo');
});

test('iter3_global_refresh_collapses_to_modal', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: true, traces: true });
  for (const id of ['scenarios', 'capabilities', 'traces'] as const) {
    await page.goto(`/#/${id}`);
    const trigger = page
      .getByTestId(`aspect-${id}`)
      .getByTestId('refresh-modal-open');
    await expect(trigger).toBeVisible();
    await trigger.click();
    const modal = page.getByTestId('refresh-modal');
    await expect(modal).toBeVisible();
    await expect(modal.getByTestId('cmd-block-command')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('refresh-modal')).toHaveCount(0);
  }
});

test('iter3_detail_has_no_refresh_trigger', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios/org-create-1776000000000-w0');
  await expect(page.getByTestId('scenario-detail')).toBeVisible();
  await expect(page.getByTestId('refresh-modal-open')).toHaveCount(0);
  // Same for screenshots and flow sub-routes.
  await page.goto('/#/scenarios/org-create-1776000000000-w0/screenshots');
  await expect(page.getByTestId('screenshots-page')).toBeVisible();
  await expect(page.getByTestId('refresh-modal-open')).toHaveCount(0);
  await page.goto('/#/scenarios/org-create-1776000000000-w0/flow');
  await expect(page.getByTestId('flow-page')).toBeVisible();
  await expect(page.getByTestId('refresh-modal-open')).toHaveCount(0);
  // Back on gallery → trigger present.
  await page.goto('/#/scenarios');
  await expect(page.getByTestId('refresh-modal-open')).toBeVisible();
});

test('iter3_detail_metadata_appears_before_media', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios/org-create-1776000000000-w0');
  await expect(page.getByTestId('scenario-detail')).toBeVisible();
  const order = await page.evaluate(() => {
    const meta = document.querySelector('[data-testid="scenario-metadata"]');
    const media = document.querySelector('[data-testid="scenario-media"]');
    if (!meta || !media) return 'missing';
    const pos = meta.compareDocumentPosition(media);
    // DOCUMENT_POSITION_FOLLOWING === 4 means media follows metadata.
    return (pos & Node.DOCUMENT_POSITION_FOLLOWING) !== 0
      ? 'metadata-first'
      : 'media-first';
  });
  expect(order).toBe('metadata-first');
});

test('iter3_detail_flipbook_and_motion_have_explanatory_tooltips', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios/org-create-1776000000000-w0');
  await expect(page.getByTestId('detail-flipbook')).toHaveAttribute(
    'title',
    /Flipbook.*one frame per step.*1\.5s/i,
  );
  await expect(page.getByTestId('detail-motion')).toHaveAttribute(
    'title',
    /Motion.*video.*slowed 2x/i,
  );
});

test('iter3_detail_video_speed_is_prominent', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios/org-create-1776000000000-w0');
  await expect(
    page.locator('.detail__video-speed-heading'),
  ).toContainText('Playback speed:');
  await expect(page.getByTestId('video-speed-current')).toBeVisible();
  await expect(page.getByTestId('video-speed-current')).toContainText('x');
});

test('iter3_detail_default_video_speed_is_0_25', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios/org-create-1776000000000-w0');
  await expect(page.getByTestId('video-speed')).toHaveValue('0.25');
  await expect(page.getByTestId('video-speed-current')).toContainText('0.25');
  // Wait for metadata so playbackRate has been set by effect.
  await page.waitForFunction(() => {
    const v = document.querySelector(
      '[data-testid="scenario-video"]',
    ) as HTMLVideoElement | null;
    return v !== null && v.playbackRate === 0.25;
  });

  // Change to 0.5 — persists.
  await page.getByTestId('video-speed').selectOption('0.5');
  const stored = await page.evaluate(() =>
    localStorage.getItem('dev-dashboard.videoSpeed'),
  );
  expect(stored).toBe('0.5');

  // Reload — still 0.5.
  await page.reload();
  await expect(page.getByTestId('video-speed')).toHaveValue('0.5');
  await expect(page.getByTestId('video-speed-current')).toContainText('0.5');

  // Lightbox video also inherits the stored speed.
  await page.getByTestId('video-lightbox-open').click();
  await expect(page.getByTestId('lightbox-video-speed')).toHaveValue('0.5');
});

test('iter3_detail_screenshots_are_a_strip', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios/org-create-1776000000000-w0');
  const strip = page.getByTestId('screenshot-strip');
  await expect(strip).toBeVisible();
  // Uses the same horizontal-scroll frame layout as gallery strip mode.
  await expect(strip.locator('.scen-strip__frames')).toBeVisible();
  await expect(strip.locator('.scen-strip__frame')).toHaveCount(3);
  // Overflow-x set to auto by the shared .scen-strip__frames rule.
  const overflowX = await strip
    .locator('.scen-strip__frames')
    .evaluate((el) => getComputedStyle(el).overflowX);
  expect(overflowX).toBe('auto');
});

test('iter3_gallery_search_input_uses_dark_tokens', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');
  const input = page.getByTestId('scenario-search');
  const bg = await input.evaluate(
    (el) => getComputedStyle(el).backgroundColor,
  );
  // Default browser input is rgb(255,255,255). Our themed input uses
  // --bg-elevated (#1b1f26 dark; #f4f4f5 light). Either way it must NOT be
  // pure white.
  expect(bg).not.toBe('rgb(255, 255, 255)');
  const color = await input.evaluate((el) => getComputedStyle(el).color);
  expect(color).not.toBe('rgb(0, 0, 0)');
});

test('iter3_gallery_gif_card_shows_title', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');
  await expect(
    page.getByTestId('scenario-card-title-org-create-1776000000000-w0'),
  ).toBeVisible();
  const overflow = await page
    .getByTestId('scenario-card-title-org-create-1776000000000-w0')
    .evaluate((el) => getComputedStyle(el).textOverflow);
  expect(overflow).toBe('ellipsis');
});

test('iter3_gallery_strip_shows_scroll_chevron_when_scrollable', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');
  await page.getByTestId('view-toggle-strip').click();
  // Force the strip to be narrow enough to overflow: shrink viewport.
  await page.setViewportSize({ width: 420, height: 900 });
  const nextChevron = page.getByTestId(
    'strip-chevron-next-org-create-1776000000000-w0',
  );
  // In a narrow viewport, 3 frames at 180px each overflow → next chevron visible.
  await expect(nextChevron).toBeVisible();
});

test('iter3_gallery_strip_rows_alternate_bg', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');
  await page.getByTestId('view-toggle-strip').click();
  const bgs = await page.evaluate(() => {
    const rows = Array.from(
      document.querySelectorAll('.scen-strips > .scen-strip'),
    ) as HTMLElement[];
    return rows.slice(0, 2).map((r) => getComputedStyle(r).backgroundColor);
  });
  expect(bgs.length).toBe(2);
  expect(bgs[0]).not.toBe(bgs[1]);
});

test('iter3_gallery_strip_img_attrs_set', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');
  await page.getByTestId('view-toggle-strip').click();
  const attrs = await page.evaluate(() => {
    const imgs = Array.from(
      document.querySelectorAll('.scen-strip__frame img'),
    ) as HTMLImageElement[];
    return imgs.map((img) => ({
      width: img.getAttribute('width'),
      height: img.getAttribute('height'),
      loading: img.getAttribute('loading'),
      decoding: img.getAttribute('decoding'),
    }));
  });
  expect(attrs.length).toBeGreaterThan(0);
  for (const a of attrs) {
    expect(a.width).toBeTruthy();
    expect(a.height).toBeTruthy();
    expect(a.decoding).toBe('async');
    expect(['eager', 'lazy']).toContain(a.loading);
  }
});

test('iter3_capabilities_search_filters_by_path_and_verb', async ({ page }) => {
  await withArtifacts({
    scenarios: false,
    capabilities: true,
    capabilitiesMode: 'full',
    traces: false,
  });
  await page.goto('/#/capabilities');
  const search = page.getByTestId('cap-search');
  await expect(search).toBeVisible();

  // Filter by path substring.
  await search.fill('expanded');
  await expect(page.getByTestId('cap-row-POST-/api/expanded')).toBeVisible();
  await expect(page.getByTestId('cap-row-GET-/api/unchanged')).toHaveCount(0);

  // Filter by HTTP verb.
  await search.fill('DELETE');
  await expect(page.getByTestId('cap-row-DELETE-/api/removed')).toBeVisible();
  await expect(page.getByTestId('cap-row-POST-/api/expanded')).toHaveCount(0);

  // Empty query restores all rows.
  await search.fill('');
  await expect(page.getByTestId('cap-row-GET-/api/unchanged')).toBeVisible();
});

test('iter3_capabilities_columns_in_new_order', async ({ page }) => {
  await withArtifacts({
    scenarios: false,
    capabilities: true,
    capabilitiesMode: 'full',
    traces: false,
  });
  await page.goto('/#/capabilities');
  const headers = await page
    .getByTestId('cap-table')
    .locator('thead th')
    .allInnerTexts();
  expect(headers).toEqual([
    'Method',
    'Path',
    'Capabilities',
    'Status',
    'Handler',
  ]);
});

test('iter3_traces_left_panel_uses_dark_tokens', async ({ page }) => {
  await withArtifacts({ scenarios: false, capabilities: false, traces: true });
  await page.goto('/#/traces');
  const first = page.getByTestId('trace-item-org-create-1776000000000-w0');
  await expect(first).toBeVisible();
  await first.click();
  const styles = await first.evaluate((el) => {
    const cs = getComputedStyle(el);
    return { bg: cs.backgroundColor, color: cs.color };
  });
  // Selected item must use themed tokens — not the browser default white/black.
  expect(styles.bg).not.toBe('rgba(0, 0, 0, 0)');
  expect(styles.color).not.toBe('rgb(0, 0, 0)');
});

test('iter3_traces_mermaid_has_dedicated_background', async ({ page }) => {
  await withArtifacts({ scenarios: false, capabilities: false, traces: true });
  await page.goto('/#/traces');
  await page.getByTestId('trace-item-org-create-1776000000000-w0').click();
  const wrap = page.getByTestId('mermaid-wrap');
  await expect(wrap).toBeVisible();
  const bg = await wrap.evaluate(
    (el) => getComputedStyle(el).backgroundColor,
  );
  // The wrap uses --graph-bg (#f8fafc) regardless of theme.
  expect(bg).toBe('rgb(248, 250, 252)');
});

test('iter3_traces_flame_iframe_fills_width', async ({ page }) => {
  await withArtifacts({ scenarios: false, capabilities: false, traces: true });
  await page.goto('/#/traces');
  await page.getByTestId('trace-item-org-create-1776000000000-w0').click();
  const iframe = page.getByTestId('flame-iframe');
  await expect(iframe).toBeVisible();
  const ratio = await iframe.evaluate((el) => {
    const parent = el.parentElement;
    if (!parent) return 0;
    const iw = el.getBoundingClientRect().width;
    const pw = parent.getBoundingClientRect().width;
    return pw > 0 ? iw / pw : 0;
  });
  expect(ratio).toBeGreaterThanOrEqual(0.9);
  const minHeight = await iframe.evaluate(
    (el) => parseFloat(getComputedStyle(el).minHeight) || 0,
  );
  expect(minHeight).toBeGreaterThanOrEqual(500);
});

test('iter3_traces_flame_wrapper_has_graph_bg', async ({ page }) => {
  await withArtifacts({ scenarios: false, capabilities: false, traces: true });
  await page.goto('/#/traces');
  await page.getByTestId('trace-item-org-create-1776000000000-w0').click();
  const wrap = page.getByTestId('flame-wrap');
  await expect(wrap).toBeVisible();
  const bg = await wrap.evaluate(
    (el) => getComputedStyle(el).backgroundColor,
  );
  expect(bg).toBe('rgb(248, 250, 252)');
});

test('iter4_traces_flame_note_points_to_cmd_f', async ({ page }) => {
  await withArtifacts({ scenarios: false, capabilities: false, traces: true });
  await page.goto('/#/traces');
  await page.getByTestId('trace-item-org-create-1776000000000-w0').click();
  const note = page.getByTestId('flame-search-note');
  await expect(note).toBeVisible();
  await expect(note).toContainText(/Cmd-F|Ctrl-F/);
  // The old "search isn't wired up" phrasing is gone — the broken search is
  // now hidden instead, so the note is pure guidance.
  await expect(note).not.toContainText(/wired up|isn't/i);
});

test('iter4_traces_flame_search_input_hidden', async ({ page }) => {
  await withArtifacts({ scenarios: false, capabilities: false, traces: true });
  await page.goto('/#/traces');
  await page.getByTestId('trace-item-org-create-1776000000000-w0').click();
  const iframe = page.getByTestId('flame-iframe');
  await expect(iframe).toBeVisible();
  // Wait for our onLoad injector to run and drop the override <style> in.
  await expect
    .poll(async () =>
      iframe.evaluate((el) => {
        const doc = (el as HTMLIFrameElement).contentDocument;
        return Boolean(doc?.getElementById('dd-flame-overrides'));
      }),
    )
    .toBe(true);
  const searchDisplay = await iframe.evaluate((el) => {
    const doc = (el as HTMLIFrameElement).contentDocument;
    const node = doc?.getElementById('search');
    if (!node) return 'absent';
    return getComputedStyle(node).display;
  });
  expect(searchDisplay).toBe('none');
});

test('iter4_traces_flame_svg_stretches_to_full_width', async ({ page }) => {
  await withArtifacts({ scenarios: false, capabilities: false, traces: true });
  await page.goto('/#/traces');
  await page.getByTestId('trace-item-org-create-1776000000000-w0').click();
  const iframe = page.getByTestId('flame-iframe');
  await expect(iframe).toBeVisible();
  await expect
    .poll(async () =>
      iframe.evaluate((el) => {
        const doc = (el as HTMLIFrameElement).contentDocument;
        return Boolean(doc?.getElementById('dd-flame-overrides'));
      }),
    )
    .toBe(true);
  const ratio = await iframe.evaluate((el) => {
    const frame = el as HTMLIFrameElement;
    const doc = frame.contentDocument;
    const svg = doc?.querySelector('svg');
    if (!svg) return 0;
    const svgW = svg.getBoundingClientRect().width;
    const iW = frame.getBoundingClientRect().width;
    return iW > 0 ? svgW / iW : 0;
  });
  expect(ratio).toBeGreaterThanOrEqual(0.9);
});

test('iter4_traces_left_panel_items_wrap_long_names', async ({ page }) => {
  await withArtifacts({ scenarios: false, capabilities: false, traces: true });
  await page.goto('/#/traces');
  const item = page.getByTestId('trace-item-org-create-1776000000000-w0');
  await expect(item).toBeVisible();
  const styles = await item.evaluate((el) => {
    const cs = getComputedStyle(el);
    return {
      overflowWrap: cs.overflowWrap,
      wordBreak: cs.wordBreak,
      whiteSpace: cs.whiteSpace,
      title: el.getAttribute('title'),
    };
  });
  // Long unbroken slugs must wrap inside the left panel so they don't push
  // into the sequence diagram column.
  expect(['anywhere', 'break-word']).toContain(styles.overflowWrap);
  expect(styles.whiteSpace).not.toBe('nowrap');
  expect(styles.title).toBeTruthy();
  // The list container must clip any residual horizontal overflow.
  const listOverflowX = await page
    .getByTestId('trace-list')
    .evaluate((el) => getComputedStyle(el).overflowX);
  expect(listOverflowX).toBe('hidden');
  // And the item must not extend past the list's right edge.
  const overflowPx = await page.evaluate(() => {
    const list = document.querySelector('[data-testid="trace-list"]');
    const btn = list?.querySelector('button');
    if (!list || !btn) return 99;
    const lr = list.getBoundingClientRect();
    const br = btn.getBoundingClientRect();
    return br.right - lr.right;
  });
  expect(overflowPx).toBeLessThanOrEqual(2);
});

test('iter4_gallery_cards_use_content_visibility_and_intrinsic_size', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');
  const card = page
    .getByTestId('scenario-card-org-create-1776000000000-w0')
    .first();
  await expect(card).toBeVisible();
  const cardStyle = await card.evaluate((el) => {
    const cs = getComputedStyle(el);
    return {
      cv: cs.contentVisibility,
      intrinsic: cs.containIntrinsicSize,
    };
  });
  expect(cardStyle.cv).toBe('auto');
  // Intrinsic size must be set (non-empty, non-'none') so off-screen cards
  // reserve space without forcing layout/paint.
  expect(cardStyle.intrinsic).not.toBe('');
  expect(cardStyle.intrinsic).not.toBe('none');

  // Switch to strip view and assert the same on strip rows.
  await page.getByTestId('view-toggle-strip').click();
  const strip = page
    .getByTestId('scenario-strip-org-create-1776000000000-w0')
    .first();
  await expect(strip).toBeVisible();
  const stripCv = await strip.evaluate(
    (el) => getComputedStyle(el).contentVisibility,
  );
  expect(stripCv).toBe('auto');
});

test('iter4_gallery_strip_chevron_appears_after_images_load', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.setViewportSize({ width: 420, height: 900 });
  await page.goto('/#/scenarios');
  await page.getByTestId('view-toggle-strip').click();
  // At least one strip frame image must be in the DOM.
  const firstFrameImg = page
    .locator('.scen-strip__frame img')
    .first();
  await expect(firstFrameImg).toBeVisible();
  // Wait until at least the first complete-able image has resolved, so the
  // chevron-visibility calc has a real scrollWidth to compare against.
  await expect
    .poll(async () =>
      firstFrameImg.evaluate(
        (img) => (img as HTMLImageElement).complete,
      ),
    )
    .toBe(true);
  const nextChevron = page.getByTestId(
    'strip-chevron-next-org-create-1776000000000-w0',
  );
  await expect(nextChevron).toBeVisible();
});

test('iter4_gallery_card_media_uses_contain_not_cover', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');
  const img = page
    .locator('[data-testid="scenario-card-org-create-1776000000000-w0"] img.scen-card__media')
    .first();
  await expect(img).toBeVisible();
  const objectFit = await img.evaluate(
    (el) => getComputedStyle(el).objectFit,
  );
  expect(objectFit).not.toBe('cover');
  expect(objectFit).toBe('contain');
});

test('iter4_gallery_gif_card_not_cropped_at_large_tile_size', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');

  // Bump the tile-size slider to 800px so each card is large.
  const slider = page.getByTestId('tile-size-slider');
  await slider.evaluate((el) => {
    const input = el as HTMLInputElement;
    const proto = Object.getPrototypeOf(input) as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
    setter?.call(input, '800');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await expect(page.getByTestId('tile-size-readout')).toContainText('800');

  const img = page
    .locator('[data-testid="scenario-card-org-create-1776000000000-w0"] img.scen-card__media')
    .first();
  await expect(img).toBeVisible();
  await img.scrollIntoViewIfNeeded();

  // Fixture GIFs are zero-byte stubs that decode to naturalWidth=0. Swap in a
  // real inline image with a known 2:1 natural aspect ratio (200x100) so we
  // can assert the rendered aspect ratio preserves it (no crop).
  const inlineImg =
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAMgAAABkCAAAAADm7SDXAAAAiElEQVR4nO3PAQkAMAzAsPk3/ZsYvJxEQTvnE/M6YIuRGiM1RmqM1BipMVJjpMZIjZEaIzVGaozUGKkxUmOkxkiNkRojNUZqjNQYqTFSY6TGSI2RGiM1RmqM1BipMVJjpMZIjZEaIzVGaozUGKkxUmOkxkiNkRojNUZqjNQYqTFSY6TGSI2RmguWSNZkqazGtQAAAABJRU5ErkJggg==';
  await img.evaluate((el, src) => {
    const i = el as HTMLImageElement;
    i.removeAttribute('loading');
    i.removeAttribute('width');
    i.removeAttribute('height');
    i.src = src;
  }, inlineImg);

  // Wait for the image to actually load so naturalWidth/Height are non-zero.
  await expect
    .poll(
      async () =>
        img.evaluate((el) => {
          const i = el as HTMLImageElement;
          return i.complete && i.naturalWidth > 0 && i.naturalHeight > 0;
        }),
      { timeout: 15000 },
    )
    .toBe(true);

  const metrics = await img.evaluate((el) => {
    const i = el as HTMLImageElement;
    const r = i.getBoundingClientRect();
    return {
      renderedW: r.width,
      renderedH: r.height,
      naturalW: i.naturalWidth,
      naturalH: i.naturalHeight,
    };
  });

  expect(metrics.renderedH).toBeGreaterThan(0);
  expect(metrics.naturalH).toBeGreaterThan(0);
  // The inline GIF is 200x100 (2:1). At tile-size 800 the rendered width should
  // be close to 800 and height close to 400 — proving the card grows with the
  // image and nothing is cropped to a forced 16:9 box.
  expect(metrics.naturalW).toBe(200);
  expect(metrics.naturalH).toBe(100);

  const naturalRatio = metrics.naturalH / metrics.naturalW;
  const renderedRatio = metrics.renderedH / metrics.renderedW;
  // Rendered aspect ratio should match natural within 5% — proves no cropping.
  const diff = Math.abs(renderedRatio - naturalRatio) / naturalRatio;
  expect(diff).toBeLessThan(0.05);
});

/**
 * Regression: when the tile-size slider is at its maximum value (1200px),
 * and the grid container is narrower than 1200px, every scenario card in
 * the fixture manifest must still be rendered and visually reachable.
 * Previously the grid used `minmax(var(--tile-size), 1fr)` which at tile
 * sizes larger than the container would leave later rows rendered outside
 * the viewport and unreachable via vertical scroll.
 */
test('iter4_gallery_all_cards_visible_at_max_tile_size', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');

  const slider = page.getByTestId('tile-size-slider');
  await slider.evaluate((el) => {
    const input = el as HTMLInputElement;
    const proto = Object.getPrototypeOf(input) as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
    setter?.call(input, '1200');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await expect(page.getByTestId('tile-size-readout')).toContainText('1200');

  // Every fixture scenario must be in the DOM and report a non-zero box.
  const slugs = [
    'org-create-1776000000000-w0',
    'project-create-1776000000001-w1',
    'member-invite-1776000000002-w2',
  ];
  for (const slug of slugs) {
    const card = page.getByTestId(`scenario-card-${slug}`);
    await card.scrollIntoViewIfNeeded();
    await expect(card).toBeVisible();
    const box = await card.boundingBox();
    expect(box, `scenario-card-${slug} has no bounding box`).not.toBeNull();
    expect(box!.height).toBeGreaterThan(0);
    expect(box!.width).toBeGreaterThan(0);
  }

  // The grid itself must not spill horizontally past its scroll parent.
  const overflowX = await page.evaluate(() => {
    const grid = document.querySelector('[data-testid="scenario-grid"]');
    const main = document.querySelector('.main');
    if (!grid || !main) return 99;
    return grid.getBoundingClientRect().right - main.getBoundingClientRect().right;
  });
  expect(overflowX).toBeLessThanOrEqual(2);
});

/**
 * When the requested tile size exceeds the grid's available width, the
 * grid must collapse to a single column (stacking cards vertically) so
 * every card remains reachable via vertical scroll.
 */
test('iter4_gallery_layout_collapses_to_one_column_when_tile_exceeds_container', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.setViewportSize({ width: 800, height: 600 });
  await page.goto('/#/scenarios');

  const slider = page.getByTestId('tile-size-slider');
  await slider.evaluate((el) => {
    const input = el as HTMLInputElement;
    const proto = Object.getPrototypeOf(input) as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
    setter?.call(input, '1200');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await expect(page.getByTestId('tile-size-readout')).toContainText('1200');

  const slugs = [
    'org-create-1776000000000-w0',
    'project-create-1776000000001-w1',
    'member-invite-1776000000002-w2',
  ];

  // Force each card into the viewport so content-visibility:auto doesn't
  // skip layout and then read their bounding rects.
  const ys: number[] = [];
  for (const slug of slugs) {
    const card = page.getByTestId(`scenario-card-${slug}`);
    await card.scrollIntoViewIfNeeded();
    const box = await card.boundingBox();
    expect(box).not.toBeNull();
    ys.push(box!.y);
  }
  // Successive cards must live on strictly different rows (differing y);
  // this proves the grid collapsed to one column under the narrow viewport.
  expect(ys[1]).not.toBe(ys[0]);
  expect(ys[2]).not.toBe(ys[1]);
});

/**
 * Guard that the gallery's scroll ancestor keeps vertical overflow
 * scrollable. If a parent sets overflow-y:hidden, later cards become
 * unreachable when the tile size is large.
 */
test('iter4_gallery_container_has_scrollable_vertical_overflow', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');
  const overflowY = await page.evaluate(() => {
    const main = document.querySelector('.main');
    if (!main) return null;
    return getComputedStyle(main).overflowY;
  });
  expect(['auto', 'scroll']).toContain(overflowY);
});

test('iter5_strip_row_click_on_background_navigates_to_detail', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');
  await page.getByTestId('view-toggle-strip').click();
  const row = page.getByTestId('scenario-strip-org-create-1776000000000-w0');
  await expect(row).toBeVisible();
  // Click the title text — part of the clickable "go to scenario" surface.
  await row.locator('.scen-strip__title').click();
  await expect(page).toHaveURL(/#\/scenarios\/org-create-1776000000000-w0$/);
});

test('iter5_strip_frame_click_opens_lightbox_and_does_not_navigate', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');
  const hashBefore = await page.evaluate(() => window.location.hash);
  await page.getByTestId('view-toggle-strip').click();
  const hashAfterToggle = await page.evaluate(() => window.location.hash);
  await page
    .getByTestId('strip-frame-org-create-1776000000000-w0-1')
    .click();
  await expect(page.getByTestId('lightbox')).toBeVisible();
  const hashAfter = await page.evaluate(() => window.location.hash);
  // Clicking a frame must not cause a navigation to the detail route.
  expect(hashAfter).toBe(hashAfterToggle);
  expect(hashBefore).not.toContain('/org-create-1776000000000-w0');
  expect(hashAfter).not.toContain('/org-create-1776000000000-w0');
});

test('iter5_strip_alternating_row_backgrounds_differ', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');
  await page.getByTestId('view-toggle-strip').click();
  await expect(
    page.getByTestId('scenario-strip-org-create-1776000000000-w0'),
  ).toBeVisible();
  const bgs = await page.evaluate(() => {
    const rows = Array.from(
      document.querySelectorAll('.scen-strips > .scen-strip'),
    ) as HTMLElement[];
    return rows.slice(0, 2).map((r) => getComputedStyle(r).backgroundColor);
  });
  expect(bgs.length).toBe(2);
  expect(bgs[0]).not.toBe(bgs[1]);
});

test('iter5_strip_row_hover_changes_background', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');
  await page.getByTestId('view-toggle-strip').click();
  const row = page.getByTestId('scenario-strip-org-create-1776000000000-w0');
  await expect(row).toBeVisible();
  const baseline = await row.evaluate(
    (el) => getComputedStyle(el).backgroundColor,
  );
  // Hover somewhere guaranteed non-frame: the title.
  await row.locator('.scen-strip__title').hover();
  // Hover dispatch can race with the first computed-style read; poll until
  // the :hover rule actually paints.
  await expect
    .poll(
      async () =>
        row.evaluate((el) => getComputedStyle(el).backgroundColor),
    )
    .not.toBe(baseline);
});

test('iter5_strip_frame_hover_changes_visual', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');
  await page.getByTestId('view-toggle-strip').click();
  const frame = page.getByTestId('strip-frame-org-create-1776000000000-w0-0');
  await expect(frame).toBeVisible();
  const baseline = await frame.evaluate((el) => {
    const s = getComputedStyle(el);
    return { bg: s.backgroundColor, outline: s.outlineColor };
  });
  // Hover an adjacent non-frame element first to ensure a clean starting state.
  await page
    .getByTestId('scenario-strip-org-create-1776000000000-w0')
    .locator('.scen-strip__title')
    .hover();
  await frame.hover();
  await expect
    .poll(async () =>
      frame.evaluate((el) => {
        const s = getComputedStyle(el);
        return s.backgroundColor !== '' && s.outlineColor !== ''
          ? `${s.backgroundColor}|${s.outlineColor}`
          : '';
      }),
    )
    .not.toBe(`${baseline.bg}|${baseline.outline}`);
});

test('iter5_strip_row_has_no_inset_card_wrapper', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');
  await page.getByTestId('view-toggle-strip').click();
  const container = page.getByTestId('scenario-strips');
  const row = page.getByTestId('scenario-strip-org-create-1776000000000-w0');
  await expect(container).toBeVisible();
  await expect(row).toBeVisible();

  // Row is edge-to-edge with the strips container (no horizontal inset).
  const [containerBox, rowBox] = await Promise.all([
    container.boundingBox(),
    row.boundingBox(),
  ]);
  expect(containerBox).not.toBeNull();
  expect(rowBox).not.toBeNull();
  if (containerBox && rowBox) {
    expect(Math.round(rowBox.x)).toBe(Math.round(containerBox.x));
    expect(Math.round(rowBox.x + rowBox.width)).toBe(
      Math.round(containerBox.x + containerBox.width),
    );
  }

  // Computed style: no rounded corners and no border forming an inset card.
  const style = await row.evaluate((el) => {
    const s = getComputedStyle(el);
    return {
      borderRadius: s.borderTopLeftRadius,
      borderTopWidth: s.borderTopWidth,
      borderLeftWidth: s.borderLeftWidth,
      paddingLeft: s.paddingLeft,
      paddingRight: s.paddingRight,
    };
  });
  expect(style.borderRadius).toBe('0px');
  expect(style.borderTopWidth).toBe('0px');
  expect(style.borderLeftWidth).toBe('0px');
  expect(style.paddingLeft).toBe('0px');
  expect(style.paddingRight).toBe('0px');
});

test('screens_panel_renders_index_with_covered_and_uncovered_sections', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/screens');

  // Covered screens: /login (1 visit), /organizations (3 visits), /projects/:projectId (1 visit)
  await expect(page.getByTestId('screen-card-login')).toBeVisible();
  await expect(page.getByTestId('screen-card-organizations')).toBeVisible();
  await expect(page.getByTestId('screen-card-projects-projectId')).toBeVisible();

  // Uncovered section: /projects, /tickets/:ticketId, /epics/:epicId, /users
  await expect(page.getByTestId('uncovered-screens')).toBeVisible();
});

test('screens_panel_shows_empty_state_when_manifest_missing', async ({
  page,
}) => {
  await withArtifacts({ scenarios: false, capabilities: false, traces: false });
  await page.goto('/#/screens');
  await expect(page.getByTestId('empty-state')).toBeVisible();
  await expect(page.getByTestId('cmd-block')).toBeVisible();
});

test('screens_card_click_opens_detail_view', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/screens');
  await page.getByTestId('screen-card-login').click();
  await expect(page.getByTestId('screen-detail')).toBeVisible();
  await expect(page.getByTestId('screens-back')).toBeVisible();
});

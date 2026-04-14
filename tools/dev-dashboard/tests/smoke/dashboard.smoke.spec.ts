import { test, expect, withArtifacts, withRealTraceArtifacts } from './fixtures';

test.describe.configure({ mode: 'serial' });

test('dashboard_boots_and_shows_three_aspect_tabs', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: true, traces: true });
  await page.goto('/');
  await expect(page.getByTestId('rail-scenarios')).toBeVisible();
  await expect(page.getByTestId('rail-capabilities')).toBeVisible();
  await expect(page.getByTestId('rail-traces')).toBeVisible();
});

test('clicking_each_aspect_tab_renders_its_panel_header', async ({ page }) => {
  const logs: string[] = [];
  page.on('console', (m) => {
    if (m.type() === 'error' || m.type() === 'warning') {
      logs.push(`[${m.type()}] ${m.text()}`);
    }
  });
  page.on('pageerror', (e) => logs.push(`[pageerror] ${String(e)}`));
  await withArtifacts({ scenarios: true, capabilities: true, traces: true });
  await page.goto('/', { timeout: 5000 });

  for (const id of ['scenarios', 'capabilities', 'traces'] as const) {
    await page.getByTestId(`rail-${id}`).click({ timeout: 3000 });
    await expect(
      page.getByTestId(`aspect-${id}`),
      `id=${id} logs=${logs.join('||')}`,
    ).toBeVisible({ timeout: 3000 });
    await expect(
      page.getByTestId(`aspect-${id}`).getByTestId('cmd-block'),
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
  await expect(page.getByTestId('freshness-summary')).toContainText('3 aspects');
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

test('repo_root_is_displayed_in_top_bar', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: true, traces: true });
  await page.goto('/');
  const text = await page.getByTestId('repo-root').innerText();
  expect(text).toContain('.tmp-repo');
});

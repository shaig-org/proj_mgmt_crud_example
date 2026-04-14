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
  await expect(page.getByTestId('scenario-card-org_create')).toBeVisible();
  await expect(page.getByTestId('scenario-card-project_create')).toBeVisible();
  await expect(page.getByTestId('scenario-card-member_invite')).toBeVisible();
});

test('scenarios_card_click_opens_detail_view_with_video_and_steps', async ({
  page,
}) => {
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.goto('/#/scenarios');
  await page.getByTestId('scenario-card-org_create').click();
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
  await expect(page.getByTestId('trace-item-org_create')).toBeVisible();
  await expect(page.getByTestId('trace-item-project_create')).toBeVisible();
});

test('traces_selecting_scenario_renders_mermaid_and_flame_iframe', async ({
  page,
}) => {
  await withArtifacts({ scenarios: false, capabilities: false, traces: true });
  await page.goto('/#/traces');
  await page.getByTestId('trace-item-org_create').click();
  // mermaid render may take a tick.
  await expect(page.getByTestId('mermaid-svg')).toBeVisible();
  const iframe = page.getByTestId('flame-iframe');
  await expect(iframe).toBeVisible();
  await expect(iframe).toHaveAttribute('src', /flame\.html$/);
});

test('traces_folded_stacks_collapsed_by_default', async ({ page }) => {
  await withArtifacts({ scenarios: false, capabilities: false, traces: true });
  await page.goto('/#/traces');
  await page.getByTestId('trace-item-org_create').click();
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
  await expect(page.getByTestId('trace-item-project_create')).toHaveAttribute(
    'aria-selected',
    'true',
  );
});

test('cross_link_scenario_to_trace_appears_only_when_trace_exists', async ({
  page,
}) => {
  // Case A: trace dir exists for org_create → button visible.
  await withArtifacts({ scenarios: true, capabilities: false, traces: true });
  await page.goto('/#/scenarios');
  await page.getByTestId('scenario-card-org_create').click();
  await expect(page.getByTestId('view-trace-link')).toBeVisible();

  // Case B: no traces → no button.
  await withArtifacts({ scenarios: true, capabilities: false, traces: false });
  await page.reload();
  await page.getByTestId('scenario-card-org_create').click();
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

  // Mermaid SVG renders (real artifacts include mermaid.md).
  await expect(page.getByTestId('mermaid-svg')).toBeVisible();

  // Flame iframe is present.
  await expect(page.getByTestId('flame-iframe')).toHaveAttribute(
    'src',
    /flame\.html$/,
  );

  // Folded stacks: expand → content appears (loads folded-compact.txt).
  await page.getByTestId('folded-expand').click();
  await expect(page.getByTestId('folded-content')).toBeVisible();
});

test('repo_root_is_displayed_in_top_bar', async ({ page }) => {
  await withArtifacts({ scenarios: true, capabilities: true, traces: true });
  await page.goto('/');
  const text = await page.getByTestId('repo-root').innerText();
  expect(text).toContain('.tmp-repo');
});

import { describe, it, expect, vi } from 'vitest';
import { copyCommand } from '../../src/lib/clipboard';

describe('clipboard', () => {
  it('clipboard_copies_only_the_command_string', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    });
    const spec = {
      refreshCommand: 'npm --prefix frontend run walkthroughs:generate',
      cwd: '<repo-root>',
      description: 'should not be copied',
    };
    const ok = await copyCommand(spec.refreshCommand);
    expect(ok).toBe(true);
    expect(writeText).toHaveBeenCalledTimes(1);
    expect(writeText).toHaveBeenCalledWith(spec.refreshCommand);
    // Nothing else in the clipboard payload.
    const arg = writeText.mock.calls[0][0] as string;
    expect(arg).not.toContain(spec.cwd);
    expect(arg).not.toContain(spec.description);
  });
});

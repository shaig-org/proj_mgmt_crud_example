import { useState } from 'react';
import { copyCommand } from '../lib/clipboard';

export interface CommandBlockProps {
  command: string;
  cwd: string;
  description: string;
  output: string;
}

export function CommandBlock({ command, cwd, description, output }: CommandBlockProps) {
  const [copied, setCopied] = useState(false);

  async function onCopy() {
    const ok = await copyCommand(command);
    if (ok) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    }
  }

  return (
    <div className="cmd-block" data-testid="cmd-block">
      <div className="cmd-block__label">Refresh command</div>
      <div className="cmd-block__row">
        <code className="cmd-block__cmd" data-testid="cmd-block-command">
          {command}
        </code>
        <button type="button" onClick={onCopy} data-testid="cmd-block-copy">
          {copied ? 'copied' : 'copy'}
        </button>
      </div>
      <div className="cmd-block__meta">Run from: <code>{cwd}</code></div>
      <div className="cmd-block__meta">Generates: <code>{output}</code></div>
      <div className="cmd-block__meta">{description}</div>
    </div>
  );
}

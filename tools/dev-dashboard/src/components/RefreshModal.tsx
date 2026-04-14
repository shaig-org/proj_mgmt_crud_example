import { useEffect, useState } from 'react';
import { copyCommand } from '../lib/clipboard';

export interface RefreshModalProps {
  command: string;
  cwd: string;
  description: string;
  output: string;
}

export function RefreshModal({
  command,
  cwd,
  description,
  output,
}: RefreshModalProps) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  async function onCopy() {
    const ok = await copyCommand(command);
    if (ok) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    }
  }

  return (
    <>
      <button
        type="button"
        className="refresh-trigger"
        data-testid="refresh-modal-open"
        onClick={() => setOpen(true)}
        title="Show the command to regenerate this view's artifacts"
      >
        How to refresh this?
      </button>
      {open && (
        <div
          className="refresh-modal__overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="refresh-modal-title"
          data-testid="refresh-modal"
          onClick={(e) => {
            if (e.target === e.currentTarget) setOpen(false);
          }}
        >
          <div className="refresh-modal__panel">
            <header className="refresh-modal__header">
              <h3 id="refresh-modal-title" className="refresh-modal__title">
                Refresh this view
              </h3>
              <button
                type="button"
                className="refresh-modal__close"
                data-testid="refresh-modal-close"
                aria-label="close"
                onClick={() => setOpen(false)}
              >
                ×
              </button>
            </header>
            <div className="cmd-block" data-testid="cmd-block">
              <div className="cmd-block__label">Refresh command</div>
              <div className="cmd-block__row">
                <code
                  className="cmd-block__cmd"
                  data-testid="cmd-block-command"
                >
                  {command}
                </code>
                <button
                  type="button"
                  onClick={onCopy}
                  data-testid="cmd-block-copy"
                >
                  {copied ? 'copied' : 'copy'}
                </button>
              </div>
              <div className="cmd-block__meta">
                Run from: <code>{cwd}</code>
              </div>
              <div className="cmd-block__meta">
                Generates: <code>{output}</code>
              </div>
              <div className="cmd-block__meta">{description}</div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

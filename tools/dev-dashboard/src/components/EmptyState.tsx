import type { AnyAspect } from '../aspects/types';
import { CommandBlock } from './CommandBlock';

export function EmptyState({ aspect }: { aspect: AnyAspect }) {
  return (
    <div className="empty" data-testid="empty-state">
      <h3>No {aspect.title.toLowerCase()} artifacts yet.</h3>
      <p>
        This panel renders data from <code>{aspect.artifacts[0].repoPath}</code>,
        which has not been generated yet.
      </p>
      <p>Run the refresh command below to produce the artifact, then reload.</p>
      <CommandBlock
        command={aspect.refreshCommand}
        cwd={aspect.refreshCwd}
        description={aspect.refreshDescription}
        output={aspect.artifacts[0].repoPath}
      />
    </div>
  );
}

import type { AnyAspect } from './types';
import { buildRegistry } from '../lib/registry';
import { scenariosAspect } from './scenarios/ScenariosAspect';
import { capabilitiesAspect } from './capabilities/CapabilitiesAspect';
import { tracesAspect } from './traces/TracesAspect';

export const aspects: ReadonlyArray<AnyAspect> = buildRegistry([
  scenariosAspect,
  capabilitiesAspect,
  tracesAspect,
]);

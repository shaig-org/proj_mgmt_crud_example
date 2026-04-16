import React from 'react';
import type { ScreenVisit } from './screenIndex';

interface ScreenDetailViewProps {
  route: string;
  visits: ScreenVisit[];
}

export function ScreenDetailView({ route, visits }: ScreenDetailViewProps): React.ReactElement {
  function goBack(): void {
    window.location.hash = '#/screens';
  }

  return (
    <div data-testid="screen-detail">
      <nav className="scen-breadcrumb" aria-label="breadcrumb">
        <button
          type="button"
          className="screens-breadcrumb__back"
          data-testid="screens-back"
          onClick={goBack}
        >
          ← Screens
        </button>
        <span className="scen-breadcrumb__sep">/</span>
        <span className="scen-breadcrumb__current">{route}</span>
      </nav>

      <h3 className="screen-detail__title">{route}</h3>
      <p className="screen-detail__subtitle">
        {visits.length} {visits.length === 1 ? 'visit' : 'visits'} across{' '}
        {new Set(visits.map((v) => v.scenarioId)).size}{' '}
        {new Set(visits.map((v) => v.scenarioId)).size === 1 ? 'scenario' : 'scenarios'}
      </p>

      {visits.length === 0 ? (
        <p className="screens-empty">No visits recorded for this screen.</p>
      ) : (
        <ul className="screen-visits" data-testid="screen-visits">
          {visits.map((visit, i) => (
            <li
              key={`${visit.scenarioId}-${visit.stepIndex}-${i}`}
              className="screen-visit"
              data-testid={`screen-visit-${i}`}
            >
              {visit.screenshot ? (
                <div className="screen-visit__thumb-wrap">
                  <img
                    src={visit.screenshot}
                    alt={`${visit.scenarioTitle} step ${visit.stepIndex}`}
                    className="screen-visit__thumb"
                    loading="lazy"
                    decoding="async"
                  />
                </div>
              ) : (
                <div className="screen-visit__thumb-wrap screen-visit__thumb-wrap--empty" aria-hidden="true" />
              )}
              <div className="screen-visit__info">
                <a
                  href={`#/scenarios/${visit.scenarioId}`}
                  className="screen-visit__scenario-link"
                  data-testid={`screen-visit-scenario-link-${i}`}
                >
                  {visit.scenarioTitle}
                </a>
                <span className="screen-visit__step">
                  Step {visit.stepIndex} — {visit.stepLabel}
                </span>
              </div>
              <span className="screen-visit__step-badge">#{visit.stepIndex}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

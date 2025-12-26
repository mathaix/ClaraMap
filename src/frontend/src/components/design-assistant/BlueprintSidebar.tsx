/**
 * Sidebar showing the current blueprint state.
 */

import clsx from 'clsx';
import type {
  DesignSessionState,
  DesignPhase,
  CardEnvelope,
} from '../../types/design-session';
import { CardStack } from './CardStack';

interface BlueprintSidebarProps {
  state: DesignSessionState | null;
  cards?: CardEnvelope[];
  activePersonaId?: string | null;
  onAction?: (actionId: string, cardId: string) => void;
}

const phaseLabels: Record<DesignPhase, string> = {
  goal_understanding: 'Goal Understanding',
  agent_configuration: 'Agent Configuration',
  blueprint_design: 'Blueprint Design',
  complete: 'Complete',
};

const phaseOrder: DesignPhase[] = [
  'goal_understanding',
  'agent_configuration',
  'blueprint_design',
  'complete',
];

export function BlueprintSidebar({ state, cards, activePersonaId, onAction }: BlueprintSidebarProps) {
  if (!state) {
    return (
      <div className="w-80 bg-gray-50 border-l border-gray-200 p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-3/4" />
          <div className="h-4 bg-gray-200 rounded w-1/2" />
          <div className="h-4 bg-gray-200 rounded w-2/3" />
        </div>
      </div>
    );
  }

  const currentPhaseIndex = phaseOrder.indexOf(state.phase);

  return (
    <div className="w-80 bg-gray-50 border-l border-gray-200 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <h2 className="font-semibold text-gray-900">Blueprint Preview</h2>
        <p className="text-sm text-gray-500 mt-1">
          {state.preview.project_name || 'New Blueprint'}
        </p>
      </div>

      {/* Phase Progress (fallback when no cards present) */}
      {!cards?.length && (
        <div className="p-4 border-b border-gray-200">
          <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">
            Progress
          </h3>
          <div className="space-y-2">
            {phaseOrder.map((phase, index) => {
              const isComplete = index < currentPhaseIndex;
              const isCurrent = phase === state.phase;

              return (
                <div key={phase} className="flex items-center gap-3">
                  <div
                    className={clsx(
                      'w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium',
                      isComplete && 'bg-green-500 text-white',
                      isCurrent && 'bg-blue-500 text-white',
                      !isComplete && !isCurrent && 'bg-gray-200 text-gray-500'
                    )}
                  >
                    {isComplete ? (
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                    ) : (
                      index + 1
                    )}
                  </div>
                  <span
                    className={clsx(
                      'text-sm',
                      isCurrent ? 'font-medium text-gray-900' : 'text-gray-500'
                    )}
                  >
                    {phaseLabels[phase]}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Card-Orchestrated Snapshot */}
      {cards?.length ? (
        <div className="border-b border-gray-200 p-4">
          <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">
            Current Step
          </h3>
          <CardStack cards={cards} activePersonaId={activePersonaId} onAction={onAction} />
        </div>
      ) : null}

      {/* Blueprint Details */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Project Info */}
        {state.preview.project_type && (
          <div>
            <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
              Project Type
            </h3>
            <p className="text-sm text-gray-900 capitalize">
              {state.preview.project_type.replace(/_/g, ' ')}
            </p>
          </div>
        )}

        {/* Domain */}
        {state.inferred_domain && (
          <div>
            <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
              Domain
            </h3>
            <p className="text-sm text-gray-900 capitalize">
              {state.inferred_domain.replace(/_/g, ' ')}
            </p>
          </div>
        )}

        {/* Entity Types */}
        {state.preview.entity_types.length > 0 && (
          <div>
            <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
              Entity Types ({state.preview.entity_types.length})
            </h3>
            <div className="flex flex-wrap gap-1">
              {state.preview.entity_types.map((entity) => (
                <span
                  key={entity}
                  className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded"
                >
                  {entity}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Agents */}
        {state.preview.agent_count > 0 && (
          <div>
            <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
              Interview Agents
            </h3>
            <p className="text-sm text-gray-900">
              {state.preview.agent_count} configured
            </p>
          </div>
        )}

        {/* Topics */}
        {state.preview.topics.length > 0 && (
          <div>
            <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
              Topics
            </h3>
            <div className="flex flex-wrap gap-1">
              {state.preview.topics.map((topic) => (
                <span
                  key={topic}
                  className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded"
                >
                  {topic}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Debug Info (collapsed by default) */}
      <details className="border-t border-gray-200">
        <summary className="p-4 text-xs font-medium text-gray-500 uppercase tracking-wide cursor-pointer hover:bg-gray-100">
          Debug Info
        </summary>
        <div className="px-4 pb-4 text-xs text-gray-500 space-y-1">
          <p>Turn: {state.debug.turn_count}</p>
          <p>Messages: {state.debug.message_count}</p>
          {state.debug.domain_confidence > 0 && (
            <p>
              Domain Confidence:{' '}
              {(state.debug.domain_confidence * 100).toFixed(0)}%
            </p>
          )}
        </div>
      </details>
    </div>
  );
}

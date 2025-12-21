/**
 * Agent Configured Card - displays the specialist agent configured in Phase 2.
 */

import type { AgentConfiguredUIComponent } from '../../types/design-session';

interface AgentConfiguredCardProps {
  agent: AgentConfiguredUIComponent;
}

export function AgentConfiguredCard({ agent }: AgentConfiguredCardProps) {
  return (
    <div className="rounded-lg border-2 border-purple-200 bg-gradient-to-br from-purple-50 to-blue-50 p-5 shadow-sm">
      {/* Header with icon */}
      <div className="flex items-start gap-3 mb-4">
        <div className="flex-shrink-0 w-10 h-10 rounded-full bg-purple-100 flex items-center justify-center">
          <svg
            className="w-5 h-5 text-purple-600"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
            />
          </svg>
        </div>
        <div>
          <p className="text-xs font-medium text-purple-600 uppercase tracking-wide">
            Specialist Agent Configured
          </p>
          <h3 className="text-lg font-semibold text-gray-900 mt-0.5">
            {agent.role}
          </h3>
        </div>
      </div>

      {/* Expertise Areas */}
      {agent.expertise_areas.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
            Expertise Areas
          </p>
          <div className="flex flex-wrap gap-2">
            {agent.expertise_areas.map((area, i) => (
              <span
                key={i}
                className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-700"
              >
                {area}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Interaction Style */}
      {agent.interaction_style && (
        <div className="mb-4">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
            Interaction Style
          </p>
          <p className="text-sm text-gray-700 italic">
            "{agent.interaction_style}"
          </p>
        </div>
      )}

      {/* Focus Areas (if provided) */}
      {agent.focus_areas && agent.focus_areas.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
            Focus Areas
          </p>
          <ul className="space-y-1">
            {agent.focus_areas.map((area, i) => (
              <li key={i} className="flex items-center gap-2 text-sm text-gray-700">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                {area}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Capabilities (if provided) */}
      {agent.capabilities && agent.capabilities.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
            Capabilities
          </p>
          <ul className="space-y-1">
            {agent.capabilities.map((cap, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                <svg
                  className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0"
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
                {cap}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Footer message */}
      <div className="mt-4 pt-3 border-t border-purple-100">
        <p className="text-xs text-gray-500 flex items-center gap-1">
          <svg
            className="w-3.5 h-3.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 10V3L4 14h7v7l9-11h-7z"
            />
          </svg>
          This specialist will help design your interview blueprint
        </p>
      </div>
    </div>
  );
}

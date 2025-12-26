/**
 * Chat message bubble component.
 */

import { useMemo } from 'react';
import type { ReactNode } from 'react';
import clsx from 'clsx';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import type {
  ChatMessage as ChatMessageType,
  AskUIComponent,
  AgentConfiguredUIComponent,
  PromptEditorUIComponent,
  DataTableUIComponent,
  ProcessMapUIComponent,
  DataTableSubmission,
  ProcessMapSubmission,
  UIComponent,
} from '../../types/design-session';
import { parseUIComponent, stripUIComponentMarkers } from '../../types/design-session';
import { OptionCards } from './OptionCards';
import { PersonaCardStack } from './CardStack';
import type { PersonaEntry } from './CardStack';
import { AgentConfiguredCard } from './AgentConfiguredCard';
import { PromptEditor } from './PromptEditor';
import { DataTableCapture } from './DataTableCapture';
import { ProcessMapBuilder } from './ProcessMapBuilder';

interface ChatMessageProps {
  message: ChatMessageType;
  onOptionSelect?: (optionId: string) => void;
  onPersonaSelect?: (persona: PersonaEntry) => void;
  activePersonaId?: string | null;
  onQuickConfirm?: (answer: 'Yes' | 'No') => void;
  isLastAssistantMessage?: boolean;
  /** Callback when user saves an edited prompt */
  onPromptSave?: (editedPrompt: string) => void;
  /** Callback when user submits a data table */
  onTableSubmit?: (payload: DataTableSubmission) => void;
  /** Callback when user submits a process map */
  onProcessMapSubmit?: (payload: ProcessMapSubmission) => void;
  /** UI component from CUSTOM event - takes precedence over text parsing */
  externalUIComponent?: UIComponent | null;
}

export function ChatMessage({
  message,
  onOptionSelect,
  onPersonaSelect,
  activePersonaId,
  onQuickConfirm,
  isLastAssistantMessage = false,
  onPromptSave,
  onTableSubmit,
  onProcessMapSubmit,
  externalUIComponent,
}: ChatMessageProps) {
  const isUser = message.role === 'user';

  // Parse any UI components from the message
  // External UI component from CUSTOM events takes precedence over text parsing
  const { textContent, uiComponent } = useMemo(() => {
    if (isUser) {
      return { textContent: message.content, uiComponent: null };
    }

    // Use external component if provided (from CUSTOM event)
    if (externalUIComponent) {
      // Still strip any legacy markers from content
      const text = stripUIComponentMarkers(message.content);
      return { textContent: text, uiComponent: externalUIComponent };
    }

    // Fallback to text parsing for backwards compatibility
    const component = parseUIComponent(message.content);
    const text = stripUIComponentMarkers(message.content);

    return { textContent: text, uiComponent: component };
  }, [message.content, isUser, externalUIComponent]);

  const showQuickConfirm =
    !isUser &&
    isLastAssistantMessage &&
    !message.isStreaming &&
    !uiComponent &&
    !!onQuickConfirm;

  const shouldShowQuickConfirm = useMemo(() => {
    if (!showQuickConfirm) return false;
    const text = textContent?.trim();
    if (!text) return false;
    const normalized = text.replace(/\s+/g, ' ').trim();
    const patterns = [
      /\bis this correct\?\s*$/i,
      /\bis that correct\?\s*$/i,
      /\bis this accurate\?\s*$/i,
      /\bis that accurate\?\s*$/i,
      /\bis this an accurate summary\?\s*$/i,
      /\bdoes this capture.*\?\s*$/i,
      /\bdoes that capture.*\?\s*$/i,
      /\bdoes this look right\?\s*$/i,
      /\bdoes that look right\?\s*$/i,
      /\bsound right\?\s*$/i,
    ];
    return patterns.some((pattern) => pattern.test(normalized));
  }, [showQuickConfirm, textContent]);

  const markdownComponents = useMemo(() => {
    const linkClass = isUser
      ? 'text-white underline'
      : 'text-blue-600 underline hover:text-blue-700';
    const inlineCodeClass = isUser
      ? 'rounded bg-blue-500/40 px-1 py-0.5 text-xs'
      : 'rounded bg-gray-200 px-1 py-0.5 text-xs';
    const blockCodeClass = isUser
      ? 'block rounded bg-blue-900/40 p-3 text-xs text-white'
      : 'block rounded bg-gray-900 p-3 text-xs text-gray-100';
    const blockquoteClass = isUser
      ? 'border-l-2 border-white/40 pl-3 text-white/90'
      : 'border-l-2 border-gray-300 pl-3 text-gray-600';

    return {
      p: ({ children }: { children?: ReactNode }) => (
        <p className="mb-2 last:mb-0">{children}</p>
      ),
      ul: ({ children }: { children?: ReactNode }) => (
        <ul className="mb-2 ml-5 list-disc space-y-1 last:mb-0">
          {children}
        </ul>
      ),
      ol: ({ children }: { children?: ReactNode }) => (
        <ol className="mb-2 ml-5 list-decimal space-y-1 last:mb-0">
          {children}
        </ol>
      ),
      li: ({ children }: { children?: ReactNode }) => (
        <li className="leading-relaxed">{children}</li>
      ),
      a: ({ children, href }: { children?: ReactNode; href?: string }) => (
        <a href={href} target="_blank" rel="noreferrer" className={linkClass}>
          {children}
        </a>
      ),
      blockquote: ({ children }: { children?: ReactNode }) => (
        <blockquote className={blockquoteClass}>{children}</blockquote>
      ),
      code: ({ inline, children }: { inline?: boolean; children?: ReactNode }) =>
        inline ? (
          <code className={inlineCodeClass}>{children}</code>
        ) : (
          <code className={blockCodeClass}>{children}</code>
        ),
    };
  }, [isUser]);

  return (
    <div
      className={clsx('flex w-full', isUser ? 'justify-end' : 'justify-start')}
    >
      <div
        className={clsx(
          'max-w-[80%] rounded-lg px-4 py-3',
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-gray-100 text-gray-900',
          message.isStreaming && 'animate-pulse'
        )}
      >
        {/* Text content rendered as markdown */}
        {textContent && (
          <div className="text-sm leading-relaxed">
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkBreaks]}
              components={markdownComponents}
            >
              {textContent}
            </ReactMarkdown>
          </div>
        )}

        {/* Streaming indicator */}
        {message.isStreaming && !textContent && (
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
            <span
              className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
              style={{ animationDelay: '0.1s' }}
            />
            <span
              className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
              style={{ animationDelay: '0.2s' }}
            />
          </div>
        )}

        {/* Quick confirmation buttons */}
        {shouldShowQuickConfirm && (
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() => onQuickConfirm?.('Yes')}
              className="rounded-md bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700"
            >
              Yes
            </button>
            <button
              type="button"
              onClick={() => onQuickConfirm?.('No')}
              className="rounded-md border border-gray-300 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
            >
              No
            </button>
          </div>
        )}

        {/* Interactive UI component - Ask tool (user_input_required) */}
        {uiComponent && uiComponent.type === 'user_input_required' && onOptionSelect && (
          <div className="mt-4">
            {(uiComponent as AskUIComponent).cards?.length ? (
              <div className="mb-4">
                <PersonaCardStack
                  cards={(uiComponent as AskUIComponent).cards || []}
                  options={(uiComponent as AskUIComponent).options}
                  onPersonaSelect={onPersonaSelect}
                  activePersonaId={activePersonaId}
                />
              </div>
            ) : null}
            <OptionCards
              question={(uiComponent as AskUIComponent).question}
              options={(uiComponent as AskUIComponent).options}
              multiSelect={(uiComponent as AskUIComponent).multi_select}
              onSelect={onOptionSelect}
            />
          </div>
        )}

        {/* Agent configured card (from Phase 2) */}
        {uiComponent && uiComponent.type === 'agent_configured' && (
          <div className="mt-4">
            <AgentConfiguredCard agent={uiComponent as AgentConfiguredUIComponent} />
          </div>
        )}

        {/* Prompt editor (from Phase 3 - editable system prompt) */}
        {uiComponent && uiComponent.type === 'prompt_editor' && onPromptSave && (
          <div className="mt-4">
            <PromptEditor
              title={(uiComponent as PromptEditorUIComponent).title}
              prompt={(uiComponent as PromptEditorUIComponent).prompt}
              description={(uiComponent as PromptEditorUIComponent).description}
              onSave={onPromptSave}
            />
          </div>
        )}

        {/* Data table capture (bulk entry) */}
        {uiComponent && uiComponent.type === 'data_table' && onTableSubmit && (
          <div className="mt-4">
            <DataTableCapture
              title={(uiComponent as DataTableUIComponent).title}
              columns={(uiComponent as DataTableUIComponent).columns}
              minRows={(uiComponent as DataTableUIComponent).min_rows}
              starterRows={(uiComponent as DataTableUIComponent).starter_rows}
              inputModes={(uiComponent as DataTableUIComponent).input_modes}
              summaryPrompt={(uiComponent as DataTableUIComponent).summary_prompt}
              onSubmit={onTableSubmit}
            />
          </div>
        )}

        {/* Process map builder */}
        {uiComponent && uiComponent.type === 'process_map' && onProcessMapSubmit && (
          <div className="mt-4">
            <ProcessMapBuilder
              title={(uiComponent as ProcessMapUIComponent).title}
              requiredFields={(uiComponent as ProcessMapUIComponent).required_fields}
              edgeTypes={(uiComponent as ProcessMapUIComponent).edge_types}
              minSteps={(uiComponent as ProcessMapUIComponent).min_steps}
              seedNodes={(uiComponent as ProcessMapUIComponent).seed_nodes}
              onSubmit={onProcessMapSubmit}
            />
          </div>
        )}
      </div>
    </div>
  );
}

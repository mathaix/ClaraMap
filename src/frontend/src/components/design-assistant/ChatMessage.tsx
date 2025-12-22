/**
 * Chat message bubble component.
 */

import { useMemo } from 'react';
import clsx from 'clsx';
import type { ChatMessage as ChatMessageType, AskUIComponent, AgentConfiguredUIComponent, PromptEditorUIComponent, UIComponent } from '../../types/design-session';
import { parseUIComponent, stripUIComponentMarkers } from '../../types/design-session';
import { OptionCards } from './OptionCards';
import { AgentConfiguredCard } from './AgentConfiguredCard';
import { PromptEditor } from './PromptEditor';

interface ChatMessageProps {
  message: ChatMessageType;
  onOptionSelect?: (optionId: string) => void;
  /** Callback when user saves an edited prompt */
  onPromptSave?: (editedPrompt: string) => void;
  /** UI component from CUSTOM event - takes precedence over text parsing */
  externalUIComponent?: UIComponent | null;
}

export function ChatMessage({ message, onOptionSelect, onPromptSave, externalUIComponent }: ChatMessageProps) {
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
        {/* Text content with markdown-like formatting */}
        {textContent && (
          <div className="whitespace-pre-wrap text-sm leading-relaxed">
            {textContent.split('\n').map((line, i) => {
              // Simple markdown parsing
              if (line.startsWith('**') && line.endsWith('**')) {
                return (
                  <p key={i} className="font-semibold mt-2 first:mt-0">
                    {line.slice(2, -2)}
                  </p>
                );
              }
              if (line.startsWith('- ')) {
                return (
                  <p key={i} className="ml-4 before:content-['•'] before:mr-2">
                    {line.slice(2)}
                  </p>
                );
              }
              if (line.trim() === '') {
                return <br key={i} />;
              }
              return <span key={i}>{line}</span>;
            })}
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

        {/* Interactive UI component - Ask tool (user_input_required) */}
        {uiComponent && uiComponent.type === 'user_input_required' && onOptionSelect && (
          <div className="mt-4">
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
      </div>
    </div>
  );
}

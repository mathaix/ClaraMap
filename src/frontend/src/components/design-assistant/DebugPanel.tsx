/**
 * Debug panel showing agent activity - tool calls, phase transitions, hydrations.
 */

import { useMemo, useState, useRef, useEffect } from 'react';
import clsx from 'clsx';
import type { DebugEvent, DebugEventType } from '../../types/design-session';

interface DebugPanelProps {
  events: DebugEvent[];
  isOpen: boolean;
  onToggle: () => void;
}

const eventTypeStyles: Record<DebugEventType, { bg: string; text: string; icon: string }> = {
  tool_call: { bg: 'bg-blue-100', text: 'text-blue-700', icon: 'T' },
  phase_transition: { bg: 'bg-purple-100', text: 'text-purple-700', icon: 'P' },
  hydration: { bg: 'bg-green-100', text: 'text-green-700', icon: 'H' },
  state_update: { bg: 'bg-gray-100', text: 'text-gray-700', icon: 'S' },
  error: { bg: 'bg-red-100', text: 'text-red-700', icon: 'E' },
};

const eventTypeLabels: Record<DebugEventType, string> = {
  tool_call: 'Tool Call',
  phase_transition: 'Phase Transition',
  hydration: 'Template Hydration',
  state_update: 'State Update',
  error: 'Error',
};

function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatTimestamp(date: Date): string {
  return date.toISOString();
}

function formatEventForClipboard(event: DebugEvent): string {
  const header = `[${formatTimestamp(event.timestamp)}] ${event.type} | ${event.title}`;
  if (!Object.keys(event.details).length) {
    return header;
  }
  return `${header}\n${JSON.stringify(event.details, null, 2)}`;
}

function formatEventLog(events: DebugEvent[]): string {
  if (!events.length) {
    return '';
  }
  return events.map(formatEventForClipboard).join('\n\n');
}

function DebugEventItem({ event }: { event: DebugEvent }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const style = eventTypeStyles[event.type];

  return (
    <div className="border-b border-gray-100 last:border-b-0">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-start gap-2 p-2 hover:bg-gray-50 text-left"
      >
        <span
          className={clsx(
            'w-5 h-5 rounded text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5',
            style.bg,
            style.text
          )}
        >
          {style.icon}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-medium text-gray-900 truncate">
              {event.title}
            </span>
            <span className="text-xs text-gray-400 flex-shrink-0">
              {formatTime(event.timestamp)}
            </span>
          </div>
          <span className={clsx('text-xs', style.text)}>
            {eventTypeLabels[event.type]}
          </span>
        </div>
        <svg
          className={clsx(
            'w-4 h-4 text-gray-400 flex-shrink-0 transition-transform',
            isExpanded && 'rotate-180'
          )}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isExpanded && Object.keys(event.details).length > 0 && (
        <div className="px-2 pb-2">
          <pre className="text-xs bg-gray-900 text-gray-100 p-2 rounded overflow-x-auto max-h-48">
            {JSON.stringify(event.details, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export function DebugPanel({ events, isOpen, onToggle }: DebugPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [showRaw, setShowRaw] = useState(false);
  const [copyStatus, setCopyStatus] = useState<'idle' | 'copied' | 'error'>('idle');
  const logText = useMemo(() => formatEventLog(events), [events]);

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events, autoScroll]);

  // Detect if user has scrolled up
  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
    setAutoScroll(isAtBottom);
  };

  useEffect(() => {
    if (copyStatus === 'idle') return;
    const timeoutId = window.setTimeout(() => setCopyStatus('idle'), 1500);
    return () => window.clearTimeout(timeoutId);
  }, [copyStatus]);

  const handleCopy = async () => {
    if (!logText) return;
    try {
      await navigator.clipboard.writeText(logText);
      setCopyStatus('copied');
    } catch {
      setCopyStatus('error');
    }
  };

  if (!isOpen) {
    return (
      <button
        onClick={onToggle}
        className="fixed bottom-4 right-4 bg-gray-900 text-white px-3 py-2 rounded-lg shadow-lg flex items-center gap-2 hover:bg-gray-800 transition-colors z-50"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
        </svg>
        <span className="text-sm font-medium">Debug</span>
        {events.length > 0 && (
          <span className="bg-blue-500 text-white text-xs px-1.5 py-0.5 rounded-full">
            {events.length}
          </span>
        )}
      </button>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 w-96 max-h-[60vh] bg-white border border-gray-200 rounded-lg shadow-xl flex flex-col z-50">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 bg-gray-50 rounded-t-lg">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
          </svg>
          <span className="text-sm font-semibold text-gray-900">Debug Panel</span>
          <span className="text-xs text-gray-500">({events.length} events)</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            disabled={!events.length}
            className={clsx(
              'text-xs px-2 py-1 rounded border',
              events.length
                ? 'border-gray-300 text-gray-600 hover:text-gray-900 hover:border-gray-400'
                : 'border-gray-200 text-gray-300 cursor-not-allowed'
            )}
          >
            {copyStatus === 'copied'
              ? 'Copied'
              : copyStatus === 'error'
              ? 'Copy failed'
              : 'Copy log'}
          </button>
          <button
            onClick={() => setShowRaw((prev) => !prev)}
            className="text-xs px-2 py-1 rounded border border-gray-300 text-gray-600 hover:text-gray-900 hover:border-gray-400"
          >
            {showRaw ? 'Hide raw' : 'Raw'}
          </button>
          <button
            onClick={onToggle}
            className="text-gray-400 hover:text-gray-600"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {showRaw && (
        <div className="border-b border-gray-100 bg-gray-50 p-2">
          <textarea
            value={logText}
            readOnly
            spellCheck={false}
            onFocus={(event) => event.currentTarget.select()}
            className="w-full h-32 text-xs font-mono text-gray-900 bg-white border border-gray-200 rounded p-2"
            placeholder="No events yet."
          />
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center gap-3 px-3 py-2 border-b border-gray-100 bg-gray-50">
        {Object.entries(eventTypeStyles).map(([type, style]) => (
          <div key={type} className="flex items-center gap-1">
            <span
              className={clsx(
                'w-4 h-4 rounded text-xs font-bold flex items-center justify-center',
                style.bg,
                style.text
              )}
            >
              {style.icon}
            </span>
            <span className="text-xs text-gray-500">{type.split('_')[0]}</span>
          </div>
        ))}
      </div>

      {/* Events List */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto"
      >
        {events.length === 0 ? (
          <div className="p-4 text-center text-sm text-gray-500">
            No events yet. Start a conversation to see agent activity.
          </div>
        ) : (
          <div>
            {events.map((event) => (
              <DebugEventItem key={event.id} event={event} />
            ))}
          </div>
        )}
      </div>

      {/* Auto-scroll indicator */}
      {!autoScroll && events.length > 0 && (
        <button
          onClick={() => {
            setAutoScroll(true);
            if (scrollRef.current) {
              scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
            }
          }}
          className="absolute bottom-12 left-1/2 -translate-x-1/2 bg-blue-500 text-white text-xs px-2 py-1 rounded-full shadow-lg"
        >
          Scroll to bottom
        </button>
      )}
    </div>
  );
}

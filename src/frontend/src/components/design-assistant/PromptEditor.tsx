/**
 * Editable prompt editor for generated system prompts.
 */

import { useState } from 'react';
import clsx from 'clsx';

interface PromptEditorProps {
  title: string;
  prompt: string;
  description?: string;
  onSave: (editedPrompt: string) => void;
}

export function PromptEditor({
  title,
  prompt,
  description,
  onSave,
}: PromptEditorProps) {
  const [editedPrompt, setEditedPrompt] = useState(prompt);
  const [isSubmitted, setIsSubmitted] = useState(false);

  const handleSave = () => {
    if (isSubmitted) return;
    setIsSubmitted(true);
    onSave(editedPrompt);
  };

  const handleReset = () => {
    setEditedPrompt(prompt);
  };

  const hasChanges = editedPrompt !== prompt;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
          {description && (
            <p className="text-sm text-gray-500 mt-1">{description}</p>
          )}
        </div>
        {hasChanges && !isSubmitted && (
          <span className="text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded">
            Modified
          </span>
        )}
      </div>

      {/* Editor */}
      <div className="relative">
        <textarea
          value={editedPrompt}
          onChange={(e) => setEditedPrompt(e.target.value)}
          disabled={isSubmitted}
          className={clsx(
            'w-full h-96 p-4 font-mono text-sm rounded-lg border-2 resize-y',
            'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            isSubmitted
              ? 'bg-gray-50 text-gray-500 cursor-not-allowed border-gray-200'
              : 'bg-white text-gray-900 border-gray-300'
          )}
          placeholder="System prompt..."
        />

        {/* Line count indicator */}
        <div className="absolute bottom-3 right-3 text-xs text-gray-400">
          {editedPrompt.split('\n').length} lines
        </div>
      </div>

      {/* Actions */}
      {!isSubmitted && (
        <div className="flex items-center justify-between">
          <button
            onClick={handleReset}
            disabled={!hasChanges}
            className={clsx(
              'px-4 py-2 text-sm font-medium rounded-lg transition-colors',
              hasChanges
                ? 'text-gray-700 hover:bg-gray-100'
                : 'text-gray-400 cursor-not-allowed'
            )}
          >
            Reset to Original
          </button>

          <button
            onClick={handleSave}
            className={clsx(
              'px-6 py-2 text-sm font-medium rounded-lg transition-colors',
              'bg-blue-600 text-white hover:bg-blue-700',
              'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2'
            )}
          >
            Save & Continue
          </button>
        </div>
      )}

      {/* Submitted state */}
      {isSubmitted && (
        <div className="flex items-center gap-2 text-green-600">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <span className="text-sm font-medium">Prompt saved</span>
        </div>
      )}
    </div>
  );
}

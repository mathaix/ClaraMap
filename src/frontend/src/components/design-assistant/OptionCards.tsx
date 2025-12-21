/**
 * Interactive option cards for the ask tool.
 */

import { useState } from 'react';
import clsx from 'clsx';
import type { AskOption } from '../../types/design-session';

interface OptionCardsProps {
  question: string;
  options: AskOption[];
  multiSelect: boolean;
  onSelect: (optionId: string) => void;
}

export function OptionCards({
  question,
  options,
  multiSelect,
  onSelect,
}: OptionCardsProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isSubmitted, setIsSubmitted] = useState(false);

  const handleOptionClick = (optionId: string) => {
    if (isSubmitted) return;

    if (multiSelect) {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        if (next.has(optionId)) {
          next.delete(optionId);
        } else {
          next.add(optionId);
        }
        return next;
      });
    } else {
      // Single select - immediately submit with label (not ID)
      setIsSubmitted(true);
      const selectedOption = options.find((opt) => opt.id === optionId);
      onSelect(selectedOption?.label || optionId);
    }
  };

  const handleSubmit = () => {
    if (selectedIds.size === 0) return;
    setIsSubmitted(true);
    // Send labels (not IDs) for multi-select
    const selectedLabels = options
      .filter((opt) => selectedIds.has(opt.id))
      .map((opt) => opt.label);
    onSelect(selectedLabels.join(', '));
  };

  return (
    <div className="space-y-3">
      <p className="font-medium text-gray-700">{question}</p>

      <div className="grid gap-2">
        {options.map((option) => {
          const isSelected = selectedIds.has(option.id);

          return (
            <button
              key={option.id}
              onClick={() => handleOptionClick(option.id)}
              disabled={isSubmitted}
              className={clsx(
                'w-full text-left p-3 rounded-lg border-2 transition-all',
                'hover:border-blue-400 hover:bg-blue-50',
                'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
                isSelected
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 bg-white',
                isSubmitted && 'opacity-60 cursor-not-allowed'
              )}
            >
              <div className="flex items-start gap-3">
                {/* Checkbox/Radio indicator */}
                <div
                  className={clsx(
                    'mt-0.5 w-5 h-5 rounded flex items-center justify-center border-2',
                    multiSelect ? 'rounded' : 'rounded-full',
                    isSelected
                      ? 'border-blue-500 bg-blue-500'
                      : 'border-gray-300 bg-white'
                  )}
                >
                  {isSelected && (
                    <svg
                      className="w-3 h-3 text-white"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={3}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  )}
                </div>

                <div className="flex-1">
                  <p className="font-medium text-gray-900">{option.label}</p>
                  {option.description && (
                    <p className="text-sm text-gray-500 mt-0.5">
                      {option.description}
                    </p>
                  )}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Submit button for multi-select */}
      {multiSelect && !isSubmitted && (
        <button
          onClick={handleSubmit}
          disabled={selectedIds.size === 0}
          className={clsx(
            'w-full py-2 px-4 rounded-lg font-medium transition-colors',
            selectedIds.size > 0
              ? 'bg-blue-600 text-white hover:bg-blue-700'
              : 'bg-gray-100 text-gray-400 cursor-not-allowed'
          )}
        >
          Confirm Selection ({selectedIds.size})
        </button>
      )}
    </div>
  );
}

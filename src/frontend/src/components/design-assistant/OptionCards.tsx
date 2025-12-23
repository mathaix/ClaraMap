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
  const [customInputs, setCustomInputs] = useState<Record<string, string>>({});

  const optionRequiresInput = (option: AskOption) => {
    if (typeof option.requires_input === 'boolean') {
      return option.requires_input;
    }
    return option.label.trim().toLowerCase().startsWith('other');
  };

  const selectedOptions = options.filter((option) => selectedIds.has(option.id));
  const optionsRequiringInput = selectedOptions.filter(optionRequiresInput);
  const allRequiredFilled = optionsRequiringInput.every(
    (option) => (customInputs[option.id] || '').trim().length > 0
  );
  const canSubmit = selectedIds.size > 0 && allRequiredFilled;

  const handleOptionClick = (optionId: string) => {
    if (isSubmitted) return;

    const selectedOption = options.find((opt) => opt.id === optionId);
    const requiresInput = selectedOption ? optionRequiresInput(selectedOption) : false;
    const wasSelected = selectedIds.has(optionId);

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
      if (wasSelected) {
        setCustomInputs((prev) => {
          const next = { ...prev };
          delete next[optionId];
          return next;
        });
      }
    } else {
      setSelectedIds(new Set([optionId]));
      if (requiresInput) {
        return;
      }
      // Single select - immediately submit with label (not ID)
      setIsSubmitted(true);
      onSelect(selectedOption?.label || optionId);
      setCustomInputs({});
    }
  };

  const handleSubmit = () => {
    if (!canSubmit) return;
    setIsSubmitted(true);
    const selectedLabels = selectedOptions.map((option) => {
      if (optionRequiresInput(option)) {
        const value = (customInputs[option.id] || '').trim();
        return value ? `${option.label}: ${value}` : option.label;
      }
      return option.label;
    });
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

      {optionsRequiringInput.length > 0 && (
        <div className="space-y-2">
          {optionsRequiringInput.map((option) => (
            <div key={option.id} className="space-y-1">
              <label className="text-sm font-medium text-gray-700">
                Please specify {option.label}
              </label>
              <input
                type="text"
                value={customInputs[option.id] || ''}
                onChange={(event) => {
                  const value = event.target.value;
                  setCustomInputs((prev) => ({ ...prev, [option.id]: value }));
                }}
                disabled={isSubmitted}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"
                placeholder="Type your answer"
              />
            </div>
          ))}
        </div>
      )}

      {/* Submit button for multi-select */}
      {(multiSelect || optionsRequiringInput.length > 0) && !isSubmitted && (
        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className={clsx(
            'w-full py-2 px-4 rounded-lg font-medium transition-colors',
            canSubmit
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

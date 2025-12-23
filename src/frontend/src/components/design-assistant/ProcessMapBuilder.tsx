/**
 * Process map builder for capturing step-based workflows.
 */

import { useMemo, useState } from 'react';
import type { ProcessMapStep, ProcessMapSubmission } from '../../types/design-session';

interface ProcessMapBuilderProps {
  title: string;
  requiredFields: string[];
  edgeTypes?: string[];
  minSteps?: number;
  seedNodes?: string[];
  onSubmit: (payload: ProcessMapSubmission) => void;
}

function buildEmptyStep(): ProcessMapStep {
  return {
    step_name: '',
    owner: '',
    outcome: '',
    edge_type: 'sequence',
  };
}

function normalizeSteps(steps: ProcessMapStep[]): ProcessMapStep[] {
  return steps.filter(
    (step) =>
      step.step_name.trim() ||
      step.owner.trim() ||
      step.outcome.trim()
  );
}

export function ProcessMapBuilder({
  title,
  requiredFields,
  edgeTypes = ['sequence', 'approval', 'parallel'],
  minSteps = 1,
  seedNodes = [],
  onSubmit,
}: ProcessMapBuilderProps) {
  const initialSteps = useMemo(() => {
    if (seedNodes.length) {
      return seedNodes.map((node) => ({
        ...buildEmptyStep(),
        step_name: node,
      }));
    }
    return [buildEmptyStep()];
  }, [seedNodes]);

  const [steps, setSteps] = useState<ProcessMapStep[]>(initialSteps);
  const [error, setError] = useState<string | null>(null);

  const handleStepChange = (index: number, field: keyof ProcessMapStep, value: string) => {
    setSteps((prev) =>
      prev.map((step, idx) => (idx === index ? { ...step, [field]: value } : step))
    );
  };

  const handleAddStep = () => {
    setSteps((prev) => [...prev, buildEmptyStep()]);
  };

  const handleRemoveStep = (index: number) => {
    setSteps((prev) => prev.filter((_, idx) => idx !== index));
  };

  const handleSubmit = () => {
    const cleanedSteps = normalizeSteps(steps);
    if (cleanedSteps.length < minSteps) {
      setError(`Add at least ${minSteps} steps.`);
      return;
    }

    const missingRequired = cleanedSteps.some((step) =>
      requiredFields.some((field) => {
        const value = (step as Record<string, string>)[field] || '';
        return !value.trim();
      })
    );

    if (missingRequired) {
      setError('Fill all required fields before submitting.');
      return;
    }

    setError(null);
    onSubmit({
      title,
      steps: cleanedSteps,
    });
  };

  return (
    <div className="mt-4 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
        <p className="text-xs text-gray-500 mt-1">
          Capture each step with ownership and outcomes.
        </p>
      </div>

      <div className="space-y-3">
        {steps.map((step, index) => (
          <div
            key={index}
            className="rounded-lg border border-gray-200 bg-white p-3 space-y-2"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-gray-500">
                Step {index + 1}
              </span>
              {steps.length > 1 && (
                <button
                  type="button"
                  onClick={() => handleRemoveStep(index)}
                  className="text-xs text-gray-400 hover:text-red-500"
                >
                  Remove
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              <input
                value={step.step_name}
                onChange={(event) => handleStepChange(index, 'step_name', event.target.value)}
                placeholder="Step name"
                className="rounded-md border border-gray-200 p-2 text-xs focus:border-blue-300 focus:outline-none"
              />
              <input
                value={step.owner}
                onChange={(event) => handleStepChange(index, 'owner', event.target.value)}
                placeholder="Owner"
                className="rounded-md border border-gray-200 p-2 text-xs focus:border-blue-300 focus:outline-none"
              />
              <input
                value={step.outcome}
                onChange={(event) => handleStepChange(index, 'outcome', event.target.value)}
                placeholder="Outcome"
                className="rounded-md border border-gray-200 p-2 text-xs focus:border-blue-300 focus:outline-none"
              />
            </div>

            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-500">Edge type</label>
              <select
                value={step.edge_type || 'sequence'}
                onChange={(event) => handleStepChange(index, 'edge_type', event.target.value)}
                className="rounded-md border border-gray-200 p-1 text-xs focus:border-blue-300 focus:outline-none"
              >
                {edgeTypes.map((edge) => (
                  <option key={edge} value={edge}>
                    {edge}
                  </option>
                ))}
              </select>
            </div>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <button
          type="button"
          onClick={handleAddStep}
          className="rounded-md border border-gray-200 px-3 py-1 text-xs text-gray-600 hover:bg-gray-50"
        >
          Add step
        </button>
        <div className="flex items-center gap-3">
          {error && <span className="text-xs text-red-500">{error}</span>}
          <button
            type="button"
            onClick={handleSubmit}
            className="rounded-md bg-blue-600 px-4 py-1 text-xs text-white hover:bg-blue-700"
          >
            Submit map
          </button>
        </div>
      </div>
    </div>
  );
}

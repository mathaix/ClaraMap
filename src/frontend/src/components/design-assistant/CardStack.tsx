/**
 * Card stack component for card-orchestrated interview setup.
 */

import type { ReactNode } from 'react';
import clsx from 'clsx';
import type { CardEnvelope, CardBody, AskOption } from '../../types/design-session';

export interface PersonaEntry {
  id: string;
  label: string;
  role?: string;
  summary?: string;
  tier?: string;
  tags?: string[];
}

interface CardStackProps {
  cards: CardEnvelope[];
  onPersonaSelect?: (persona: PersonaEntry) => void;
  activePersonaId?: string | null;
  onAction?: (actionId: string, cardId: string) => void;
}

interface PersonaCardStackProps {
  cards?: CardEnvelope[];
  options?: AskOption[];
  onPersonaSelect?: (persona: PersonaEntry) => void;
  activePersonaId?: string | null;
}

const STEP_STATUS_STYLES: Record<string, string> = {
  done: 'bg-green-500',
  current: 'bg-blue-600',
  upcoming: 'bg-gray-300',
  optional: 'bg-amber-400',
  locked: 'bg-gray-300',
  draft: 'bg-gray-300',
};

const ACTION_STYLE_MAP: Record<string, string> = {
  primary: 'bg-blue-600 text-white',
  secondary: 'bg-gray-100 text-gray-700',
  ghost: 'bg-transparent text-gray-500 border border-gray-200',
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isStringArray(value: unknown): value is string[] {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every((item) => typeof item === 'string')
  );
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function asString(value: unknown): string | null {
  if (isNonEmptyString(value)) return value.trim();
  if (typeof value === 'number') return String(value);
  return null;
}

function asStringArray(value: unknown): string[] | null {
  if (!Array.isArray(value)) return null;
  const list = value.filter((item) => typeof item === 'string' && item.trim().length > 0);
  return list.length ? list.map((item) => item.trim()) : null;
}

function normalizeId(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '');
}

function formatKeyLabel(key: string): string {
  return key.replace(/_/g, ' ');
}

function renderValue(value: unknown, depth = 0): ReactNode {
  if (value === null || value === undefined) return null;
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return <span className="text-sm text-gray-700">{String(value)}</span>;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return null;
    if (value.every((item) => typeof item === 'string')) {
      return (
        <ul className="mt-1 space-y-1">
          {value.map((item, idx) => (
            <li key={`${item}-${idx}`} className="text-sm text-gray-700">
              {item}
            </li>
          ))}
        </ul>
      );
    }
    return (
      <ul className="mt-1 space-y-1">
        {value.map((item, idx) => (
          <li key={`item-${idx}`} className="text-sm text-gray-700">
            {renderValue(item, depth + 1)}
          </li>
        ))}
      </ul>
    );
  }
  if (isRecord(value)) {
    if (depth > 2) {
      return <span className="text-sm text-gray-500">Details available</span>;
    }
    return (
      <div className="mt-2 space-y-1">
        {Object.entries(value).map(([entryKey, entryValue]) => (
          <div key={entryKey} className="flex flex-col gap-1">
            <span className="text-xs uppercase tracking-wide text-gray-400">
              {formatKeyLabel(entryKey)}
            </span>
            {renderValue(entryValue, depth + 1)}
          </div>
        ))}
      </div>
    );
  }
  return null;
}

function renderStepList(steps: unknown[], depth = 0): ReactNode {
  return (
    <ol className={clsx('space-y-2', depth > 0 ? 'mt-2 ml-4 border-l border-gray-200 pl-3' : 'mt-3')}>
      {steps.map((step, index) => {
        if (!isRecord(step)) return null;
        const label = typeof step.label === 'string' ? step.label : `Step ${index + 1}`;
        const status = typeof step.status === 'string' ? step.status : 'upcoming';
        const dotClass = STEP_STATUS_STYLES[status] || STEP_STATUS_STYLES.upcoming;
        const substeps = Array.isArray(step.substeps) ? step.substeps : [];

        return (
          <li key={`${label}-${index}`} className="text-sm text-gray-700">
            <div className="flex items-center gap-2">
              <span
                className={clsx(
                  depth > 0 ? 'h-2 w-2' : 'h-2.5 w-2.5',
                  'rounded-full',
                  dotClass
                )}
              />
              <span
                className={clsx(
                  status === 'current' ? 'font-semibold text-gray-900' : 'font-medium'
                )}
              >
                {label}
              </span>
              <span className="text-xs uppercase tracking-wide text-gray-400">{status}</span>
            </div>
            {substeps.length > 0 ? renderStepList(substeps, depth + 1) : null}
          </li>
        );
      })}
    </ol>
  );
}

function renderStepper(body: Record<string, unknown>): ReactNode {
  const steps = body.steps;
  if (!Array.isArray(steps)) return null;
  return renderStepList(steps);
}

function buildPersonaEntry(
  raw: Record<string, unknown>,
  fallbackLabel: string,
  tier?: string
): PersonaEntry {
  const label =
    asString(raw.name) ??
    asString(raw.title) ??
    asString(raw.label) ??
    asString(raw.role) ??
    fallbackLabel;
  const role = asString(raw.role);
  const summary =
    asString(raw.summary) ??
    asString(raw.description) ??
    asString(raw.goal) ??
    asString(raw.context);
  const tags =
    asStringArray(raw.tags) ??
    asStringArray(raw.focus_areas) ??
    asStringArray(raw.responsibilities) ??
    asStringArray(raw.topics) ??
    undefined;
  const normalized = normalizeId(label);
  const fallbackId = normalizeId(fallbackLabel) || fallbackLabel;
  const id = asString(raw.id) ?? (normalized || fallbackId);

  const resolvedTier = asString(raw.tier) ?? tier;

  return {
    id,
    label,
    role: role ?? undefined,
    summary: summary ?? undefined,
    tier: resolvedTier ?? undefined,
    tags,
  };
}

function extractPersonasFromList(list: unknown[], tier?: string): PersonaEntry[] {
  return list
    .map((item, index) => {
      if (typeof item === 'string' && item.trim().length > 0) {
        const label = item.trim();
        return {
          id: normalizeId(label) || `persona-${index + 1}`,
          label,
          tier,
        };
      }
      if (!isRecord(item)) return null;
      return buildPersonaEntry(item, `Persona ${index + 1}`, tier);
    })
    .filter((entry): entry is PersonaEntry => entry !== null);
}

function extractPersonas(body: CardBody): PersonaEntry[] {
  if (Array.isArray(body)) {
    return extractPersonasFromList(body);
  }
  if (!isRecord(body)) return [];

  if (Array.isArray(body.personas)) {
    return extractPersonasFromList(body.personas);
  }
  if (isRecord(body.personas)) {
    const grouped: PersonaEntry[] = [];
    const personaGroups = body.personas as Record<string, unknown>;
    ['must', 'should', 'nice', 'primary', 'secondary', 'optional'].forEach((tier) => {
      const value = personaGroups[tier];
      if (Array.isArray(value)) {
        grouped.push(...extractPersonasFromList(value, tier));
      }
    });
    if (grouped.length) return grouped;
  }

  const tiers: Array<[string, string]> = [
    ['must', 'must'],
    ['should', 'should'],
    ['nice', 'nice'],
    ['primary', 'primary'],
    ['secondary', 'secondary'],
    ['optional', 'optional'],
  ];
  const grouped: PersonaEntry[] = [];
  tiers.forEach(([key, tier]) => {
    const value = body[key];
    if (Array.isArray(value)) {
      grouped.push(...extractPersonasFromList(value, tier));
    }
  });
  if (grouped.length) return grouped;

  if (Array.isArray(body.people)) {
    return extractPersonasFromList(body.people);
  }
  if (Array.isArray(body.audiences)) {
    return extractPersonasFromList(body.audiences);
  }

  return [];
}

function extractPersonasFromOptions(options: AskOption[]): PersonaEntry[] {
  const results: PersonaEntry[] = [];
  for (let i = 0; i < options.length; i++) {
    const option = options[i];
    if (!option.label) continue;
    const label = option.label.trim();
    if (!label) continue;
    results.push({
      id: option.id || normalizeId(label) || `persona-${i + 1}`,
      label,
      summary: option.description?.trim(),
    });
  }
  return results;
}

function getActiveStepperLabel(cards?: CardEnvelope[]): string | null {
  if (!cards?.length) return null;
  const stepperCard = cards.find((card) => card.type.toLowerCase() === 'stepper');
  if (!stepperCard || !isRecord(stepperCard.body)) return null;

  const steps = stepperCard.body.steps;
  if (!Array.isArray(steps) || steps.length === 0) return null;

  const currentStepRaw = stepperCard.body.current_step;
  const currentStep =
    typeof currentStepRaw === 'number'
      ? currentStepRaw
      : Number.parseInt(String(currentStepRaw || ''), 10);
  if (Number.isFinite(currentStep) && currentStep > 0 && currentStep <= steps.length) {
    const entry = steps[currentStep - 1];
    if (isRecord(entry) && typeof entry.label === 'string') {
      return entry.label;
    }
  }

  const activeStep = steps.find((step) => {
    if (!isRecord(step)) return false;
    const status = typeof step.status === 'string' ? step.status.toLowerCase() : '';
    return status === 'current' || status === 'active' || status === 'in_progress';
  });

  if (activeStep && typeof activeStep.label === 'string') {
    return activeStep.label;
  }

  return null;
}

function isPersonaStep(cards?: CardEnvelope[]): boolean {
  const label = getActiveStepperLabel(cards);
  return label ? label.toLowerCase().includes('persona') : false;
}

function renderPersonasCard(
  card: CardEnvelope,
  onPersonaSelect?: (persona: PersonaEntry) => void,
  activePersonaId?: string | null
): ReactNode {
  const personas = extractPersonas(card.body);
  if (!personas.length) {
    return renderValue(card.body);
  }

  return renderPersonaList(personas, onPersonaSelect, activePersonaId);
}

function renderPersonaList(
  personas: PersonaEntry[],
  onPersonaSelect?: (persona: PersonaEntry) => void,
  activePersonaId?: string | null
): ReactNode {
  if (!personas.length) return null;

  const instruction =
    onPersonaSelect ? "Click a persona card to continue in that person's context." : null;

  return (
    <div className="mt-3 space-y-3">
      {instruction ? (
        <p className="text-xs text-gray-500">{instruction}</p>
      ) : null}
      <div className="space-y-3">
        {personas.map((persona, index) => {
          const isActive = activePersonaId === persona.id;
          const isInteractive = Boolean(onPersonaSelect);
          const cardContent = (
            <>
              <div className="flex items-start justify-between gap-3">
                <div>
                  {persona.tier && (
                    <p className="text-[10px] uppercase tracking-wide text-gray-400">
                      {persona.tier}
                    </p>
                  )}
                  <h5 className="text-sm font-semibold text-gray-900">{persona.label}</h5>
                  {persona.role && persona.role !== persona.label && (
                    <p className="text-xs text-gray-500">{persona.role}</p>
                  )}
                </div>
                {isActive && (
                  <span className="rounded-full bg-blue-50 px-2 py-1 text-[10px] font-semibold text-blue-700">
                    Active
                  </span>
                )}
              </div>
              {persona.summary && (
                <p className="mt-2 text-xs text-gray-600">{persona.summary}</p>
              )}
              {persona.tags && persona.tags.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {persona.tags.slice(0, 4).map((tag) => (
                    <span
                      key={`${persona.id}-${tag}`}
                      className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-600"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </>
          );

          const classes = clsx(
            'relative w-full rounded-xl border px-4 py-3 text-left shadow-sm transition',
            isActive ? 'border-blue-400 bg-blue-50/40' : 'border-gray-200 bg-white',
            isInteractive && 'hover:border-blue-300 hover:shadow-md'
          );

          return (
            <div key={`${persona.id}-${index}`} className={clsx(index > 0 && '-mt-1')}>
              {isInteractive ? (
                <button
                  type="button"
                  className={classes}
                  onClick={() => onPersonaSelect?.(persona)}
                >
                  {cardContent}
                </button>
              ) : (
                <div className={classes}>{cardContent}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function renderCardBody(
  card: CardEnvelope,
  onPersonaSelect?: (persona: PersonaEntry) => void,
  activePersonaId?: string | null
): ReactNode {
  const body: CardBody = card.body;
  const cardType = card.type.toLowerCase();
  if (cardType === 'stepper' && isRecord(body)) {
    return renderStepper(body);
  }
  if (cardType === 'personas' || cardType === 'persona') {
    return renderPersonasCard(card, onPersonaSelect, activePersonaId);
  }
  if (typeof body === 'string') {
    return <p className="mt-3 text-sm text-gray-700">{body}</p>;
  }
  if (isStringArray(body)) {
    return (
      <ul className="mt-3 space-y-1">
        {body.map((item, idx) => (
          <li key={`${item}-${idx}`} className="text-sm text-gray-700">
            {item}
          </li>
        ))}
      </ul>
    );
  }
  if (isRecord(body)) {
    return <div className="mt-3">{renderValue(body)}</div>;
  }
  return null;
}

function renderHelper(helper: CardEnvelope['helper']): ReactNode {
  if (!helper) return null;
  const hasWhy = helper.why_this && helper.why_this.length > 0;
  const hasRisks = helper.risks_if_skipped && helper.risks_if_skipped.length > 0;
  if (!hasWhy && !hasRisks) return null;

  return (
    <div className="mt-3 space-y-2 border-t border-gray-100 pt-3 text-xs text-gray-500">
      {hasWhy && (
        <div>
          <p className="text-[10px] uppercase tracking-wide text-gray-400">Why this</p>
          <ul className="mt-1 space-y-1">
            {helper.why_this?.map((item, idx) => (
              <li key={`why-${idx}`}>{item}</li>
            ))}
          </ul>
        </div>
      )}
      {hasRisks && (
        <div>
          <p className="text-[10px] uppercase tracking-wide text-gray-400">Risks if skipped</p>
          <ul className="mt-1 space-y-1">
            {helper.risks_if_skipped?.map((item, idx) => (
              <li key={`risk-${idx}`}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function renderActions(
  actions: CardEnvelope['actions'],
  cardId: string,
  onAction?: (actionId: string, cardId: string) => void
): ReactNode {
  if (!actions || actions.length === 0) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {actions.map((action) => {
        const styleClass = ACTION_STYLE_MAP[action.style || ''] || 'bg-gray-100 text-gray-700';
        return (
          <button
            key={action.id}
            type="button"
            onClick={() => onAction?.(action.id, cardId)}
            disabled={!onAction}
            className={clsx(
              'inline-flex items-center rounded-full px-3 py-1 text-xs font-medium transition-colors',
              styleClass,
              onAction && 'hover:opacity-80 cursor-pointer',
              !onAction && 'cursor-default'
            )}
          >
            {action.label}
          </button>
        );
      })}
    </div>
  );
}

export function CardStack({ cards, onPersonaSelect, activePersonaId, onAction }: CardStackProps) {
  if (!cards.length) return null;

  return (
    <div className="space-y-3">
      {cards.map((card) => (
        <div
          key={card.card_id}
          className="rounded-xl border border-gray-200 bg-white px-4 py-3 shadow-sm"
        >
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-[10px] uppercase tracking-wide text-gray-400">
                {card.type}
              </p>
              <h4 className="text-sm font-semibold text-gray-900">{card.title}</h4>
              {card.subtitle && (
                <p className="text-xs text-gray-500">{card.subtitle}</p>
              )}
            </div>
          </div>
          {renderCardBody(card, onPersonaSelect, activePersonaId)}
          {renderActions(card.actions, card.card_id, onAction)}
          {renderHelper(card.helper)}
        </div>
      ))}
    </div>
  );
}

export function PersonaCardStack({
  cards,
  options,
  onPersonaSelect,
  activePersonaId,
}: PersonaCardStackProps) {
  if (!cards?.length && !options?.length) return null;

  const personaCard = cards?.find((card) => {
    const cardType = card.type.toLowerCase();
    return cardType === 'personas' || cardType === 'persona';
  });

  if (personaCard) {
    const personas = extractPersonas(personaCard.body);
    if (personas.length) {
      return renderPersonaList(personas, onPersonaSelect, activePersonaId);
    }
  }

  if (options?.length && isPersonaStep(cards)) {
    const personas = extractPersonasFromOptions(options);
    if (personas.length) {
      return renderPersonaList(personas, onPersonaSelect, activePersonaId);
    }
  }

  return null;
}

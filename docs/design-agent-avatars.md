# Unique Avatars + Character Names for Interview Specialists

## Goal
Give each Interview Specialist a unique visual identity:
1. **Character name** - Fun, memorable name like "Atlas", "Nova", "Echo"
2. **Unique avatar** - Generated from the character name

Display: **Atlas** (Systems Consolidation Interview Specialist) with a unique avatar.

## Recommended Approach

### Part 1: Character Name Generation
Deterministic name picker based on agent ID hash. Names are memorable, professional-sounding, and diverse.

### Part 2: Avatar Generation (Boring Avatars)
Use **boring-avatars** npm package - lightweight React component (~3KB) that generates beautiful SVG avatars from the character name.

## Implementation

### Step 1: Install Package
```bash
cd src/frontend && npm install boring-avatars
```

### Step 2: Create Agent Name Generator
```tsx
// src/frontend/src/utils/agentNames.ts

// Curated list of memorable character names
const CHARACTER_NAMES = [
  'Atlas', 'Nova', 'Echo', 'Luna', 'Sage',
  'Phoenix', 'Orion', 'Iris', 'Zephyr', 'Clio',
  'Jasper', 'Maya', 'Felix', 'Aurora', 'Quinn',
  'River', 'Skylar', 'Ember', 'Rowan', 'Indigo',
  'Aria', 'Kai', 'Terra', 'Finn', 'Celeste',
  'Leo', 'Ivy', 'Aspen', 'Blake', 'Wren'
];

// Simple hash function for deterministic selection
function hashString(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

/**
 * Generate a character name deterministically from agent ID
 * Same ID always returns the same name
 */
export function getAgentCharacterName(agentId: string): string {
  const index = hashString(agentId) % CHARACTER_NAMES.length;
  return CHARACTER_NAMES[index];
}
```

### Step 3: Create AgentAvatar Component
Create a reusable avatar component with randomized styles:

```tsx
// src/frontend/src/components/AgentAvatar.tsx
import Avatar from 'boring-avatars';

type AvatarVariant = 'marble' | 'beam' | 'pixel' | 'sunset' | 'ring' | 'bauhaus';

interface AgentAvatarProps {
  name: string;
  size?: number;
  variant?: AvatarVariant; // Override auto-selection if needed
}

// Clara brand colors for avatar palette
const CLARA_COLORS = ['#3B82F6', '#8B5CF6', '#06B6D4', '#10B981', '#F59E0B'];

// Available styles for variety
const VARIANTS: AvatarVariant[] = ['beam', 'marble', 'bauhaus', 'pixel'];

// Simple hash function to pick variant deterministically from name
function hashString(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

export function AgentAvatar({ name, size = 40, variant }: AgentAvatarProps) {
  // Auto-select variant based on name hash if not explicitly provided
  const selectedVariant = variant ?? VARIANTS[hashString(name) % VARIANTS.length];

  return (
    <Avatar
      name={name}
      size={size}
      variant={selectedVariant}
      colors={CLARA_COLORS}
    />
  );
}
```

This ensures:
- Same agent name → same avatar (deterministic)
- Different agent names → likely different styles (varied)

### Step 4: Update ProjectDetailPage.tsx
Replace the static user icon SVG with `<AgentAvatar>`:

**Before (lines ~367-380):**
```tsx
<div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center">
  <svg className="w-6 h-6 text-blue-600" ...>
    {/* user silhouette path */}
  </svg>
</div>
```

**After:**
```tsx
<AgentAvatar name={getAgentCharacterName(agent.id)} size={48} />
```

Also update the display to show the character name:
```tsx
<h3 className="font-semibold text-gray-900">
  {getAgentCharacterName(agent.id)} <span className="text-gray-500 font-normal">({agent.name})</span>
</h3>
```

### Step 5: Update AgentConfiguredCard.tsx (Optional)
Same pattern for the Design Assistant conversation card if desired.

## Files to Modify

| File | Change |
|------|--------|
| `package.json` | Add `boring-avatars` dependency |
| `src/utils/agentNames.ts` | New utility (create) |
| `src/components/AgentAvatar.tsx` | New component (create) |
| `src/pages/ProjectDetailPage.tsx` | Replace static icon with AgentAvatar |
| `src/components/design-assistant/AgentConfiguredCard.tsx` | (Optional) Replace icon |

## Visual Examples

Boring Avatars styles:
- **beam**: Friendly face-like circles (recommended)
- **marble**: Organic gradient blobs
- **bauhaus**: Abstract geometric
- **pixel**: 8-bit style squares
- **sunset**: Layered gradient waves
- **ring**: Concentric circles

## Alternative Considered

**DiceBear** - More style options but requires either:
- External API calls (latency, dependency)
- Larger package size for local generation

Boring Avatars is simpler and sufficient for this use case.

# tsdown Config Pattern for TypeScript Monorepo Packages

## Context
When building TypeScript packages with tsdown in a pnpm monorepo, the config pattern matters for correct output.

## Pattern

```typescript
// packages/<package-name>/tsdown.config.ts
import { defineConfig } from 'tsdown';

export default defineConfig({
  entry: ['src/index.ts'],  // SINGLE entry point - the barrel file
  format: ['esm'],
  dts: true,
  clean: true,
  treeshake: true
});
```

## Key Rules

### 1. Single Entry Point
Use a SINGLE entry point: `['src/index.ts']`

**WRONG - Multiple entries:**
```typescript
entry: [
  'src/index.ts',
  'src/common.ts',
  'src/evidence.ts',
  'src/observation.ts',
  // ... all source files
]
```

**Why wrong:** Multiple entries produce duplicate module outputs. tsdown handles re-exports from the single index.ts barrel file correctly.

### 2. Barrel Export Pattern
Your `src/index.ts` should re-export everything:
```typescript
// src/index.ts
export * from './common';
export * from './evidence';
export * from './observation';
export * from './session';
export * from './claim';
export * from './proof';
```

### 3. Package.json Exports
Match the output format in package.json:
```json
{
  "main": "./dist/index.js",
  "module": "./dist/index.mjs",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "import": "./dist/index.mjs",
      "require": "./dist/index.js",
      "types": "./dist/index.d.ts"
    }
  }
}
```

## Common Pitfalls

### Pitfall 1: Multiple entries produce duplicate outputs
If you specify multiple entries, tsdown builds each as a separate entry point, creating duplicate `.js`, `.mjs`, `.d.ts` files that conflict.

### Pitfall 2: Missing `dts: true`
Without `dts: true`, TypeScript declaration files won't be generated, breaking type checking for consumers.

### Pitfall 3: Wrong format
Use `format: ['esm']` for modern packages. For dual ESM/CommonJS, use `format: ['esm', 'cjs']` but this is rarely needed in modern Node.js.

## VAP Project Examples

### Core Package (packages/core/tsdown.config.ts)
```typescript
import { defineConfig } from 'tsdown';

export default defineConfig({
  entry: [
    'src/index.ts',
    'src/common.ts',
    'src/observation.ts',
    'src/evidence.ts',
    'src/session.ts',
    'src/claim.ts',
    'src/proof.ts'
  ],
  format: ['esm'],
  dts: true,
  clean: true,
  treeshake: true
});
```

Wait - this actually HAS multiple entries! This is a special case because the package has sub-path exports (./observation, ./evidence, ./session). For this pattern, multiple entries ARE correct.

### Pipeline Package (packages/pipeline/tsdown.config.ts)
```typescript
import { defineConfig } from 'tsdown';

export default defineConfig({
  entry: ['src/index.ts'],  // Single entry - only barrel export
  format: ['esm'],
  dts: true,
  clean: true,
  treeshake: true
});
```

### Store Package (packages/store/tsdown.config.ts)
```typescript
import { defineConfig } from 'tsdown';

export default defineConfig({
  entry: ['src/index.ts'],
  format: ['esm'],
  dts: true,
  clean: true,
  treeshake: true
});
```

### Conformance Package (packages/conformance/tsdown.config.ts)
```typescript
import { defineConfig } from 'tsdown';

export default defineConfig({
  entry: ['src/index.ts'],
  format: ['esm'],
  dts: true,
  clean: true,
  treeshake: true
});
```

## Rule Summary

| Package Type | Entry Pattern | Reason |
|--------------|---------------|--------|
| Single barrel export (pipeline, store, conformance) | `['src/index.ts']` | Simple re-export, single output |
| Sub-path exports (core) | Multiple entries including sub-paths | Each sub-path needs its own entry |
| No sub-path exports | Single index.ts entry | Barrel handles all re-exports |

## Verification
After config change, run:
```bash
pnpm build --filter=@verified-attention/<package>
```

Check output:
- Single `dist/index.js` + `dist/index.mjs` + `dist/index.d.ts`
- For core: additional `dist/observation.js`, `dist/evidence.js`, etc.
- No duplicate files
- `pnpm typecheck` passes
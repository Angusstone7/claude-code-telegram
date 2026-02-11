# Research: Admin Panel UI Modernization

## R1: Tailwind CSS v4 Dark Theme via @theme

**Decision**: Replace all CSS custom property values in the single `@theme` block in `index.css`.

**Rationale**: Tailwind v4 uses CSS-based configuration (`@theme` directive) instead of JavaScript config files. The existing `index.css` already defines all color tokens — we simply change the values from light to dark. This is the most minimal and correct approach: one file change propagates to all components using semantic tokens (`bg-background`, `text-foreground`, `bg-card`, etc.).

**Alternatives considered**:
- Adding `dark:` variant classes to every component — rejected: 200+ className changes vs. 30 CSS variable changes
- Adding a `tailwind.config.ts` with darkMode configuration — rejected: Tailwind v4 doesn't use JS config by default
- Creating a separate dark theme CSS file — rejected: unnecessary complexity, single `@theme` block is sufficient

## R2: Glass Morphism Implementation with Tailwind

**Decision**: Use `backdrop-blur-[14px]` and `backdrop-saturate-[140%]` Tailwind arbitrary values on glass surfaces (sidebar, header, cards). Combine with semi-transparent `rgba()` backgrounds defined in CSS variables.

**Rationale**: Tailwind v4 supports arbitrary values via bracket notation. This avoids custom CSS — everything stays in className strings. The `backdrop-filter` property has 96%+ browser support (caniuse.com, 2026).

**Alternatives considered**:
- Custom CSS classes for glass effect — rejected: mixing CSS and Tailwind reduces consistency
- CSS `@supports` wrapper for each glass element — rejected: browser support is sufficient; fallback via opaque semi-transparent bg is automatic

## R3: Background Gradient Approach

**Decision**: Apply multi-layer radial gradient as inline style on the root layout container (`AppLayout.tsx`), not in CSS variables. This is because Tailwind v4 `@theme` does not support complex gradient values as custom properties for `background`.

**Rationale**: The cosmic gradient background (purple spot top-left, cyan spot top-right, pink spot bottom) needs to be applied once on the main container. Inline style is acceptable for a one-time application.

**Alternatives considered**:
- Defining gradient in `@theme` — rejected: CSS custom properties in `@theme` are limited to simple values for Tailwind token resolution
- Separate CSS class — acceptable but inline is simpler for a single use

## R4: Color Palette Selection

**Decision**: Primary purple `#7C6CFF`, accent cyan `#4DE1FF`, background `#0B0F17`, text `#E2E8F0`. These match the reference JARVIS Core Admin project.

**Rationale**: The user explicitly requested matching the reference project's aesthetic. These colors provide high contrast on dark backgrounds, feel modern (neon-on-dark), and have sufficient WCAG contrast ratios:
- `#E2E8F0` on `#0B0F17` = contrast ratio ~13.5:1 (AAA)
- `#94A3B8` on `#0B0F17` = contrast ratio ~7.2:1 (AA)
- `#7C6CFF` on `#0B0F17` = contrast ratio ~4.8:1 (AA for large text)

**Alternatives considered**:
- Tailwind's default slate palette for dark mode — rejected: user wants the specific purple/cyan aesthetic
- Shadcn/ui default dark theme — rejected: too generic, user wants premium feel

## R5: Component Modification Strategy

**Decision**: Modify classNames directly in component files. No new wrapper components or HOCs.

**Rationale**: The theme change is achieved primarily through CSS variable updates (which cascade automatically). Component-level changes are needed only for:
1. Adding `backdrop-blur` and `backdrop-saturate` to glass surfaces
2. Changing hardcoded color classes (e.g., `bg-blue-600` → `bg-primary`)
3. Adding hover/transition classes where missing
4. Updating border radius from `rounded-lg` to `rounded-xl` where appropriate

**Alternatives considered**:
- Creating a ThemeProvider context — rejected: overkill for CSS-variable-based theming
- Wrapping all cards in a `GlassCard` component — rejected: violates "no structural rewrite" constraint; inline classes are sufficient

## R6: Metric Card Icon Box Pattern

**Decision**: Replace the current solid colored background (`bg-blue-600`, `bg-purple-600`, etc.) on metric card icons with a softer tinted background using the color at 20% opacity: `bg-blue-500/20 text-blue-400`.

**Rationale**: The reference project uses this pattern for a more refined, modern look. Solid bright backgrounds feel flat and dated. Semi-transparent tints integrate with the glass morphism aesthetic.

**Alternatives considered**:
- Keeping solid backgrounds — rejected: clashes with glass morphism
- Gradient icon backgrounds — rejected: overly complex, diminishing returns

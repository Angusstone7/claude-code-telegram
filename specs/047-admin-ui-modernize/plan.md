# Implementation Plan: Admin Panel UI Modernization

**Branch**: `047-admin-ui-modernize` | **Date**: 2026-02-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/047-admin-ui-modernize/spec.md`

## Summary

Transform the admin panel from a generic light-themed UI into a modern dark-themed interface with glass morphism effects, inspired by the JARVIS Core Admin reference project. This is a **CSS/styling-only change** — no backend modifications, no new components, no structural rewrites. All changes happen in the frontend `src/` directory via Tailwind CSS v4 custom properties and component className updates.

## Technical Context

**Language/Version**: TypeScript 5.x, React 18+
**Primary Dependencies**: Tailwind CSS v4 (CSS-based config via `@theme`), lucide-react (icons), React Router, TanStack Query
**Storage**: N/A (no data model changes)
**Testing**: Visual verification (no unit tests for CSS-only changes)
**Target Platform**: Modern browsers (Chrome 90+, Firefox 90+, Safari 15+, Edge 90+)
**Project Type**: Frontend-only changes within existing web application
**Performance Goals**: No perceptible rendering slowdown from backdrop-filter; <16ms paint time
**Constraints**: `backdrop-filter` support required (fallback for unsupported browsers); `prefers-reduced-motion` respected
**Scale/Scope**: 11 pages, ~15 components affected; ~1 CSS file + ~20 component files to modify

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. SOLID | PASS | No new classes; only modifying CSS variables and className strings |
| II. DDD | PASS | No domain/business logic changes |
| III. OOP & Composition | PASS | No structural changes to component hierarchy |
| IV. Root Cause Resolution | PASS | Addresses root cause: outdated light theme with no visual depth |
| V. Modern Stack | PASS | Using Tailwind v4 CSS-based config (modern), glass morphism (contemporary pattern) |
| VI. DRY | PASS | Theme defined once via CSS custom properties, consumed everywhere via Tailwind classes |
| VII. Modularity | PASS | Theme is a single concern (index.css), components only change classNames |
| VIII. API & Contracts | N/A | No API changes |
| IX. No Hardcoding | PASS | All colors/sizes defined as CSS custom properties in `@theme`, not hardcoded in components |
| X. Prompt Management | N/A | No prompts involved |
| XI. Localization | PASS | No text changes; all i18n preserved |
| XII. Code Quality | PASS | Visual verification; existing behavior unchanged |

**Gate Result**: PASS — no violations.

## Project Structure

### Documentation (this feature)

```text
specs/047-admin-ui-modernize/
├── plan.md              # This file
├── research.md          # Phase 0: design system research
├── quickstart.md        # Phase 1: integration guide
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (files to modify)

```text
frontend/src/
├── index.css                              # PRIMARY: Theme variables (dark palette + glass tokens)
├── components/
│   ├── layout/
│   │   ├── AppLayout.tsx                  # Background gradients, content area styling
│   │   ├── Sidebar.tsx                    # Glass morphism sidebar, active states, hover transitions
│   │   └── Header.tsx                     # Glass morphism header, border treatment
│   ├── chat/
│   │   ├── ChatWindow.tsx                 # Dark message area background
│   │   ├── MessageBubble.tsx              # Message bubble colors (user=purple, assistant=glass)
│   │   ├── HITLCard.tsx                   # Card border/bg updates
│   │   ├── PlanCard.tsx                   # Card border/bg updates
│   │   ├── QuestionCard.tsx               # Card border/bg updates
│   │   └── FileUpload.tsx                 # Drop zone styling
│   ├── common/
│   │   ├── LoadingSpinner.tsx             # Spinner colors
│   │   └── EmptyState.tsx                 # Icon background, text colors
│   └── project/
│       ├── ProjectCard.tsx                # Card glass effect, hover
│       ├── ProjectList.tsx                # Form styling
│       ├── ContextList.tsx                # List item styling
│       └── VariableManager.tsx            # Table/form styling
├── pages/
│   ├── DashboardPage.tsx                  # Metric cards redesign, status badges
│   ├── ChatPage.tsx                       # Chat layout dark treatment
│   ├── LoginPage.tsx                      # Dark login card, centered
│   ├── ProjectsPage.tsx                   # Panel styling
│   ├── FileBrowserPage.tsx                # File list dark treatment
│   ├── SettingsPage.tsx                   # Form elements dark treatment
│   ├── DockerPage.tsx                     # Table/card dark treatment
│   ├── PluginsPage.tsx                    # Card dark treatment
│   ├── SSHPage.tsx                        # Terminal-like dark treatment
│   ├── GitLabPage.tsx                     # Card dark treatment
│   └── UsersPage.tsx                      # Table dark treatment
└── lib/
    └── utils.ts                           # No changes needed
```

**Structure Decision**: Frontend-only modification within the existing `frontend/src/` structure. No new directories or files need to be created — all changes are to existing files. The primary change is to `index.css` (theme definition), followed by className updates in component files.

## Design System Definition

### Color Palette

| Token | Current (Light) | New (Dark) | Usage |
|-------|-----------------|------------|-------|
| background | #ffffff | #0B0F17 | Page background |
| foreground | #0a0a0a | #E2E8F0 | Primary text |
| card | #ffffff | rgba(255,255,255,0.06) | Card surfaces |
| card-foreground | #0a0a0a | #E2E8F0 | Card text |
| popover | #ffffff | rgba(20,24,35,0.95) | Dropdowns, tooltips |
| popover-foreground | #0a0a0a | #E2E8F0 | Popover text |
| primary | #171717 | #7C6CFF | Buttons, links, active states |
| primary-foreground | #fafafa | #FFFFFF | Text on primary |
| secondary | #f5f5f5 | rgba(255,255,255,0.08) | Secondary surfaces |
| secondary-foreground | #171717 | #E2E8F0 | Secondary text |
| muted | #f5f5f5 | rgba(255,255,255,0.06) | Muted backgrounds |
| muted-foreground | #737373 | #94A3B8 | Muted text |
| accent | #f5f5f5 | rgba(124,108,255,0.15) | Accent backgrounds |
| accent-foreground | #171717 | #E2E8F0 | Accent text |
| destructive | #ef4444 | #EF4444 | Error/danger (unchanged) |
| border | #e5e5e5 | rgba(255,255,255,0.08) | Borders |
| input | #e5e5e5 | rgba(255,255,255,0.10) | Input borders |
| ring | #0a0a0a | #7C6CFF | Focus rings |

### Sidebar Tokens

| Token | Current | New |
|-------|---------|-----|
| sidebar-background | #fafafa | rgba(20,24,35,0.55) |
| sidebar-foreground | #0a0a0a | #CBD5E1 |
| sidebar-primary | #171717 | #7C6CFF |
| sidebar-primary-foreground | #fafafa | #FFFFFF |
| sidebar-accent | #f5f5f5 | rgba(124,108,255,0.15) |
| sidebar-accent-foreground | #171717 | #E2E8F0 |
| sidebar-border | #e5e5e5 | rgba(255,255,255,0.08) |
| sidebar-ring | #0a0a0a | #7C6CFF |

### Additional CSS Properties (new)

```css
/* Glass morphism tokens */
--glass-blur: blur(14px) saturate(140%);
--glass-bg: rgba(255,255,255,0.06);
--glass-border: 1px solid rgba(255,255,255,0.08);

/* Background gradient spots */
--bg-gradient:
  radial-gradient(900px circle at 10% 10%, rgba(124,108,255,0.20), transparent 55%),
  radial-gradient(800px circle at 90% 20%, rgba(77,225,255,0.12), transparent 55%),
  radial-gradient(900px circle at 50% 95%, rgba(255,77,148,0.08), transparent 60%),
  #0B0F17;

/* Shadows */
--shadow-card: 0 18px 60px rgba(0,0,0,0.35);
--shadow-inset: inset 0 1px 0 rgba(255,255,255,0.05);

/* Transitions */
--transition-default: 150ms ease;
```

### Component Patterns

**Glass Card**:
```
bg-card backdrop-blur-[14px] border border-border
shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]
hover:border-primary/50 transition-colors duration-150
```

**Glass Sidebar**:
```
bg-sidebar-background backdrop-blur-[14px] border-r border-sidebar-border
```

**Glass Header**:
```
bg-sidebar-background backdrop-blur-[14px] border-b border-border
```

**Metric Card Icon Box**:
```
rounded-xl p-2.5 bg-{color}/20 text-{color}
```

**Status Badge (Pill)**:
```
rounded-full px-2.5 py-1 text-xs font-medium
bg-green-500/15 text-green-400 (online)
bg-red-500/15 text-red-400 (offline)
```

**Buttons**:
```
rounded-xl normal-case transition-all duration-150
```

**Input Fields**:
```
bg-secondary border-input focus:border-primary focus:ring-primary/30 rounded-xl
```

## Complexity Tracking

> No constitution violations found — table intentionally empty.

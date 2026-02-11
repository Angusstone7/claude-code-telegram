# Feature Specification: Admin Panel UI Modernization

**Feature Branch**: `047-admin-ui-modernize`
**Created**: 2026-02-11
**Status**: Draft
**Input**: User description: "Modernize admin panel with contemporary design — glass morphism, dark theme, modern card styles, animations, and polished visual hierarchy inspired by JARVIS Core Admin reference project"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Modern Dark Theme & Glass Morphism (Priority: P1)

An administrator opens the admin panel and sees a sleek, dark-themed interface with glass morphism effects. Cards and panels have semi-transparent backgrounds with backdrop blur. The overall look feels premium and contemporary — similar to modern dashboard tools and macOS/Windows 11 aesthetics. The dark background uses subtle radial gradient color spots (purple and blue) for depth, and all surfaces (sidebar, header, cards) have frosted-glass effect.

**Why this priority**: The visual theme is the foundation — all other visual improvements depend on the base color scheme, background effects, and surface treatment being established first.

**Independent Test**: Can be tested by opening any page and verifying the dark background, glass card surfaces, and frosted sidebar/header are visible. The admin panel should feel visually cohesive and "premium" on first impression.

**Acceptance Scenarios**:

1. **Given** the admin panel is loaded, **When** the user views any page, **Then** the background is dark with subtle colored radial gradients
2. **Given** any card or panel element, **When** the user views it, **Then** it has semi-transparent background with visible backdrop blur effect
3. **Given** the sidebar and top header, **When** the user views them, **Then** they have frosted-glass appearance with subtle borders
4. **Given** any interactive card, **When** the user hovers over it, **Then** the border subtly highlights with an accent color

---

### User Story 2 - Improved Dashboard Layout & Metric Cards (Priority: P2)

The dashboard page displays system metrics in redesigned cards with colored icon boxes, large bold numbers, smooth progress bars with rounded ends, and clear visual hierarchy. Status badges use soft-colored pill shapes. The projects section has cards with hover effects. The overall layout has proper spacing, typography weight variations, and visual grouping.

**Why this priority**: The dashboard is the first page users see after login — its visual quality sets the tone for the entire experience.

**Independent Test**: Can be tested by logging in and checking the dashboard: metric cards should have colored icon backgrounds, bold metric values, rounded progress bars, and hover states on project cards.

**Acceptance Scenarios**:

1. **Given** the dashboard loads, **When** the user views metric cards, **Then** each card has a colored icon box, a large bold metric value, and a rounded progress bar
2. **Given** the dashboard loads, **When** the user views the Claude Status section, **Then** status badges are pill-shaped with color-coded backgrounds
3. **Given** project cards are visible, **When** the user hovers over a project card, **Then** the card's border subtly highlights and the card appears slightly elevated
4. **Given** any section heading, **When** the user reads it, **Then** typography has clear hierarchy — large bold headings, medium subheadings, smaller secondary text

---

### User Story 3 - Modernized Sidebar & Navigation (Priority: P3)

The sidebar navigation has a clean dark background with glass morphism, smooth icon+text alignment, active state highlighting with accent color, and hover transitions. The top header shows user info cleanly. The overall navigation feels smooth with no visual jarring.

**Why this priority**: Navigation is used constantly — improving its visual quality enhances every interaction with the panel.

**Independent Test**: Can be tested by clicking through sidebar menu items and verifying active states, hover effects, icon alignment, and smooth transitions.

**Acceptance Scenarios**:

1. **Given** the sidebar is visible, **When** the user views it, **Then** it has a dark semi-transparent background with a subtle right border
2. **Given** a sidebar menu item, **When** the user hovers over it, **Then** the background subtly highlights with a smooth transition
3. **Given** a sidebar menu item, **When** it is the active/current page, **Then** it is highlighted with the primary accent color
4. **Given** the top header, **When** the user views it, **Then** it has a frosted-glass background with subtle bottom border

---

### User Story 4 - Polished Form Elements & Buttons (Priority: P4)

All interactive elements — buttons, inputs, selects, toggles — have consistent modern styling: proper border radius, smooth transitions, focus states with accent color, and refined spacing. Buttons have no forced uppercase text.

**Why this priority**: Consistent interactive elements complete the modern feel across all pages (settings, login, chat input, etc.)

**Independent Test**: Can be tested by visiting the Settings or Login page and verifying buttons, inputs, and other form elements have modern styling with smooth hover/focus transitions.

**Acceptance Scenarios**:

1. **Given** any button in the interface, **When** the user views it, **Then** it has rounded corners, no uppercase transformation, and a smooth hover transition
2. **Given** any input field, **When** the user focuses on it, **Then** the border highlights with the accent color with a smooth transition
3. **Given** any form page (Login, Settings), **When** the user interacts with elements, **Then** all elements are visually consistent with the overall dark theme

---

### Edge Cases

- What happens when the browser does not support `backdrop-filter` (glass morphism)? Fallback to solid semi-transparent backgrounds.
- How does the interface look on very narrow screens (mobile)? Layout should remain functional with responsive grid adjustments.
- What if the user has `prefers-reduced-motion` enabled? Disable non-essential animations and transitions.
- How does the interface render when data is loading? Loading states should use subtle pulsing effects consistent with the dark theme.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The admin panel MUST use a dark color scheme with a near-black base background and semi-transparent surfaces
- **FR-002**: All card-type components MUST have semi-transparent backgrounds with backdrop blur for glass morphism effect
- **FR-003**: The sidebar MUST have a dark glass-morphism background with a subtle right border separator
- **FR-004**: The top header bar MUST have a frosted-glass background with a subtle bottom border
- **FR-005**: Metric cards on the dashboard MUST display icons in colored background boxes, large bold values, and rounded progress bars
- **FR-006**: Interactive elements (cards, buttons, menu items) MUST have smooth hover transitions
- **FR-007**: The active sidebar item MUST be visually highlighted with the primary accent color
- **FR-008**: Buttons MUST have rounded corners, no uppercase text transformation
- **FR-009**: The background MUST include subtle radial gradient color spots for visual depth
- **FR-010**: Status badges MUST be pill-shaped with color-coded backgrounds matching their state
- **FR-011**: The interface MUST gracefully degrade when backdrop-filter is not supported
- **FR-012**: The interface MUST respect prefers-reduced-motion media query by disabling non-essential animations

### Key Entities

- **Theme Configuration**: Color palette (primary purple, accent cyan, background, surface colors), border radius values, transition timings, shadow definitions
- **Component Surfaces**: Cards, sidebar, header, modals — each with defined transparency, blur, and border treatments
- **Interactive States**: Default, hover, active, focus, disabled — each with defined visual treatment

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users rate the admin panel appearance as "modern" or "professional" — significant visual improvement vs. current design
- **SC-002**: All pages render correctly with the new theme without perceptible slowdown from glass effects
- **SC-003**: All interactive elements have visible hover/focus states — 100% coverage across all pages
- **SC-004**: The interface remains functional (no layout breaks) on viewports from 320px to 2560px width
- **SC-005**: Zero visual regression on existing functionality — all features (dashboard, chat, projects, settings, docker, SSH, etc.) remain fully operational

## Assumptions

- The admin panel already uses Tailwind CSS — new styles will be implemented via Tailwind utility classes and CSS custom properties
- The current light theme will be replaced entirely with a dark theme (no theme toggle needed)
- The existing component structure (pages, layout, cards) will be preserved — this is a visual redesign, not a structural rewrite
- The primary brand color will be purple with cyan as accent, matching the reference project's palette
- All existing functionality must be preserved — this is purely a visual enhancement

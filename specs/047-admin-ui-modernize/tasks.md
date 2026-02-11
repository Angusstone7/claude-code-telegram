# Tasks: Admin Panel UI Modernization

**Input**: Design documents from `/specs/047-admin-ui-modernize/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, quickstart.md

**Tests**: Not applicable — this is a CSS/styling-only change with visual verification.

**Organization**: Tasks grouped by user story. Each story can be verified independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- All file paths relative to repository root

---

## Phase 1: Setup (Theme Foundation)

**Purpose**: Replace the light color palette with dark palette in CSS custom properties. This single change cascades to all components using Tailwind semantic classes.

- [X] T001 Update dark color palette in `@theme` block in frontend/src/index.css — replace all 22 color variables (background, foreground, card, primary, secondary, muted, accent, border, input, ring, sidebar-*) with dark values per plan.md Color Palette table
- [X] T002 Add glass morphism utility styles and backdrop-filter fallback in frontend/src/index.css — add `@layer base` styles for `.glass` utility class, `@supports` fallback for backdrop-filter, and `prefers-reduced-motion` media query to disable transitions

**Checkpoint**: After T001-T002, opening any page should show dark background and light text. Most elements auto-adapt via Tailwind semantic classes.

---

## Phase 2: Foundational (Layout Shell)

**Purpose**: Apply glass morphism to the main layout containers (AppLayout, Sidebar, Header) that wrap ALL pages. MUST complete before user story work.

**⚠️ CRITICAL**: Layout shell affects every page — must be done first.

- [X] T003 Update AppLayout in frontend/src/components/layout/AppLayout.tsx — add multi-layer radial gradient background (purple at 10%/10%, cyan at 90%/20%, pink at 50%/95% over #0B0F17) as inline style on root container; update content area with `overflow-y-auto` and proper dark scrollbar styling
- [X] T004 [P] Update Sidebar in frontend/src/components/layout/Sidebar.tsx — add `backdrop-blur-[14px] backdrop-saturate-[140%]` to sidebar container; update active nav item to use `bg-accent text-primary font-medium` with left accent border (`border-l-2 border-primary`); add `gap-3` for icon-text alignment; add `hover:bg-secondary transition-colors duration-150` to nav items; update "Admin Panel" logo text to use `text-primary font-bold`; ensure smooth `transition-all duration-150` on all interactive items
- [X] T005 [P] Update Header in frontend/src/components/layout/Header.tsx — add `backdrop-blur-[14px] backdrop-saturate-[140%]` to header container; update border to use theme border color; update language selector dropdown styling for dark theme (dark popover bg, light text); update user display section with proper contrast; update logout button hover state to `hover:bg-destructive/15 hover:text-destructive transition-colors duration-150`

**Checkpoint**: Sidebar + Header now have glass morphism. All pages inherit dark background with gradient.

---

## Phase 3: User Story 1 - Dark Theme & Glass Morphism (Priority: P1) 🎯 MVP

**Goal**: All card-type surfaces across the app have glass morphism (semi-transparent bg + backdrop blur + subtle border). Interactive cards have hover effects.

**Independent Test**: Open any page — cards should have frosted-glass appearance with subtle borders, and highlight on hover.

### Implementation for User Story 1

- [X] T006 [US1] Update common EmptyState component in frontend/src/components/common/EmptyState.tsx — change icon container from `bg-gray-100` to `bg-secondary rounded-xl`; update text colors for dark theme
- [X] T007 [P] [US1] Update common LoadingSpinner component in frontend/src/components/common/LoadingSpinner.tsx — change spinner border from `border-gray-300 border-t-blue-600` to `border-muted-foreground/30 border-t-primary`
- [X] T008 [P] [US1] Update LoginPage in frontend/src/pages/LoginPage.tsx — add glass card effect to login container (`backdrop-blur-[14px] border border-border shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]`); update error alert colors for dark background; update input fields and button styling for dark theme; add radial gradient background to login page wrapper
- [X] T009 [P] [US1] Update ProjectCard in frontend/src/components/project/ProjectCard.tsx — add `backdrop-blur-[14px] hover:border-primary/50 transition-colors duration-150` to card container; update active state border color
- [X] T010 [P] [US1] Update ProjectList in frontend/src/components/project/ProjectList.tsx — update create project form inputs and button for dark theme; update list container borders
- [X] T011 [P] [US1] Update ContextList in frontend/src/components/project/ContextList.tsx — update list item hover states; update action button colors for dark theme; update create form inputs
- [X] T012 [P] [US1] Update VariableManager in frontend/src/components/project/VariableManager.tsx — update filter buttons, form inputs, scope badges, and table rows for dark theme; add hover transitions to variable items

**Checkpoint**: US1 complete — all surfaces have consistent glass morphism. Login, project management, and common components match the dark theme.

---

## Phase 4: User Story 2 - Dashboard Metric Cards (Priority: P2)

**Goal**: Dashboard displays redesigned metric cards with tinted icon boxes, bold values, rounded progress bars, pill status badges, and hover effects on project cards.

**Independent Test**: Login and view dashboard — metric cards have colored icon backgrounds (not solid), bold numbers, smooth progress bars; status badges are pill-shaped; project cards highlight on hover.

### Implementation for User Story 2

- [X] T013 [US2] Redesign MetricCard component in frontend/src/pages/DashboardPage.tsx — change icon container from solid `bg-{color}` to tinted `bg-{color}/20 text-{color}` with `rounded-xl p-2.5`; increase value font to `text-2xl font-bold`; update progress bar to `rounded-full` with height increase; add `backdrop-blur-[14px] hover:border-primary/50 transition-colors duration-150` to card wrapper
- [X] T014 [US2] Redesign StatusBadge component in frontend/src/pages/DashboardPage.tsx — change to pill shape with `rounded-full`; use semi-transparent backgrounds `bg-green-500/15 text-green-400` for online and `bg-red-500/15 text-red-400` for offline; update indicator dot styling
- [X] T015 [US2] Update Dashboard projects section in frontend/src/pages/DashboardPage.tsx — add `hover:border-primary/50 transition-all duration-150 hover:-translate-y-0.5` to project cards; update section heading typography to `text-xl font-bold`; ensure glass card styling on each project card

**Checkpoint**: US2 complete — dashboard is the visual showcase of the new design.

---

## Phase 5: User Story 3 - Sidebar & Navigation (Priority: P3)

**Goal**: Sidebar navigation has smooth transitions, purple accent active state, and clean icon alignment. Header displays user info cleanly.

**Independent Test**: Click through all sidebar items — active state shows purple highlight, hover has smooth transition, icons align with text.

### Implementation for User Story 3

- [X] T016 [US3] Verify Sidebar navigation states in frontend/src/components/layout/Sidebar.tsx — confirm active item styling from T004 renders correctly (`bg-accent text-primary font-medium`, `border-l-2 border-primary`, `gap-3`); verify transitions are smooth; adjust any remaining visual inconsistencies
- [X] T017 [US3] Verify Header layout in frontend/src/components/layout/Header.tsx — confirm dropdown styling, user display contrast, and logout hover state from T005 render correctly; adjust any remaining visual inconsistencies

**Checkpoint**: US3 complete — navigation feels polished and responsive.

---

## Phase 6: User Story 4 - Polished Form Elements & Buttons (Priority: P4)

**Goal**: All interactive elements have consistent modern styling: rounded-xl corners, smooth transitions, accent focus states.

**Independent Test**: Visit Settings, Login, and Chat pages — all buttons have rounded corners and smooth hover; all inputs highlight with purple on focus.

### Implementation for User Story 4

- [X] T018 [US4] Update SettingsPage form elements in frontend/src/pages/SettingsPage.tsx — update all `<input>`, `<select>`, `<button>` elements with `rounded-xl transition-all duration-150`; update focus states to `focus:border-primary focus:ring-2 focus:ring-primary/30`; update save button to `bg-primary hover:bg-primary/90 text-primary-foreground rounded-xl`; update toggle switches for dark theme
- [X] T019 [P] [US4] Update ChatPage input area in frontend/src/pages/ChatPage.tsx — update chat input textarea with dark bg, rounded-xl, accent focus ring; update send button styling; update connection badge for dark theme; update session sidebar panel styling
- [X] T020 [P] [US4] Update chat components for dark theme in frontend/src/components/chat/MessageBubble.tsx — change user message bubble from `bg-blue-600` to `bg-primary/20 border border-primary/30`; change assistant bubble border for dark theme; update code block background to `bg-black/30 rounded-lg`; update timestamp and tool badge colors
- [X] T021 [P] [US4] Update interactive chat cards in frontend/src/components/chat/HITLCard.tsx, frontend/src/components/chat/PlanCard.tsx, frontend/src/components/chat/QuestionCard.tsx — update card borders, backgrounds, and button colors for dark theme; update approve/reject buttons with rounded-xl and transitions
- [X] T022 [P] [US4] Update FileUpload in frontend/src/components/chat/FileUpload.tsx — update drop zone border and background for dark theme; update progress bar and file preview styling

**Checkpoint**: US4 complete — all interactive elements consistent across all pages.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Apply dark theme to remaining pages and ensure visual consistency across the entire admin panel.

- [X] T023 [P] Update ProjectsPage in frontend/src/pages/ProjectsPage.tsx — update panel dividers, empty states, and section headers for dark theme
- [X] T024 [P] Update FileBrowserPage in frontend/src/pages/FileBrowserPage.tsx — update breadcrumbs, file list items, folder icons, create folder form for dark theme; add hover transitions to file entries
- [X] T025 [P] Update DockerPage in frontend/src/pages/DockerPage.tsx — update container cards/tables, status indicators, and action buttons for dark theme
- [X] T026 [P] Update SSHPage in frontend/src/pages/SSHPage.tsx — update terminal-style output area with dark bg; update command input and buttons for dark theme
- [X] T027 [P] Update PluginsPage in frontend/src/pages/PluginsPage.tsx — update plugin cards with glass effect and hover transitions for dark theme
- [X] T028 [P] Update GitLabPage in frontend/src/pages/GitLabPage.tsx — update GitLab integration cards and forms for dark theme
- [X] T029 [P] Update UsersPage in frontend/src/pages/UsersPage.tsx — update user table, role badges, and action buttons for dark theme
- [X] T030 Update ChatWindow in frontend/src/components/chat/ChatWindow.tsx — update empty state, date separators, and scroll area background for dark theme
- [X] T031 Visual verification of all 11 pages — open each page (Dashboard, Chat, Projects, Files, Settings, Docker, Plugins, SSH, GitLab, Users, Login) and verify: (1) consistent dark theme, no broken layouts, all text readable, all interactive elements have hover/focus states; (2) responsive layout at viewport breakpoints 320px, 768px, 1440px, 2560px (SC-004); (3) backdrop-filter disabled fallback renders solid semi-transparent backgrounds (FR-011); (4) prefers-reduced-motion emulation disables non-essential animations (FR-012)

**Checkpoint**: All pages visually consistent. Admin panel modernization complete.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — layout shell needs theme vars
- **User Stories (Phase 3-6)**: All depend on Phase 2 — layout must be dark before component updates
  - US1 (P1): Can start after Phase 2
  - US2 (P2): Can start after Phase 2 (independent of US1)
  - US3 (P3): Can start after Phase 2 (refines Phase 2 sidebar/header work)
  - US4 (P4): Can start after Phase 2 (independent of US1-US3)
- **Polish (Phase 7)**: Depends on Phase 2 minimum; can start in parallel with US phases

### User Story Dependencies

- **US1 (P1)**: After Phase 2 — no dependencies on other stories
- **US2 (P2)**: After Phase 2 — no dependencies on other stories
- **US3 (P3)**: After Phase 2 — refines sidebar/header from Phase 2 foundational work
- **US4 (P4)**: After Phase 2 — no dependencies on other stories

### Within Each User Story

- Tasks marked [P] within a story can run in parallel (different files)
- Tasks without [P] have sequential dependencies within their story

### Parallel Opportunities

- T004 + T005 can run in parallel (Sidebar + Header, different files)
- T006 + T007 + T008 + T009 + T010 + T011 + T012 can all run in parallel (US1, all different files)
- T013 + T014 + T015 are in the same file — must be sequential
- T018 + T019 + T020 + T021 + T022 can run in parallel (US4, different files)
- T023-T029 can all run in parallel (Polish, all different pages)

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tasks in parallel (all different files):
Task: "T006 - Update EmptyState in frontend/src/components/common/EmptyState.tsx"
Task: "T007 - Update LoadingSpinner in frontend/src/components/common/LoadingSpinner.tsx"
Task: "T008 - Update LoginPage in frontend/src/pages/LoginPage.tsx"
Task: "T009 - Update ProjectCard in frontend/src/components/project/ProjectCard.tsx"
Task: "T010 - Update ProjectList in frontend/src/components/project/ProjectList.tsx"
Task: "T011 - Update ContextList in frontend/src/components/project/ContextList.tsx"
Task: "T012 - Update VariableManager in frontend/src/components/project/VariableManager.tsx"
```

## Parallel Example: Polish Phase

```bash
# Launch all polish page tasks in parallel (all different files):
Task: "T023 - Update ProjectsPage"
Task: "T024 - Update FileBrowserPage"
Task: "T025 - Update DockerPage"
Task: "T026 - Update SSHPage"
Task: "T027 - Update PluginsPage"
Task: "T028 - Update GitLabPage"
Task: "T029 - Update UsersPage"
Task: "T030 - Update ChatWindow"
```

---

## Implementation Strategy

### MVP First (Phase 1 + 2 + US1)

1. Complete Phase 1: index.css theme update (T001-T002)
2. Complete Phase 2: Layout shell glass morphism (T003-T005)
3. **STOP and VERIFY**: Dark theme + glass layout visible on all pages
4. Complete US1: All cards/surfaces updated (T006-T012)
5. **STOP and VERIFY**: Consistent glass morphism on all surfaces

### Incremental Delivery

1. Phase 1+2 → Dark layout ready
2. Add US1 → All surfaces consistent → **Deploy/Demo (MVP!)**
3. Add US2 → Dashboard polished → Deploy/Demo
4. Add US3 → Navigation refined → Deploy/Demo
5. Add US4 → Forms polished → Deploy/Demo
6. Polish → All pages consistent → Final Deploy

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Most visual changes cascade from index.css theme vars — component changes are refinements
- No new files or components created — all changes to existing files
- No backend changes needed
- Commit after each phase completion for easy rollback

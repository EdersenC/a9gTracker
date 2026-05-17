# UI/Input Specification

Status: needs review  
Owner: UI/Input Specification Agent  
Scope: `ui_flow`  
Product context: social media experience for cats, dogs, and LLM personas

## Purpose

Define the v1 user-facing screens, controls, feedback states, navigation, UI state needs, and input events required for a future implementation. This document is design-only and intentionally avoids runtime, persistence, API, and domain ownership changes.

## Consumed Dependencies

The UI depends on the Product Specification and Runtime Flow Specification for the following behavior:

- Product scope: v1 is a social feed where cat, dog, and LLM personas can be represented, post content, react to posts, and browse a mixed community timeline.
- Product non-goals: v1 UI does not require monetization, complex moderation tooling, private messaging, advanced recommendation controls, or external social graph imports unless later specs add them.
- Product acceptance criteria: users can understand who is posting, create simple posts, view the feed, react to posts, and see clear feedback for loading, success, empty, and error states.
- Runtime sequence: UI starts by requesting initial session/profile context and feed data, then renders the active screen, dispatches user events, reflects optimistic or confirmed state updates, and exposes recoverable error states.
- Runtime event/update contract: UI emits typed input events and receives runtime state updates rather than owning domain mutation rules directly.

Because source Product and Runtime Flow design sheets were not present in this worktree, the dependencies above are limited to the AgentWorkContract handoff context and must be reconciled during integration.

## Screen/Control Map

### App Shell

Primary purpose: provide stable navigation and global status across the product.

Controls:

- Feed navigation item: opens the community feed.
- Compose button: opens the post composer from any primary screen.
- Profile switcher: selects active posting identity when multiple personas exist.
- Notifications/status indicator: shows unread activity or runtime connectivity status if available.
- Settings navigation item: opens local user and persona preferences.

Feedback states:

- Initializing: app session and first feed load are pending.
- Online: runtime can send and receive updates.
- Offline/degraded: runtime cannot currently sync; read-only cached state may remain visible if provided by data/runtime.
- Recoverable error: shell-level banner with retry control for startup or session load failure.

Runtime/data dependencies:

- Requires session state, active profile identity, network/sync status, and last known runtime error.
- Does not own authentication, profile persistence, or sync decisions.

Navigation:

- Feed, profile, and settings are top-level destinations.
- Compose is modal or overlay state on top of the current destination.

### Community Feed

Primary purpose: browse recent posts from cats, dogs, and LLM personas.

Controls:

- Feed filter segmented control: All, Cats, Dogs, LLMs.
- Sort control: Recent first for v1; additional options only if Product Spec later allows them.
- Refresh control: requests the latest feed snapshot.
- Post card reaction controls: like, cheer, or equivalent simple reaction set defined by product copy.
- Comment/reply entry point: opens post detail if replies are in v1; otherwise disabled or omitted.
- Author/profile link: opens profile detail for the selected persona.

Feedback states:

- Loading feed: skeleton or compact loading rows before posts are available.
- Refreshing feed: existing posts remain visible with a non-blocking progress indicator.
- Empty feed: clear empty state when no posts match the active filter.
- Filter empty: empty state scoped to the selected filter with a control to return to All.
- Reaction pending: selected reaction shows pending visual affordance until runtime confirms or rejects it.
- Reaction failed: inline message and restored previous reaction state.
- Feed load failed: retryable error state that preserves any last known posts supplied by runtime/data.

Runtime/data dependencies:

- Requires feed collection, post IDs, author/persona metadata, media references if supported, reaction counts, viewer reaction state, timestamps, and pagination/refresh status.
- Requires runtime to provide loading, refreshing, empty, partial-data, and error statuses separately from raw post data.
- UI must not calculate feed ranking or mutate reaction counts as source of truth; optimistic display is allowed only while tagged as pending.

Navigation:

- Selecting a post opens Post Detail when the runtime/product include a detail surface.
- Selecting an author opens Profile Detail.
- Compose returns to Feed after successful post creation unless launched from another screen.

### Post Composer

Primary purpose: create a new post for the active cat, dog, or LLM persona.

Controls:

- Active persona selector: chooses which persona authors the post.
- Text input: required post body.
- Optional media picker placeholder: visible only if product/runtime expose media support.
- Tone/style selector for LLM personas: optional v1 control if persona metadata exposes supported tones.
- Submit button: dispatches create-post event.
- Cancel/close button: exits without submitting.
- Clear draft control: removes local unsent text after confirmation if a draft exists.

Feedback states:

- Drafting: local unsent input is editable.
- Validation error: submit is blocked for empty or over-limit body, missing persona, or unsupported media.
- Submitting: submit control is disabled and progress is visible.
- Submit success: composer closes and feed shows the created post or pending insertion supplied by runtime.
- Submit failed: draft remains intact with retry and edit controls.
- Unsaved changes: close/cancel prompts before discarding a non-empty draft.

Runtime/data dependencies:

- Requires active persona, allowed post length, supported attachment capabilities, create-post pending/error state, and optional draft persistence status.
- UI owns transient input text and validation display, but runtime/domain owns post creation, IDs, timestamps, and durable save status.

Navigation:

- Opened from App Shell or empty feed prompt.
- On success, returns to the previous screen and requests or receives feed update.
- On cancel with no draft, returns immediately.

### Post Detail

Primary purpose: inspect one post and associated interaction history when available.

Controls:

- Back control: returns to previous list/profile context.
- Reaction controls: same reaction model as feed cards.
- Reply/comment composer: included only if replies are in the product/runtime contract.
- Share/copy link control: optional if runtime exposes stable post URLs.

Feedback states:

- Loading post: shown when route opens before post data is available.
- Missing/deleted post: not-found state with return-to-feed control.
- Interaction pending: reply or reaction operation is pending.
- Interaction failed: inline retry or rollback message.

Runtime/data dependencies:

- Requires selected post ID, post detail payload, viewer reaction state, reply list if supported, and deletion/visibility status.
- UI must handle post detail being unavailable even if the feed previously displayed a post.

Navigation:

- Back returns to the originating screen.
- Author link opens Profile Detail.

### Profile Detail

Primary purpose: show a cat, dog, or LLM persona identity and their posts.

Controls:

- Back control.
- Follow/unfollow or favorite control if product/runtime include relationship state.
- Profile post filter: Posts, Reactions, or About only when data supports these categories.
- Edit profile control for owned personas only.

Feedback states:

- Loading profile.
- Profile not found or unavailable.
- Empty profile posts.
- Follow/favorite pending and failed states if the control exists.

Runtime/data dependencies:

- Requires persona ID, display name, type (`cat`, `dog`, or `llm`), avatar/media reference if available, bio/description, ownership flag, relationship state if supported, and profile posts.
- UI does not infer persona type from display text; it consumes explicit data from runtime/data.

Navigation:

- Selecting one of the profile's posts opens Post Detail.
- Edit profile opens Profile Editor for owned personas only.

### Profile Editor

Primary purpose: create or update the user's owned persona records.

Controls:

- Persona type selector: Cat, Dog, LLM.
- Display name input.
- Bio/description input.
- Avatar/media selector placeholder if supported.
- Save button.
- Cancel button.

Feedback states:

- Validation error: missing name, invalid persona type, or over-limit fields.
- Saving.
- Save success.
- Save failed with retry and preserved edits.
- Unsaved changes prompt.

Runtime/data dependencies:

- Requires supported persona types, owned persona list, field limits, save pending/error state, and persisted persona result.
- UI owns unsaved form fields only; runtime/data owns canonical persona records.

Navigation:

- Entry from App Shell profile switcher, Profile Detail edit control, or first-run onboarding.
- Save returns to Profile Detail or previous screen with updated persona context.

### Settings

Primary purpose: expose v1 user preferences and operational controls that affect local UI behavior.

Controls:

- Active persona management entry point.
- Feed default filter selector.
- Accessibility/display preferences if product scope includes them.
- Sign out/reset session control only if runtime exposes session handling.

Feedback states:

- Loading settings.
- Saving settings.
- Save failed with retry.
- Destructive action confirmation.

Runtime/data dependencies:

- Requires settings payload, supported preference keys, save status, and session capabilities.
- UI must not expose settings that have no runtime/data backing.

Navigation:

- Back or primary navigation returns to Feed.
- Persona management opens Profile Editor or profile list when available.

## UI State Needs

The UI layer needs the following state, either local-only or supplied by runtime/data:

- Current route: active screen, route parameters, and previous-screen context for back navigation.
- Session status: initializing, ready, unauthenticated if applicable, failed.
- Active persona ID: selected author identity for posting and profile context.
- Persona catalog: IDs, display names, persona types, avatars/media references, ownership flags, and availability status.
- Feed query: active filter, sort, pagination cursor if any, refresh status, and last successful query time if provided.
- Feed results: ordered post IDs and loading/error/empty status.
- Post entities: post ID, author persona ID, text, optional media metadata, created timestamp, reaction counts, viewer reaction, visibility/deletion state.
- Pending operations: create post, update persona, react to post, refresh feed, load detail, save settings.
- Draft state: composer body, selected persona, selected media placeholder, validation errors, dirty/clean flag.
- UI error state: scoped errors for shell, feed, composer, detail, profile, and settings.
- Connectivity/sync state: online/offline/degraded indicators and queued-operation hints if runtime supports them.
- Accessibility state: focus target after navigation/modal close, disabled control reasons, and live-region messages for async results.

Ownership rules:

- UI owns route, focus, open modal state, unsaved form input, local validation messages, and transient disabled/loading presentation.
- Runtime/data own canonical session, personas, posts, reactions, settings, persistence state, and operation outcomes.
- Any optimistic UI update must remain associated with a pending operation ID or equivalent runtime status so rollback is possible.

## Input Events

The UI emits these events to the runtime/application boundary. Names are implementation-facing suggestions, not new shared API routes.

| Event | Triggering control | Required payload | Expected runtime response |
| --- | --- | --- | --- |
| `app.started` | Initial render | None | Session/profile/feed bootstrap status |
| `route.changed` | Top-level navigation, back, deep link | Target route and route params | Updated screen state or load status |
| `feed.refreshRequested` | Refresh control | Active filter/sort/cursor context | Refresh pending, then feed snapshot or error |
| `feed.filterChanged` | Feed filter segmented control | Filter value: `all`, `cats`, `dogs`, or `llms` | Feed query state and matching results |
| `post.composeOpened` | Compose button or empty prompt | Origin route and optional preselected persona ID | Composer-ready state |
| `post.draftChanged` | Composer text/media/persona fields | Draft field name and value | Validation state and updated local draft acceptance |
| `post.createRequested` | Composer submit | Persona ID, body text, optional media reference | Create pending, then created post or error |
| `post.createCancelled` | Composer cancel/close | Draft dirty flag | Close approval or unsaved-changes handling |
| `post.detailRequested` | Post selection | Post ID and origin route | Post detail payload, missing state, or error |
| `post.reactionToggled` | Reaction control | Post ID, reaction type, previous viewer reaction | Pending reaction status, confirmed counts, or rollback error |
| `profile.openRequested` | Author/profile link | Persona ID and origin route | Profile payload and profile posts or error |
| `profile.editOpened` | Edit profile/persona management | Persona ID or new-persona marker | Editable profile state and field limits |
| `profile.saveRequested` | Profile editor save | Persona ID if editing, persona type, display name, bio, optional avatar reference | Save pending, then persisted persona or error |
| `settings.openRequested` | Settings navigation | None | Settings payload and capability flags |
| `settings.saveRequested` | Settings save/change control | Supported preference key/value changes | Save pending, then persisted settings or error |
| `modal.dismissRequested` | Escape, close, cancel | Modal ID and dirty flag | Dismissed state or confirmation requirement |
| `error.retryRequested` | Retry control | Failed operation ID or error scope | Re-run operation status |

## State Transitions Runtime Must Support

- Startup: `uninitialized -> bootstrapping -> ready` or `failed`.
- Feed loading: `idle -> loading -> ready`, `ready -> refreshing -> ready`, or any loading state to `failed`.
- Composer: `closed -> drafting -> submitting -> submitted -> closed`, with failure returning to `drafting` while preserving inputs.
- Reaction: `stable -> pending -> stable` on success, or `pending -> failed -> stable` on rollback.
- Profile editor: `closed -> editing -> saving -> saved -> closed`, with failure returning to `editing`.
- Offline/degraded operation: runtime may return a queued/pending status only if data contracts support queued operations; otherwise UI presents a blocking failure.

## Feedback Requirements

Every async user action must expose:

- Immediate visible response within the current screen or control.
- Disabled or guarded repeat submission while the same operation is pending.
- Clear success, failure, or no-op result.
- Recovery path for failures where retry is meaningful.
- Preservation of user-entered draft/form data after failed create or save operations.

## Out of Scope

- Implementing actual screens, components, routes, or styles.
- Defining API endpoints, database schema, persistence strategy, recommendation/ranking algorithms, or moderation workflow.
- Changing shared event payload contracts beyond naming the UI events that the runtime must support.
- Taking ownership of Product, Runtime Flow, Data Architecture, API Contract, or Persistence specifications.

## Integration Notes

- During integration, align event names and payloads with the accepted API/Interface Contract Specification.
- Reconcile persona, post, reaction, setting, and operation-status field names with Data Architecture before implementation.
- Product Spec should confirm whether replies, follow/favorite, media attachments, share links, authentication, and offline queued operations are in v1.
- Runtime Flow should confirm whether navigation is browser-route based, in-app state based, or another adapter-specific pattern.

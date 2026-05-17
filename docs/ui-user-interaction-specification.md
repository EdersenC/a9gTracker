# UI/User Interaction Specification

Status: implementation slice for `ui_flow`

Owner: UI/Input Specification Agent

User goal: a social media product for cats, dogs, and LLM participants.

## Scope

This specification defines the v1 user-facing screens, controls, visible feedback states, navigation transitions, and UI-originated input events that the runtime flow must support. It stays at the UI contract level and does not define domain algorithms, persistence schema, API routes, moderation policy, or model behavior.

## Consumed Inputs

- Product scope: v1 is treated as a social feed where cat, dog, and LLM profiles can publish posts, read a mixed feed, react, and comment.
- Product non-goals: v1 excludes full marketplace behavior, long-form groups, direct messaging, live streaming, payment flows, and advanced recommendation tuning.
- Product acceptance criteria: a user can identify the active profile type, browse posts, create a post, react, comment, and receive clear success or failure feedback.
- Runtime sequence: UI dispatches explicit events to the runtime; runtime owns initialization, data loading, mutation execution, state updates, and shutdown.
- Runtime event/update contract: UI renders runtime state snapshots and emits input events without directly mutating durable data.

Local repository note: the current worktree does not include the Product Spec or Runtime Flow Spec files. The above consumed inputs are derived from the AgentWorkContract and the locked user-goal context.

## Screen/Control Map

### App Shell

Purpose: provide stable navigation and session context across all authenticated v1 screens.

Primary controls:
- Active profile switcher: selects the current cat, dog, or LLM profile context.
- Home/feed navigation control: opens the main feed.
- Compose control: opens the post composer.
- Profile navigation control: opens the selected profile.
- Settings/control menu: opens account, display, notification, and sign-out controls.

Feedback states:
- Initializing: app shell renders a neutral loading state while runtime restores session and fetches required data.
- Offline or degraded network: shell shows a persistent network banner while keeping cached readable content available when runtime provides it.
- Profile unavailable: profile switcher is disabled with a retry affordance when runtime cannot load profile choices.
- Unauthorized: shell routes to the sign-in or profile setup surface.

Runtime/data dependencies:
- Requires session status, active profile id, available profile summaries, unread notification count, network status, and current route.
- Depends on runtime navigation state rather than directly inspecting storage.

### Sign-In and Profile Setup

Purpose: let a person enter the v1 experience and establish a visible social identity for a cat, dog, or LLM profile.

Primary controls:
- Sign-in form controls for the configured auth mechanism.
- Create profile control.
- Profile type selector: cat, dog, or LLM.
- Display name input.
- Avatar/media picker.
- Bio/short description input.
- Save profile control.
- Cancel/back control where a prior authenticated route exists.

Feedback states:
- Empty form: required fields are visibly marked.
- Submitting: save/sign-in controls are disabled and a progress indicator is shown.
- Validation error: invalid or missing fields are shown next to the affected control.
- Auth failure: form-level error explains that sign-in failed without exposing sensitive internals.
- Profile creation success: runtime routes to the feed with the new profile selected.

Runtime/data dependencies:
- Requires auth/session state, profile type options, profile validation constraints, and profile creation/update results.
- Emits profile creation/update events; runtime owns persistence and identity assignment.

### Home Feed

Purpose: present the mixed social timeline for cat, dog, and LLM profiles.

Primary controls:
- Feed filter segmented control: all, cats, dogs, LLMs, following.
- Sort control: recent or highlighted, if supported by product/runtime.
- Refresh control.
- Infinite scroll/load-more trigger.
- Post card controls: open details, react, comment, share/copy link if supported, and open author profile.
- Empty-state compose control.

Feedback states:
- Loading feed: skeleton rows or compact loading indicator.
- Empty feed: clear empty state with a compose action.
- Refreshing: non-blocking refresh indicator.
- Mutation pending: the affected reaction/comment control reflects pending state.
- Mutation failed: the affected post card shows retry/dismiss feedback.
- End of feed: subtle completion state when no more items are available.
- Feed load error: retry control with preserved prior content if available.

Runtime/data dependencies:
- Requires feed item list, pagination cursor, active filter/sort, pending mutation map, load/error statuses, and active profile context.
- Depends on post, profile summary, reaction summary, comment count, and media preview data supplied by runtime/data layers.

### Compose Post

Purpose: allow the active profile to publish a short social post.

Primary controls:
- Text input.
- Media attachment picker.
- Audience/type visibility selector where supported.
- Post action.
- Save draft or close action if runtime supports drafts; otherwise close discards only unsent local input after confirmation.
- Attachment remove controls.

Feedback states:
- Character or content limit feedback.
- Empty content validation.
- Media upload/processing progress.
- Submitting state with disabled post action.
- Publish success with route back to feed or inserted post.
- Publish failure with retry and keep-editing controls.
- Unsaved local input confirmation when closing with content present.

Runtime/data dependencies:
- Requires active profile id/type, post validation constraints, supported media constraints, upload/publish status, created post result, and optional draft support flag.
- UI may hold local unsent input, but runtime owns publish, upload, and durable draft decisions.

### Post Detail

Purpose: focus one post and its conversation thread.

Primary controls:
- Back/feed navigation control.
- Author profile control.
- Reaction control.
- Comment input.
- Submit comment control.
- Comment pagination/load-more control.
- Comment-level controls: react, open author, report/hide if supported.

Feedback states:
- Loading post/thread.
- Missing or deleted post.
- Comment submit pending.
- Comment validation error.
- Comment submit failure with retry.
- Thread load error with retry.
- Optimistic reaction state while runtime confirms the mutation.

Runtime/data dependencies:
- Requires selected post id, post detail, comments, comment pagination cursor, reaction state, pending mutation map, and error statuses.
- Runtime owns comment creation, reaction updates, and detail hydration.

### Profile

Purpose: show a cat, dog, or LLM participant and their posts.

Primary controls:
- Follow/unfollow control.
- Edit profile control when the active profile owns the viewed profile.
- Profile posts tab.
- Profile about/details tab.
- Profile feed pagination/load-more.
- Post card controls reused from Home Feed.

Feedback states:
- Loading profile.
- Profile not found.
- Follow/unfollow pending.
- Follow/unfollow failure with retry.
- Empty profile posts.
- Owner edit success/failure.

Runtime/data dependencies:
- Requires profile detail, viewer relationship, ownership flag, profile post list, pagination cursor, and pending relationship mutation state.
- Runtime owns follow state, profile updates, and profile feed retrieval.

### Notifications

Purpose: surface social activity that needs attention.

Primary controls:
- Notification list item control: opens post, profile, or comment target.
- Mark all read control.
- Notification filter control if runtime supports categories.
- Refresh/load-more control.

Feedback states:
- Loading notifications.
- Empty notifications.
- Mark-read pending.
- Notification target unavailable.
- Load or mark-read failure with retry.

Runtime/data dependencies:
- Requires notification list, unread count, target references, read status, pagination cursor, and pending mark-read state.
- Runtime resolves target navigation and owns read-state mutation.

### Settings

Purpose: expose account-level and display preferences without mixing them into domain logic.

Primary controls:
- Active profile management controls.
- Notification preference toggles.
- Display preference controls.
- Sign-out control.

Feedback states:
- Loading settings.
- Save pending.
- Save success.
- Save failure with retry.
- Sign-out pending.

Runtime/data dependencies:
- Requires current user settings, profile list, update status, and sign-out result.
- Runtime owns settings persistence and session teardown.

## Navigation and State Transitions

- Unauthenticated app start routes to Sign-In.
- Authenticated app start routes to Home Feed after session/profile hydration.
- No profile after sign-in routes to Profile Setup.
- App Shell navigation may move between Home Feed, Profile, Notifications, and Settings without clearing active profile context.
- Compose can open from App Shell, Home Feed empty state, or Profile; successful publish returns to the invoking surface and refreshes or inserts the created post.
- Selecting a post card routes to Post Detail.
- Selecting a profile identity routes to Profile.
- Runtime-authored fatal session expiration routes to Sign-In and clears UI-only input state.
- Runtime-authored recoverable errors keep the current route and expose local retry controls.

## UI State Needs

The UI layer needs these runtime-provided state groups:

- Session state: unknown, authenticated, unauthenticated, expired.
- Active profile state: selected profile id, profile type, display name, avatar, ownership capabilities.
- Navigation state: current route, route params, prior route for back/close behavior.
- Network state: online, offline, reconnecting, degraded, last successful sync time.
- Feed state: active filter, sort, items, pagination cursor, loading status, refresh status, error status.
- Post detail state: selected post, comments, pagination cursor, loading status, error status.
- Profile state: viewed profile, relationship state, profile posts, loading status, error status.
- Notification state: unread count, notification items, pagination cursor, mark-read status.
- Settings state: preference values, save status, sign-out status.
- Mutation state: pending, succeeded, failed, retryable status keyed by operation and target id.
- Validation state: field-level errors for sign-in, profile setup, compose, comment, and settings forms.
- Media state: selected local attachments, upload progress, upload failure, accepted media constraints.

UI-owned ephemeral state:

- Form field text before submission.
- Open/closed state for menus, dialogs, and composer.
- Currently focused input/control.
- Local unsaved compose/comment content.
- Scroll position where runtime does not require durable restoration.

UI must not own:

- Durable profile, post, comment, reaction, follow, notification, or settings records.
- Server-assigned ids, timestamps, relationship truth, or permission decisions.
- Recommendation, ranking, moderation, or LLM response logic.

## Input Events

All events are emitted by the UI and handled by runtime/application services. Event names are stable UI contracts for future implementation; payloads should contain ids and simple values, not domain objects assembled by the UI.

### Session and Shell Events

- `AppOpened`: no payload; runtime initializes session, profiles, and initial route.
- `RouteRequested`: `{ "route": string, "params": object }`.
- `BackRequested`: no payload or `{ "fallbackRoute": string }`.
- `ActiveProfileSelected`: `{ "profileId": string }`.
- `RefreshRequested`: `{ "surface": "feed" | "postDetail" | "profile" | "notifications" | "settings" }`.
- `RetryRequested`: `{ "operationId": string, "targetType": string, "targetId": string | null }`.
- `SignOutRequested`: no payload.

### Auth and Profile Events

- `SignInSubmitted`: auth payload defined by the auth adapter; UI passes only user-entered credentials/tokens.
- `ProfileCreateSubmitted`: `{ "type": "cat" | "dog" | "llm", "displayName": string, "avatarRef": string | null, "bio": string }`.
- `ProfileUpdateSubmitted`: `{ "profileId": string, "displayName": string, "avatarRef": string | null, "bio": string }`.
- `ProfileViewed`: `{ "profileId": string }`.
- `FollowToggled`: `{ "profileId": string, "desiredFollowing": boolean }`.

### Feed and Post Events

- `FeedFilterChanged`: `{ "filter": "all" | "cats" | "dogs" | "llms" | "following" }`.
- `FeedSortChanged`: `{ "sort": "recent" | "highlighted" }`.
- `FeedLoadMoreRequested`: `{ "cursor": string | null }`.
- `ComposeOpened`: `{ "sourceRoute": string }`.
- `ComposeClosed`: `{ "hasUnsavedInput": boolean }`.
- `PostSubmitted`: `{ "authorProfileId": string, "body": string, "mediaRefs": string[], "visibility": string | null }`.
- `PostViewed`: `{ "postId": string }`.
- `PostReactionToggled`: `{ "postId": string, "reactionType": string, "desiredActive": boolean }`.
- `PostShared`: `{ "postId": string }`.

### Comment Events

- `CommentSubmitted`: `{ "postId": string, "authorProfileId": string, "body": string }`.
- `CommentLoadMoreRequested`: `{ "postId": string, "cursor": string | null }`.
- `CommentReactionToggled`: `{ "commentId": string, "reactionType": string, "desiredActive": boolean }`.

### Media Events

- `MediaSelected`: `{ "localRef": string, "mediaType": string, "sizeBytes": number }`.
- `MediaRemoved`: `{ "localRef": string }`.
- `MediaUploadRetryRequested`: `{ "localRef": string }`.

### Notification and Settings Events

- `NotificationsOpened`: no payload.
- `NotificationSelected`: `{ "notificationId": string, "targetType": string, "targetId": string }`.
- `NotificationsLoadMoreRequested`: `{ "cursor": string | null }`.
- `NotificationsMarkAllReadRequested`: no payload.
- `SettingsPreferenceChanged`: `{ "key": string, "value": boolean | string | number }`.
- `SettingsSaveRequested`: `{ "changedKeys": string[] }`.

## Feedback Requirements

Primary visible feedback states required across v1:

- Loading: every data-backed surface renders an intentional loading state.
- Empty: every list surface renders an empty state with the most relevant next action.
- Pending mutation: controls that initiated mutations show disabled or pending state until runtime resolves the event.
- Success: create/update actions show route changes, inserted content, or compact confirmation.
- Validation failure: form-level and field-level errors preserve user input.
- Runtime failure: failed loads and failed mutations expose retry where the runtime marks the operation retryable.
- Offline/degraded: app shell provides a global status indicator; surfaces preserve last runtime-provided readable data where available.
- Unauthorized/session expired: user is moved to sign-in and UI-only unsaved sensitive inputs are cleared.

## Contract Boundaries

- UI depends on runtime for session, routing decisions, data snapshots, mutation execution, retryability, and persistence outcomes.
- UI depends on data contracts for profiles, posts, comments, reactions, follows, notifications, settings, media references, and operation statuses.
- UI provides only screen/control map, UI state needs, and input events.
- UI does not introduce new API routes, database schema, workflow rules, domain entities, or cross-agent shared payload changes beyond the event names and UI-facing payload sketches listed here.

## Acceptance Coverage

- Primary controls are listed for App Shell, Sign-In/Profile Setup, Home Feed, Compose Post, Post Detail, Profile, Notifications, and Settings.
- Feedback states are listed per screen and summarized globally.
- UI dependencies on runtime/data state are explicit for every screen.
- Input events are enumerated with intended payload shape and runtime ownership.


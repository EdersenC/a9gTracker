# Runtime Flow Specification

Status: needs_review

Owner: Runtime Flow Specification Agent

User goal: A social media for cats, dogs, and LLMs.

## Purpose

Define the v1 runtime sequence for the social feed experience, including
startup, event handling, state updates, background operations, validation,
error handling, and shutdown. Future implementation slices should follow this
runtime order rather than introducing competing loops.

## Runtime Assumptions

- The product is a lightweight social media application for three actor types:
  cat profiles, dog profiles, and LLM profiles.
- The runtime is request/event driven. UI adapters emit typed events, domain
  services validate and transform them, persistence stores durable state, and
  view state is derived from domain state.
- Authentication and production-grade moderation are outside this v1 runtime
  unless later accepted architecture decisions add them.
- Persistence may be local or server-backed depending on the database slice,
  but runtime ownership remains the same: persistence owns durable reads and
  writes; domain services own validated state mutations.

## Module Runtime Boundaries

| Runtime Area | Owner | Responsibility |
| --- | --- | --- |
| Application shell | Runtime adapter | Starts the app, mounts UI, wires event handlers, and coordinates shutdown. |
| UI state | UI adapter | Holds transient screen state such as active tab, draft text, pending indicators, and visible error messages. |
| Domain state | Domain services | Owns validated mutations for profiles, posts, reactions, follows, and feed composition rules. |
| Durable state | Persistence adapter | Loads, saves, and reports persistence errors for durable entities. |
| API/event boundary | Interface adapter | Converts external requests or UI actions into domain events and serializes responses. |
| Background work | Runtime coordinator | Schedules feed refresh, retry, and cache revalidation without mutating domain state directly. |

## Ordered Startup Sequence

1. Runtime adapter starts the application process.
2. Load runtime configuration, feature flags, and environment-specific adapter
   bindings.
3. Initialize persistence adapter.
4. Read durable state required for first paint:
   profiles, session placeholder, seed feed data, and locally saved drafts if
   supported by the persistence slice.
5. Validate loaded data shape against the data contract. Invalid records are
   ignored or quarantined by persistence and reported as recoverable runtime
   errors.
6. Initialize domain services with validated state snapshots.
7. Derive initial UI state from domain state:
   selected feed, profile summaries, composer availability, loading status, and
   empty-state flags.
8. Mount UI and register event handlers.
9. Start background operations:
   feed refresh timer, failed-write retry queue, and any adapter health checks.
10. Mark runtime as ready and accept user events.

## Main Event Loop

The runtime handles one user event at a time through a single ordered pipeline:

1. UI adapter emits an input event with a stable event name and payload.
2. Runtime coordinator attaches runtime metadata:
   request id, actor id if available, timestamp, and current screen context.
3. Event payload is validated at the interface boundary.
4. Invalid events stop before domain execution. UI state receives a validation
   error and no durable write is attempted.
5. Valid events are routed to the owning domain service.
6. Domain service applies business validation and computes a state transition.
7. Domain service returns one of:
   accepted mutation, rejected mutation, no-op, or async operation required.
8. Runtime coordinator persists accepted durable mutations through the
   persistence adapter.
9. Persistence success commits the domain state snapshot and emits a UI refresh
   signal.
10. Persistence failure rolls back or leaves the prior committed domain snapshot
    intact, records the failure, and updates UI state with a retryable error.
11. UI adapter re-derives visible state from the latest committed domain state
    plus transient UI state.
12. Runtime coordinator emits post-event side effects, such as analytics hooks
    or background refresh scheduling, only after mutation handling completes.

## User Input Events

| Event | Payload Owner | Mutation Owner | Durable Write | Runtime Result |
| --- | --- | --- | --- | --- |
| `app.opened` | Runtime adapter | Runtime coordinator | No | Starts startup sequence and first feed load. |
| `feed.refreshRequested` | UI adapter | Feed service | Optional | Refreshes feed from durable or remote state. |
| `composer.draftChanged` | UI adapter | UI adapter | Optional | Updates transient draft state; persistence may save draft if supported. |
| `post.createRequested` | UI adapter | Post service | Yes | Validates actor and content, creates post, refreshes feed. |
| `post.deleteRequested` | UI adapter | Post service | Yes | Validates ownership, removes or tombstones post, refreshes feed. |
| `reaction.toggleRequested` | UI adapter | Reaction service | Yes | Adds or removes a reaction, updates counters. |
| `profile.openRequested` | UI adapter | UI adapter | No | Changes navigation state and loads profile view data. |
| `profile.updateRequested` | UI adapter | Profile service | Yes | Validates profile fields and saves profile changes. |
| `follow.toggleRequested` | UI adapter | Relationship service | Yes | Adds or removes following relationship and refreshes relevant feeds. |
| `llm.replyRequested` | UI adapter | LLM interaction service | Yes, if reply accepted | Queues or generates an LLM profile reply and inserts accepted result as a post or comment. |
| `error.dismissRequested` | UI adapter | UI adapter | No | Clears visible transient error state. |
| `app.shutdownRequested` | Runtime adapter | Runtime coordinator | Optional flush | Stops background work, flushes pending writes, and releases adapters. |

## Background Operations

Background operations must not mutate committed domain state directly. They
must emit the same event/update contract used by user actions.

| Operation | Trigger | Owner | Mutation Path |
| --- | --- | --- | --- |
| Feed refresh | Startup, manual refresh, interval | Runtime coordinator | Emits `feed.refreshRequested`; feed service owns resulting state changes. |
| Failed-write retry | Persistence failure with retryable status | Runtime coordinator | Replays original accepted mutation through persistence adapter after backoff. |
| Draft autosave | Composer changes after debounce | UI adapter and persistence adapter | Saves draft only; does not create a post. |
| LLM reply generation | `llm.replyRequested` | LLM interaction service | Emits accepted generated content back through post/comment creation flow. |
| Adapter health check | Startup and interval | Runtime coordinator | Updates runtime health state only. |

## State Mutation Ownership

| State | Owner | Mutation Rule |
| --- | --- | --- |
| Runtime readiness, health, and pending operation registry | Runtime coordinator | Mutated only during startup, shutdown, retries, and adapter status changes. |
| Active screen, selected tab, modal state, drafts, loading flags, visible errors | UI adapter | Transient only unless a persistence contract explicitly supports draft saving. |
| Profile entities | Profile service | Mutated only after profile validation passes. |
| Post entities and post lifecycle | Post service | Mutated only through create, delete, or generated-content acceptance flows. |
| Reactions and reaction counts | Reaction service | Mutated only through reaction toggle events; counters are derived or updated atomically. |
| Follow relationships | Relationship service | Mutated only through follow toggle events. |
| Feed ordering and filters | Feed service | Derived from profiles, posts, relationships, and accepted filtering rules. |
| Durable records | Persistence adapter | Written only after a domain service returns an accepted mutation. |
| Event payload schemas | API/interface contract owner | Runtime consumes the schema and must request interface changes before altering it. |

## Validation Flow

1. Interface validation checks event name, payload shape, required ids, content
   size limits, and known actor/profile type.
2. Domain validation checks ownership, allowed profile type behavior, post
   visibility, reaction eligibility, relationship constraints, and LLM reply
   acceptance rules.
3. Persistence validation checks durable record shape and write preconditions.
4. Validation failures return structured errors to UI state with no committed
   domain mutation.
5. Recoverable validation failures keep the runtime ready. Fatal validation
   failures move runtime health to degraded and block only the affected action.

## Error Flow

| Error Type | Owner | Runtime Behavior |
| --- | --- | --- |
| Invalid UI payload | Interface adapter | Reject event, show validation error, do not call domain service. |
| Domain rule rejection | Domain service | Return rejected mutation, show user-facing error or disabled state. |
| Persistence read failure | Persistence adapter | Start with empty or last-known valid state when allowed; mark runtime degraded. |
| Persistence write failure | Persistence adapter and runtime coordinator | Keep prior committed state, enqueue retry if retryable, show pending/error state. |
| Background operation failure | Runtime coordinator | Record failure, back off, keep foreground event loop available. |
| LLM generation failure | LLM interaction service | Mark generated reply failed; do not create post/comment unless valid content exists. |

## Shutdown Sequence

1. Stop accepting new user events except cancellation or close confirmation.
2. Cancel or finish in-flight background operations according to their owner
   contract.
3. Flush pending durable writes and draft autosave when the persistence adapter
   supports it.
4. Persist runtime-safe checkpoints if defined by the persistence slice.
5. Release network, storage, timer, and UI subscriptions.
6. Clear transient runtime registries.
7. Exit application process or return control to the host shell.

## Event/Update Contract Provided

Runtime Flow provides these contracts to Product and System Architecture:

- Runtime sequence: startup, single event pipeline, background operation
  scheduling, validation/error handling, and shutdown order defined above.
- Event/update contract: all user and background actions enter through typed
  events, interface validation runs before domain mutation, domain services own
  accepted state transitions, persistence owns durable writes, and UI state is
  derived after commit or rejection.

## Acceptance Criteria Mapping

- Main runtime events are ordered: startup, event loop, background operations,
  validation/error flow, and shutdown are specified in explicit order.
- State mutation owners are clear: each runtime state category maps to exactly
  one mutation owner, with persistence and UI transient state called out
  separately.

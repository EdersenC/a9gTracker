# UI/User Flow Spec (ui_flow)

## Scope
Define the CLI/text UI surfaces and user flows for v1 of a 2-party network where personal AI harnesses can perform work for another harness.

Constraints:
- Runtime/UI target: CLI/text.
- Persistence strategy: SQLite (through runtime/data layer, not direct UI ownership).
- UI layer remains separate from domain logic.

## Screen/Control Map

### 1. Boot/Startup Screen
Purpose:
- Show startup progress before interactive usage.

Primary controls:
- `Ctrl+C`: request graceful shutdown.

Feedback states:
- `BOOT_LOADING`: loading config/runtime modules.
- `BOOT_NETWORK_WAIT`: network/session bootstrap in progress.
- `BOOT_READY`: startup complete, handoff to Main Menu.
- `BOOT_ERROR`: startup failed with recoverable/non-recoverable reason.

Navigation:
- Success -> Main Menu.
- Error -> Error/Recovery Screen.

Dependencies:
- Runtime status events: `startup_started`, `startup_progress`, `startup_failed`, `startup_ready`.
- Data reads: local harness identity/profile snapshot for header display.

### 2. Main Menu Screen
Purpose:
- Primary navigation hub for operator actions.

Primary controls:
- `1`: View inbox/work requests.
- `2`: Create outbound work request.
- `3`: View active jobs.
- `4`: View job history.
- `5`: Manage peer connections.
- `6`: Refresh runtime state.
- `q`: Quit.

Feedback states:
- `MENU_IDLE`: waiting for selection.
- `MENU_REFRESHING`: pull latest runtime snapshot.
- `MENU_INPUT_INVALID`: unsupported command.

Navigation:
- `1` -> Inbox Screen.
- `2` -> Create Request Screen.
- `3` -> Active Jobs Screen.
- `4` -> History Screen.
- `5` -> Peers Screen.
- `q` -> Exit Confirmation Screen.

Dependencies:
- Runtime aggregate snapshot for badge counts (pending inbox, active jobs, peers online).
- Data entities: `work_request`, `job`, `peer`, `harness_profile` summaries.

### 3. Inbox Screen
Purpose:
- Review inbound work requests from other harnesses.

Primary controls:
- `j/k` or `n/p`: move selection.
- `Enter`: open selected request details.
- `a`: accept request.
- `d`: decline request.
- `r`: refresh inbox.
- `b`: back to Main Menu.

Feedback states:
- `INBOX_LOADING`.
- `INBOX_EMPTY`.
- `INBOX_LIST`.
- `INBOX_ACTION_PENDING` (accept/decline in progress).
- `INBOX_ACTION_SUCCESS`.
- `INBOX_ACTION_ERROR`.

Navigation:
- `Enter` -> Request Detail Screen.
- `b` -> Main Menu.

Dependencies:
- Runtime query/list event for pending requests.
- Mutation events for accept/decline.
- Data fields: request id, sender harness id, task summary, reward/terms, created-at, expiration.

### 4. Request Detail Screen
Purpose:
- Inspect one request before decision.

Primary controls:
- `a`: accept.
- `d`: decline.
- `b`: back to Inbox.

Feedback states:
- `DETAIL_LOADING`.
- `DETAIL_READY`.
- `DETAIL_MUTATION_PENDING`.
- `DETAIL_MUTATION_SUCCESS`.
- `DETAIL_MUTATION_ERROR`.

Navigation:
- Decision success -> Active Jobs Screen (if accepted) or Inbox Screen (if declined).
- `b` -> Inbox Screen.

Dependencies:
- Runtime fetch by request id.
- Data fields: full instructions/payload summary, constraints, requester metadata.

### 5. Create Request Screen
Purpose:
- Compose and submit outbound work request to a peer harness.

Primary controls:
- Form fields (sequential prompts):
  - target peer id.
  - task description.
  - deliverable format.
  - deadline.
  - optional compensation/priority.
- `s`: submit.
- `c`: cancel draft.
- `b`: back.

Feedback states:
- `CREATE_EDITING`.
- `CREATE_VALIDATION_ERROR`.
- `CREATE_SUBMITTING`.
- `CREATE_SUBMIT_SUCCESS`.
- `CREATE_SUBMIT_ERROR`.

Navigation:
- Submit success -> Main Menu (with confirmation banner).
- Cancel/back -> Main Menu.

Dependencies:
- Runtime validation + submit events.
- Data dependencies: peer directory for autocomplete/validation; request schema constraints.

### 6. Active Jobs Screen
Purpose:
- Monitor jobs currently running (local worker or remote worker).

Primary controls:
- `j/k` or `n/p`: move selection.
- `Enter`: view job detail/log tail.
- `x`: cancel selected job (if allowed).
- `r`: refresh.
- `b`: back.

Feedback states:
- `JOBS_LOADING`.
- `JOBS_EMPTY`.
- `JOBS_LIST`.
- `JOBS_CANCEL_PENDING`.
- `JOBS_CANCEL_SUCCESS`.
- `JOBS_CANCEL_ERROR`.

Navigation:
- `Enter` -> Job Detail Screen.
- `b` -> Main Menu.

Dependencies:
- Runtime list active jobs.
- Job status stream updates (queued/running/waiting_for_peer/completed/failed/cancelled).

### 7. Job Detail Screen
Purpose:
- Inspect status timeline and latest output/error for one job.

Primary controls:
- `l`: toggle log tail view.
- `x`: cancel job (if cancellable).
- `r`: refresh details.
- `b`: back to Active Jobs.

Feedback states:
- `JOB_DETAIL_LOADING`.
- `JOB_DETAIL_READY`.
- `JOB_DETAIL_STREAMING`.
- `JOB_DETAIL_ERROR`.

Navigation:
- `b` -> Active Jobs Screen.

Dependencies:
- Runtime fetch/subscribe by job id.
- Data fields: status history, current step, partial outputs, failure reason.

### 8. History Screen
Purpose:
- Browse completed/failed jobs and outbound/inbound request outcomes.

Primary controls:
- `f`: change filter (all/completed/failed/cancelled).
- `j/k`: move selection.
- `Enter`: open historical detail.
- `r`: refresh.
- `b`: back.

Feedback states:
- `HISTORY_LOADING`.
- `HISTORY_EMPTY`.
- `HISTORY_LIST`.

Navigation:
- `Enter` -> Job Detail Screen (read-only mode).
- `b` -> Main Menu.

Dependencies:
- Runtime paged query over persisted records (SQLite-backed via data layer).

### 9. Peers Screen
Purpose:
- View and manage known peer harnesses.

Primary controls:
- `a`: add peer.
- `e`: edit selected peer label/metadata.
- `t`: test connectivity/handshake.
- `d`: disable/remove peer.
- `r`: refresh.
- `b`: back.

Feedback states:
- `PEERS_LOADING`.
- `PEERS_EMPTY`.
- `PEERS_LIST`.
- `PEER_MUTATION_PENDING`.
- `PEER_MUTATION_SUCCESS`.
- `PEER_MUTATION_ERROR`.
- `PEER_TEST_PENDING`.
- `PEER_TEST_RESULT`.

Navigation:
- add/edit prompts run inline then return to Peers list.
- `b` -> Main Menu.

Dependencies:
- Runtime peer registry read/write events.
- Data fields: peer id, endpoint, trust status, last-seen, health.

### 10. Error/Recovery Screen
Purpose:
- Present recoverable failures and next actions.

Primary controls:
- `r`: retry failed action.
- `m`: return to Main Menu (if safe).
- `q`: quit.

Feedback states:
- `ERROR_BLOCKING`.
- `ERROR_RECOVERABLE`.
- `ERROR_RETRY_PENDING`.

Navigation:
- Retry success -> previous screen.
- `m` -> Main Menu.
- `q` -> Exit.

Dependencies:
- Runtime error envelope: code, message, action context, retryability.

### 11. Exit Confirmation Screen
Purpose:
- Avoid accidental shutdown while jobs are active.

Primary controls:
- `y`: confirm exit.
- `n`: cancel and return.

Feedback states:
- `EXIT_CONFIRM_IDLE`.
- `EXIT_BLOCKED_ACTIVE_JOBS` (requires explicit override or cancellation first).

Navigation:
- `y` -> Shutdown sequence.
- `n` -> Main Menu.

Dependencies:
- Runtime active-job count and shutdown policy.

## UI State Needs

State owned by UI adapter:
- `currentScreen`: enum of screen ids.
- `selectedIndexByScreen`: list cursor positions.
- `flashMessage`: transient success/error banner.
- `draftCreateRequest`: in-progress form fields.
- `pendingAction`: action id + started-at for spinners/disabled controls.
- `lastError`: latest UI-displayable error envelope.
- `filters`: history/status filters.

State consumed from runtime/data layers:
- `harnessProfileSummary`.
- `inboxSummary` and `inboxItems`.
- `activeJobsSummary` and `activeJobs`.
- `jobDetails[jobId]` + optional log tail.
- `historyPage` + cursor.
- `peerDirectory` + peer health snapshots.
- `networkHealth` + startup/shutdown state.

Derived UI state:
- `canExitSafely` (no active jobs).
- `canCancelSelectedJob`.
- `canSubmitRequestDraft` (validation passed).
- `emptyStateMessage` per screen.

## Input Events (UI -> Runtime)

Common navigation/control events:
- `ui.navigate(screenId)`
- `ui.back()`
- `ui.refresh(scope)`
- `ui.quit.requested()`
- `ui.quit.confirmed()`

Inbox/request events:
- `ui.inbox.list.requested(filter, cursor)`
- `ui.request.detail.requested(requestId)`
- `ui.request.accept.requested(requestId)`
- `ui.request.decline.requested(requestId, reason?)`
- `ui.request.create.submitted(payload)`

Job events:
- `ui.jobs.active.list.requested()`
- `ui.job.detail.requested(jobId)`
- `ui.job.cancel.requested(jobId)`
- `ui.job.history.list.requested(filter, cursor)`

Peer events:
- `ui.peer.list.requested()`
- `ui.peer.add.requested(payload)`
- `ui.peer.update.requested(peerId, patch)`
- `ui.peer.remove.requested(peerId)`
- `ui.peer.test.requested(peerId)`

Recovery events:
- `ui.error.retry.requested(actionContextId)`

## Runtime/Data Feedback Contract (Runtime -> UI)

Required response/update envelopes consumed by UI:
- `ack`: command accepted with correlation id.
- `result.success`: command completed with data payload.
- `result.error`: command failed with error envelope (code, message, retryable, context).
- `state.snapshot`: full refresh payload for a requested scope.
- `state.delta`: incremental update for active screen models.
- `lifecycle`: startup/shutdown progress notifications.

Minimum behavior rules:
- Every mutating UI event must receive either `result.success` or `result.error`.
- Async updates (job progress, peer health) must be deliverable as `state.delta` without forcing full redraw.
- Payloads should be display-ready or include explicit formatting metadata to keep formatting logic out of domain services.

## Navigation Summary

Primary path:
- Boot -> Main Menu -> (Inbox | Create Request | Active Jobs | History | Peers) -> Detail screens -> Main Menu -> Exit Confirmation -> Shutdown.

Recovery path:
- Any screen on blocking failure -> Error/Recovery -> Retry or Main Menu.

## Acceptance Coverage

- Primary controls listed: yes (per screen control mapping above).
- Feedback states listed: yes (state enums per screen).
- UI dependencies on runtime/data explicit: yes (dependencies section per screen + shared contracts above).

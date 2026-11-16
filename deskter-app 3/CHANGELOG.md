# Publishing and pricing corrections

## Unified frontend and save-flow revision

- Run one frontend against the server or an explicitly labeled browser-local preview adapter; remove the separately maintained chat-demo implementation from the workflow.
- Offer explicit Save draft and Publish asset actions for new assets, and Save changes for edits.
- Show native validation errors in the form, preserve input on failure, guard repeated submissions, prevent Escape during a pending save, and show request progress.
- Accept properly grouped currency input including `₱1,250.50` and `PHP 1250.50`; reject malformed grouping, invalid precision, zero paid rates, and amounts outside the supported range.
- Translate static-server HTML responses, network failures and timeouts into actionable messages.
- Persist local-preview data in browser storage when available; explicitly label session-only fallback.
- Add form-submit, persistence, error-recovery and API-transport regression tests. Chromium still cannot launch under the environment's restrictions.

## Reliability revision

- Add full asset detail and seller listing dialogs, buyer inquiry history, and seller responses.
- Reject malformed record IDs consistently with HTTP 400 rather than database failures.
- Preserve passwords exactly, validate email shape, rotate the current session on login, and purge expired sessions on authentication.
- Close SQLite connections reliably after every operation.
- Count only currently visible saved listings; retain their saved relationship if an owner republishes them.
- Prevent an unsuccessful state reload from resuming a pending authenticated action with stale state.
- Add regression coverage for reply ownership, inquiry privacy, archived saves, malformed inputs, passwords, session expiry, UI rendering, detail escaping, and quote filters.

- Resume asset creation after authentication; resume save, follow, and inquiry intents too.
- Commit database mutations before sending success responses, preventing a subsequent reload from racing the database commit.
- Clear filters after saving so the new asset is visible in Assets.
- Add private drafts, publication, archival, republication, and an idempotent upgrade for existing databases.
- Enforce visibility and ownership on the server. Unpublished listings cannot receive new saves or inquiries.
- Add six explicit PHP pricing models, integer centavo conversion, validation, and price labels including billing intervals.
- Add profile display-name editing and reject self-following.
- Replace sample listings with real database records and useful empty states.
- Mark unavailable sidebar sections Soon and disable the Pro upgrade control.
- Improve card alignment, stable cover colors, long-description handling, modal layout, and submit progress feedback.
- Explain how to start the server when the HTML is opened directly.

Four backend test methods pass, covering existing-data migration, publication lifecycle, visibility, ownership, inquiries, account operations, and pricing validation. Frontend pricing and escaping tests pass. Full browser rendering and browser form interactions remain unverified because Chromium cannot launch under the environment's restrictions.

This is still not a production release. Hosted deployment, payments, uploads/fulfillment, email verification and recovery, login throttling, protected moderation, ad delivery, and Pro billing remain outstanding.

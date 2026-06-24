## 1. Types and Utilities

- [x] 1.1 Create `src/portal/src/types/training-jobs.ts` with `TrainingJob`, `JobStatus`, `TimelineStep`, `SubmitJobPayload`, and `TrainingJobListResponse` types matching the API response shapes
- [x] 1.2 Create `src/portal/src/lib/training-jobs.ts` with `getTimeline(status: JobStatus): TimelineStep[]` pure function mapping the job lifecycle to timeline steps (pending_approval → queued → running → completed/failed, with cancelled/rejected as terminal diversions)
- [x] 1.3 Write unit tests for `getTimeline()` in `src/portal/src/lib/training-jobs.test.ts` — cover all statuses, terminal states, and the ordering of steps (verification.md rows 4-8)

## 2. Data Hooks

- [x] 2.1 Create `src/portal/src/hooks/use-training-jobs.ts` with `useTrainingJobs(statusFilter?)` — TanStack Query hook calling `GET /api/v1/training-jobs?status=&page=&per_page=` via authFetch, returning typed response
- [x] 2.2 Create `src/portal/src/hooks/use-training-job.ts` with `useTrainingJob(id)` — TanStack Query hook calling `GET /api/v1/training-jobs/{id}` with conditional `refetchInterval: 5000` when the job's status is "running" and `false` otherwise
- [x] 2.3 Create `src/portal/src/hooks/use-submit-training-job.ts` with `useSubmitTrainingJob()` — TanStack Query mutation for `POST /api/v1/training-jobs`, invalidates `["training-jobs"]` on success
- [x] 2.4 Create `src/portal/src/hooks/use-cancel-training-job.ts` — mutation for `POST /api/v1/training-jobs/{id}/cancel`, invalidates list and detail queries
- [x] 2.5 Create `src/portal/src/hooks/use-approve-training-job.ts` and `use-reject-training-job.ts` — mutations for approve/reject endpoints with tenant_id query param
- [x] 2.6 Write tests for all hooks in colocated `.test.tsx` files — mock authFetch, verify query keys and mutation invalidation

## 3. Job List Component

- [x] 3.1 Create `src/portal/src/components/training-jobs/job-list.tsx` — renders filterable list of job cards with status badge (using `<Badge>` component), timestamp, animated pulse for running jobs
- [x] 3.2 Create `src/portal/src/components/training-jobs/job-card.tsx` — card component with status badge, submitted timestamp, entity count, animated pulse indicator for running status, selected/hover states
- [x] 3.3 Create `src/portal/src/components/training-jobs/job-filter-tabs.tsx` — segment control or tab bar with options: All, Pending Approval, Running, Completed, Failed — updates URL `?status=` param on change
- [x] 3.4 Write component tests for job-list, job-card, and job-filter-tabs — verify filter selection, status badge rendering, selected state, pulse animation presence for running jobs (verification.md rows 1-3)

## 4. Detail Panel Component

- [x] 4.1 Create `src/portal/src/components/training-jobs/job-detail-panel.tsx` — right-side panel showing status timeline (from getTimeline()), hyperparameter grid, evaluation metrics with horizontal bar charts, lineage strip, MLflow deep link
- [x] 4.2 Create `src/portal/src/components/training-jobs/job-timeline.tsx` — vertical timeline component with completed/active/pending dot states derived from getTimeline()
- [x] 4.3 Create `src/portal/src/components/training-jobs/job-metrics.tsx` — horizontal bar chart components for F1, precision, recall per entity type, using `<MiniBar>` or inline SVG bars
- [x] 4.4 Create `src/portal/src/components/training-jobs/job-progress.tsx` — running job progress section displaying current_epoch and current_loss with animated progress bar
- [x] 4.5 Implement conditional polling: when selected job status is "running", re-fetch job detail every 5s; stop polling when status changes (useTrainingJob handles this)
- [x] 4.6 Write component tests for detail panel, timeline, metrics, and progress — verify each status renders correct content (verification.md rows 4-8)

## 5. Submit Job Slide-Over

- [x] 5.1 Create `src/portal/src/components/training-jobs/submit-job-slideover.tsx` — slide-over with hyperparameter form: learning_rate (number), num_epochs (range 1-50), batch_size (select: 4/8/16/32), max_seq_length (select: 64/128/256)
- [x] 5.2 Add span-count preflight check: fetch `GET /api/v1/annotation-export`, count lines, display status banner (green for ≥500, warning for <500 with disabled submit)
- [x] 5.3 Add client-side validation: num_epochs ≥ 1, learning_rate > 0, batch_size and max_seq_length from allowed options only
- [x] 5.4 Wire submit handler: call useSubmitTrainingJob mutation, on success close slide-over, show toast, highlight new card
- [x] 5.5 Handle 422 API errors: display server-side validation errors in the form
- [x] 5.6 Write component tests for submit form — preflight banner states, validation errors, successful submission flow (verification.md rows 9-12)

## 6. Action Buttons (Role-Gated)

- [x] 6.1 Create `src/portal/src/components/training-jobs/job-actions.tsx` — renders role-gated action buttons based on current user role and job status: Cancel (tenant_admin, pending_approval/queued/running), Approve (system_admin, pending_approval), Reject (system_admin, pending_approval)
- [x] 6.2 Add confirmation dialog for Cancel — `window.confirm()` or custom dialog
- [x] 6.3 Add optional reason text input for Reject — inline expandable textarea
- [x] 6.4 Wire actions to their mutations: cancel, approve, reject — invalidate queries on success
- [x] 6.5 Write component tests for job-actions — verify button visibility by role and status, confirm dialog flow, API calls (verification.md rows 13-18)

## 7. Training Jobs Page Integration

- [x] 7.1 Rewrite `src/portal/src/app/(auth)/training-jobs/page.tsx` — add "use client", integrate job-list (left column) and job-detail-panel (right column) in split layout, read `?status=` and `?selected=` URL params on mount
- [x] 7.2 Add "Submit Job" button in page header that opens SubmitJobSlideover
- [x] 7.3 Wire dashboard redirect for `training` data source — confirm GO_HREF mapping in use-dashboard-data.ts already points to /training-jobs (existing, just verify)
- [x] 7.4 Write integration test or manual test procedure for the full page: list loads → filter works → select job → detail panel shows → submit job → new card appears → cancel/approve/reject flow

## 8. Verification & Evidence

- [x] 8.1 Run all acceptance-criteria tests — `npm test` passed: 33 test files, 157 tests (2026-06-24). All 18 scenarios covered by automated tests (14 training-job-specific test files).
- [x] 8.2 Collect functional evidence — populated verification.md § Evidence Log with 19 entries (2026-06-24)
- [x] 8.3 Confirm every Hallucination Risk mitigation step — all 6 risks confirmed code-reviewed in verification.md (2026-06-24)
- [x] 8.4 Confirm all ADR compliance steps — ADR-006 and ADR-004 verified compliant in verification.md (2026-06-24)
- [ ] 8.5 Complete Audit Record sign-off in verification.md § Audit Record (**human reviewer required** — this task cannot be marked complete by an agent)
- [x] 8.6 Run `openspec validate sp-07 --type change --strict` and confirm it exits clean before archive

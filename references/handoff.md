# Safe handoff reports

Read this reference only when saving is requested. The report is useful even
when persistence is unavailable: always return it in the conversation. Saving
adds a local Markdown artifact, not a collector, background job, or Git commit.

This save procedure only creates new, generated filenames under the current
worktree's `.agents/handoff/`. If the user requests a different location or an
exact filename, explain the supported destination and ask before substituting
it. Without confirmation of that substitution (including non-interactive
execution), return the report without saving; do not silently redirect the output
or treat the request as permission to overwrite. A custom export is a separate explicitly scoped task,
not an exception to this procedure's path and non-overwrite guarantees.

## Identity inside the report

Prepend a compact metadata block to the saved five-part report. This is the
saved artifact's format, not a requirement to repeat a YAML/frontmatter block in
the conversational response; retain the normal comparison and evidence bindings
there. Use the same facts already collected for the summary; do not re-resolve
moving refs at save time. Escape ref labels as data, not executable shell text or Markdown syntax.
Record:

- `generated_at`: generation time in UTC ISO 8601, such as `2026-10-01T08:15:30Z`.
- `comparison_mode`: `branch-introduced`, `endpoint-snapshot`, `single-commit`,
  or `working-tree`, matching the comparison actually performed. For combined
  committed + WIP reports retain the committed mode and describe WIP separately.
- `base_label`, `target_label`, and the full `base_sha`, `target_sha`, and
  `merge_base_sha`. Short IDs in a title or filename do not replace full IDs here.
  Use `null` with an explicit reason for inapplicable/unavailable identities,
  never a guessed SHA: root-commit base is `null` (`root-empty-tree`); merge-base
  is `null` (`not-applicable`) for endpoint, single-commit, and WIP-only modes.
  A WIP-only report's target is its full HEAD SHA, or `null` (`unborn-HEAD`).
  Preserve requested range notation; for a merge single-commit comparison also
  record the selected parent index and full parent SHA.
- `tree_left`, `tree_right`: full tree object IDs actually compared, distinct
  from commit SHAs. For a root commit, record the repository-format empty-tree
  object ID on the left and the root commit's tree ID on the right; do not
  mislabel the empty tree as a commit. For WIP-only mode use `null` with a reason
  and identify the mutable layers in `wip_scope`, rather than inventing tree IDs.
- `history_selection`: the exact frozen commit/range selection and traversal
  options used for the count and timeline; use `none` for WIP-only reports.
  Record committed path restrictions as well: the actual pathspecs/exclusions
  and whether they apply to tree statistics, history selection, or both. State
  `whole repository` explicitly when there are no path restrictions.
- `wip_scope`: mark staged, unstaged, and untracked each as included or excluded;
  include path restrictions and the untracked line-count policy. For committed
  only reports mark all three excluded, even if the worktree is dirty. For WIP
  also record full `wip_head_sha` (or `null` with reason) and observation time or
  collection interval. State that uncommitted contents are not reconstructible
  from HEAD and may change during collection; disclose any observed movement.

Capture WIP facts before creating the report directory/file so the handoff does
not count itself as an input change. Do not silently omit pre-existing reports
from a user-requested scope; disclose any exclusions.

## Filename

Use this layout relative to the current repository/worktree root:

```text
.agents/handoff/<UTC>-<target>-<target-id>-vs-<base>-<base-id>-<nonce>.md
.agents/handoff/<UTC>-<target>-<head-id>-working-tree-<nonce>.md
```

- `<UTC>` uses filesystem-safe UTC time, e.g. `20261001T081530Z`.
- Each ref label becomes an ASCII slug: replace characters outside
  `[A-Za-z0-9_-]` with `-`, trim leading/trailing `-`, truncate to 40 characters,
  and use `ref` if empty. Thus dots, slashes, traversal, and control characters
  cannot become path components. Treat labels only as data; quote shell arguments
  and never interpolate raw refs into executable code.
- IDs are the first 12 hexadecimal characters of the already captured full SHAs;
  use `none` when the corresponding SHA is null. Metadata explains why.
- `<nonce>` is a fresh 12-character hexadecimal random suffix for every save.
  Timestamp, short SHA, or sanitized labels alone are not uniqueness guarantees:
  distinct refs can sanitize identically and multiple reports can share HEAD.
- A collision is a retry with a new nonce, never permission to truncate a file.
  Allow at most three candidate-creation attempts total, including the first;
  if all collide, report persistence failure without a fourth attempt.

## Safe-write procedure

1. Anchor the destination to the verified physical root of the current worktree,
   not the shell's incidental subdirectory or another linked worktree. Inspect
   `.agents`, `handoff`, and the candidate file without following symlinks. Reject
   every symlink (including dangling links), non-directory parent, or non-regular
   existing target; do not repair, unlink, or replace them. Resolve the intended
   absolute destination and verify it remains under that root before mutation.
2. Create missing directories only along that checked chain. Preserve the same
   no-symlink/containment guarantees while creating/opening them: use no-follow,
   directory-relative operations anchored to verified directory handles, or an
   equivalent host primitive that prevents parent replacement from redirecting
   the write. A one-time realpath/existence check followed by an ordinary write
   does not protect against symlink races. On Unix, Python's `os.open` with
   `dir_fd`, `O_DIRECTORY`/`O_NOFOLLOW` for each directory and
   `O_CREAT | O_EXCL | O_NOFOLLOW` for the file provides suitable primitives;
   check platform support rather than assuming it. This is an implementation
   option, not a new dependency or bundled script. If available tools cannot
   ensure these guarantees, decline persistence rather than claiming a safe save.
3. Check Git ignore status for the actual candidate path, not just the directory
   (a file-level negation can override it). Warn if the report is not ignored or
   the check fails; do not modify `.gitignore`, `.git/info/exclude`, global ignore
   rules, or the index. Being unignored is a warning, not permission to stage it.
4. Create the file with exclusive-create and no-follow semantics under the
   verified parent. Do not use a check-then-write, plain truncating redirection,
   or a generic write tool that overwrites existing files. Existing regular
   files trigger the nonce retry; symlinks and other types trigger refusal.
   This contract does not offer overwrite, even on a repeat save request: offer
   a new version instead. Any separate overwrite operation would require fresh
   explicit user confirmation of the exact existing path and its contents, and
   is outside this skill's save procedure.
5. Write the metadata and full report; check completion, close, and verify the
   newly created regular file's contents through the safe handle/path. Only then
   return its path as saved. If writing/verification fails, state the error and
   any known partial artifact path without presenting it as a successful report.
   Do not delete or rewrite pre-existing artifacts to recover. Always deliver
   the complete report in the conversation, including when permission, collision
   retries, or path safety prevents persistence; an ignore warning alone does not
   block an otherwise safe save.

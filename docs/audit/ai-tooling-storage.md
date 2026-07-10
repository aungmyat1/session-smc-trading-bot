# AI Tooling Storage Audit

Date: 2026-07-06
Status: Findings only — no cleanup performed
Related: `config/storage_policy.yaml` (`cache_cleanup.requires_confirmation_paths`),
`docs/vps/CLEANUP_PLAN.md` ("Needs Confirmation" section, prior partial coverage)

## Scope

`~/.claude`, `~/.codex`, `~/.gemini`, `~/.continue`, `~/.antigravity-ide-server`
— five AI coding-tool directories totaling **~1.86G** on `auto-trade-vps`.

## Findings by directory

| Directory | Size | Last modified | Purpose | Cache vs. config |
|---|---:|---|---|---|
| `~/.claude` | 243M | 2026-07-06 (today — active) | Claude Code CLI: `projects/` (202M, session transcripts + memory files), `file-history/` (34M, edit undo history), `plugins/` (6.4M) | **Mixed** — `projects/` contains this project's own persistent memory system (`memory/*.md` referenced throughout this session) — NOT a pure cache; deleting would destroy cross-session memory |
| `~/.codex` | 553M | 2026-07-05 | Codex CLI: `sessions/` (87M), `.tmp/` (87M), `cache/` (4.4M), `plugins/` (2.6M) — the remaining ~370M is unaccounted for in the top-level breakdown (likely binaries/logs below the depth-1 scan) | **Mostly cache/session-log** — `.tmp/` (87M) is very likely safe to clear; `sessions/` is session history, lower confidence it's safe without knowing if any session is still referenced |
| `~/.gemini` | 273M | 2026-07-03 (3 days stale) | `antigravity-ide/` (246M — the large majority), `antigravity-cli/` (25M), `tmp/`, `history/` | **Likely mostly cache** (IDE extension bundle/state) — 3-day staleness suggests this isn't being actively written; lower-risk cleanup candidate than `.codex`/`.claude` |
| `~/.continue` | 190M | 2026-07-04 | `index/` (81M — semantic code index), `sessions/` (55M), `dev_data/` (55M) | **Mixed** — `index/` is a rebuildable embedding index (safe to clear, rebuilds on next use); `sessions/`/`dev_data/` are usage history, not obviously safe without knowing retention needs |
| `~/.antigravity-ide-server` | 600M | 2026-07-06 (today — active) | `bin/` (349M — IDE server binaries), `extensions/` (249M) | **Not a cache** — this is an installed IDE server (Antigravity IDE remote server), analogous to `~/.vscode-server`; deleting it would break that IDE connection, not just force a redownload of a small cache |

## Active usage signal

Both `~/.claude` and `~/.antigravity-ide-server` show a **last-modified
timestamp of today** — consistent with this being an actively-used
development/agent session on this host right now (this very session, plus
whatever else is connected). `~/.gemini` is the most stale (3 days), the
weakest "still needed" signal of the five.

## Safe cleanup opportunities (documented, not executed)

| Candidate | Confidence | Est. reclaim |
|---|---|---:|
| `~/.codex/.tmp/` | High — named as a temp directory | ~87M |
| `~/.continue/index/` | High — rebuildable semantic index | ~81M |
| `~/.gemini` (whole dir, if Gemini/Antigravity IDE usage on this host is confirmed retired) | Medium — needs an explicit "is this still used" answer from the owner, not inferable from staleness alone | ~273M |
| `~/.codex/sessions/`, `~/.continue/sessions/`, `~/.continue/dev_data/` | Low — session/usage history, no clear staleness signal that it's abandoned | ~197M combined |

**Not candidates for cleanup at all:**
- `~/.claude/projects/` — contains this project's live memory system.
- `~/.antigravity-ide-server/{bin,extensions}` — installed IDE server, not a cache; removing it breaks that IDE connection outright, same caution as `~/.vscode-server` in `docs/vps/CLEANUP_PLAN.md`.

## Recommendation

Total confidently-safe reclaim without further owner input: **~168M**
(`~/.codex/.tmp` + `~/.continue/index`). The larger opportunity
(`~/.gemini`, 273M) needs one factual question answered first: is Gemini /
Antigravity IDE still in active use on this host? That single answer
resolves the largest reclaim candidate in this audit. No deletion is proposed
here — this document is findings only, per this task's constraints.

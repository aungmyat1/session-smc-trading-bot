# Wine Investigation Report — auto-trade-vps

Date: 2026-07-07
Status: Investigation closed — root cause not determined, evidence exhausted
for the diagnostic budget of this phase
Related: `docs/svos/ADR-0011-MT5LINUX-BROKER-BRIDGE.md` (provisioning appendix),
`docs/svos/ADR-0012-SYSTEM2-HOSTING-STRATEGY.md`

## Symptom

`wine cmd /c echo hello` (and `mt5setup.exe /auto`) fails consistently with:
```
wine: could not load kernel32.dll, status c0000135
```
Reproduced across: 2 Wine versions (11.11, 11.12 staging), 2 independently
bootstrapped prefixes (`~/.mt5`, `~/.mt5-terminal`), 3 Xvfb display sessions,
memory conditions from 400Mi to 1.9G free. 4/4 clean-state attempts failed
identically (one apparent "success" trace was later determined to be a
misread of background service-process output, not the target command).

## Hypotheses evaluated

| # | Hypothesis | Evidence for | Evidence against | Validation performed | Confidence |
|---|---|---|---|---|---|
| 1 | Kernel/Wine NTDLL loader incompatibility (kernel 6.17.0-1020-gcp vs. wine-staging) | Host runs an unusually recent kernel; wine-staging's own loader banner explicitly warns it's an experimental build | Upgrading wine-staging 11.11→11.12 (a different build against the same kernel) did not change the outcome — if this were a hard kernel/loader incompatibility specific to one Wine build, a version bump might reasonably be expected to shift behavior | Ran the exact same test on both versions, identical failure | **Medium** — not ruled out, but the version-independence of the failure weakens it somewhat |
| 2 | AppArmor restriction | Ubuntu ships AppArmor by default; some distros ship wine-specific confinement profiles | `aa-status` shows 120 loaded profiles, 26 in enforce mode — none reference `wine`, `wineserver`, or `winehq` by name or path | Ran `sudo aa-status`, inspected the full enforce-mode list | **Low** — no evidence found supporting this hypothesis |
| 3 | Yama ptrace restriction | Wine's loader can use ptrace-like mechanisms in some configurations | `/proc/sys/kernel/yama/ptrace_scope` = 1, the Ubuntu default (restricted, not disabled) — same value present on most working Wine installs; Wine failing here is a single self-contained process tree, not attempting to ptrace an unrelated process | Checked the sysctl value | **Low** — standard value, no evidence of an unusual restriction |
| 4 | `mmap_min_addr` blocking low-address mappings PE loading needs | Some old Wine/DOS-mode compatibility issues relate to low-memory-address mapping | Value is 65536, the standard Ubuntu default — not unusually restrictive | Checked the sysctl value | **Low** |
| 5 | Package corruption / incomplete configuration | Prefix was flagged as "dormant" for weeks before this investigation — could have been created against a broken package state | All 4 relevant packages (`wine-staging`, `wine-staging-amd64`, `wine-staging-i386:i386`, `winehq-staging`) report dpkg status `ii` (fully installed and configured) at both 11.11 and 11.12; a full version upgrade replaced all package content and the failure persisted identically | `dpkg -l` before and after upgrade | **Low** — an upgrade that touches every package file and doesn't change the outcome argues against simple corruption |
| 6 | Missing native Linux library dependency for the Wine loader itself | Wine binaries have real `.so` dependencies | `ldd $(which wine64)` showed zero "not found" entries; `libc6:i386` (needed for the 32-bit/WoW64 compatibility layer) is installed | Ran `ldd`, checked `dpkg -l libc6:i386` | **Low** — no missing dependency found at this level |
| 7 | Filesystem permissions | Prefix files could be owned by the wrong user/mode | Both prefixes were created fresh by the same user (`aungp`) that ran the failing commands; no permission-denied errors appeared in any run, only the DLL-load status code | Inspected `ls -la` output during earlier phases, no anomalies found | **Low** |
| 8 | Environment variable interference (`WINEDLLOVERRIDES`, locale, etc.) | Untested directly | The error is a loader-level status code (`c0000135` = `STATUS_DLL_NOT_FOUND`), not a locale or override-shaped symptom; no custom Wine env vars were set beyond `WINEPREFIX`/`WINEARCH`/`DISPLAY` in any run | Reviewed the exact commands run across all attempts | **Low** |
| 9 | Container/cgroup resource restriction | Host is memory-constrained | This is a full GCE Compute Engine VM (KVM), not a container — no cgroup/namespace restriction layer beyond standard systemd slices; memory headroom varied 400Mi-1.9G across test runs with no change in outcome | Checked `free -h` at each attempt; confirmed VM (not container) via `docs/vps/VPS_INVENTORY.md`'s existing platform identification | **Low** |
| 10 | Deeper syscall-level failure (ptrace/strace investigation) | `strace` is available on the host | Attempted `strace -f` (timed out — ptrace-follow overhead too high for the process tree within a reasonable window) and `strace` without `-f` (ran against `~/.wine`, a different, unrelated prefix, by mistake; produced 3.5MB of IPC chatter with wineserver but the trace was killed by timeout before reaching either a clean exit or the failure point) | Both attempts were inconclusive, not negative — this remains genuinely untested, not ruled out | Two attempts, both inconclusive due to tooling overhead/scope error | **Untested** — the strace attempts did not produce usable evidence either way |

## Disposition

No single hypothesis was confirmed. The strongest surviving candidate is
**#1 (kernel/Wine loader incompatibility)** by elimination — every other
tested hypothesis has evidence against it, and #1 is the one not
contradicted by the version-upgrade test (only weakened, not ruled out).
**#10 (deeper strace analysis)** remains a legitimate next step but requires
a properly-scoped diagnostic session (longer timeout budget, correct prefix
target, ideally `strace -f -e trace=memory,openat -o log` run in the
background and inspected after, rather than run inline with a hard timeout)
that this phase's diagnostic budget did not accommodate.

**Stopping here per this investigation's own governance rule**: evidence
for the cheaply-testable hypotheses is exhausted; continuing would mean
either speculating without evidence or re-attempting the same inconclusive
strace approach, which risks becoming exactly the "randomly retry commands"
pattern this investigation was explicitly scoped to avoid.

## Recommendation

Do not invest further diagnostic time on **this specific host's** Wine
installation without a properly-scoped session (dedicated strace tooling,
no inline timeout pressure, willingness to accept it may still not resolve).
Given `docs/svos/ADR-0012-SYSTEM2-HOSTING-STRATEGY.md` already recommends a
dedicated execution node, and a fresh node would use a clean base image
(sidestepping whatever this specific host's history — kernel version,
package state, or something not yet identified — is contributing to the
failure), that path is lower-risk than continuing to debug this host in place.

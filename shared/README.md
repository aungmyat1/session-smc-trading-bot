# shared

This package root is reserved for pure, reusable contracts and logic that can
be consumed by both the future `production/` runtime and the existing `svos/`
qualification stack.

Allowed directions:

- `shared` may depend on standard library, pure third-party utilities, and
  schema/model packages that have no runtime side effects.
- `shared` must not depend on `svos`, `execution`, `dashboard`, `research`, or
  broker/database runtime adapters.

Initial migration targets are documented in
`docs/architecture/shared_library_design.md`.

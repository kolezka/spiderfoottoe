# Selective upstream sync

This fork develops independently. Upstream commits are candidates for individual backports, not a release train. Do not merge the upstream tip or advertise version parity based on a partial sync.

## Comparison boundary

- Fork base: `7f4b0a2ca7ca94a9e688c28b2b498acf9a691496`
- Upstream: `poppopjmp/spiderfoot` at `4b53ca68ea63548c25c4148a3a18bda8d9417c74`
- Common ancestor: `2dad3615ba720d4e0d4b9a2662d1643217ee232f`
- At those revisions: 17 fork-only commits, 111 upstream-only commits, including merges. These counts describe history, not 111 missing fixes.

## Selection

The [111-commit inventory](upstream-sync-inventory.txt) includes merge commits. Unless explicitly listed here, a commit in that inventory was omitted in full. The following changes were ported by hunk, not by merging their entire commits:

- `4ef92852`: preserve boolean settings across integer and string serialization. Cover both global and module settings.
- `6145e3b9`: log the missing database connection string in the maintenance task instead of raising a `NameError`. This path does not require a running database.
- `cc709451`: enable the narrow blocking Flake8 gate; do not import unrelated product or workflow changes.
- `bb015f6c` and `5792e6b9`: adapt the installation guide to the Compose service and frontend port, keeping the fork's clone URL. Do not import upstream release metadata, Helm, or module documentation.

No active scanner integration, automatic upstream merge, release or deploy workflow is included.

Keep the fork's first-boot settings when porting unrelated changes. For example, the upstream core Compose file has writable cache mounts but uses a different size; its Qdrant snapshots path is still `/qdrant/snapshots` rather than the fork's volume-backed path. Neither file should be replaced wholesale. See [fork changes](fork-changes.md) for the fork-specific behavior.

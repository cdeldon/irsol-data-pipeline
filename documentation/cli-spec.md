# CLI Specification (Cyclopts)

## Status

Draft specification for the next-generation command-line interface built with
`cyclopts`.

## Goals

- Provide one cohesive CLI entry point for operations tasks.
- Replace standalone scripts with a command/sub-command model.
- Keep output human-readable by default, including a runtime ASCII banner.
- Support shell completion and flow-group auto-completion.

## Finalized Decisions

- Primary executable name: `idp`
- Legacy standalone commands are removed:
  - `irsol-configure`
  - `irsol-dashboard`
  - `irsol-serve-flat-field-correction`
  - `irsol-serve-slit-images`
  - `irsol-serve-maintenance`

## Command Tree

```text
idp
  plot
    profile <input-dat-file-path> [--show] [--output-path <output-png-file-path>]
  prefect
    start
    reset-database
    flows
      list
      serve [flow-groups...]
    variables
      list
      configure
  info
```

## `plot` Commands

### `plot profile`

#### Synopsis

```bash
idp plot profile <input-dat-file-path> [--show] [--output-path <output-png-file-path>]
```

#### Arguments

- `<input-dat-file-path>`: Existing `.dat` or `.sav` measurement file.

#### Options

- `--show`: Display the rendered figure after saving it.
- `--output-path <output-png-file-path>`: Optional `.png` path to write.

#### Behavior

- Loads Stokes parameters from the requested raw measurement file.
- Renders the four-panel Stokes profile plot using the library plotting routine.
- Saves the result as a `.png` image when `--output-path` is provided.
- Requires at least one of `--show` or `--output-path`.

#### Exit Codes

- `0`: success
- `2`: invalid arguments
- `1`: runtime error (file loading or plotting)

## Global Behavior

- All commands print a human-readable runtime presentation banner by default.
- Banner content reuses current runtime presentation semantics:
  - Pipeline version
  - OS and Python runtime
  - Key dependency versions
- Global flags:
  - `--help`: show help text.
  - `--version`: print package version and exit `0`.
  - `--no-banner`: suppress the ASCII runtime banner.

## Flow Group Registry

Allowed flow-group identifiers for `prefect flows serve [flow-groups...]`:

- `flat-field-correction`
- `slit-images`
- `maintenance`

These are the canonical user-facing IDs and map to deployment sets by topic.

## Shell Completion and Auto-Completion

### Positional Flow Completion

- `idp prefect flows serve <TAB>` must suggest only valid flow-group IDs from the
  registry. This is most likely implemented by the `cyclopts` framework, but might need configuration in the app code to provide the dynamic list of flow groups (possibly as string literals)
- Completion is prefix-based and case-sensitive to canonical lowercase IDs.
- Invalid values are rejected at parse time with an error and non-zero exit.

### Shell Completion Script

- The CLI exposes completion generation compatible with `bash` and `zsh`.
- Completion includes commands, options, and flow-group positional suggestions.

## `prefect flows` Commands

### `prefect flows list`

#### Synopsis

```bash
idp prefect flows list [--format table|json] [--topic TOPIC]
```

#### Options

- `--format`: output format. Default `table`.
- `--topic`: filter by topic tag (`flat-field-correction`, `slit-images`,
  `maintenance`).

#### Behavior

- Displays discoverable flow groups and concrete flow/deployment metadata.
- Human-readable table output includes:
  - Flow group
  - Flow name
  - Schedule type (manual/scheduled when available)
  - Default deployment name(s) served by that group
- JSON output includes stable keys suitable for tooling.

#### Exit Codes

- `0`: success
- `2`: invalid arguments
- `1`: runtime error (Prefect/API/internal)

### `prefect flows serve`

#### Synopsis

```bash
idp prefect flows serve [flow-groups...] [--all]
```

#### Arguments

- `flow-groups...`: zero or more values from the flow group registry.

#### Options

- `--all`: serve all flow groups. Shall not be used when specific flow groups are provided.

#### Selection Rules

- Valid forms:
  - `idp prefect flows serve flat-field-correction`
  - `idp prefect flows serve flat-field-correction slit-images`
  - `idp prefect flows serve --all`
- Invalid form:
  - `idp prefect flows serve --all flat-field-correction` (mutually exclusive)

#### Behavior

- Registers deployments for selected flow groups.
- Starts serving selected deployments in one process.
- Relies on internal prefect printing for deployed flow information and health status.
- Acts as a blocking operations command that keeps the serve process alive until interrupted.

#### Exit Codes

- `0`: server exited normally
- `2`: invalid arguments or mutually exclusive options
- `1`: runtime error (deployment registration, Prefect startup)

## `prefect` Commands

### `prefect start`

#### Synopsis

```bash
idp prefect start
```

#### Behavior

- Delegates to Prefect's native Cyclopts `server_app` implementation.
- Starts the Prefect server process using Prefect's maintained CLI logic.

#### Exit Codes

- Delegated from Prefect's `server start` command behavior.

### `prefect reset-database`

#### Synopsis

```bash
idp prefect reset-database
```

#### Behavior

- Delegates to Prefect's native Cyclopts database reset implementation.
- Drops and recreates Prefect's local database state.

#### Exit Codes

- Delegated from Prefect's `server database reset` command behavior.

## `prefect variables` Commands

### `prefect variables list`

#### Synopsis

```bash
idp prefect variables list [--format table|json]
```

#### Options

- `--format`: output format. Default `table`.

#### Behavior

- Reads and displays current Prefect variable values.
- Includes at least:
  - Variable name
  - Current value (or explicit unset indicator)
  - Required flag
  - Topic tags using that variable
  - Default value configured in registry (if any)
- Table output is for operators; JSON output is stable for automation.

#### Exit Codes

- `0`: success
- `2`: invalid arguments
- `1`: runtime error (Prefect/API/internal)

### `prefect variables configure`

#### Synopsis

```bash
idp prefect variables configure [--update-existing]
```

#### Options

- `--update-existing`: prompt to update already-set variables.

#### Behavior

- Interactive setup for required and optional variables.
- Prompts mirror current bootstrap experience.
- Confirmation is required before writing a value.
- Final report summarizes statuses (`set`, `updated`, `already-set`,
  `kept-existing`, `skipped`, `failed`).

#### Exit Codes

- `0`: completed with no failures
- `3`: completed with one or more variable failures
- `2`: invalid arguments
- `1`: runtime error

## `info` Command

### Synopsis

```bash
idp info
idp info --format table|json
```

### Options

- `--format`: output format. Default `table`.

### Behavior

- Prints operational information in a human-readable format.
- Always includes runtime banner unless `--no-banner` is set.
- Includes:
  - Installed pipeline version
  - Runtime environment details
  - Registered flow groups
  - Prefect variable status summary

### Exit Codes

- `0`: success
- `2`: invalid arguments
- `1`: runtime error

## Error Contract

- Parse/validation errors go to stderr and use exit code `2`.
- Runtime errors go to stderr and use exit code `1`, except for
  partial-success `variables configure` (`3`).
- Error messages must be actionable and include the failing command context.

## Packaging Contract

`pyproject.toml` scripts section will expose:

- `idp = irsol_data_pipeline.cli.app:app`

No legacy script entries remain after migration.


## Implementation Sequence

1. Introduce new `cyclopts` app module and command wiring.
2. Port variable bootstrap logic into `variables configure`.
3. Port serve scripts into group-selectable `prefect flows serve`.
4. Add `prefect flows list` and `info` read-only reporting commands.
5. Add completion support and completion tests.
6. Update docs (`running.md`, `prefect-production.md`) to new commands.
7. Remove legacy script exports from `pyproject.toml`.

## Global notes
* `PREFECT_ENABLED=true` is always set by the code CLI automatically
* table reports are printed using `rich` and are intended for human operators
* JSON reports are intended for automation and should have stable keys and formats

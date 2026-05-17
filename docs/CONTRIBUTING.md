# Contributing

PRs welcome — bug fixes, additional model support, better documentation,
translations, dashboard examples, automation examples.

## Repository layout

See [ARCHITECTURE.md](ARCHITECTURE.md) for a tour of the modules in
`custom_components/helios_easycontrol3/` and how data flows from the
device through the coordinator into HA entities.

## Adding a new entity

If you want to expose another value, the mechanical steps are:

1. **Add a constant** to `addresses.py` (with a comment about what it
   represents).
2. **Add a field** to `KWLSnapshot` in `coordinator.py`.
3. **Register it** in the appropriate poll list in `coordinator.py`
   (`_HIGH_ADDR_POLL` for periodic reads, `_DEVICE_INFO_ADDRS` for
   one-time-on-setup reads).
4. **Map the raw value** in `_apply_high_address_values()`.
5. **Define the entity** (`_SensorDef` / `_NumberDef` / `_SwitchDef` /
   `_BinaryDef`) in the matching platform file
   (`sensor.py`, `number.py`, etc.).
6. **Add translation strings** in `translations/en.json` and
   `translations/de.json` if the entity uses `translation_key`.

## Code style

- Type hints everywhere, Python 3.10+ syntax (`int | None`).
- Docstrings in English.
- No `print()` — use `_LOGGER.debug/info/warning`.
- `async` functions for all WebSocket calls.
- **Never swallow `asyncio.CancelledError`.**

## Testing

- Syntax check all Python files before committing:
  `python3 -c "import ast; ast.parse(open(f).read())"`.
- Validate JSON / YAML.
- Live-test on your own KWL with the WebUI open in parallel for
  cross-checking values.

## Release checklist (for maintainers)

- [ ] Bump version in `manifest.json`.
- [ ] Update `docs/CHANGELOG.md`.
- [ ] Pre-commit privacy audit (see `PRE_COMMIT_PRIVACY_AUDIT.md` in repo
      root).
- [ ] `git tag vX.Y.Z && git push origin vX.Y.Z`.
- [ ] Create the GitHub release so HACS picks it up.

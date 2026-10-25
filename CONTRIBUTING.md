# Contributing

Help make imports, search, citations and local installation reliable. Research work is frozen while the product milestones ship.

## Develop

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
PYTHONPATH=prototype .venv/bin/python -m unittest discover -s prototype/tests -v
```

Default tests require no external services or private conversations. Add a regression test for each bug fix, using small invented fixtures. Existing optional model tests skip when dependencies/assets are absent; report skips honestly. Do not download models or tune reserved evaluation sets as part of a product bug fix.

CI runs the base suite and package smoke checks on macOS and Linux, Python 3.9–3.13. This is configured coverage, not a claim that remote jobs have already passed. Test installed artifacts as well as source imports when changing packaging.

## Report a bug

Include the version, OS/Python version, exact steps, and a minimal synthetic export/transcript that reproduces the issue. Distinguish an actual MCP call from a model's description of one. Omit local usernames, private exports, employer/client data, credentials and database files. See [SECURITY.md](SECURITY.md) for sensitive vulnerabilities.

## License

Contribute only material you have the right to share. Original contributions use Apache-2.0. Preserve third-party licenses and document any new runtime dependencies. Public repository and reporting details will be added when publication is configured; no contact address is assumed.

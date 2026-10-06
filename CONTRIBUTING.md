# Contributing

Bug reports, ideas and pull requests are welcome.

## Report a bug
Open an issue and paste the output of `claudio-vibecode doctor` and `claudio-vibecode status`. Say which phone
and browser you use.

## Develop
```bash
git clone https://github.com/restante/claudio-vibecode && cd claudio-vibecode
bash install.sh --dev        # links the mod and installs the package editable into claudio-tts's environment
```
Run the checks:
```bash
pytest -q && ruff check . && ruff format --check .
claude plugin validate src/claudio_vibecode/mod && claude plugin test src/claudio_vibecode/mod
```
Keep changes small, add a test for new behaviour, and don't add dependencies without a reason. The hub uses only
the Python standard library for HTTP on purpose.

## Design rules
- Off by default; anything that can make Claude act needs a paired phone and says so in the docs.
- Every route needs a token except the static page and `/pair` (which answers on the computer only).
- The phone page is plain HTML and JavaScript: no build step, no external requests.

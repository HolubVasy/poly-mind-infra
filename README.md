# poly-mind-infra

Configuration of `chat.poly-mind.net` - the LibreChat chat the owner's mother
works in - kept in Git and deployed from here.

Everything the chat is configured with (models, presets, nginx, certificate
hooks) lives in this repository. The server is only a reflection of `main`.

## Change something

1. Edit on a branch, open a pull request. `Validate` checks it - most important,
   that every preset's model is in its endpoint's model list.
2. Merge. `Deploy` applies it to the server within a minute and checks that the
   chat answers. If it does not, the change is rolled back automatically.

Changing `librechat.yaml` restarts the chat for about 10 seconds - merge when
mom is not using it.

### Add or change a preset

Edit `presets/presets.json`. For a new preset use a new UUID as `presetId`, and
make sure its `model` is listed under its endpoint in `librechat/librechat.yaml`.
Presets made in the chat UI are removed by the next deploy - make them here.

## Models are checked every month

On the 1st, `Model check` compares all models with OpenRouter:

- a model that disappeared is replaced by its successor, merged and deployed
  automatically (a preset with a vanished model is already broken);
- newer versions and price changes come as a pull request with a
  before -> after table. You decide.

Run it any time: Actions -> Model check -> Run workflow.

## Reminders

Every evening at 21:00 (Warsaw, summer time) Telegram gets the list of pull
requests still waiting for you. Nothing open - no message.

## If something goes wrong

- The chat is down after a deploy that did not roll back: Actions -> Deploy ->
  re-run the last green run, or revert the pull request and merge the revert.
- Every replaced file has a backup next to it on the server:
  `<file>.bak-<timestamp>`; presets are backed up in MongoDB as
  `presets_backup_<timestamp>`.

Details for maintainers and for Claude: [CLAUDE.md](CLAUDE.md).

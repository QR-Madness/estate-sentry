# Demo producer snapshot

`mock-estate.tar.gz` is a source snapshot of the development producer that
normally lives beside this repo at `../mock-estate/`. It replays video files
onto the same frame contract a Raspberry Pi edge agent will use, so the
perception pipeline can be exercised without hardware.

## Why it is here

`mock-estate` is its own git repository, but it has no remote — it exists on one
machine. Both the root `CLAUDE.md` and `docs/Todo.md` reference it as part of
the documented run procedure, so losing it would cost the dev loop. This is a
backup, not a mirror.

**It goes stale.** Nothing updates it automatically. Treat the working
`../mock-estate/` as the source of truth and refresh this when it moves.

## Extract

```bash
tar -xzf demo/mock-estate.tar.gz -C ..     # unpacks to ../mock-estate/
cd ../mock-estate && uv sync
```

Then follow that project's own README: it needs clips in `footage/` and a
`cameras.yaml` (copy `cameras.example.yaml`), neither of which is in the
archive.

## What is not in it

Only the files `mock-estate` tracks — 8 of them. Deliberately absent:

- `footage/` — clips are not distributable; the producer's README records
  provenance and licences
- `cameras.yaml` — local config naming those clips
- `.venv/`

## Refresh

Built with `git archive`, so it contains exactly the tracked files at a commit
and nothing from the working tree:

```bash
cd ../mock-estate
git archive --format=tar --prefix=mock-estate/ HEAD \
  | gzip -n -9 > ../estate-sentry/demo/mock-estate.tar.gz
```

`gzip -n` omits the timestamp, so rebuilding an unchanged tree reproduces the
archive byte for byte and leaves no diff. Record the source commit below when
you refresh.

**Snapshot of:** `mock-estate` @ `3d8f405` — *Add the mock estate producer under
version control* (2026-09-20)

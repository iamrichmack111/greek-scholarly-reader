# Greek Scholarly Reader — v6.3.0 candidate

Standalone interactive Ancient Greek / English parallel reader and local scholarly import tools. Source material and databases are **not** included.

## Existing local library

```bash
./install.sh
./run.sh
```

By default the reader binds to `127.0.0.1:8799`; to serve your private LAN set `HOST=0.0.0.0` and set up a firewall appropriately.

The default library location is `$HOME/GREEK-LIBRARY`, overridable using `GREEK_LIBRARY_HOME`.

The reader requires `data/alignments_v6.db` built from downloaded Perseus XML. `data/scholarly.db` provides optional LSJ word inspections.

## Rebuild the alignment index

```bash
./build.sh
```

This reads original Perseus XML and stores matched book/chapter/section pairs. It is citation-level alignment, **not** verified word-by-word or sentence-by-sentence equivalence. Input content is never automatically committed.

## Build scholarly text index

`scholar.py` is included for reproducibility. It imports sources already present under `$HOME/GREEK-LIBRARY`; consult its `--help` for build and search commands. This operation can be long-running.

## Public data release

Do **not** upload either `scholarly.db` or `alignments_v6.db` yet. Generate the edition inventory first:

```bash
python3 audit_sources.py --base "$HOME/GREEK-LIBRARY" --output source-license-review.csv
```

Each edition must be checked for copyright, license, translation rights and attribution requirements. `snapshot_local.sh` can create **local only** compressed backups; its output is not approved for distribution.

## Repositories cited for source provenance

- Perseus: https://github.com/PerseusDL/canonical-greekLit
- First1KGreek: https://github.com/OpenGreekAndLatin/First1KGreek
- LSJ Logeion: https://github.com/helmadik/LSJLogeion
- Papyri.info: https://github.com/papyri/idp.data

Different editions may carry different reuse restrictions. Keep per-edition licenses and original citations with any approved derivative dataset.

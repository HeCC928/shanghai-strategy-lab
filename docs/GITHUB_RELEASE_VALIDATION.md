# Public source release checks

Checked locally on **2 October 2026**, Windows / Python 3.10.

This record concerns the GitHub source distribution. The earlier historical snapshot and offline-bundle reproduction are documented separately in [VALIDATION_V3.md](VALIDATION_V3.md).

## Completed local checks

- Python suite: **41 passed**, 41.09 seconds.
- Frontend: TypeScript check and Vite production build passed. The approximately 4.9 MB JavaScript bundle produces a size warning; it is not a build failure and is intentionally served locally.
- PowerShell: the README command blocks and both launcher/setup scripts parse without syntax errors.
- Public demo preparation: `scripts/prepare_demo.py` generated a 12-instrument synthetic snapshot, synthetic market reference and saved experiment in an isolated output directory, with the application offline guard enabled.
- The preparation script does not modify historical showcase IDs or historical result files.

## Source archive and fresh-copy checks

- Extracted the public ZIP into a fresh directory; verified all 117 packaged source/document/image hashes against its internal manifest. The manifest itself is the 118th file.
- Confirmed that historical `storage`, Python environments, web runtime packages, `node_modules` and compiled frontend assets were absent from the archive.
- Ran the extracted `scripts/prepare_demo.py` with no historical storage present. It produced snapshot `edc8d99e125dcf0c` and a complete synthetic experiment.
- Loaded that snapshot through the normal checksum validator. The API reported 12 synthetic instruments and the synthetic study label.
- Checked run detail, trade listing, a buy's linked price/plan details, English report, evidence ZIP and PNG export. All returned HTTP 200; the chart had a valid PNG signature.
- Supplied the successfully built frontend and existing web dependencies to the extracted copy for startup verification. Started its own server on port 8773, received HTTP 200 for the page, confirmed `offline: true` and synthetic-only saved results, then stopped that process.
- Checked the root README's local links against archive contents, including all seven V3 screenshots. Screenshots were visually inspected; they depict the historical showcase, not the synthetic demo.
- Final packaging includes this updated validation record and verifies the ZIP CRC and each packaged file hash again. No public upload was performed.

## Scope

No GitHub repository was created or pushed during packaging. The workflow is supplied for future GitHub runs; no remote CI result is claimed. Dependency installation from a completely new Internet-connected machine was not repeated in this check. Existing local dependency installations were used for execution and build verification.

# CardioTwin dataset

**Extension of Z-Alizadeh Sani Dataset** — UCI Machine Learning Repository, dataset id 411.

- Page: https://archive.ics.uci.edu/dataset/411/extention+of+z+alizadeh+sani+dataset
- Download: https://archive.ics.uci.edu/static/public/411/extention+of+z+alizadeh+sani+dataset.zip
- Licence: **CC BY 4.0** — redistribution and adaptation allowed with attribution.
- Records: 303 patients, 59 columns (54 model inputs, 4 label columns, 1 constant column that is dropped).
- Citation: Alizadehsani, R., Roshanzamir, M., Sani, Z. A. (2017). *Extension of Z-Alizadeh Sani dataset* [Dataset]. UCI Machine Learning Repository.

## Why the CSV is committed (and how it is verified)

The file is ~40 KB, CC BY 4.0, and is needed by tests / CI to reproduce training offline, so
`z_alizadeh_sani_extension.csv` is committed **verbatim** (first sheet of the UCI workbook written by pandas — no
values changed; the `Fmale` spelling is normalised to `Female` at load time, not in the file).

Provenance is enforced, not asserted:

| Item | SHA-256 |
| --- | --- |
| UCI zip (pinned in `app/cardiotwin/data.py`, checked on import) | `e97af1a18733d64fa88caa0628e5fe7ce6b2e26ec4c7ee03baade92a6f1470e8` |
| `z_alizadeh_sani_extension.csv` (recorded inside the model artifact, checked by a test) | `b60472ecebdd4ea11d09b8a793711b8da2051fdf79eeae5b88f33269e4a02d37` |

Re-derive the CSV from the official download (refuses to run if the archive hash changes):

```bash
cd backend
python -m app.cardiotwin.data --import     # download from UCI, verify hash, write the CSV
python -m app.cardiotwin.data              # validate schema, print the CSV hash
```

## Things to know about the labels

* There is **no column named `CAD`**. The overall CAD label is `Cath` (`CAD` / `Normal`).
* `Cath == CAD` iff at least one of LAD / LCX / RCA is `Stenotic` in **302 of 303** rows (one row has a stenotic
  vessel but `Cath = Normal`). The vessel labels therefore almost determine the overall label — which is why `LAD`,
  `LCX`, `RCA` and `Cath` are excluded from every model's inputs (see `docs/CARDIOTWIN.md`).
* `Exertional CP` is constant (`N`) and is dropped; `BMI` is derived from `Weight` / `Length` (kept: collinearity,
  not leakage).

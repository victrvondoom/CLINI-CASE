# Track 7 external data source

CLINI-CASE adds ONE real external source to the Track 7 import workflow. It is a curated sample
for exercising field mapping and provenance. It is not a monitoring dataset and supports no
health inference.

## Source

| Item | Value |
|---|---|
| Source | Water Quality Portal (WQP), Result and Station web services |
| Publisher | National Water Quality Monitoring Council; U.S. Geological Survey (USGS); U.S. Environmental Protection Agency (EPA) |
| URL | https://www.waterqualitydata.us (services under `/data/`) |
| Citation (from the WQP user guide) | Water Quality Portal. Washington (DC): National Water Quality Monitoring Council, United States Geological Survey (USGS), Environmental Protection Agency (EPA); 2021. https://doi.org/10.5066/P9QRKUVJ |
| Site | `USGS-11173200`, Arroyo Hondo near San Jose, CA (Stream; provider NWIS) |
| Retrieval date | 2026-10-02 (verification run, UTC 04:26). The script writes the actual UTC time into every output file. |

Why this source: it is an official US government service returning real discrete observations
with an explicit sample fraction (`Dissolved` or `Total`), numeric value, unit (`ug/l`),
collection date and time, laboratory, and analytical method. Those map onto the gateway's
`LabSample` model without ML.

## Exact query

```
GET https://www.waterqualitydata.us/data/Result/search?siteid=USGS-11173200&characteristicName=Arsenic&startDateLo=01-01-2023&startDateHi=12-31-2023&dataProfile=narrowResult&mimeType=csv&zip=no&sorted=no
GET https://www.waterqualitydata.us/data/Station/search?siteid=USGS-11173200&mimeType=csv&zip=no
```

The Result query returned 26 rows. Selection is deterministic: sort by (`ActivityStartDate`,
time, `ResultIdentifier`), keep the first 8 rows that have an explicit Dissolved or Total
fraction, a numeric `ug/l` value, and no qualifier or non-detect flag. Skipped rows are listed in
the output with a reason.

## Run it

```
cd backend
python scripts/fetch_external_water_data.py --out <path-outside-repo>/wqp_arsenic.json [--limit 8]
```

Options: `--site`, `--start`, `--end` (MM-DD-YYYY), `--retrieval-date`. TLS verification is
always on. Behind a TLS-inspecting antivirus or proxy, use `--ca-bundle PEM`, set
`SSL_CERT_FILE`, or use `--system-trust` (needs the optional `truststore` package). On the
development machine Python failed with `CERTIFICATE_VERIFY_FAILED: unable to get local issuer
certificate` and succeeded with `--system-trust`; `curl` worked directly.

The output holds, per record: `source`, `publisher`, `query_urls`, `retrieval_date`,
`source_schema` (all Result and Station column names), `source_row` (verbatim), `station_row`,
`transformations` (`{source_field, target_field, rule}`), and `gateway_source`, a ready-to-post
`Source` for `POST /api/v1/interop/import` (`format: json`, `synthetic: false`).

## License and redistribution decision

Decision: raw WQP data is NOT committed to this repository.

Evidence: the WQP site describes itself as integrating "publicly available water-quality data from
the United States Geological Survey (USGS), the Environmental Protection Agency (EPA), and over 400
state, federal, tribal, and local agencies". The WQP user guide gives a citation format and a
USGS provisional-data disclaimer ("The data are released on the condition that neither the USGS
nor the United States Government may be held liable for any damages resulting from its authorized
or unauthorized use."). Neither states a redistribution license, and contributor terms can
differ. USGS publishes its own public-domain policy page, but it returned HTTP 403 to automated
retrieval during this work, so the exact wording could not be quoted and is not relied on here.
A clear, quotable permission was therefore not established. The sample is reproducible from the
query above instead. If a maintainer confirms the USGS public-domain terms in writing, a sample
may be added under `backend/data/interop/external/` with the citation above.

Test code embeds only hand-written `TEST` rows in the WQP column layout; they are not WQP data.

## Field mapping

Flattened payload keys are names the existing deterministic mapper recognises.

| Source column | Gateway field | Rule |
|---|---|---|
| `ResultIdentifier` | `sample_no` -> `sample_id` | verbatim |
| Station `MonitoringLocationName` | `sample_location` -> `location_name` | verbatim |
| Station `MonitoringLocationName` | `water_source` -> `waterbody_name` | reused; WQP has no waterbody name |
| `ActivityStartDate` + `ActivityStartTime/Time` + `...TimeZoneCode` | `sample_time` -> `collected_at` | local time to UTC with a fixed offset table; unknown codes are skipped |
| `LaboratoryName` | `lab` -> `laboratory` | verbatim |
| `ResultMeasureValue` with `ResultSampleFractionText=Dissolved` | `arsenic_dissolved` -> `value` (+ concept `dissolved_arsenic`) | explicit qualifier in the key; no rescale |
| `ResultMeasureValue` with `ResultSampleFractionText=Total` | `total_arsenic` -> `value` (+ concept `total_arsenic`) | explicit qualifier in the key; no rescale |
| `ResultMeasure/MeasureUnitCode` | `units` -> `unit` | `ug/l` normalised to `ug/L` |
| Station `MonitoringLocationTypeName` | `kind` | `Stream` -> `stream`; other types omitted |
| `OrganizationFormalName` | `collector` | proxy: reporting organization, not a named sampler |
| `OrganizationIdentifier/ActivityIdentifier/ResultIdentifier` | `report_reference` | joined with `/` |
| `ResultAnalyticalMethod/MethodIdentifier` + `MethodName` | `method` | joined |
| `AnalysisStartDate` | `report_time` -> `reported_at` | proxy: WQP has no report-issue time; reviewer must confirm or reject |
| `ResultStatusIdentifier`, `MonitoringLocationIdentifier`, `ProviderName` | same names | no gateway target; stay unresolved and are preserved in the source |

A bare `arsenic` key is never emitted. Rows with `Unfiltered` or blank fractions are skipped,
because the fraction is not stated.

Gateway check on the 8 fetched records (run in-process, not committed): all analyte, value,
unit, time, laboratory and location fields map deterministically; the only unresolved fields are
the three context fields above. After accept/reject decisions, all 8 normalise and pass the
FHIR validation. `report_time` and `collector` are proxies and need reviewer confirmation.

## What was not copied

The repository holds no WQP rows. Of the ~85 Result columns, the sample uses 13; the rest
(biological, taxonomic, depth, precision and similar columns) are kept only in the local output's
`source_row`, never mapped. No coordinates or well data are used.

## Limits

- A curated sample from one stream site over one year, not a monitoring dataset.
- Values are USGS-reported results with status `Preliminary` at retrieval and may be revised.
- No health inference, exposure or risk claim, and no model, is made from these values.
- Dissolved and Total fractions do not establish chemical speciation.

## Offline fallback

Tests never touch the network. The repository's deterministic fixtures in
`backend/data/interop/` (`environmental-dissolved.json`, `environmental.json`,
`laboratory.csv`) remain the offline path for CLINI-CASE demos and CI.

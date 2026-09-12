# Data Sources

## Tier A — Real, published

### BOM Australian Tropical Cyclone Database
- Landing page: https://www.bom.gov.au/cyclone/tropical-cyclone-knowledge-centre/databases/
- Endpoint: http://www.bom.gov.au/clim_data/IDCKMSTM0S.csv
- Retrieved: 2026-09-02
- Raw file: data/raw/bom/IDCKMSTM0S.csv (7.6 MB)
- Licence: Commonwealth of Australia, Bureau of Meteorology
- Tier: A (real, published)
- Processing script: src/step1_download_bom.py
- Processing: retained all track points for any cyclone with at least one
  observation inside the Pilbara bounding box (lat -24.0 to -17.5,
  lon 113.0 to 122.5) from 2015 onward. Aggregated to one row
  per event. Peak defined as the in-box observation with the lowest central
  pressure. Category derived from maximum sustained wind using the BOM
  Australian scale. Distance to Port Hedland and Dampier computed by haversine
  from the peak position.
- Output: data/processed/dim_cyclone_event.csv (27 events)
- Output: data/processed/cyclone_track_points.csv (958 points)

### BOM Australian Tropical Cyclone Database
- Landing page: https://www.bom.gov.au/cyclone/tropical-cyclone-knowledge-centre/databases/
- Endpoint: http://www.bom.gov.au/clim_data/IDCKMSTM0S.csv
- Retrieved: 2026-09-02
- Raw file: data/raw/bom/IDCKMSTM0S.csv (7.6 MB)
- Licence: Commonwealth of Australia, Bureau of Meteorology
- Tier: A (real, published)
- Script: src/step1_download_bom.py (v2)

**Processing**
- Retained all track points for any cyclone with at least one observation
  inside the Pilbara bounding box (lat -24.0 to -17.5,
  lon 113.0 to 122.5) from 2015 onward.
- Aggregated to one row per event. Peak defined as the in-box observation with
  the lowest central pressure.
- Distances to Port Hedland and Dampier computed by haversine from the closest
  in-box track point.

**Known data quality issue and correction**
- MAX_WIND_SPD is recorded by BOM in metres per second. Version 1 of this
  script applied the Australian km/h category scale directly to those values
  and classified 26 of 27 Pilbara events as Category 0, contradicting the
  central pressure recorded on the same rows. Cyclone Zelia, at 927 hPa,
  returned Category 0.
- Corrected by converting to km/h (x 3.6) before categorising. Both the
  original m/s value and the converted km/h value are retained in the output.
- A validation step now cross-checks the wind-derived category against an
  independent pressure-derived category and against three published reference
  events, and fails loudly if they diverge.

**Outputs**
- data/processed/dim_cyclone_event.csv (27 events)
- data/processed/cyclone_track_points.csv (958 points)

### Pilbara Ports monthly cargo statistics
- Landing pages (saved manually, see method below):
  - https://www.pilbaraports.com.au/ports/port-of-port-hedland/about-port-of-hedland/port-statistics-and-reports
  - https://www.pilbaraports.com.au/ports/port-of-dampier/about-port-of-dampier/port-statistics-and-reports
- Retrieved: 2026-09-02
- Licence: Pilbara Ports Authority, Government of Western Australia
- Tier: A (real, published)
- Script: src/step2_pilbara_ports.py (v3)

**Method**
- The statistics pages block automated requests, returning no content links
  even though the published page is plain HTML rather than JavaScript
  rendered. The pages were therefore saved from a browser and parsed locally;
  only the PDFs were fetched over the network.
- Each month link is assigned the year heading closest before it in the raw
  HTML. The year cannot be taken from the URL, because several entries point
  into a media folder for an unrelated year.
- Port Hedland labels sections by calendar year; Dampier labels them by
  financial year ("2025-26"). For span labels, July to December map to the
  first year and January to June to the second.
- Only tonnage reports were collected. Cargo-by-destination reports were
  skipped as they are not used in this analysis.

**Output**
- data/processed/fact_port_throughput.csv (138 rows from 138 PDFs)

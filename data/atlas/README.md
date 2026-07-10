# Historical Geostrategic Atlas data

`atlas.json` is generated from the normalized IDs in `data/history-stack/`.
Its supported overlays are documentary and discovery views:

- FRUS activity
- documented access relationships
- treaties and policy instruments
- strategic stockpile policy
- historical episodes
- NARA query plans
- country-level resource associations

The registry also describes requested quantitative layers that are not yet
supported. They remain locked until compatible official country-year data,
units, methods, and citations are added.

`world-orientation.geojson` contains trimmed Natural Earth 1:110m modern
generalized country polygons. Natural Earth is public domain and is used only
for orientation. It is not historical boundary evidence and is not treated as
an official U.S. Government source.

Rebuild both files:

```bash
python scripts/build_atlas_data.py
```

Rebuild documentary overlays while retaining the checked-in basemap:

```bash
python scripts/build_atlas_data.py --skip-basemap
```

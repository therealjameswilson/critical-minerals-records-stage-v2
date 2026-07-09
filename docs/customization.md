# Customization Points

The two HTML edits every adopter makes, plus the smaller knobs in
`cache_format.py`. Everything else is generic.

---

## 1. The clearance block

Records Stage's "Approvals & Clearances" section defaults to the
upstream FRUS toolkit's bureaus (A/SKS/OH, A/SKS, A/FO, D, D-MR, P, C, S/P,
M, E, T, F, R, GPA, M/WHL). These are almost certainly wrong for any other
organization.

In `records-stage.html`, find the marker `<!-- CLEARANCE_DEFAULTS -->` and
replace the row block. Each row needs:

```html
<tr>
  <td>{Office or bureau code}</td>
  <td>
    <select>
      <option>Required Clearance</option>
      <option>Info</option>
      <option>Info*</option>
      <option>N/A</option>
    </select>
  </td>
  <td><input placeholder="Initials"></td>
</tr>
```

Status options (Required Clearance / Info / Info\* / N/A) carry over without
change.

---

## 2. The "Drafted by" line

Above the clearance block, the **Drafted** line is hardcoded to
`A/SKS/OH – [Name], [Phone #]`. Edit the `<!-- DRAFTED_BY -->` block in
`records-stage.html` to your equivalent.

---

## 3. Score thresholding and compact fields

In `cache_format.py`:

- `MIN_SCORE` — events scoring below this are excluded from the cache at
  build time. Lower for small corpora; higher for large ones.
- `COMPACT_EXTRA_FIELDS` — which `extra.*` fields surface into the HTML
  tool. Add a mapping here for each adopter-defined field you want
  searchable / displayable.

---

## 4. Subject taxonomy

If you have one, implement `taxonomy.py:load_taxonomy()`. If you don't,
leave the stub raising `NotImplementedError`. The subject filter UI in the
HTML tool checks whether the embedded `SUBJECT_TAXONOMY` is non-empty and
hides itself if it is.

---

## What you should NOT customize

- **The cache schema.** Adding required fields makes your cache incompatible
  with the generic HTML shell, which means future toolkit upgrades won't
  apply to your fork.
- **The compact-format keys.** Single letters (`y`, `t`, `u`, `s`, `sc`,
  `sb`) are chosen to keep the embedded cache small. Don't expand them.
- **The `MM-DD` keying.** The whole "on this day" workflow depends on it.
  If you need different temporal slicing (yearly, by quarter, by named
  period), that's a different tool.

---

## What you might fork

If your editorial workflow is wildly different — say, you're not building
tweets but generating press releases, or you don't have a clearance step at
all — fork `records-stage.html` and replace whole sections. The cache and
the Python build chain are unaffected. Forking the HTML shell is cheap;
forking the data layer would be expensive and break future portability.

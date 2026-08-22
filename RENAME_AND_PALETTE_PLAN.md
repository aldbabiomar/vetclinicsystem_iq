# VetClinicSystem_IQ Rename + Palette Setting — Execution Plan

Goal: one shared codebase, deployed independently for Vetzone_IQ and ChamPet_IQ,
differing only by a color palette. This document is the full sweep of every
place that needs to change, ordered by risk, with exact file:line references.
Nothing in this repo has been modified — this is the checklist for doing it.

**Scope decision baked into this plan:** no real multi-tenancy (no shared DB,
no `clinic_id` columns). Each clinic gets its own `.env` + its own Postgres
database, running the same codebase. That's already how the app is built
(env-driven config, DB-backed settings) — this plan extends that pattern, it
doesn't replace it.

**Pre-deployment status changes the risk calculus.** There are no live
installs, no existing Postgres volumes, no backup files already on a
clinic's disk, no `.plist` already loaded on someone's Mac. Almost every
"failure mode" flagged below in earlier drafts of this plan was really a
*migration* risk — old state colliding with new identifiers. With nothing
deployed yet, that risk is zero: there's nothing to migrate, only new state
to get right once. What's left is pure execution precision (touch every file
that references an identifier, not miss one), not compatibility risk. This
flips the recommendation below from "avoid renaming internals" to "rename
them properly now, while it's free" — see next section.

---

## Identifier prefix: full rename is now the right call

Every `VETZONE_*` env var, the Docker container/volume names, the logger
name, and the localStorage keys currently use `vetzone`/`vz` as a prefix.
With no live installs to protect, there's no longer a compatibility argument
for leaving them mismatched with the new brand — a half-renamed codebase
(user-facing text says VetClinicSystem_IQ, but env vars and Docker
containers still say `vetzone`) is just permanent inconsistency for no
benefit. **Do the full rename in Phase 3**, including the items that were
previously flagged as "needs a migration step" — those migration steps are
no longer needed, only the plain rename is. Precision still matters (miss
one reference and something breaks on first run), it's just a much cheaper
kind of risk than a live-migration bug.

---

## Phase 0 — Safety prep

1. Create a dedicated branch for this work: `git checkout -b rename-vetclinicsystem`.
2. Take a full Postgres backup via the existing Settings → Backup Now flow
   before touching `docker-compose.yml` or `.env.example`.
3. Do NOT touch the live `.env` (only `.env.example`, the template) until the
   very end, and only on a deployment you're prepared to restart.

---

## Phase 1 — Palette setting (do this first: independent, low risk, fully reversible)

This reuses the existing `settings` key/value table pattern already used for
`clinic_name`, `backup_dir`, etc. — see [app.py:5117-5126](app.py:5117).

### 1.1 Add the second palette to CSS

[static/style.css:1-80](static/style.css:1) currently defines one light
palette on `:root` and one dark override on `html[data-theme="dark"]`. Add a
second palette as a new attribute selector, `html[data-palette="champet"]`
for light and `html[data-palette="champet"][data-theme="dark"]` for dark,
each redefining the same custom properties.

**Gap check against the supplied ChamPet values:** the full var list actually
consumed by style.css (grep-confirmed at style.css:3-41, 169, 470, 702) is
larger than what was supplied. Three variables are load-bearing in specific
components and were missing from the light-mode values given:

| Variable | Missing from supplied palette | Where it's actually used |
|---|---|---|
| `--primary-pastel` | yes | `.new-role-card:hover` border ([style.css:702](static/style.css:702)) |
| `--accent-tan` / `--accent-tan-tint` | yes | grooming appointment chip background ([style.css:470](static/style.css:470)) |
| `--sidebar-active-ink` | yes | active nav item text color ([style.css:169](static/style.css:169)) |

Left undefined, these three fall through to whatever `:root` (Vetzone)
has set — ChamPet would silently show Vetzone's rose/tan colors in exactly
those three spots. `--sidebar-active-ink` and `--primary-pastel` are
mechanically derivable from the given values (see below); `--accent-tan` is
a genuinely new creative decision — vetzone's tan is a category-distinguishing
color independent of its brand hue (used for one appointment type's chip),
not derived from primary/sidebar at all, so there's no formula to derive
ChamPet's equivalent from what was supplied. I picked a soft violet
(`#8478B0`) to stay visually distinct from `--primary` (teal) and `--warn`
(already amber/gold) — **treat this one hex value as a placeholder pending
your sign-off, not a computed result** like everything else in this section.

**Derivation method used below**, mirrored from how Vetzone's existing dark
block relates to its light block (style.css:1-80): neutrals invert in
lightness (bg/paper go near-black, ink goes near-white, keeping the same hue
family); brand colors (`primary`, `ok`, `warn`, `danger`) get brightened
~15–20% for contrast against a dark background — notably `--primary-dark`
flips from "darker than primary" in light mode to "lighter/more prominent
than primary" in dark mode in Vetzone's own block (`#955F62` → `#E3B3B5`),
so this isn't a naming bug, it's how the existing dark theme already works;
every `*-tint` becomes a dark, desaturated version of the same hue instead
of a light one; shadows switch from `rgba(<ink-rgb>, …)` to pure
`rgba(0,0,0,…)` at the same opacities Vetzone uses.

One structural difference worth noting: Vetzone's sidebar is a *mid-tone*
blue in light mode (`#99B9C9`) that goes dark in dark mode. ChamPet's
sidebar is *already* dark navy in light mode (`#293659`) — this app's
sidebar reads as "always dark" by design for ChamPet, not "light in light
mode." So the dark-mode sidebar below only deepens slightly rather than
inverting, and `--sidebar-active-ink` stays light text in *both* modes
(unlike Vetzone, where it's dark rose text in light mode on a white pill,
and light text in dark mode) — because ChamPet's active pill is a lighter
navy, not white, in either mode.

```css
/* ---- ChamPet palette (light) ---- */
html[data-palette="champet"] {
  --bg: #F5F8FA;
  --paper: #FFFFFF;
  --ink: #212B3D;
  --ink-soft: #7C879A;
  --line: #E2E8EF;
  --line-soft: #EEF2F6;

  --primary: #1B9CBE;
  --primary-dark: #147089;
  --primary-tint: #E3F5FA;
  --primary-pastel: #6BC0D6; /* derived: same ~40% primary→tint blend ratio as Vetzone's own pastel */

  --sidebar-bg: #293659;
  --sidebar-ink: #E7ECF5;
  --sidebar-muted: #92A0BE;
  --sidebar-active: #37477A;
  --sidebar-active-ink: #E7ECF5; /* derived: active pill is a lighter navy, not white, so text stays light */

  --accent-tan: #8478B0;       /* placeholder — needs your sign-off, see gap note above */
  --accent-tan-tint: #EFEBF7;  /* placeholder, paired with the above */

  --ok: #4C9B79;
  --ok-tint: #E9F4EE;
  --warn: #C08A3C;
  --warn-tint: #FAF1E1;
  --danger: #C15B4E;
  --danger-tint: #FAEAE7;
  --muted: #9BA5B7;
  --muted-tint: #EEF1F5;

  --shadow-sm: 0 1px 2px rgba(33,43,61,0.05);
  --shadow: 0 2px 10px rgba(33,43,61,0.06), 0 1px 2px rgba(33,43,61,0.04);
  --shadow-lg: 0 16px 48px rgba(33,43,61,0.16);
}

/* ---- ChamPet palette (dark) ---- */
html[data-palette="champet"][data-theme="dark"] {
  --bg: #10141C;
  --paper: #1A2130;
  --ink: #E7ECF5;
  --ink-soft: #8C97B0;
  --line: #2C3547;
  --line-soft: #212838;

  --primary: #3FB8D6;
  --primary-dark: #63C9E2;   /* lighter than --primary here, matching Vetzone's dark-mode flip */
  --primary-tint: #16303A;
  --primary-pastel: #6BC0D6; /* unchanged from light — Vetzone keeps this identical across modes too */

  --sidebar-bg: #1E2740;     /* deepened slightly, not inverted — see structural note above */
  --sidebar-ink: #E7ECF5;
  --sidebar-muted: #7C89A8;
  --sidebar-active: #2F3D63;
  --sidebar-active-ink: #E7ECF5;

  --accent-tan: #8478B0;     /* unchanged from light, same pattern as Vetzone's accent-tan */
  --accent-tan-tint: #2A2438;

  --ok: #6FBE9B;
  --ok-tint: #1B2E24;
  --warn: #DDA85E;
  --warn-tint: #33270F;
  --danger: #DD8172;
  --danger-tint: #33201B;
  --muted: #8791A8;
  --muted-tint: #232838;

  --shadow-sm: 0 1px 2px rgba(0,0,0,0.35);
  --shadow: 0 2px 10px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3);
  --shadow-lg: 0 16px 48px rgba(0,0,0,0.55);
}

/* Component-level dark-mode fix, mirroring the one Vetzone already needs at
   style.css:83 for the same chip under its own accent-tan hue: */
html[data-palette="champet"][data-theme="dark"] .appt-chip.grooming { color: #E4DEF2; }
```

The `html[data-theme="dark"] .nav-link.active` box-shadow/border rule at
[style.css:86](static/style.css:86) is structural (no literal color), so it
applies to both palettes unchanged — no ChamPet-specific override needed
there.

**All values above should get an actual visual QA pass** (per the Phase 5
checklist item for palette combinations) before being treated as final —
especially the two flagged placeholders (`--accent-tan` and its dark-mode
grooming-chip text color), which were chosen for contrast/distinctness by
eye, not computed from anything you supplied.

Two literal-hex fallbacks to check don't need touching:
[templates/audit_session_view.html:69](templates/audit_session_view.html:69)
and [templates/settings.html:288](templates/settings.html:288) both use
`var(--paper-alt, #f5f5f5)` — the fallback only fires if `--paper-alt` is
undefined, so it's palette-agnostic and safe to leave.

### 1.2 Register the setting server-side

Add `"theme_palette"` to the whitelist loop at
[app.py:5117-5119](app.py:5117) so it's persisted the same way every other
setting is:

```python
for key in ["clinic_name", "clinic_location", "audit_overdue_days", "expiry_soon_days", "opening_date",
            "appt_start_time", "appt_end_time", "appt_slot_minutes",
            "backup_dir", "backup_time", "backup_retention", "theme_palette"]:
```

No numeric-range or time validation needed (it's not in `NUMERIC_RANGES` or
`TIME_FIELDS`) — but do add a value whitelist check (e.g. only accept
`"vetzone"` or `"champet"`) before the `INSERT`, since this value flows
straight into an HTML attribute in step 1.3 — reject anything else with a
flash error rather than trusting the form field blindly.

### 1.3 Apply it before first paint

[templates/base.html:12-19](templates/base.html:12) already has an
inline script that runs before paint to set `data-theme` from localStorage
(avoiding a flash of the wrong theme). The palette needs the same treatment,
but server-rendered rather than localStorage-based (it's a clinic-wide
setting, not a per-user one):

```html
<html lang="en" data-palette="{{ settings.theme_palette or 'vetzone' }}">
```

`settings` needs to already be in every template's render context for this —
confirm it's passed on every route that renders via `base.html`, not just
`/settings` (check how `clinic_name` currently reaches
[templates/base.html:6](templates/base.html:6) — it's likely injected via a
`context_processor` in app.py rather than passed per-route; reuse the same
mechanism for `theme_palette`).

### 1.4 Add the UI control

A `<select>` dropdown in [templates/settings.html](templates/settings.html),
near `clinic_name`/`clinic_location`, posting `name="theme_palette"` to the
existing `/settings` POST handler — no new route needed. Display labels are
distinct from the internal stored value (`vetzone` / `champet`, matching the
`data-palette` attribute values used throughout this plan):

```html
<div class="detail-item">
  <div class="k">Color Palette</div>
  <div class="v">
    <select name="theme_palette">
      <option value="vetzone" {{ 'selected' if settings.theme_palette in (None, 'vetzone') }}>Pastel - Vetzone IQ</option>
      <option value="champet" {{ 'selected' if settings.theme_palette == 'champet' }}>Blue Shades - ChamPet IQ</option>
    </select>
  </div>
</div>
```

(Markup above follows the `.detail-item`/`.k`/`.v` structure already used
elsewhere on that page — adjust to match whatever the surrounding fields
actually use if this differs.) The value-whitelist check mentioned at the
end of 1.2 should accept exactly `"vetzone"` and `"champet"` — reject
anything else with a flash error rather than trusting the submitted form
value blindly, since it flows straight into an HTML attribute in 1.3.

### 1.5 Fix the hardcoded chart colors

[templates/insights.html:173-174](templates/insights.html:173) and
[:200](templates/insights.html:200) hardcode a `COLORS` object and a
literal hex array for Chart.js — these do **not** read CSS variables and
will show Vetzone's rose/blue palette regardless of the setting unless
fixed. Two options:
- Read the resolved CSS custom properties at render time via
  `getComputedStyle(document.documentElement).getPropertyValue('--primary')`
  (works, adds a few lines of JS), or
- Define a second, parallel JS color map and pick between them server-side
  via `{{ settings.theme_palette }}` when rendering the `<script>` block.

Either way, this file is the one place the CSS-variable approach doesn't
cover automatically — don't skip it, or the dashboards will silently stay
one clinic's colors.

### 1.6 Palette-branch every static image asset, not just the logo

Decision (per your steer): favicons and the error-page illustrations get a
second, palette-matched set, same as the logo. That's five asset families to
duplicate and branch, not one:

| Asset family | Current files | Referenced at |
|---|---|---|
| Logo | `logo-login-{dark,light}.png`, `logo-sidebar-{dark,light}.png` | wherever `url_for('static', filename='logo-...')` is called (base.html + sidebar partial) |
| Favicon | `favicon-v2.ico`, `favicon-v2-32.png`, `favicon-v2-180.png`, `favicon.svg` | [templates/base.html:8-10](templates/base.html:8) |
| Error pages | `error-403.png`, `error-404.png`, `error-500.png` | wherever the 403/404/500 error handlers render their templates (check `app.py` error handlers / whatever template includes these images) |

For each family, add a `-champet` variant (e.g. `favicon-v2-champet.ico`,
`error-404-champet.png`) and branch the `url_for(...)` call on
`settings.theme_palette` at render time — same mechanism as 1.3's
`data-palette` attribute, just resolved server-side into a filename suffix
instead of a CSS attribute. A small helper is worth it here since the same
branch (`'-champet' if settings.theme_palette == 'champet' else ''`) repeats
across ~9 image references — either a Jinja macro/context processor
function, or a small `static_asset(name, palette)` helper called from each
template, rather than duplicating the ternary at every call site.

Note the favicon `<link>` tags in `templates/base.html:8-10` render once per
page load from server-side context, so this works cleanly with no
before-paint flash concern (unlike the CSS palette, which needs the
before-paint script in 1.3 because it's client-rendered from localStorage —
the favicon has no such issue since it's resolved server-side per request).

### 1.7 Test

- Toggle the setting, confirm `data-theme` × `data-palette` all four
  combinations (light/dark × vetzone/champet) render correctly.
- Confirm Insights charts pick up the right palette.
- Confirm an unset/legacy `theme_palette` (existing installs, empty
  `settings` row) defaults to `'vetzone'` and doesn't throw.

---

## Phase 2 — Brand rename, Tier 1: user-visible text (safe, mechanical)

These are prose/UI strings only — no other file depends on their exact
value, so this is a straightforward find-and-replace + read-through. All
instances of "Vetzone IQ" / "Vetzone-created" / "Vetzone" as prose:

| File | Lines |
|---|---|
| [README.md](README.md) | 1, 3, 19, 20, 29 ("cd vetzone" — see Phase 4), 186, 198 |
| [CHANGELOG.md](CHANGELOG.md) | 3, 224, 320, 324 |
| [CHANGELOG_SECURITY_FIXES.md](CHANGELOG_SECURITY_FIXES.md) | 1, 3, 230, 233 |
| [app.py](app.py) | 593, 615 (`clinic_name` default value), 1300, 2747, 5375, 5416 |
| [import_seed.py:256](import_seed.py:256) | `"clinic_name": "Vetzone IQ"` default |
| [auth.py:3](auth.py:3) | module docstring |
| [autostart.py](autostart.py) | 2, 86, 121, 141, 153 (Windows/macOS user-facing messages) |
| [backup.py](backup.py) | 2, 108, 139, 358 (user-facing validation messages) |
| [db.py:2](db.py:2), [logic.py:2](logic.py:2), [import_seed.py:2](import_seed.py:2), [jobs.py:11](jobs.py:11), [updater.py:293](updater.py:293) | docstrings/comments |
| [schema_postgres.sql:1](schema_postgres.sql:1), [:223](schema_postgres.sql:223) | comments only |
| [templates/settings.html](templates/settings.html) | 47, 67, 77, 110, 125, 162, 171, 198, 207, 242, 257, 287 |
| [templates/inventory_catalog.html](templates/inventory_catalog.html) | 119, 138, 156, 239, 247 |

Note: since `clinic_name` is already a DB-backed setting rendered via
`{{ clinic_name }}` in most page titles/headers, the *default value* strings
at app.py:593,615 and import_seed.py:256 are what actually need changing —
existing installs' DB rows won't be touched by a code change (which is
correct: an existing Vetzone_IQ deployment's DB should keep saying "Vetzone
IQ" unless someone edits it in Settings).

**Action:** straightforward global find/replace of the prose strings, then a
manual read-through of each diff (not just a blind sed) since a few of these
sit inside longer sentences ("Vetzone-created barcode", "Vetzone can create
one and print...") where "Vetzone" isn't a clean standalone token.

---

## Phase 3 — Brand rename, Tier 2: operational identifiers (surgical precision required)

Everything here is referenced by **other code**, not just displayed as text.
Do this phase in full (per the pre-deployment note above, the old
"live-install migration" concerns below no longer apply — do the clean
rename). The precision requirement is still real: each identifier is
referenced from multiple files, and missing one reference breaks that
feature on first run with no build-time error to catch it.

### 3a. Env var names (`VETZONE_DATA_DIR`, `VETZONE_RELEASES_DIR`, `VETZONE_PORT`, `VETZONE_HOST`, `VETZONE_ALLOWED_NETWORKS`, `VETZONE_PG_CONTAINER`, `VETZONE_DEV`)

Referenced in: [.env.example:11,26,27,39,41,42](/.env.example),
[app.py:24,102,5400,5413,5414](app.py:24), [setup.py](setup.py) (10+ refs,
lines 254,289,306,329,331,343,344,346,377,444,445),
[updater.py:32,33,238,239](updater.py:32),
[reconcile_attachments.py:45](reconcile_attachments.py:45).

**Failure mode if inconsistent:** any one of these files left on the old
name silently breaks — the app falls back to defaults instead of erroring,
so e.g. `setup.py` writing `VETZONE_PORT` while `app.py` reads a renamed var
means the app starts on the wrong port with no error message. Must be
renamed as a single atomic search-and-replace across all five files, then
the "already managed" detection in `setup.py:242-254` and the updater's
subprocess env-passing in `updater.py:238-239` specifically re-tested (these
two are the easiest to miss since they're mid-function, not top-of-file).

### 3b. Launcher script filenames (`Start Vetzone.command`, `Start Vetzone.bat`)

Referenced by **literal string**, not just as files-on-disk, in:
[autostart.py:36,52,86,141](autostart.py:36),
[setup.py:259-260,434-435,449](setup.py:259), plus the scripts'
own self-relaunch lines
([Start Vetzone.bat:15,67](/Start%20Vetzone.bat), [Start Vetzone.command:15,64](/Start%20Vetzone.command)),
plus README.md:19-20 and CHANGELOG.md:320.

**Failure mode:** rename the files on disk but miss one literal-string
reference → `autostart.py`'s `_macos_enable()`/`_windows_enable()` silently
return `False, "Could not find..."` (autostart.py:86,141) instead of an
exception, so this fails quietly in the UI as a flash message, easy to not
notice in testing. Must rename file + every string reference together, then
manually re-test enabling autostart on both platforms.

### 3c. macOS launchd label `com.vetzoneiq.autostart` ([autostart.py:23](autostart.py:23))

`is_enabled()` checks whether a plist exists at a path derived from
`AGENT_LABEL` (autostart.py:32,58). Pre-deployment, there's no existing
install with an old-label plist already loaded, so this is a plain rename —
just update `AGENT_LABEL` to something like `com.vetclinicsystemiq.autostart`
and the plist path, filename, and `<key>Label</key>` value all follow
automatically since they're all derived from the one constant. (Flag for
later: *after* this app is actually deployed, renaming this constant again
would reintroduce the orphaned-old-plist problem — fine to ignore now, worth
remembering if a rename like this ever comes up post-launch.)

### 3d. Docker/Postgres identifiers (`vetzone_postgres`, `vetzone` user/db, `vetzone_pgdata` volume)

[docker-compose.yml:4,7-9,16,18,24-25](docker-compose.yml:4),
[.env.example:4-5,11](/.env.example),
[backup.py:55,67,287](backup.py:55) (hardcoded fallback defaults, not just
reading env).

Pre-deployment, there's no existing Docker volume with real data in it to
worry about — renaming `vetzone_pgdata` → e.g. `vetclinicsystemiq_pgdata` in
`docker-compose.yml:24-25` (and the matching container/user/db names) is
just a plain edit, tested with a fresh `docker-compose up`. (Flag for later:
once either clinic is actually running on this, renaming these again *would*
orphan the volume and need an explicit `pg_dump`/`pg_restore` — not a
concern now, worth remembering before ever doing this again post-launch.)

### 3e. `GITHUB_REPO` + self-updater ([.env.example:17](/.env.example), [updater.py:111](updater.py:111))

Must exactly match wherever the code actually ends up living on GitHub
(Phase 4). If it drifts even briefly (renamed repo, stale `GITHUB_REPO`),
the self-update check fails silently against a 404 — worth an explicit
manual check-for-updates test after Phase 4, not just after Phase 3.

### 3f. Backup file prefix `vetzone_backup_` ([backup.py:22](backup.py:22), [reconcile_attachments.py:57](reconcile_attachments.py:57))

`backup.py:108,358` validate uploaded restore files by checking this
prefix. Pre-deployment, no clinic has a backup file on disk yet, so this is
a free rename — update `FILENAME_PREFIX` in backup.py:22 and the regex in
reconcile_attachments.py:57 together, no dual-prefix compatibility shim
needed. (Flag for later: once a clinic has real backups sitting on disk,
renaming this again would need the old-prefix-still-accepted handling
described in earlier drafts of this plan — not needed now.)

### 3g. Logger name `"vetzone.errors"` ([app.py:179](app.py:179))

Cosmetic — only affects log line prefixes on disk. Safe to rename or leave;
lowest priority in this entire phase.

### 3h. localStorage keys (`vetzoneiq-theme` at [base.html:16,198](templates/base.html:16), `vetzoneiq-navgroup-*` at [static/ui.js:178](static/ui.js:178))

Safe to rename. Only side effect: existing users' saved theme/collapsed-nav
preferences silently reset to default once, on their first page load after
the change (new key = cache miss, not a bug, not visible as an error).
Mention it if you rename these, otherwise skip.

### 3i. Repo folder name `Vetzone_IQ` (this directory)

No code anywhere depends on this path — confirmed no Python imports
reference it (flat script layout, not an installed package). Rename the
local folder any time with zero code risk; it's purely cosmetic for
whoever's looking at a Finder window or terminal prompt.

### 3j. Misc

- [dev_seed/vetzone_test_data.dump](dev_seed/vetzone_test_data.dump) —
  dev-only fixture, rename freely, just grep for whatever loads it by
  literal path first.
- `window.VZProgress` / `VZToast` / `VZSpring` / `VZDialog` (JS globals
  across static/progress.js, static/ui.js, static/rebuild.js,
  static/unsaved-changes*.js, several templates) — an internal "VZ"
  namespace, not literally "Vetzone" text, purely internal, zero external
  coupling. Out of scope — skip unless doing a full identity pass for its
  own sake.

---

## Phase 4 — GitHub repo rename

1. Rename the repo on GitHub: Settings → repository name →
   `vetclinicsystem_iq`. GitHub auto-redirects the old URL, but update the
   local remote anyway:
   ```bash
   git remote set-url origin https://github.com/aldbabiomar/vetclinicsystem_iq.git
   ```
2. Update `GITHUB_REPO` in `.env.example` (and in every live deployment's
   actual `.env`) to `aldbabiomar/vetclinicsystem_iq` — see 3e above for why
   this must be exact.
3. Update the clone instructions at [README.md:29](README.md:29)
   (`cd vetzone` → new folder name) and any other literal repo-name
   references in README.md/CHANGELOG.md.
4. Manually trigger "Check for updates" in Settings on a test deployment
   afterward to confirm the updater actually resolves the new repo's
   releases API before relying on it.

---

## Phase 5 — Verification checklist (run after Phase 3 + 4, whichever items you did)

- [ ] `docker-compose up` from a clean checkout succeeds, new container/
      volume/user names all match (validates 3d)
- [ ] Enable/disable autostart on macOS: confirm plist created/removed at
      the new label path, correct contents (validates 3c)
- [ ] Enable/disable autostart on Windows: confirm shortcut file appears in
      Startup folder (validates 3b)
- [ ] Settings → Check for updates → confirms it reaches the renamed repo
      (validates 3e, 4)
- [ ] Take a backup, then restore it — round-trip with the new filename
      prefix (validates 3f)
- [ ] Palette toggle: all 4 CSS combinations (vetzone/champet × light/dark)
      across dashboard, settings, and Insights charts, PLUS all 3
      image-asset families (logo, favicon, error pages) rendering the right
      variant per palette (validates 1.1–1.6)
- [ ] Trigger each of the 403/404/500 error pages manually and confirm the
      correct palette's illustration renders (validates 1.6)
- [ ] Fresh `setup.py` run on a machine with no prior install (validates 3a,
      3b together)
- [ ] `grep -rniI "vetzone"` across the repo one more time post-change —
      every remaining hit should be either a deliberate historical reference
      (CHANGELOG entries describing past versions) or something you can
      name a reason for keeping; anything else is a miss

---

## Recommended sequencing

1. **Phase 1 (palette, including the full image-asset sweep in 1.6) first**
   — fully independent of everything else, testable in isolation, zero
   coupling to the rename.
2. **Phase 2 (cosmetic text)** — safe, can be one careful commit with a
   full diff read-through.
3. **Phase 3 (operational identifiers, full rename)** — do it as a single
   atomic commit covering every sub-item together (don't split 3a from 3b
   from 3d across separate commits — they're interdependent and a
   half-renamed state is broken), then run the full Phase 5 checklist
   before merging. Since this is pre-deployment, there's no rush to stage
   this conservatively — get it right once.
4. **Phase 4 (GitHub rename) last**, once the renamed code is already
   working locally — rename the repo, then immediately update `GITHUB_REPO`
   everywhere it's configured.

Once either deployment actually goes live, this plan's "pre-deployment"
shortcuts (3c, 3d, 3f skipping migration handling) stop applying — any
*future* rename of these same identifiers would need the live-migration
handling this version intentionally skips. Worth a one-line note in the repo
(e.g. this file, kept around) so that context isn't lost by the time it
matters.

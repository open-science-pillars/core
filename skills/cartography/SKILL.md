---
name: cartography
description: "Publication-quality maps with cartopy: projections, uniform colormaps, stippling and uncertainty visualization, multi-panel layouts, Hovmoller."
user-invocable: false
---

# cartography

Background expertise for maps and figures that survive review.

## Projections

- Global fields: Robinson or Equal Earth for presentation (area
  impressions matter); PlateCarree is a working view, not a publication
  default, because it exaggerates high latitudes.
- Polar: NorthPolarStereo / SouthPolarStereo with `set_extent` and a
  circular boundary path; never show polar fields on PlateCarree.
- Regional midlatitude: LambertConformal centered on the domain.
- **Always pass `transform=ccrs.PlateCarree()`** (or the data's actual
  CRS) to every plotting call on a GeoAxes. Omitting it is the classic
  silent bug: data draws in projection coordinates and lands in the wrong
  place or not at all.
- Global longitudes need a cyclic point
  (`cartopy.util.add_cyclic_point`) or a seam gap appears at the dateline
  or prime meridian.
- Coastlines at the resolution the domain needs (`'110m'` global,
  `'50m'` regional); gridline labels on, ticks meaningful.

## Colormaps: perceptually uniform, matched to the variable

Rules: sequential colormaps for magnitudes, diverging only when the field
has a physically meaningful center (zero anomaly, zero trend, zero
divergence), and the center pinned there (`vmin=-vmax`, or
`TwoSlopeNorm` when the range is asymmetric). Never jet or rainbow;
perceptual banding manufactures features that are not in the data.

cmocean table (fall back to viridis/cividis and RdBu_r when cmocean is
unavailable):

| Field | cmocean | Type |
|---|---|---|
| temperature, SST | `thermal` | sequential |
| anomalies, trends, budgets, divergence | `balance` | diverging |
| salinity | `haline` | sequential |
| velocity or speed magnitude | `speed` | sequential |
| vorticity, curl | `curl` | diverging |
| sea ice concentration | `ice` | sequential |
| precipitation, moisture | `rain` (rate) / `tempo` (accumulating) | sequential |
| bathymetry, topography | `deep` / `topo` | sequential / split |
| dissolved oxygen | `oxy` | sequential with thresholds |
| chlorophyll, biomass | `algae` | sequential |
| cyclic phase (direction, season, tide phase) | `phase` | cyclic |
| model-obs or version differences | `diff` | diverging |

State units on every colorbar label; a colorbar without units is a
finding in review.

## Figure sizes

| Context | Width | Fonts at final size |
|---|---|---|
| single-column journal figure | 3.5 in / 89 mm | >= 7 pt |
| double-column journal figure | 7.2 in / 183 mm | >= 7 pt |
| slide (16:9) | 13.3 x 7.5 in | >= 18 pt |

Set the true final size at creation (`figsize=`), use
`constrained_layout=True`, export vector (PDF/SVG) or >= 300 dpi raster.
Do not create a huge figure and shrink it in a document; fonts and line
widths shrink with it.

## Stippling and significance marking

Mark per-cell statistical significance on trend or composite maps with
stippling or hatching over the field:

```python
cf = ax.contourf(lon, lat, slope, levels=levels, cmap=cmap,
                 transform=ccrs.PlateCarree())
ax.contourf(lon, lat, pvals < 0.05, levels=[0.5, 1.5],
            colors="none", hatches=[".."], transform=ccrs.PlateCarree())
```

- **The caption defines the marking, always**: which test, which level
  ("stippling: p < 0.05, Hamed-Rao modified Mann-Kendall"), and what the
  stippled state is.
- When most of the field is significant, stippling the significant area
  blackens the map; mark the NON-significant regions instead and say so.
- Per-cell significance is not field significance; basic-statistics
  carries the FDR rule for map-wide claims.

## Multi-panel layouts

- Build with `plt.subplots(..., subplot_kw={"projection": proj},
  constrained_layout=True)`; label panels (a), (b), (c).
- **Panels that invite comparison share one colorbar**: same levels and
  norm on every panel, one `fig.colorbar(mappable, ax=axs)` for the set.
  Per-panel colorbars with different ranges on comparable fields is a
  review finding; use them only when panels show different variables.
- Seasonal panel sets (DJF/MAM/JJA/SON) follow the QS-DEC convention
  from basic-statistics; label seasons, not month triplets.

## Hovmoller diagrams

Time against longitude (or latitude): `pcolormesh` or `contourf` with
time on the vertical axis, stated direction (increasing downward matches
reading order for forecasts; increasing upward matches time series
intuition; pick one and label it), anomalies on a centered diverging map,
and the averaged-over band stated in the title (for example "5S-5N mean").

## Uncertainty visualization

Per SPEC §3.3, this section is load-bearing, not decoration:

- **Interval bands on time series:** `fill_between` around the line, the
  method and level in the label ("95% CI, block bootstrap"), band drawn
  under the line, alpha kept legible in print.
- **Spread maps:** an ensemble mean map is accompanied by a spread map
  (standard deviation or IQR, sequential colormap), same projection and
  extent, side by side.
- **Agreement maps and hatching:** for multi-member results, map the
  fraction of members agreeing on sign; hatch regions of LOW agreement
  (state the threshold, for example "hatching: fewer than 80% of members
  agree on sign"). Hatching low agreement keeps the visually quiet
  regions trustworthy.
- **The pairing rule: any interpolated or machine-learning-derived
  surface presented to stakeholders ships with an adjacent uncertainty
  map** (prediction standard error, cross-validation error, or ensemble
  spread). A kriged or ML surface without its uncertainty panel is not
  presentable.
- Every band, hatch, and stipple is defined in the caption with method
  and level; an undefined marking is worse than none.

## Must NOT

- Never use jet or rainbow colormaps, or a diverging map without a
  physically meaningful, pinned center.
- Never omit `transform=` on GeoAxes plotting calls.
- Never plot comparable panels with unshared color scales or unlabeled
  colorbars.
- Never mark stippling, hatching, or bands without defining test, level,
  and meaning in the caption.
- Never present an interpolated or ML-derived surface to stakeholders
  without its adjacent uncertainty map.
- Never export print figures below 300 dpi or with fonts under 7 pt at
  final size.

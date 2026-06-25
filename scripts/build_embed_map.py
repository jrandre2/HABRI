#!/usr/bin/env python3
"""Build a lightweight, embeddable HABRI web map (NC + Tennessee, shared scale).

Reads the shared-scale NC+TN standardized layer and emits a small, self-contained
Leaflet page suitable for hosting on GitHub Pages and embedding in a blog via an
``<iframe>``. The heavy source GeoPackage stays out of git (see .gitignore); only
the simplified GeoJSON + HTML artifact under ``web/map/`` is committed and deployed.

Why not the existing Folium maps: ``habri_nc_tn_standardized.html`` is ~157 MB and
``habri_map.html`` ~23 MB — both inline full-precision geometry and exceed GitHub's
100 MB/file hard limit (the 157 MB file would not load smoothly anyway). This script
simplifies geometry (~90 m tolerance) and trims coordinate precision to land near
~5 MB while staying detailed enough for county-level zoom.

Usage::

    python scripts/build_embed_map.py                 # defaults
    python scripts/build_embed_map.py --tolerance 0.0005 --precision 5

Output::

    web/map/index.html            # self-contained Leaflet page (vendored Leaflet)
    web/map/habri_nc_tn.geojson   # simplified, trimmed shared-scale layer
    web/map/vendor/leaflet.{js,css}

The companion ``scripts/build_site.py`` copies ``web/`` into ``_site/`` so the map
deploys at https://jrandre2.github.io/HABRI/map/ via the Pages workflow.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_GPKG = PROJECT_ROOT / "data" / "processed" / "habri_nc_tn_standardized.gpkg"
OUT_DIR = PROJECT_ROOT / "web" / "map"

# Properties carried into the GeoJSON. Geometry dominates file size, so the column
# list is kept tight; everything here feeds the tooltip or the color toggle.
KEEP_COLS = [
    "GEOID", "state_abbr", "county_name",
    "H_E", "I_F", "C_C", "HABRI",
    "HABRI_quintile", "HABRI_quintile_state", "risk_profile",
]
ROUND3 = ["H_E", "I_F", "C_C", "HABRI"]
QUINT = ["HABRI_quintile", "HABRI_quintile_state"]

TITLE = "HABRI — Broadband Outage Risk"
SUBTITLE = ("North Carolina + Tennessee, shared cross-state scale. "
            "Higher scores = greater risk of losing connectivity in a disaster. "
            "Hover a tract for detail; switch the driver at top-right.")
SOURCES = "FEMA NRI v1.20 · Ookla · FCC BDC · HIFLD · Census ACS 2022"
REPO = "https://github.com/jrandre2/HABRI"


def build_geojson(tolerance: float, precision: int) -> Path:
    print(f"Reading {SRC_GPKG.relative_to(PROJECT_ROOT)} ...")
    gdf = gpd.read_file(SRC_GPKG)
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)

    missing = [c for c in KEEP_COLS if c not in gdf.columns]
    if missing:
        sys.exit(f"ERROR: source layer missing expected columns: {missing}")

    out = gdf[KEEP_COLS + ["geometry"]].copy()
    for c in ROUND3:
        out[c] = pd.to_numeric(out[c], errors="coerce").round(3)
    for c in QUINT:
        out[c] = pd.to_numeric(out[c], errors="coerce").round().astype("Int64")

    if tolerance > 0:
        # preserve_topology avoids self-intersections; thin white tract strokes in
        # the page mask the small inter-tract gaps independent simplification leaves.
        out["geometry"] = out.geometry.simplify(tolerance, preserve_topology=True)

    geojson_path = OUT_DIR / "habri_nc_tn.geojson"
    if geojson_path.exists():
        geojson_path.unlink()
    out.to_file(geojson_path, driver="GeoJSON", COORDINATE_PRECISION=precision)

    size_mb = geojson_path.stat().st_size / 1e6
    print(f"  wrote {geojson_path.relative_to(PROJECT_ROOT)}  "
          f"({len(out):,} tracts, {size_mb:.2f} MB, tol={tolerance}, prec={precision})")
    if size_mb > 90:
        print("  WARNING: >90 MB — increase --tolerance; GitHub rejects files >100 MB.")
    return geojson_path


def build_html() -> Path:
    html = HTML_TEMPLATE
    for token, value in {
        "__TITLE__": TITLE,
        "__SUBTITLE__": SUBTITLE,
        "__SOURCES__": SOURCES,
        "__REPO__": REPO,
        "__BUILD_DATE__": date.today().isoformat(),
        "__GEOJSON__": "habri_nc_tn.geojson",
    }.items():
        html = html.replace(token, value)
    html_path = OUT_DIR / "index.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"  wrote {html_path.relative_to(PROJECT_ROOT)}  "
          f"({html_path.stat().st_size/1e3:.1f} KB)")
    return html_path


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<link rel="stylesheet" href="vendor/leaflet.css">
<style>
  html,body{margin:0;height:100%;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;}
  #map{position:absolute;inset:0;background:#e9ecef;}
  .panel{background:rgba(255,255,255,.95);border-radius:8px;box-shadow:0 1px 6px rgba(0,0,0,.25);}
  #titlebar{position:absolute;top:10px;left:10px;z-index:1000;max-width:330px;padding:10px 12px;}
  #titlebar h1{margin:0 0 3px;font-size:15px;line-height:1.2;color:#212529;}
  #titlebar p{margin:0;font-size:11.5px;color:#555;line-height:1.4;}
  #controls{position:absolute;top:10px;right:10px;z-index:1000;padding:8px 10px;font-size:12.5px;}
  #controls label{font-weight:600;color:#333;display:block;margin-bottom:4px;}
  #controls select{font-size:12.5px;padding:3px 4px;width:185px;}
  #legend{position:absolute;bottom:24px;right:10px;z-index:1000;padding:8px 10px;font-size:11.5px;color:#333;width:175px;}
  #legend .lt{font-weight:600;margin-bottom:5px;}
  .grad{height:12px;border-radius:2px;border:1px solid #ccc;}
  .gl{display:flex;justify-content:space-between;font-size:10.5px;color:#666;margin-top:2px;}
  .sw{display:inline-block;width:13px;height:13px;border-radius:3px;margin-right:6px;vertical-align:-2px;border:1px solid rgba(0,0,0,.2);}
  .leaflet-tooltip.habri{font-size:12px;line-height:1.45;padding:6px 8px;}
  #credit{position:absolute;bottom:2px;left:8px;z-index:1000;font-size:10px;color:#666;background:rgba(255,255,255,.75);padding:1px 6px;border-radius:3px;}
  #credit a{color:#666;}
</style>
</head>
<body>
<div id="map"></div>
<div id="titlebar" class="panel">
  <h1>__TITLE__</h1>
  <p>__SUBTITLE__</p>
</div>
<div id="controls" class="panel">
  <label for="field">Color tracts by</label>
  <select id="field"></select>
</div>
<div id="legend" class="panel"></div>
<div id="credit">__SOURCES__ &middot; <a href="__REPO__" target="_blank" rel="noopener">data &amp; methods</a> &middot; built __BUILD_DATE__</div>

<script src="vendor/leaflet.js"></script>
<script>
const GEOJSON_URL="__GEOJSON__";
const FIELDS=[
 {key:'HABRI',label:'Overall HABRI risk',type:'seq'},
 {key:'H_E',label:'Hazard exposure',type:'seq'},
 {key:'I_F',label:'Infrastructure fragility',type:'seq'},
 {key:'C_C',label:'Coping-capacity deficit',type:'seq'},
 {key:'risk_profile',label:'Risk profile (cluster)',type:'cat'}
];
const RAMP=['#ffffcc','#fed976','#feb24c','#fd8d3c','#f03b20','#bd0026'];
const PROFILE_COLORS={'Power-Dependent':'#3182bd','Dual-Risk':'#756bb1','Transport-Fragile':'#e6550d'};
const GRAD_CSS='linear-gradient(to right,'+RAMP.join(',')+')';
function hex2rgb(h){return [parseInt(h.slice(1,3),16),parseInt(h.slice(3,5),16),parseInt(h.slice(5,7),16)];}
function rampColor(t){t=Math.max(0,Math.min(1,t));const n=RAMP.length-1;let i=Math.floor(t*n);if(i>=n)i=n-1;const f=t*n-i;const a=hex2rgb(RAMP[i]),b=hex2rgb(RAMP[i+1]);const m=k=>Math.round(a[k]+(b[k]-a[k])*f);return 'rgb('+m(0)+','+m(1)+','+m(2)+')';}

const map=L.map('map',{minZoom:5,maxZoom:12});
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',{
  attribution:'&copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  subdomains:'abcd',maxZoom:19
}).addTo(map);

let layer,domains={},current=FIELDS[0];
function fmt(v){return (v==null||isNaN(v))?'n/a':Number(v).toFixed(3);}
function styleFor(field){return function(f){const p=f.properties;let fill='#cccccc';
  if(field.type==='cat'){fill=PROFILE_COLORS[p[field.key]]||'#cccccc';}
  else{const d=domains[field.key];const span=(d[1]-d[0])||1;fill=rampColor((p[field.key]-d[0])/span);}
  return {fillColor:fill,weight:0.3,color:'#ffffff',opacity:0.55,fillOpacity:0.82};};}
function tip(p){return '<b>'+p.county_name+' County, '+p.state_abbr+'</b><br>'+
  'HABRI (NC+TN scale): <b>'+fmt(p.HABRI)+'</b> &middot; Q'+p.HABRI_quintile+'/5<br>'+
  'Within '+p.state_abbr+': Q'+p.HABRI_quintile_state+'/5<br>'+
  'Profile: '+p.risk_profile+'<br>'+
  '<span style="color:#666">Hazard '+fmt(p.H_E)+' &middot; Infra '+fmt(p.I_F)+' &middot; Coping '+fmt(p.C_C)+'</span>';}
function highlight(e){const l=e.target;l.setStyle({weight:1.6,color:'#222',opacity:1});l.bringToFront();}
function reset(e){layer.resetStyle(e.target);}
function updateLegend(){const el=document.getElementById('legend');
  if(current.type==='cat'){let h='<div class="lt">'+current.label+'</div>';
    for(const k in PROFILE_COLORS){h+='<div><span class="sw" style="background:'+PROFILE_COLORS[k]+'"></span>'+k+'</div>';}
    el.innerHTML=h;}
  else{const d=domains[current.key];const mid=(d[0]+d[1])/2;
    el.innerHTML='<div class="lt">'+current.label+'</div>'+
      '<div class="grad" style="background:'+GRAD_CSS+'"></div>'+
      '<div class="gl"><span>'+d[0].toFixed(2)+'</span><span>'+mid.toFixed(2)+'</span><span>'+d[1].toFixed(2)+'</span></div>'+
      '<div style="margin-top:4px;color:#666">Higher = greater risk</div>';}}
function applyField(){layer.setStyle(styleFor(current));updateLegend();}

fetch(GEOJSON_URL).then(r=>r.json()).then(gj=>{
  for(const fd of FIELDS){if(fd.type==='seq'){let mn=Infinity,mx=-Infinity;
    for(const ft of gj.features){const v=ft.properties[fd.key];if(v!=null&&!isNaN(v)){if(v<mn)mn=v;if(v>mx)mx=v;}}
    domains[fd.key]=[mn,mx];}}
  layer=L.geoJSON(gj,{style:styleFor(current),onEachFeature:function(f,l){
    l.bindTooltip(tip(f.properties),{sticky:true,className:'habri'});
    l.on({mouseover:highlight,mouseout:reset});}}).addTo(map);
  map.fitBounds(layer.getBounds(),{padding:[10,10]});
  const sel=document.getElementById('field');
  FIELDS.forEach(function(fd,i){const o=document.createElement('option');o.value=i;o.textContent=fd.label;sel.appendChild(o);});
  sel.addEventListener('change',function(e){current=FIELDS[+e.target.value];applyField();});
  updateLegend();
}).catch(function(err){document.getElementById('map').innerHTML='<p style="padding:20px;font-family:sans-serif">Could not load map data: '+err+'</p>';});
</script>
</body>
</html>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the embeddable NC+TN HABRI map.")
    ap.add_argument("--tolerance", type=float, default=0.0008,
                    help="Geometry simplification tolerance in degrees (~0.0008 = ~75 m).")
    ap.add_argument("--precision", type=int, default=4,
                    help="GeoJSON coordinate decimal places (4 = ~11 m).")
    args = ap.parse_args()

    if not SRC_GPKG.exists():
        sys.exit(f"ERROR: {SRC_GPKG} not found. Run scripts/build_habri_nc_tn_combined.py first.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Building embeddable HABRI map (NC + TN)...")
    gj = build_geojson(args.tolerance, args.precision)
    build_html()

    total = sum(p.stat().st_size for p in OUT_DIR.rglob("*") if p.is_file()) / 1e6
    print(f"\nDone. web/map/ total = {total:.2f} MB")
    print(f"Local preview:  python -m http.server -d web 8000  →  http://localhost:8000/map/")
    print(f"Deployed (after build_site.py + Pages): https://jrandre2.github.io/HABRI/map/")


if __name__ == "__main__":
    main()

// Replace YOUR_CARTO_BASEMAP_KEY with your domain-restricted CARTO basemaps key.
// Keep the configured deployment copy separate from this public example.
// Use an absolute URL here only if the API is hosted on a different domain.
window.AIRSENT_CONFIG = {
  apiBase: location.origin,
  // SITL bundle: keyless Esri satellite tiles (same source as teleop.py) so maps
  // render without a CARTO key. The deployed console keeps its own copy.
  mapTileUrl: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  mapAttribution: "Tiles &copy; Esri",
  mapMaxZoom: 19,
};
window.airsentApiUrl = function(path, websocket = false) {
  const url = new URL(path, window.AIRSENT_CONFIG.apiBase);
  if (websocket) url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.href;
};
window.airsentMapLayer = function(map) {
  const cfg = window.AIRSENT_CONFIG;
  const layer = L.tileLayer(cfg.mapTileUrl, {
    maxZoom: cfg.mapMaxZoom, subdomains: "abcd", attribution: cfg.mapAttribution,
  }).addTo(map);
  const notice = L.control({position: "bottomleft"});
  notice.onAdd = function() {
    const el = L.DomUtil.create("div");
    el.textContent = "Map tiles unavailable — check network or map provider configuration";
    el.style.cssText = "display:none;background:#18202b;color:#fff;padding:8px;max-width:260px;font:12px sans-serif";
    this.message = el;
    return el;
  };
  notice.addTo(map);
  layer.on("tileerror", () => { notice.message.style.display = "block"; });
  layer.on("tileload", () => { notice.message.style.display = "none"; });
  return layer;
};

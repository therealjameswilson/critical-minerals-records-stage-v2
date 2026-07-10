const isLocalSite = ["localhost", "127.0.0.1"].includes(window.location.hostname);
const naraProxyUrl = isLocalSite
  ? "http://localhost:5757"
  : "https://critical-minerals-records-stage-v2.jagwilson.workers.dev";

window.HISTORY_RUNTIME_CONFIG = Object.freeze({
  naraProxyUrl
});

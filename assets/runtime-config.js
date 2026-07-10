const localNaraProxy = ["localhost", "127.0.0.1"].includes(window.location.hostname)
  ? "http://localhost:5757"
  : "";

window.HISTORY_RUNTIME_CONFIG = Object.freeze({
  naraProxyUrl: localNaraProxy
});

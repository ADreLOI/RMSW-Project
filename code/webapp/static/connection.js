"use strict";
// Passwords live only in this closure and are never stored or put in URLs.
window.LabConnection = (() => {
  const config = window.LAB_CONFIG || {};
  let base = "", password = "", online = false, revision = 0, manifest;
  const text = (key) => I18N.t(key);
  const keyFor = (path) => {
    const url = new URL(path, location.origin);
    if (url.searchParams.get("dataset") === "core") url.searchParams.delete("dataset");
    url.searchParams.sort();
    return url.pathname + (url.searchParams.size ? "?" + url.searchParams.toString() : "");
  };
  function origin(value) {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password || url.pathname !== "/" || url.search || url.hash)
      throw Error(text("remote.invalid"));
    return url.origin;
  }
  async function authenticated(path, options = {}) {
    const headers = new Headers(options.headers || {});
    const bytes = new TextEncoder().encode("lab:" + password);
    headers.set("Authorization", "Basic " + btoa(Array.from(bytes, (b) => String.fromCharCode(b)).join("")));
    return fetch(base + path, { ...options, headers, credentials: "omit", redirect: "error" });
  }
  async function request(path, options = {}) {
    const current = revision;
    let response;
    if (!config.static) response = await fetch(path, options);
    else if (online) response = await authenticated(path, options);
    else {
      if (options.method && options.method !== "GET") throw Error(text("remote.required"));
      if (!manifest) {
        const result = await fetch("./data/manifest.json");
        if (!result.ok) throw Error(text("remote.unavailable"));
        manifest = await result.json();
      }
      const entry = manifest[keyFor(path)];
      if (!entry) throw Error(text("remote.notPublished"));
      response = await fetch(new URL(entry.path, document.baseURI));
    }
    if (current !== revision) throw Error(text("remote.changed"));
    return response;
  }
  async function liveUrl() {
    if (!config.static) {
      const url = new URL("/live", location.href);
      url.protocol = location.protocol === "https:" ? "wss:" : "ws:";
      return url.href;
    }
    const response = await authenticated("/live-ticket", { method: "POST" });
    if (!response.ok) {
      const error = Error(response.status === 401 ? text("remote.passwordError") : text("remote.unavailable"));
      error.stopRetry = [401, 403].includes(response.status);
      throw error;
    }
    const { ticket } = await response.json();
    const url = new URL("/live", base);
    url.protocol = "wss:";
    url.searchParams.set("ticket", ticket);
    return url.href;
  }
  function init() {
    const panel = document.getElementById("remote-panel");
    panel.hidden = !config.static;
    if (!config.static) return;
    document.getElementById("relay-url").value = config.relayUrl || "";
    document.getElementById("remote-form").addEventListener("submit", (event) => {
      event.preventDefault();
      try {
        base = origin(document.getElementById("relay-url").value.trim());
        password = document.getElementById("relay-password").value;
        document.getElementById("relay-password").value = "";
        online = false;
        ++revision;
        window.dispatchEvent(new Event("lab-connect"));
      } catch (error) {
        document.getElementById("remote-status").textContent = error.message;
      }
    });
    document.getElementById("remote-disconnect").addEventListener("click", () => {
      base = password = ""; online = false; ++revision;
      window.dispatchEvent(new Event("lab-disconnect"));
    });
    // API links include figures, raw logs and ZIPs. Authenticate the download too.
    document.addEventListener("click", async (event) => {
      const anchor = event.target.closest("a");
      const path = anchor?.getAttribute("href");
      if (!path?.startsWith("/api/")) return;
      event.preventDefault();
      try {
        const response = await request(path);
        if (!response.ok) throw Error((await response.json()).error || text("remote.unavailable"));
        const name = response.headers.get("Content-Disposition")?.match(/filename="([^"]+)"/)?.[1]
          || (!online && manifest?.[keyFor(path)]?.name) || "download";
        const url = URL.createObjectURL(await response.blob());
        const link = document.createElement("a");
        link.href = url; link.download = name;
        document.body.appendChild(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 60000);
      } catch (error) {
        document.getElementById("toast").textContent = error.message;
        document.getElementById("toast").hidden = false;
      }
    });
  }
  return {
    static: Boolean(config.static), request, liveUrl, init,
    get remote() { return Boolean(base && password); },
    get online() { return online; },
    setOnline(value) { if (online !== value) { online = value; ++revision; } },
  };
})();

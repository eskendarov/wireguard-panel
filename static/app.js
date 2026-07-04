const loginScreen = document.getElementById("login-screen");
const mainScreen = document.getElementById("main-screen");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const peersBody = document.getElementById("peers-body");
const addModal = document.getElementById("add-modal");
const qrModal = document.getElementById("qr-modal");

function showMain() {
  loginScreen.classList.add("hidden");
  mainScreen.classList.remove("hidden");
  refreshPeers();
}

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let value = bytes;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i++;
  }
  return `${value.toFixed(1)} ${units[i]}`;
}

function formatHandshake(unixSeconds) {
  if (!unixSeconds) return "never";
  const seconds = Math.floor(Date.now() / 1000) - unixSeconds;
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

async function refreshPeers() {
  const res = await fetch("/api/peers");
  if (res.status === 401) {
    mainScreen.classList.add("hidden");
    loginScreen.classList.remove("hidden");
    return;
  }
  const peers = await res.json();
  peersBody.innerHTML = "";
  for (const peer of peers) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><span class="dot ${peer.online ? "online" : "offline"}"></span>${peer.online ? "online" : "offline"}</td>
      <td>${peer.name}</td>
      <td>${peer.address_v4}</td>
      <td>${formatBytes(peer.transfer_tx)}</td>
      <td>${formatBytes(peer.transfer_rx)}</td>
      <td>${formatHandshake(peer.latest_handshake)}</td>
      <td>
        <button class="ghost" data-qr="${peer.id}" data-name="${peer.name}">QR</button>
        <button class="ghost" data-toggle="${peer.id}">${peer.enabled ? "Disable" : "Enable"}</button>
        <button class="ghost" data-delete="${peer.id}">Delete</button>
      </td>
    `;
    peersBody.appendChild(row);
  }
}

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const password = document.getElementById("login-password").value;
  const res = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (res.ok) {
    loginError.textContent = "";
    showMain();
  } else {
    loginError.textContent = "Wrong password";
  }
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" });
  location.reload();
});

document.getElementById("add-btn").addEventListener("click", () => {
  addModal.classList.remove("hidden");
});

document.getElementById("add-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = document.getElementById("add-name").value.trim();
  const res = await fetch("/api/peers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (res.ok) {
    document.getElementById("add-name").value = "";
    addModal.classList.add("hidden");
    refreshPeers();
  }
});

peersBody.addEventListener("click", async (e) => {
  const target = e.target;
  if (target.dataset.qr) {
    document.getElementById("qr-name").textContent = target.dataset.name;
    document.getElementById("qr-image").src = `/api/peers/${target.dataset.qr}/qr?t=${Date.now()}`;
    document.getElementById("qr-download").href = `/api/peers/${target.dataset.qr}/config`;
    qrModal.classList.remove("hidden");
  }
  if (target.dataset.toggle) {
    await fetch(`/api/peers/${target.dataset.toggle}/toggle`, { method: "POST" });
    refreshPeers();
  }
  if (target.dataset.delete) {
    if (confirm("Delete this client? This cannot be undone.")) {
      await fetch(`/api/peers/${target.dataset.delete}`, { method: "DELETE" });
      refreshPeers();
    }
  }
});

document.querySelectorAll("[data-close]").forEach((btn) => {
  btn.addEventListener("click", () => {
    addModal.classList.add("hidden");
    qrModal.classList.add("hidden");
  });
});

// Check if we're already logged in (session cookie still valid).
fetch("/api/peers").then((res) => {
  if (res.ok) showMain();
});

setInterval(() => {
  if (!mainScreen.classList.contains("hidden")) refreshPeers();
}, 5000);

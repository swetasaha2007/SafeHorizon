const API_BASE = location.protocol === "file:" ? "http://127.0.0.1:5000" : "";
const DEMO_HINT = " You can still demonstrate the system with Demo mode.";

// ---------------------------------------------------------
// DOM references
// ---------------------------------------------------------
const $ = (id) => document.getElementById(id);

const el = {
  form: $("locationForm"),
  input: $("locationInput"),
  analyzeBtn: $("analyzeBtn"),
  geoBtn: $("geoBtn"),
  status: $("status"),
  statusIcon: $("statusIcon"),
  statusText: $("statusText"),
  locName: $("locName"), locLat: $("locLat"), locLng: $("locLng"),
  wxRain: $("wxRain"), wxWind: $("wxWind"), wxTemp: $("wxTemp"),
  wxHumidity: $("wxHumidity"), wxCond: $("wxCond"), wxFlood: $("wxFlood"),
  riskCard: $("riskCard"), riskLevel: $("riskLevel"), riskScore: $("riskScore"),
  riskMeter: $("riskMeter"), riskAction: $("riskAction"), riskReasons: $("riskReasons"),
  riskIconUse: $("riskIconUse"),
  shelterName: $("shelterName"), shelterAddress: $("shelterAddress"),
  shelterDistance: $("shelterDistance"), shelterCapacity: $("shelterCapacity"),
  routeBtn: $("routeBtn"), routeFrom: $("routeFrom"), routeTo: $("routeTo"),
  scenarioBtns: document.querySelectorAll(".demo-switch button"),
  demoOnly: document.querySelectorAll(".demo-only")
};

// ---------------------------------------------------------
// Status bar: idle | loading | success | error
// ---------------------------------------------------------
function setStatus(state, message) {
  el.status.className = "status status--" + state;
  el.statusText.textContent = message;

  const icons = { success: "i-check", error: "i-x", idle: "i-pin" };
  el.statusIcon.innerHTML = state === "loading"
    ? '<span class="spinner"></span>'
    : `<svg><use href="#${icons[state]}"/></svg>`;
}

function setBusy(busy) {
  el.analyzeBtn.disabled = busy;
  el.geoBtn.disabled = busy;
  el.scenarioBtns.forEach((b) => (b.disabled = busy));
}

// ---------------------------------------------------------
// Render functions — each section of the dashboard
// ---------------------------------------------------------
function renderLocation(loc) {
  el.locName.textContent = loc.name;
  el.locLat.textContent = Number(loc.latitude).toFixed(4);
  el.locLng.textContent = Number(loc.longitude).toFixed(4);
  el.routeFrom.textContent = loc.name;
}

function renderWeather(w) {
  el.wxRain.textContent = w.rainfall === null ? "N/A" : `${w.rainfall} mm`;
  el.wxWind.textContent = `${w.wind_speed} km/h`;
  el.wxTemp.textContent = `${w.temperature}°C`;
  el.wxHumidity.textContent = `${w.humidity}%`;
  el.wxCond.textContent = w.condition;
}

function renderFloodLevel(flood) {
  el.wxFlood.textContent = `${flood.value} ${flood.unit}`;
}

function renderRisk(risk) {
  const levelKey = {
    "SAFE": "safe",
    "EVACUATE": "evacuate",
    "EVACUATE IMMEDIATELY": "immediate"
  }[risk.level] || "evacuate";

  el.riskCard.dataset.level = levelKey;
  el.riskLevel.textContent = risk.level;
  el.riskScore.textContent = risk.score;
  el.riskMeter.style.width = Math.max(0, Math.min(100, risk.score)) + "%";
  el.riskAction.textContent = risk.action;
  el.riskIconUse.setAttribute("href", levelKey === "safe" ? "#i-check" : "#i-alert");

  el.riskReasons.innerHTML = "";
  risk.reasons.forEach((reason) => {
    const li = document.createElement("li");
    li.textContent = reason;
    el.riskReasons.appendChild(li);
  });
}

function renderShelter(s, distanceKm) {
  el.shelterName.textContent = s.name;
  el.shelterAddress.textContent = s.address;
  el.shelterDistance.textContent = `${distanceKm} km`;
  el.shelterCapacity.textContent = s.capacity;
  el.routeTo.textContent = s.name;
}

// Google Maps directions link
function renderRoute(route) {
  const ok = route && typeof route.url === "string" && route.url.startsWith("https://www.google.com/maps/dir/");
  el.routeBtn.href = ok ? route.url : "#";
  el.routeBtn.classList.toggle("is-disabled", !ok);
  el.routeBtn.setAttribute("aria-disabled", String(!ok));
  return ok;
}

// data: { location, weather, flood_level, risk, shelter, distance_km, route }
function renderAll(data) {
  renderLocation(data.location);
  renderWeather(data.weather);
  renderFloodLevel(data.flood_level);
  renderRisk(data.risk);
  renderShelter(data.shelter, data.distance_km);
  return renderRoute(data.route);
}

// Show / hide the DEMO DATA labels and highlight the active scenario
function setDemoMode(name) {
  el.scenarioBtns.forEach((b) => b.classList.toggle("active", b.dataset.scenario === name));
  el.demoOnly.forEach((node) => (node.hidden = !name));
}

// ---------------------------------------------------------
// Flask API calls
// ---------------------------------------------------------

// Fetch JSON from Flask. Throws an Error with a user-friendly message on failure.
async function api(path, body) {
  let res;
  try {
    res = await fetch(API_BASE + path, body === undefined ? {} : {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
  } catch {
    throw new Error("Cannot reach the server. Make sure Flask is running (python app.py).");
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Something went wrong on the server.");
  return data;
}

// params: { latitude, longitude }  or  { query: "Kolkata" }
async function fetchAnalysis(params) {
  // 1. Weather (OpenWeather) + demo flood level
  const { location, weather, flood_level } = await api("/api/analyze", params);

  // 2. Risk score + nearest shelter + route
  const assessment = await api("/api/assess-risk", {
    latitude: location.latitude,
    longitude: location.longitude,
    rainfall: weather.rainfall,
    wind_speed: weather.wind_speed,
    flood_level: flood_level.value
  });

  return { location, weather, ...assessment };
}

function finish(routeOk, message) {
  if (routeOk) setStatus("success", message);
  else setStatus("error", "Risk assessment complete, but the evacuation route could not be created. Use the shelter address to navigate.");
}

async function analyze(params) {
  setBusy(true);
  setStatus("loading", "Analyzing location...");
  try {
    const data = await fetchAnalysis(params);
    const routeOk = renderAll(data);
    setDemoMode(null);
    finish(routeOk, "Risk assessment complete. Flood level is demo data.");
  } catch (err) {
    console.warn(err);
    setStatus("error", err.message + DEMO_HINT);
  } finally {
    setBusy(false);
  }
}

// DEMO MODE: predefined location, weather and flood level
async function runDemo(name) {
  setBusy(true);
  setStatus("loading", "Loading demo scenario...");
  try {
    const data = await api(`/api/demo/${name}`);
    const routeOk = renderAll(data);
    setDemoMode(name);
    finish(routeOk, `DEMO DATA: ${data.title} scenario. Enter a location or use your current location for real weather.`);
  } catch (err) {
    console.warn(err);
    setStatus("error", err.message);
  } finally {
    setBusy(false);
  }
}

// ---------------------------------------------------------
// Event handlers
// ---------------------------------------------------------
el.form.addEventListener("submit", (e) => {
  e.preventDefault();
  const query = el.input.value.trim();
  if (!query) {
    el.input.classList.add("invalid");
    el.input.focus();
    setStatus("error", "Please enter a location to analyze.");
    return;
  }
  el.input.classList.remove("invalid");
  analyze({ query });
});

el.input.addEventListener("input", () => el.input.classList.remove("invalid"));

el.geoBtn.addEventListener("click", () => {
  if (!("geolocation" in navigator)) {
    setStatus("error", "Unable to access your location. Geolocation is not supported." + DEMO_HINT);
    return;
  }
  setBusy(true);
  setStatus("loading", "Getting your location...");
  navigator.geolocation.getCurrentPosition(
    async (pos) => {
      try {
        // Send the coordinates to Flask, which validates them
        const coords = await api("/api/location", {
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude
        });
        await analyze(coords);
      } catch (err) {
        setBusy(false);
        setStatus("error", err.message);
      }
    },
    (err) => {
      setBusy(false);
      const messages = {
        1: "Unable to access your location: permission was denied. Please allow location access or enter it manually.",
        2: "Unable to access your location: position unavailable. Please enter it manually.",
        3: "Unable to access your location: the request timed out. Please try again or enter it manually."
      };
      setStatus("error", (messages[err.code] || "Unable to access your location. Please enter it manually.") + DEMO_HINT);
    },
    { enableHighAccuracy: true, timeout: 10000 }
  );
});

// Block the route button until a valid route exists
el.routeBtn.addEventListener("click", (e) => {
  if (el.routeBtn.classList.contains("is-disabled")) {
    e.preventDefault();
    setStatus("error", "No evacuation route yet. Analyze a location or choose a Demo mode scenario first.");
  }
});

el.scenarioBtns.forEach((btn) => {
  btn.addEventListener("click", () => runDemo(btn.dataset.scenario));
});

runDemo("high");

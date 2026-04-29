'use strict';

const API_BASE = 'http://127.0.0.1:8000';
const WS_URL = 'ws://127.0.0.1:8000/ws/live';
const NOMINATIM = 'https://nominatim.openstreetmap.org/search';
const DEFAULT_CENTER = [15.3173, 75.7139];
const REFRESH_MS = 20000;
const STORAGE_KEY = 'crowdpulse-auth';

const state = {
  auth: null,
  currentLocation: null,
  predictLocation: null,
  currentPrediction: null,
  sessionId: `crowd-${Math.random().toString(36).slice(2)}`,
  maps: { main: null, heat: null },
  markers: { main: null, circle: null, heat: [] },
  charts: { history: null, predict: null, peak: null, week: null },
  websocket: null,
  liveTimer: null,
  lastHeatmap: [],
};

const CROWD_COLOR = pct =>
  pct < 30 ? '#22c55e' : pct < 60 ? '#f59e0b' : pct < 80 ? '#f97316' : '#ef4444';

const CROWD_LABEL = pct =>
  pct < 30 ? 'LOW' : pct < 60 ? 'MODERATE' : pct < 80 ? 'HIGH' : 'VERY HIGH';

document.addEventListener('DOMContentLoaded', async () => {
  initClock();
  initAuthTabs();
  initAuthForms();
  initLogout();
  restoreAuth();

  if (state.auth?.token) {
    const valid = await hydrateUser();
    if (valid) {
      bootApp();
      return;
    }
  }

  showAuthShell();
});

function initClock() {
  const el = document.getElementById('timeDisplay');
  const render = () => {
    if (!el) return;
    el.textContent = new Date().toLocaleTimeString('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
    });
  };
  render();
  setInterval(render, 1000);
}

function initAuthTabs() {
  document.querySelectorAll('.auth-tab').forEach(button => {
    button.addEventListener('click', () => {
      const mode = button.dataset.authMode;
      document.querySelectorAll('.auth-tab').forEach(node => node.classList.toggle('active', node === button));
      document.getElementById('loginForm').classList.toggle('active', mode === 'login');
      document.getElementById('signupForm').classList.toggle('active', mode === 'signup');
    });
  });
}

function initAuthForms() {
  document.getElementById('loginForm').addEventListener('submit', async event => {
    event.preventDefault();
    const payload = {
      email: document.getElementById('loginEmail').value.trim(),
      password: document.getElementById('loginPassword').value,
    };
    await submitAuth('login', payload, document.getElementById('loginSubmit'));
  });

  document.getElementById('signupForm').addEventListener('submit', async event => {
    event.preventDefault();
    const payload = {
      name: document.getElementById('signupName').value.trim(),
      email: document.getElementById('signupEmail').value.trim(),
      password: document.getElementById('signupPassword').value,
    };
    await submitAuth('signup', payload, document.getElementById('signupSubmit'));
  });
}

async function submitAuth(mode, payload, button) {
  const label = button.textContent;
  button.disabled = true;
  button.textContent = mode === 'login' ? 'Signing In...' : 'Creating Account...';
  try {
    const response = await fetch(`${API_BASE}/auth/${mode}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || data.message || 'Auth failed');
    }

    state.auth = {
      token: data.token,
      name: data.name,
      email: data.email,
    };
    persistAuth();
    updateMemberUI();
    showToast(mode === 'login' ? 'Signed in successfully' : 'Account created successfully');
    showAppShell();
    bootApp();
  } catch (error) {
    showToast(error.message || 'Authentication failed', 'error');
  } finally {
    button.disabled = false;
    button.textContent = label;
  }
}

function initLogout() {
  document.getElementById('logoutBtn').addEventListener('click', logout);
}

async function logout() {
  try {
    if (state.auth?.token) {
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        headers: authHeaders(),
      });
    }
  } catch {
    // Frontend logout still proceeds.
  }

  clearInterval(state.liveTimer);
  state.liveTimer = null;
  state.currentLocation = null;
  state.predictLocation = null;
  state.currentPrediction = null;
  if (state.websocket) {
    state.websocket.close();
    state.websocket = null;
  }
  state.auth = null;
  localStorage.removeItem(STORAGE_KEY);
  showAuthShell();
  showToast('Logged out');
}

function restoreAuth() {
  try {
    state.auth = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
  } catch {
    state.auth = null;
  }
}

function persistAuth() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.auth));
}

async function hydrateUser() {
  try {
    const response = await fetch(`${API_BASE}/auth/me`, { headers: authHeaders() });
    if (!response.ok) return false;
    const user = await response.json();
    state.auth = {
      token: state.auth.token,
      name: user.name,
      email: user.email,
    };
    persistAuth();
    updateMemberUI();
    return true;
  } catch {
    return false;
  }
}

function authHeaders(extra = {}) {
  return {
    Authorization: `Bearer ${state.auth?.token || ''}`,
    ...extra,
  };
}

function showAuthShell() {
  document.getElementById('authShell').classList.remove('hidden');
  document.getElementById('appShell').classList.add('hidden');
}

function showAppShell() {
  document.getElementById('authShell').classList.add('hidden');
  document.getElementById('appShell').classList.remove('hidden');
}

function updateMemberUI() {
  const name = state.auth?.name || 'Guest';
  const email = state.auth?.email || 'guest@example.com';
  document.getElementById('memberName').textContent = name;
  document.getElementById('memberEmail').textContent = email;
  document.getElementById('memberAvatar').textContent = initials(name);
  document.getElementById('welcomeTitle').textContent = `Hi ${name.split(' ')[0]}, ready for your next crowd check?`;
  document.getElementById('welcomeText').textContent = 'Search a place to see its real-time crowd percentage, future forecast, and live visit advice.';
}

let appBooted = false;
function bootApp() {
  updateMemberUI();
  if (appBooted) {
    if (!state.websocket) connectWebSocket();
    loadHeatmap();
    return;
  }
  appBooted = true;

  initTabs();
  initMaps();
  initGauge();
  initSearch('searchInput', 'searchResults', location => {
    state.currentLocation = location;
    document.getElementById('searchInput').value = location.name;
    activateLocation(location);
  });
  initSearch('predictLocation', 'predictResults', location => {
    state.predictLocation = location;
    document.getElementById('predictLocation').value = location.name;
  });
  initPredictForm();
  initSidebarToggle();
  initGps();
  initCheckIn();
  fillHourSelect();
  connectWebSocket();
  loadHeatmap();
  setInterval(loadHeatmap, 30000);
}

function initTabs() {
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', event => {
      event.preventDefault();
      const tab = item.dataset.tab;
      document.querySelectorAll('.nav-item').forEach(node => node.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(node => node.classList.remove('active'));
      item.classList.add('active');
      document.getElementById(`tab-${tab}`).classList.add('active');
      setTimeout(() => {
        state.maps.main?.invalidateSize();
        state.maps.heat?.invalidateSize();
      }, 120);

      if (window.innerWidth <= 780) {
        document.getElementById('sidebar').classList.remove('open');
      }
    });
  });
}

function initMaps() {
  state.maps.main = L.map('map', { center: DEFAULT_CENTER, zoom: 7, zoomControl: true });
  state.maps.heat = L.map('heatmap', { center: DEFAULT_CENTER, zoom: 7, zoomControl: true });
  [state.maps.main, state.maps.heat].forEach(map => {
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap',
      maxZoom: 19,
    }).addTo(map);
  });
}

function initGauge() {
  drawGauge(0, '#6b7fa8');
}

function initSearch(inputId, resultsId, onSelect) {
  const input = document.getElementById(inputId);
  const results = document.getElementById(resultsId);
  let debounce = null;

  input.addEventListener('input', () => {
    clearTimeout(debounce);
    const q = input.value.trim();
    if (q.length < 2) {
      results.classList.remove('open');
      return;
    }
    debounce = setTimeout(async () => {
      const items = await searchPlaces(q);
      if (!items.length) {
        results.classList.remove('open');
        return;
      }
      renderSearchResults(results, input, items, onSelect);
    }, 250);
  });

  document.addEventListener('click', event => {
    if (!input.contains(event.target) && !results.contains(event.target)) {
      results.classList.remove('open');
    }
  });
}

async function searchPlaces(query) {
  const url = `${NOMINATIM}?q=${encodeURIComponent(query)}&format=json&limit=6&addressdetails=1`;
  try {
    const response = await fetch(url, { headers: { 'Accept-Language': 'en' } });
    const data = await response.json();
    return data.map(item => ({
      name: item.display_name.split(',')[0].trim(),
      addr: item.display_name.split(',').slice(1, 4).join(', ').trim(),
      lat: parseFloat(item.lat),
      lng: parseFloat(item.lon),
    }));
  } catch {
    return [];
  }
}

function renderSearchResults(container, input, items, onSelect) {
  container.innerHTML = items.map((item, index) => `
    <div class="search-result-item" data-index="${index}">
      <div class="result-name">${escapeHtml(item.name)}</div>
      <div class="result-addr">${escapeHtml(item.addr)}</div>
    </div>
  `).join('');
  container.querySelectorAll('.search-result-item').forEach(node => {
    node.addEventListener('mousedown', () => {
      const item = items[Number(node.dataset.index)];
      input.value = item.name;
      container.classList.remove('open');
      onSelect(item);
    });
  });
  container.classList.add('open');
}

async function activateLocation(location) {
  updateMapSelection(location, 0);
  document.getElementById('checkinBtn').disabled = false;
  document.getElementById('checkinSub').textContent = `Signed in as ${state.auth.name}. Your presence can improve live accuracy.`;
  await refreshCurrentLocation();

  if (state.liveTimer) clearInterval(state.liveTimer);
  state.liveTimer = setInterval(refreshCurrentLocation, REFRESH_MS);
}

async function refreshCurrentLocation() {
  if (!state.currentLocation) return;
  try {
    const prediction = await fetchPredictionForCoords(state.currentLocation, new Date());
    state.currentPrediction = prediction;
    updateDashboard(prediction);
    updateHistoryChart(prediction.forecast_24h || []);
    updateAnalytics(prediction);
    updateMapSelection(state.currentLocation, prediction.crowd_pct);
  } catch {
    showToast('Backend is not reachable on port 8000', 'error');
  }
}

async function fetchPredictionForCoords(location, date) {
  const payload = {
    location_name: location.name,
    lat: location.lat,
    lng: location.lng,
    hour: date.getHours(),
    day_of_week: (date.getDay() + 6) % 7,
    target_date: date.toISOString(),
  };
  const response = await fetch(`${API_BASE}/predict/`, {
    method: 'POST',
    headers: {
      ...authHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error('prediction_failed');
  return response.json();
}

async function fetchPredictionByName(name, date) {
  const params = new URLSearchParams({
    name,
    hour: String(date.getHours()),
    day_of_week: String((date.getDay() + 6) % 7),
    date: date.toISOString(),
  });
  const response = await fetch(`${API_BASE}/predict/place?${params.toString()}`, {
    headers: authHeaders(),
  });
  if (!response.ok) throw new Error('place_prediction_failed');
  return response.json();
}

function updateDashboard(prediction) {
  const pct = prediction.crowd_pct ?? 0;
  const color = CROWD_COLOR(pct);
  const level = prediction.crowdLevel || CROWD_LABEL(pct);

  document.getElementById('statCrowdVal').textContent = `${pct.toFixed(1)}%`;
  document.getElementById('statCrowdVal').style.color = color;
  document.getElementById('statCrowdSub').textContent = prediction.recommendation || 'Live estimate';
  document.getElementById('statCrowdBar').style.width = `${pct}%`;
  document.getElementById('statCrowdBar').style.background = color;

  document.getElementById('statPeopleVal').textContent = prediction.current_count ?? '-';
  document.getElementById('statPeopleSub').textContent = `of ${prediction.capacity ?? '-'} capacity`;

  const levelEl = document.getElementById('statLevelVal');
  levelEl.textContent = level.replace('_', ' ');
  levelEl.className = `stat-value level-badge level-${level.replace(/\s+/g, '_')}`;
  document.getElementById('statLevelSub').textContent = `Confidence ${Math.round((prediction.confidence || 0) * 100)}%`;

  drawGauge(pct, color);
  document.getElementById('gaugePct').textContent = `${pct.toFixed(1)}%`;
  document.getElementById('gaugePct').style.color = color;
  document.getElementById('gaugeLabel').textContent = level.replace('_', ' ');
  document.getElementById('infoLocation').textContent = prediction.location_name || '-';
  document.getElementById('infoUpdated').textContent = new Date(prediction.predicted_at).toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  });
  document.getElementById('infoAdvice').textContent = prediction.bestTimeAdvice || prediction.recommendation || '-';
}

function updateMapSelection(location, pct) {
  const color = CROWD_COLOR(pct);
  if (state.markers.main) state.maps.main.removeLayer(state.markers.main);
  if (state.markers.circle) state.maps.main.removeLayer(state.markers.circle);

  state.markers.main = L.marker([location.lat, location.lng]).addTo(state.maps.main);
  state.markers.main.bindPopup(`<b>${escapeHtml(location.name)}</b><br>${pct.toFixed(1)}% predicted crowd`);
  state.markers.circle = L.circle([location.lat, location.lng], {
    radius: 500 + pct * 22,
    color,
    fillColor: color,
    fillOpacity: 0.25,
  }).addTo(state.maps.main);
  state.maps.main.flyTo([location.lat, location.lng], 14, { duration: 1.2 });
}

function updateHistoryChart(forecast) {
  const canvas = document.getElementById('historyChart');
  const empty = document.getElementById('historyEmpty');
  const locationBadge = document.getElementById('historyLocation');
  if (!forecast.length || !state.currentLocation) {
    canvas.style.display = 'none';
    empty.style.display = 'block';
    locationBadge.textContent = '-';
    return;
  }

  canvas.style.display = 'block';
  empty.style.display = 'none';
  locationBadge.textContent = state.currentLocation.name;

  if (state.charts.history) state.charts.history.destroy();
  state.charts.history = new Chart(canvas.getContext('2d'), {
    type: 'line',
    data: {
      labels: forecast.map(item => item.clock_label || formatHour(item.hour)),
      datasets: [{
        data: forecast.map(item => item.pct),
        borderColor: '#38bdf8',
        backgroundColor: 'rgba(56,189,248,0.18)',
        fill: true,
        tension: 0.35,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#6b7fa8', maxTicksLimit: 8 } },
        y: { min: 0, max: 100, ticks: { color: '#6b7fa8', callback: value => `${value}%` } },
      },
    },
  });
}

function initPredictForm() {
  document.getElementById('predictBtn').addEventListener('click', async () => {
    const placeName = document.getElementById('predictLocation').value.trim();
    const dateStr = document.getElementById('predictDate').value;
    const hour = Number(document.getElementById('predictHour').value);
    if (!placeName) {
      showToast('Enter a place name first', 'error');
      return;
    }
    if (!dateStr) {
      showToast('Choose a date first', 'error');
      return;
    }

    const targetDate = new Date(`${dateStr}T${String(hour).padStart(2, '0')}:00:00`);
    const button = document.getElementById('predictBtn');
    button.disabled = true;
    button.textContent = 'Predicting...';

    try {
      let prediction;
      if (state.predictLocation && state.predictLocation.name.toLowerCase() === placeName.toLowerCase()) {
        prediction = await fetchPredictionForCoords(state.predictLocation, targetDate);
      } else {
        prediction = await fetchPredictionByName(placeName, targetDate);
      }
      showPredictResult(prediction, dateStr);
    } catch {
      showToast('Prediction failed. Check backend or place spelling.', 'error');
    } finally {
      button.disabled = false;
      button.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg> Generate Prediction';
    }
  });
}

function showPredictResult(prediction, dateStr) {
  const pct = prediction.crowd_pct ?? 0;
  const color = CROWD_COLOR(pct);
  document.getElementById('predictResult').style.display = 'block';
  document.getElementById('resultPct').textContent = `${pct.toFixed(1)}%`;
  document.getElementById('resultPct').style.color = color;
  document.getElementById('resultLevel').textContent = (prediction.crowdLevel || CROWD_LABEL(pct)).replace('_', ' ');
  document.getElementById('resultLevel').className = `result-level level-${(prediction.crowdLevel || CROWD_LABEL(pct)).replace(/\s+/g, '_')}`;
  document.getElementById('resultAdvice').textContent = prediction.recommendation || '-';
  document.getElementById('bestTimeBox').textContent = prediction.bestTimeAdvice || '-';
  updatePredictChart(prediction.hourlyBreakdown || [], dateStr);
}

function updatePredictChart(hourly, dateStr) {
  const canvas = document.getElementById('predictChart');
  const empty = document.getElementById('predictEmpty');
  document.getElementById('predictChartDate').textContent = dateStr;

  if (!hourly.length) {
    canvas.style.display = 'none';
    empty.style.display = 'block';
    return;
  }

  canvas.style.display = 'block';
  empty.style.display = 'none';
  if (state.charts.predict) state.charts.predict.destroy();
  state.charts.predict = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels: hourly.map(item => item.label),
      datasets: [{
        data: hourly.map(item => item.crowdPct),
        backgroundColor: hourly.map(item => `${CROWD_COLOR(item.crowdPct)}cc`),
        borderRadius: 4,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#6b7fa8', maxTicksLimit: 8 } },
        y: { min: 0, max: 100, ticks: { color: '#6b7fa8', callback: value => `${value}%` } },
      },
    },
  });
}

function updateAnalytics(prediction) {
  const forecast = prediction.forecast_24h || [];
  document.getElementById('bestTimesLocation').textContent = prediction.location_name || '-';
  document.getElementById('peakEmpty').style.display = forecast.length ? 'none' : 'block';
  document.getElementById('weekEmpty').style.display = forecast.length ? 'none' : 'block';

  if (!forecast.length) return;

  const peakCanvas = document.getElementById('peakChart');
  if (state.charts.peak) state.charts.peak.destroy();
  state.charts.peak = new Chart(peakCanvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels: forecast.map(item => formatHour(item.hour)),
      datasets: [{ data: forecast.map(item => item.pct), backgroundColor: forecast.map(item => `${CROWD_COLOR(item.pct)}bb`) }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#6b7fa8', maxTicksLimit: 8 } },
        y: { min: 0, max: 100, ticks: { color: '#6b7fa8', callback: value => `${value}%` } },
      },
    },
  });

  const weekday = [];
  for (let day = 0; day < 7; day += 1) {
    const isWeekend = day >= 5;
    const avg = forecast.reduce((sum, item) => {
      const bias = isWeekend ? (prediction.place_type === 'transport' ? 1.03 : 1.14) : 0.97;
      return sum + Math.min(100, item.pct * bias);
    }, 0) / forecast.length;
    weekday.push(Number(avg.toFixed(1)));
  }

  const weekCanvas = document.getElementById('weekChart');
  if (state.charts.week) state.charts.week.destroy();
  state.charts.week = new Chart(weekCanvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
      datasets: [{ data: weekday, backgroundColor: weekday.map(value => `${CROWD_COLOR(value)}bb`) }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#6b7fa8' } },
        y: { min: 0, max: 100, ticks: { color: '#6b7fa8', callback: value => `${value}%` } },
      },
    },
  });

  const bestTimes = [...forecast].sort((a, b) => a.pct - b.pct).slice(0, 5);
  document.getElementById('bestTimesGrid').innerHTML = bestTimes.map(item => `
    <div class="time-slot best">
      <div class="time-slot-time">${formatHour(item.hour)}</div>
      <div class="time-slot-pct">${item.pct.toFixed(0)}% crowd</div>
    </div>
  `).join('');
}

async function loadHeatmap() {
  try {
    const [heatmapResponse, rawResponse] = await Promise.all([
      fetch(`${API_BASE}/predict/heatmap`, { headers: authHeaders() }),
      fetch(`${API_BASE}/location/heatmap-raw`, { headers: authHeaders() }),
    ]);
    const live = heatmapResponse.ok ? await heatmapResponse.json() : { locations: [] };
    const raw = rawResponse.ok ? await rawResponse.json() : { points: [] };
    state.lastHeatmap = live.locations || [];
    renderHeatmap(state.lastHeatmap, raw.points || []);
    renderLocationCards(state.lastHeatmap);
  } catch {
    renderLocationCards([]);
  }
}

function renderHeatmap(locations, points) {
  state.markers.heat.forEach(layer => state.maps.heat.removeLayer(layer));
  state.markers.heat = [];

  locations.forEach(item => {
    const color = CROWD_COLOR(item.crowd_pct);
    const radius = 900 + item.crowd_pct * 25;
    state.markers.heat.push(
      L.circle([item.lat, item.lng], {
        radius,
        color,
        fillColor: color,
        fillOpacity: 0.16,
      }).addTo(state.maps.heat)
    );
  });

  points.forEach(point => {
    const intensity = Math.min(100, point.count * 12);
    const color = CROWD_COLOR(intensity);
    state.markers.heat.push(
      L.circleMarker([point.lat, point.lng], {
        radius: Math.min(16, 4 + point.count),
        color,
        fillColor: color,
        fillOpacity: 0.28,
      }).addTo(state.maps.heat)
    );
  });
}

function renderLocationCards(locations) {
  const container = document.getElementById('locationCards');
  if (!locations.length) {
    container.innerHTML = '<div class="loc-card"><div class="loc-card-name">No live signals yet</div><div class="loc-card-type">Search a place and use check-in to start feeding real-time accuracy.</div></div>';
    return;
  }

  container.innerHTML = locations.slice(0, 8).map(item => `
    <div class="loc-card">
      <div class="loc-card-name">${escapeHtml(item.name)}</div>
      <div class="loc-card-pct" style="color:${CROWD_COLOR(item.crowd_pct)}">${item.crowd_pct.toFixed(1)}%</div>
      <div class="loc-card-bar"><div class="loc-card-fill" style="width:${item.crowd_pct}%;background:${CROWD_COLOR(item.crowd_pct)}"></div></div>
      <div class="loc-card-type">${escapeHtml(item.type)} live reference</div>
    </div>
  `).join('');
}

function connectWebSocket() {
  try {
    state.websocket = new WebSocket(WS_URL);
    state.websocket.onopen = () => updateWsStatus(true);
    state.websocket.onclose = () => updateWsStatus(false);
    state.websocket.onerror = () => updateWsStatus(false);
    state.websocket.onmessage = event => {
      const payload = JSON.parse(event.data);
      if (payload.locations) {
        state.lastHeatmap = payload.locations;
        renderHeatmap(state.lastHeatmap, []);
        renderLocationCards(state.lastHeatmap);
      }
    };
  } catch {
    updateWsStatus(false);
  }
}

function updateWsStatus(connected) {
  document.getElementById('wsStatus').className = `status-dot ${connected ? 'connected' : 'error'}`;
  document.getElementById('wsStatusText').textContent = connected ? 'Live connected' : 'Offline mode';
}

function initGps() {
  document.getElementById('gpsBtn').addEventListener('click', () => {
    if (!navigator.geolocation) {
      showToast('Geolocation is not available in this browser', 'error');
      return;
    }
    navigator.geolocation.getCurrentPosition(async position => {
      const location = {
        name: 'Current location',
        addr: 'Detected from GPS',
        lat: position.coords.latitude,
        lng: position.coords.longitude,
      };
      state.currentLocation = location;
      document.getElementById('searchInput').value = location.name;
      await activateLocation(location);
      await sendLocationPing(position.coords.latitude, position.coords.longitude, position.coords.accuracy);
    }, () => showToast('Unable to read your GPS location', 'error'));
  });
}

function initCheckIn() {
  document.getElementById('checkinBtn').addEventListener('click', async () => {
    if (!state.currentLocation) {
      showToast('Search a place first', 'error');
      return;
    }
    try {
      await sendLocationPing(state.currentLocation.lat, state.currentLocation.lng, null);
      document.getElementById('checkinSub').textContent = `Presence registered for ${state.auth.name}. Live model will learn from it.`;
      showToast('Presence registered');
      await refreshCurrentLocation();
    } catch {
      showToast('Check-in failed', 'error');
    }
  });
}

async function sendLocationPing(lat, lng, accuracy) {
  await fetch(`${API_BASE}/location/ping`, {
    method: 'POST',
    headers: {
      ...authHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      lat,
      lng,
      accuracy_m: accuracy,
      session_id: `${state.sessionId}-${(state.auth?.email || 'guest').replace(/[^a-z0-9]/gi, '')}`,
      timestamp: new Date().toISOString(),
    }),
  });
}

function fillHourSelect() {
  const select = document.getElementById('predictHour');
  select.innerHTML = Array.from({ length: 24 }, (_, hour) =>
    `<option value="${hour}">${formatHour(hour)}</option>`
  ).join('');
  const dateInput = document.getElementById('predictDate');
  dateInput.value = new Date().toISOString().slice(0, 10);
  select.value = String(new Date().getHours());
}

function initSidebarToggle() {
  document.getElementById('sidebarToggle').addEventListener('click', () => {
    if (window.innerWidth <= 780) {
      document.getElementById('sidebar').classList.toggle('open');
      return;
    }

    document.getElementById('appShell').classList.toggle('sidebar-collapsed');
  });
  document.getElementById('refreshHeatmap').addEventListener('click', loadHeatmap);
}

function drawGauge(pct, color) {
  const canvas = document.getElementById('gaugeCanvas');
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;
  const cx = width / 2;
  const cy = height / 2;
  const radius = 84;

  ctx.clearRect(0, 0, width, height);
  ctx.lineWidth = 16;
  ctx.strokeStyle = 'rgba(99,120,200,0.15)';
  ctx.beginPath();
  ctx.arc(cx, cy, radius, Math.PI * 0.75, Math.PI * 2.25);
  ctx.stroke();

  ctx.strokeStyle = color;
  ctx.beginPath();
  ctx.arc(cx, cy, radius, Math.PI * 0.75, Math.PI * (0.75 + 1.5 * pct / 100));
  ctx.stroke();
}

function showToast(message, type = 'info') {
  const el = document.getElementById('toast');
  el.textContent = message;
  el.style.borderColor = type === 'error' ? 'rgba(239,68,68,0.4)' : 'rgba(99,120,200,0.18)';
  el.classList.add('show');
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => el.classList.remove('show'), 3200);
}

function initials(name) {
  return String(name || 'CP')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0].toUpperCase())
    .join('');
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatHour(hour) {
  const suffix = hour < 12 ? 'AM' : 'PM';
  const display = hour % 12 || 12;
  return `${display}:00 ${suffix}`;
}

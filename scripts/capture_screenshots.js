const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const OUT_DIR = path.resolve(__dirname, '../docs/screenshots');
const BASE_URL = 'http://localhost:8765';

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function captureMissionControl(browser) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`${BASE_URL}/console_source.html`);
  await sleep(2000);
  
  // Start auto demo
  await page.click('#demo-btn');
  await sleep(1000);
  
  // Wait until mid-run (after packet loss ~40 ticks, contention ~80, dropout ~120)
  // At speed 2, that's about 60 ticks per second real-time? No, TICK_MS=700, speed=2 means 2 steps per tick, so ~2.8 steps/sec
  // Wait ~45 seconds for mid-run state with packet loss active and some drones searching
  await sleep(45000);
  
  await page.screenshot({ path: path.join(OUT_DIR, 'mission-control.png'), fullPage: false });
  console.log('Captured mission-control.png');
  
  // Wait for survivor found (auto demo survivorAt=160 ticks)
  // Already waited 45s, need a bit more. But let's check the state.
  const footerText = await page.$eval('#footer-msg', el => el.textContent);
  console.log('Footer at mission-control:', footerText);
  
  // If survivor not found yet, wait more
  let attempts = 0;
  while (attempts < 60) {
    const ft = await page.$eval('#footer-msg', el => el.textContent);
    if (ft.includes('Survivor detected') || ft.includes('survivor')) {
      break;
    }
    await sleep(1000);
    attempts++;
  }
  
  await page.screenshot({ path: path.join(OUT_DIR, 'survivor-found.png'), fullPage: false });
  console.log('Captured survivor-found.png');
  await page.close();
}

async function captureLiveDashboard(browser) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`${BASE_URL}/live.html`);
  await sleep(1500);
  
  // Inject mock data to show a populated dashboard
  const mockPayload = {
    grid: Array.from({length: 10}, (_, y) =>
      Array.from({length: 10}, (_, x) => ({
        x, y,
        certainty: Math.random() > 0.3 ? 0.5 + Math.random() * 0.4 : 0.5,
        owner: Math.random() > 0.7 ? Math.floor(Math.random() * 5) : null
      }))
    ),
    summary: {
      drones: [
        { id: 'drone_1', position: [2, 3], target: [4, 5], status: 'searching', alive: true, reachable: true, searched_cells: 12, battery: 87, role: 'scout', subzone: 'A1' },
        { id: 'drone_2', position: [7, 1], target: [7, 2], status: 'transiting', alive: true, reachable: true, searched_cells: 8, battery: 62, role: 'scout', subzone: 'A2' },
        { id: 'drone_3', position: [1, 8], target: [2, 8], status: 'claiming', alive: true, reachable: true, searched_cells: 15, battery: 45, role: 'scout', subzone: 'B1' },
        { id: 'drone_4', position: [5, 5], target: [5, 5], status: 'searching', alive: true, reachable: true, searched_cells: 9, battery: 91, role: 'scout', subzone: 'B2' },
        { id: 'drone_5', position: [9, 9], target: [8, 8], status: 'idle', alive: false, reachable: false, searched_cells: 3, battery: 0, role: 'scout', subzone: 'C1' },
      ],
      target: [7, 3],
      auctions: 8,
      dropouts: 1,
      consensus_rounds: 12,
      mesh_messages: 156,
      survivor_receipts: 1,
      failures: [
        { drone_id: 'drone_5', failure_type: 'failure', t: 45, recovered: false }
      ],
      consensus: [
        { round_id: 12, cell: [5, 5], vote_count: 4, status: 'resolved' },
        { round_id: 11, cell: [3, 2], vote_count: 3, status: 'resolved' },
        { round_id: 10, cell: [7, 1], vote_count: 4, status: 'resolved' },
      ]
    },
    stats: {
      coverage: 0.42,
      average_entropy: 0.68,
      auctions: 8,
      dropouts: 1,
      duration_elapsed: 128,
      consensus_rounds: 12,
      mesh_messages: 156,
      survivor_receipts: 1,
      survivor_found: true
    },
    mesh: {
      transport: 'local',
      peers: [
        { peer_id: 'drone_1', stale: false, last_seen_ms: 120 },
        { peer_id: 'drone_2', stale: false, last_seen_ms: 340 },
        { peer_id: 'drone_3', stale: false, last_seen_ms: 180 },
        { peer_id: 'drone_4', stale: false, last_seen_ms: 90 },
        { peer_id: 'drone_5', stale: true, last_seen_ms: 45000 },
      ],
      messages: 156
    },
    system: {
      tick_seconds: 1,
      tick_delay_seconds: 0.5,
      requested_drone_count: 5,
      target: [7, 3]
    },
    events: [
      { type: 'survivor_found', message: 'Survivor confirmed at [7,3] by drone_4', t: 128 },
      { type: 'bft', message: 'Auction at [5,5] winner: drone_4', t: 95 },
      { type: 'failure', message: 'drone_5 heartbeat timeout', t: 45 },
      { type: 'bft', message: 'Auction at [3,2] winner: drone_1', t: 38 },
      { type: 'mesh', message: 'Peer drone_2 joined mesh', t: 12 },
    ]
  };
  
  await page.evaluate((payload) => {
    renderPayload(payload);
    setStatus('live', 'Live');
  }, mockPayload);
  
  await sleep(1000);
  await page.screenshot({ path: path.join(OUT_DIR, 'live-dashboard.png'), fullPage: true });
  console.log('Captured live-dashboard.png');
  await page.close();
}

async function captureTUI(browser) {
  const page = await browser.newPage({ viewport: { width: 1000, height: 700 } });
  await page.goto(`${BASE_URL}/tui_preview.html`);
  await sleep(1500);
  await page.screenshot({ path: path.join(OUT_DIR, 'tui.png'), fullPage: true });
  console.log('Captured tui.png');
  await page.close();
}

(async () => {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  
  try {
    await captureMissionControl(browser);
  } catch (e) {
    console.error('mission-control failed:', e.message);
  }
  
  try {
    await captureLiveDashboard(browser);
  } catch (e) {
    console.error('live-dashboard failed:', e.message);
  }
  
  try {
    await captureTUI(browser);
  } catch (e) {
    console.error('tui failed:', e.message);
  }
  
  await browser.close();
  console.log('All captures done');
})();

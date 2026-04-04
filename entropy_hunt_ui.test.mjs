import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

function extractScript(htmlPath) {
  const html = fs.readFileSync(htmlPath, "utf8");
  const match = html.match(/<script>([\s\S]*?)<\/script>/);
  assert.ok(match, `inline script missing in ${htmlPath}`);
  return match[1];
}

function createMath(randomValues = []) {
  const math = Object.create(Math);
  let idx = 0;
  math.random = () => (idx < randomValues.length ? randomValues[idx++] : 0.5);
  math.__setRandom = (values) => {
    idx = 0;
    randomValues = [...values];
  };
  return math;
}

function createSandbox(randomValues = []) {
  const intervals = [];
  const elements = new Map();
  const math = createMath(randomValues);

  const ctx = {
    fillStyle: "",
    strokeStyle: "",
    lineWidth: 0,
    beginPath() {},
    moveTo() {},
    lineTo() {},
    stroke() {},
    fill() {},
    arc() {},
    fillRect() {},
    strokeRect() {},
    clearRect() {},
    setLineDash() {},
  };

  function makeElement(id) {
    const classes = new Set();
    const el = {
      id,
      style: {},
      innerHTML: "",
      textContent: "",
      value: "2",
      width: 240,
      height: 240,
      getContext: () => ctx,
      addEventListener() {},
      getBoundingClientRect: () => ({ left: 0, top: 0 }),
      classList: {
        add(name) {
          classes.add(name);
        },
        remove(name) {
          classes.delete(name);
        },
        toggle(name, force) {
          if (typeof force === "boolean") {
            if (force) classes.add(name);
            else classes.delete(name);
            return force;
          }
          if (classes.has(name)) {
            classes.delete(name);
            return false;
          }
          classes.add(name);
          return true;
        },
        contains(name) {
          return classes.has(name);
        },
      },
    };
    elements.set(id, el);
    return el;
  }

  const document = {
    documentElement: {},
    getElementById(id) {
      return elements.get(id) || makeElement(id);
    },
  };

  const sandbox = {
    console,
    Math: math,
    document,
    getComputedStyle() {
      return {
        getPropertyValue() {
          return "";
        },
      };
    },
    setInterval(fn, ms) {
      intervals.push({ fn, ms });
      return intervals.length;
    },
    clearInterval() {},
    window: null,
  };

  sandbox.window = sandbox;
  sandbox.__intervals = intervals;
  return sandbox;
}

function loadSimulation(htmlPath, exportExpr, randomValues = []) {
  const sandbox = createSandbox(randomValues);
  const source = `${extractScript(htmlPath)}\n;globalThis.__testExports = ${exportExpr};`;
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox, { filename: htmlPath });
  return { sandbox, exports: sandbox.__testExports };
}

test("v2 entropy helper matches Shannon expectations", () => {
  const { exports } = loadSimulation("entropy_hunt_v2.html", `({ H })`);
  assert.equal(exports.H(0), 0);
  assert.equal(exports.H(1), 0);
  assert.ok(Math.abs(exports.H(0.5) - 1) < 1e-9);
});

test("v2 maxEntropyCell chooses the best eligible cell", () => {
  const { exports } = loadSimulation(
    "entropy_hunt_v2.html",
    `({ maxEntropyCell, get grid(){return grid;} })`,
  );
  for (const row of exports.grid) {
    for (const cell of row) {
      cell.c = 1;
      cell.owner = -1;
    }
  }

  exports.grid[4][4].c = 0.5; // best but claimed
  exports.grid[2][7].c = 0.5; // best but excluded
  exports.grid[6][1].c = 0.4; // best eligible fallback
  exports.grid[4][4].owner = 3;

  const best = exports.maxEntropyCell([[7, 2]]);
  assert.deepEqual([...best], [1, 6]);
});

test("v2 contested auction prefers the nearer drone deterministically", () => {
  const { exports } = loadSimulation(
    "entropy_hunt_v2.html",
    `({ assignTargets, get grid(){return grid;}, get drones(){return drones;}, get auctions(){return auctions;}, get events(){return events;} })`,
  );
  for (const row of exports.grid) {
    for (const cell of row) {
      cell.c = 1;
      cell.owner = -1;
    }
  }
  exports.grid[5][5].c = 0.5;

  exports.drones.forEach((d, i) => {
    d.stale = true;
    d.status = "idle";
    d.x = i;
    d.y = i;
    d.tx = i;
    d.ty = i;
  });

  const incumbent = exports.drones[0];
  incumbent.stale = false;
  incumbent.x = 5;
  incumbent.y = 3;
  incumbent.tx = 5;
  incumbent.ty = 5;
  incumbent.status = "transit";

  const challenger = exports.drones[1];
  challenger.stale = false;
  challenger.x = 5;
  challenger.y = 4;
  challenger.tx = 1;
  challenger.ty = 1;
  challenger.status = "idle";

  exports.assignTargets();

  assert.equal(exports.auctions, 1);
  assert.equal(challenger.tx, 5);
  assert.equal(challenger.ty, 5);
  assert.match(exports.events[0].msg, /winner: drone_2/i);
});

test("v2 reviveAll re-randomizes x and y independently", () => {
  const { sandbox, exports } = loadSimulation(
    "entropy_hunt_v2.html",
    `({ reviveAll, get drones(){return drones;} })`,
  );
  const drone = exports.drones[0];
  drone.stale = true;

  sandbox.Math.__setRandom([0.1, 0.8]);
  exports.reviveAll();

  assert.equal(drone.x, 1);
  assert.equal(drone.y, 8);
});

test("v2 replay payload imports simulation output into the console state", () => {
  const { exports } = loadSimulation(
    "entropy_hunt_v2.html",
    `({
      applyReplayPayload,
      get sourceMode(){return sourceMode;},
      get elapsed(){return elapsed;},
      get bftRounds(){return bftRounds;},
      get dropouts(){return dropouts;},
      get found(){return found;},
      get missionComplete(){return missionComplete;},
      get events(){return events;},
      get drones(){return drones;},
      get grid(){return grid;}
    })`,
  );

  const payload = {
    summary: {
      duration_elapsed: 180,
      bft_rounds: 63,
      auctions: 13,
      dropouts: 1,
      survivor_found: true,
      drones: [
        { id: "drone_1", alive: true, position: [2, 5], target: [2, 5], status: "searching", searched_cells: 163 },
        { id: "drone_2", alive: false, position: [6, 1], target: null, status: "stale", searched_cells: 53 },
      ],
    },
    events: [{ t: 60, type: "survivor", message: "survivor found by drone_1" }],
    grid: Array.from({ length: 10 }, (_, y) =>
      Array.from({ length: 10 }, (_, x) => ({
        x,
        y,
        certainty: x === 2 && y === 5 ? 0.98 : 0.5,
      })),
    ),
  };

  exports.applyReplayPayload(payload);

  assert.equal(exports.sourceMode, "replay");
  assert.equal(exports.elapsed, 180);
  assert.equal(exports.bftRounds, 63);
  assert.equal(exports.dropouts, 1);
  assert.equal(exports.found, true);
  assert.equal(exports.missionComplete, true);
  assert.equal(exports.drones[0].x, 2);
  assert.equal(exports.drones[0].y, 5);
  assert.equal(exports.drones[1].stale, true);
  assert.equal(exports.grid[5][2].certainty, 0.98);
  assert.match(exports.events[0].msg, /survivor found/i);
});

test("mockup reconnect path re-randomizes x and y independently", () => {
  const { sandbox, exports } = loadSimulation(
    "entropy_hunt_mockup.html",
    `({ get drones(){return drones;}, get elapsed(){return elapsed;}, set elapsed(v){ elapsed = v; } })`,
  );

  assert.equal(sandbox.__intervals.length, 1);
  exports.elapsed = 14;

  sandbox.Math.__setRandom([0.1, 0.2, 0.7, 0.3]);
  sandbox.__intervals[0].fn();

  const drone = exports.drones[1];
  assert.equal(drone.x, 7);
  assert.equal(drone.y, 3);
});

test("mockup replay payload imports final map snapshots", () => {
  const { exports } = loadSimulation(
    "entropy_hunt_mockup.html",
    `({
      applyReplayPayload,
      get replayMode(){return replayMode;},
      get drones(){return drones;},
      get events(){return events;},
      get grid(){return grid;},
      get elapsed(){return elapsed;},
      get bftRound(){return bftRound;}
    })`,
  );

  const payload = {
    summary: {
      duration_elapsed: 30,
      bft_rounds: 14,
      auctions: 2,
      drones: [
        { alive: true, position: [1, 1], target: [1, 1], status: "searching", searched_cells: 28 },
        { alive: false, position: [1, 2], target: null, status: "stale", searched_cells: 10 },
      ],
    },
    events: [{ t: 12, type: "stale", message: "drone_2 heartbeat timeout" }],
    grid: Array.from({ length: 10 }, (_, y) =>
      Array.from({ length: 10 }, (_, x) => ({
        x,
        y,
        certainty: x === 1 && y === 1 ? 0.95 : 0.5,
      })),
    ),
  };

  exports.applyReplayPayload(payload);

  assert.equal(exports.replayMode, true);
  assert.equal(exports.elapsed, 30);
  assert.equal(exports.bftRound, 14);
  assert.equal(exports.drones[0].x, 1);
  assert.equal(exports.drones[1].status, "stale");
  assert.equal(exports.grid[1][1], 0.95);
  assert.match(exports.events[0].msg, /heartbeat timeout/i);
});

test("v2 auto demo drives staged packet loss, contention, dropout, and survivor milestones", () => {
  const { exports } = loadSimulation(
    "entropy_hunt_v2.html",
    `({
      toggleAutoDemo,
      tick,
      setSpeed,
      get autoDemo(){return autoDemo;},
      get packetDrop(){return packetDrop;},
      get elapsed(){return elapsed;},
      set elapsed(v){ elapsed = v; },
      get drones(){return drones;},
      get events(){return events;},
      get found(){return found;},
      get missionComplete(){return missionComplete;},
      get bftRounds(){return bftRounds;}
    })`,
  );

  exports.setSpeed(1);
  exports.toggleAutoDemo(true);

  exports.elapsed = 39;
  exports.tick();
  assert.equal(exports.packetDrop, true);
  assert.equal(exports.autoDemo.packetLoss, true);
  assert.match(exports.events[0].msg, /packet-loss stage/i);

  exports.elapsed = 79;
  exports.tick();
  assert.equal(exports.autoDemo.contention, true);
  assert.ok(exports.bftRounds >= 1);
  assert.ok(
    exports.events.some((event) => /staged contention/i.test(event.msg)),
  );
  assert.ok(exports.events.some((event) => event.type === "bft"));

  exports.elapsed = 119;
  exports.tick();
  assert.equal(exports.autoDemo.dropout, true);
  assert.equal(
    exports.drones.find((drone) => drone.id === "drone_2").stale,
    true,
  );

  exports.elapsed = 159;
  exports.tick();
  assert.equal(exports.autoDemo.survivor, true);
  assert.equal(exports.found, true);
  assert.equal(exports.missionComplete, true);
  assert.ok(
    exports.events.some((event) =>
      /survivor confirmation run/i.test(event.msg),
    ),
  );
  assert.ok(exports.events.some((event) => /SURVIVOR EVENT/i.test(event.msg)));
});

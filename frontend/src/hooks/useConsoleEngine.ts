import { useCallback, useEffect, useRef, useState } from 'react'
import type {
  AutoDemoState,
  Cell,
  Drone,
  LogEvent,
  SnapshotDrone,
  SnapshotPayload,
  SnapshotSummary,
  SourceMode,
  SyntheticBaseline,
  ToastState,
} from '@/types/console'

const GRID_SIZE = 10
const SEARCH_INCREMENT = 0.12
const SEARCH_COMPLETE = 0.92
const DECAY_RATE = 0.001
const TICK_MS = 700
const NAMES = ['drone_1', 'drone_2', 'drone_3', 'drone_4', 'drone_5']
const COLORS = ['#378ADD', '#1D9E75', '#BA7517', '#D85A30', '#D4537E']
const START_POSITIONS: [number, number][] = [
  [0, 0],
  [GRID_SIZE - 1, 0],
  [0, GRID_SIZE - 1],
  [GRID_SIZE - 1, GRID_SIZE - 1],
  [Math.floor(GRID_SIZE / 2), Math.floor(GRID_SIZE / 2)],
]
const DEMO_CONTENTION_CELL = { x: 5, y: 5 }
const DEMO_TIMELINE = {
  packetLossAt: 40,
  contentionAt: 80,
  dropoutAt: 120,
  survivorAt: 160,
}

function entropyValue(certainty: number): number {
  if (certainty <= 0 || certainty >= 1) return 0
  return -(certainty * Math.log2(certainty) + (1 - certainty) * Math.log2(1 - certainty))
}

function cellKey(x: number, y: number): string {
  return `${x},${y}`
}

function distanceTo(drone: Drone, x: number, y: number): number {
  return Math.hypot(x - drone.x, y - drone.y)
}

function compareCandidates(
  a: { entropy: number; distance: number; y: number; x: number },
  b: { entropy: number; distance: number; y: number; x: number },
): number {
  return b.entropy - a.entropy || a.distance - b.distance || a.y - b.y || a.x - b.x
}

function compareClaimants(
  left: { drone: Drone },
  right: { drone: Drone },
  x: number,
  y: number,
): number {
  const distanceDelta = distanceTo(left.drone, x, y) - distanceTo(right.drone, x, y)
  if (Math.abs(distanceDelta) > 1e-9) {
    return distanceDelta
  }
  return left.drone.id.localeCompare(right.drone.id)
}

function mapBackendStatus(rawStatus: string | undefined | null): string {
  return (
    {
      transiting: 'transit',
      claiming: 'transit',
      claim_won: 'searching',
      claim_lost: 'transit',
      stale: 'offline',
    } as Record<string, string>
  )[rawStatus ?? ''] || rawStatus || 'idle'
}

function mapReplayEventType(type: string): LogEvent['type'] {
  return (
    {
      auction: 'bft',
      bft: 'bft',
      failure: 'err',
      stale: 'err',
      heartbeat_timeout: 'err',
      zone_release: 'warn',
      zone_priority_reclaim: 'ok',
      survivor: 'ok',
      survivor_found: 'ok',
      survivor_ack: 'ok',
      zone_complete: 'ok',
      claim: 'info',
      mesh: 'info',
      map: 'info',
    } as Record<string, LogEvent['type']>
  )[type] || 'info'
}

function formatReplayEvent(event: { type?: string; message?: string; t?: number }): LogEvent {
  return {
    type: mapReplayEventType(event.type ?? ''),
    msg: event.message || event.type || 'replay event',
    t: event.t ?? 0,
  }
}

function makeInitialGrid(): Cell[][] {
  return Array.from({ length: GRID_SIZE }, (_, y) =>
    Array.from({ length: GRID_SIZE }, (_, x) => ({
      x,
      y,
      certainty: 0.5,
      owner: -1,
      ownerId: null,
    })),
  )
}

function makeInitialDrones(): Drone[] {
  return NAMES.map((id, index) => {
    const [x, y] = START_POSITIONS[index]
    return {
      id,
      color: COLORS[index],
      x,
      y,
      tx: null,
      ty: null,
      stale: false,
      status: 'idle',
      cells: 0,
    }
  })
}

export function useConsoleEngine() {
  const [grid, setGrid] = useState<Cell[][]>(makeInitialGrid)
  const [drones, setDrones] = useState<Drone[]>(makeInitialDrones)
  const [elapsed, setElapsed] = useState(0)
  const [bftRounds, setBftRounds] = useState(0)
  const [auctions, setAuctions] = useState(0)
  const [dropouts, setDropouts] = useState(0)
  const [found, setFound] = useState(false)
  const [missionComplete, setMissionComplete] = useState(false)
  const [events, setEvents] = useState<LogEvent[]>([])
  const [sourceMode, setSourceMode] = useState<SourceMode>('synthetic')
  const [speed, setSpeedState] = useState(2)
  const [packetDrop, setPacketDropState] = useState(false)
  const [target, setTarget] = useState<{ x: number; y: number }>({ x: 7, y: 3 })
  const [autoDemo, setAutoDemo] = useState<AutoDemoState>({
    enabled: false,
    packetLoss: false,
    contention: false,
    dropout: false,
    survivor: false,
  })
  const [toast, setToast] = useState<ToastState>({
    type: 'info',
    message: '',
    visible: false,
  })
  const [footerMsg, setFooterMsg] = useState('Initialising vertex P2P mesh')
  const [loading, setLoading] = useState(false)
  const [liveUrl, setLiveUrl] = useState('http://127.0.0.1:8765/snapshot.json')

  const livePollHandle = useRef<ReturnType<typeof setInterval> | null>(null)
  const syntheticBaseline = useRef<SyntheticBaseline | null>(null)

  const speedRef = useRef(speed)
  const packetDropRef = useRef(packetDrop)
  const sourceModeRef = useRef(sourceMode)
  const missionCompleteRef = useRef(missionComplete)
  const autoDemoRef = useRef(autoDemo)
  const gridRef = useRef(grid)
  const dronesRef = useRef(drones)
  const elapsedRef = useRef(elapsed)
  const bftRoundsRef = useRef(bftRounds)
  const auctionsRef = useRef(auctions)
  const dropoutsRef = useRef(dropouts)
  const foundRef = useRef(found)
  const eventsRef = useRef(events)
  const targetRef = useRef(target)

  useEffect(() => { speedRef.current = speed }, [speed])
  useEffect(() => { packetDropRef.current = packetDrop }, [packetDrop])
  useEffect(() => { sourceModeRef.current = sourceMode }, [sourceMode])
  useEffect(() => { missionCompleteRef.current = missionComplete }, [missionComplete])
  useEffect(() => { autoDemoRef.current = autoDemo }, [autoDemo])
  useEffect(() => { gridRef.current = grid }, [grid])
  useEffect(() => { dronesRef.current = drones }, [drones])
  useEffect(() => { elapsedRef.current = elapsed }, [elapsed])
  useEffect(() => { bftRoundsRef.current = bftRounds }, [bftRounds])
  useEffect(() => { auctionsRef.current = auctions }, [auctions])
  useEffect(() => { dropoutsRef.current = dropouts }, [dropouts])
  useEffect(() => { foundRef.current = found }, [found])
  useEffect(() => { eventsRef.current = events }, [events])
  useEffect(() => { targetRef.current = target }, [target])

  const addEvent = useCallback((type: LogEvent['type'], msg: string) => {
    const newEvent: LogEvent = { type, msg, t: elapsedRef.current }
    setEvents((prev) => {
      const next = [newEvent, ...prev]
      if (next.length > 24) next.pop()
      return next
    })
  }, [])

  const showToast = useCallback((type: ToastState['type'], message: string) => {
    setToast({ type, message, visible: true })
    setTimeout(() => {
      setToast((prev) => ({ ...prev, visible: false }))
    }, 3000)
  }, [])

  const getCell = useCallback((x: number, y: number): Cell => {
    return gridRef.current[y][x]
  }, [])

  const setCell = useCallback((x: number, y: number, patch: Partial<Cell>) => {
    setGrid((prev) => {
      const next = prev.map((row) => row.map((c) => ({ ...c })))
      next[y][x] = { ...next[y][x], ...patch }
      return next
    })
  }, [])

  const setDrone = useCallback((index: number, patch: Partial<Drone>) => {
    setDrones((prev) => {
      const next = [...prev]
      next[index] = { ...next[index], ...patch }
      return next
    })
  }, [])

  const releaseClaim = useCallback((index: number) => {
    setGrid((prev) =>
      prev.map((row) =>
        row.map((cell) =>
          cell.owner === index ? { ...cell, owner: -1, ownerId: null } : cell,
        ),
      ),
    )
  }, [])

  const buildCandidates = useCallback(
    (drone: Drone, reserved: Set<string>) => {
      const candidates: { x: number; y: number; entropy: number; distance: number }[] = []
      for (let y = 0; y < GRID_SIZE; y += 1) {
        for (let x = 0; x < GRID_SIZE; x += 1) {
          const key = cellKey(x, y)
          const cell = getCell(x, y)
          if (reserved.has(key) || cell.owner >= 0) continue
          candidates.push({
            x,
            y,
            entropy: entropyValue(cell.certainty),
            distance: distanceTo(drone, x, y),
          })
        }
      }
      return candidates.sort(compareCandidates)
    },
    [getCell],
  )

  const grantClaim = useCallback(
    (index: number, candidate: { x: number; y: number }) => {
      const drone = dronesRef.current[index]
      setGrid((prev) => {
        const next = prev.map((row) => row.map((c) => ({ ...c })))
        next[candidate.y][candidate.x] = {
          ...next[candidate.y][candidate.x],
          owner: index,
          ownerId: drone.id,
        }
        return next
      })
      setDrone(index, {
        tx: candidate.x,
        ty: candidate.y,
        status:
          drone.x === candidate.x && drone.y === candidate.y ? 'searching' : 'transit',
      })
    },
    [getCell, setDrone],
  )

  const reassignIdleDrones = useCallback(() => {
    const reserved = new Set<string>()

    dronesRef.current.forEach((drone, index) => {
      if (drone.stale || drone.tx == null || drone.ty == null) return
      if (drone.status === 'transit' || drone.status === 'searching') {
        reserved.add(cellKey(drone.tx, drone.ty))
        setCell(drone.tx, drone.ty, { owner: index, ownerId: drone.id })
      }
    })

    let pending = dronesRef.current
      .map((drone, index) => ({
        index,
        drone,
        candidates: buildCandidates(drone, reserved),
      }))
      .filter(({ drone }) => !drone.stale && drone.status === 'idle')

    while (pending.length) {
      const proposals = new Map<string, { index: number; drone: Drone; candidate: { x: number; y: number }; candidates: { x: number; y: number; entropy: number; distance: number }[] }[]>()
      const nextPending: typeof pending = []

      pending.forEach((entry) => {
        while (
          entry.candidates.length &&
          reserved.has(cellKey(entry.candidates[0].x, entry.candidates[0].y))
        ) {
          entry.candidates.shift()
        }
        const candidate = entry.candidates.shift()
        if (!candidate) {
          setDrone(entry.index, { tx: null, ty: null, status: 'idle' })
          return
        }
        const key = cellKey(candidate.x, candidate.y)
        const group = proposals.get(key) || []
        group.push({ ...entry, candidate })
        proposals.set(key, group)
      })

      proposals.forEach((group, key) => {
        if (group.length === 1) {
          const { index, candidate } = group[0]
          grantClaim(index, candidate)
          reserved.add(key)
          return
        }

        setBftRounds((prev) => prev + 1)
        setAuctions((prev) => prev + 1)
        group.sort((left, right) =>
          compareClaimants(left, right, group[0].candidate.x, group[0].candidate.y),
        )
        const [winner, ...losers] = group
        addEvent(
          'bft',
          `Auction resolved at [${winner.candidate.x},${winner.candidate.y}] - ${group.map(({ drone }) => drone.id).join(' vs ')} -> ${winner.drone.id}`,
        )
        grantClaim(winner.index, winner.candidate)
        reserved.add(key)
        losers.forEach(({ index, drone, candidates }) => {
          nextPending.push({ index, drone, candidates })
        })
      })

      pending = nextPending
    }
  }, [addEvent, buildCandidates, grantClaim, releaseClaim, setCell, setDrone])

  const handleSearch = useCallback(
    (drone: Drone, index: number) => {
      const cell = getCell(drone.x, drone.y)
      const wasComplete = cell.certainty >= SEARCH_COMPLETE
      setCell(drone.x, drone.y, { owner: index, ownerId: drone.id })
      const newCertainty = Math.min(0.98, cell.certainty + SEARCH_INCREMENT)
      setCell(drone.x, drone.y, { certainty: newCertainty })

      if (!wasComplete && newCertainty >= SEARCH_COMPLETE) {
        setDrone(index, { cells: drone.cells + 1, status: 'idle', tx: null, ty: null })
        setCell(drone.x, drone.y, { owner: -1, ownerId: null })

        if (!foundRef.current && drone.x === targetRef.current.x && drone.y === targetRef.current.y) {
          setFound(true)
          setMissionComplete(true)
          addEvent(
            'ok',
            `SURVIVOR EVENT at [${targetRef.current.x},${targetRef.current.y}] - demo mesh notification raised`,
          )
          setFooterMsg('Survivor detected - demo run complete')
        }
      }
    },
    [addEvent, getCell, setCell, setDrone],
  )

  const stepDrones = useCallback(() => {
    dronesRef.current.forEach((drone, index) => {
      if (drone.stale) return
      if (packetDropRef.current && Math.random() < 0.2) return

      if (drone.status === 'transit' && drone.tx != null && drone.ty != null) {
        let newX = drone.x
        let newY = drone.y
        if (drone.x !== drone.tx) {
          newX += drone.x < drone.tx ? 1 : -1
        } else if (drone.y !== drone.ty) {
          newY += drone.y < drone.ty ? 1 : -1
        }
        setDrone(index, { x: newX, y: newY })
        if (newX === drone.tx && newY === drone.ty) {
          setDrone(index, { status: 'searching' })
        }
      }

      if (
        drone.status === 'searching' &&
        drone.tx != null &&
        drone.ty != null &&
        drone.x === drone.tx &&
        drone.y === drone.ty
      ) {
        handleSearch(drone, index)
      }
    })
  }, [handleSearch, setDrone])

  const decayGrid = useCallback(() => {
    setGrid((prev) =>
      prev.map((row) =>
        row.map((cell) =>
          cell.owner < 0
            ? { ...cell, certainty: cell.certainty + DECAY_RATE * (0.5 - cell.certainty) }
            : cell,
        ),
      ),
    )
  }, [])

  const coverage = useCallback((): number => {
    let searched = 0
    gridRef.current.forEach((row) => {
      row.forEach((cell) => {
        if (cell.certainty >= SEARCH_COMPLETE) searched += 1
      })
    })
    return Math.round((searched / (GRID_SIZE * GRID_SIZE)) * 100)
  }, [])

  const averageEntropy = useCallback((): string => {
    let total = 0
    gridRef.current.forEach((row) => {
      row.forEach((cell) => {
        total += entropyValue(cell.certainty)
      })
    })
    return (total / (GRID_SIZE * GRID_SIZE)).toFixed(2)
  }, [])

  const getAliveDrone = useCallback((droneId: string): Drone | null => {
    const drone = dronesRef.current.find((d) => d.id === droneId)
    return drone && !drone.stale ? drone : null
  }, [])

  const nearestAliveDroneTo = useCallback(
    (x: number, y: number, excludeIds: string[] = []): Drone | null => {
      const alive = dronesRef.current
        .filter((drone) => !drone.stale && !excludeIds.includes(drone.id))
        .sort((left, right) => {
          const distanceDelta = distanceTo(left, x, y) - distanceTo(right, x, y)
          if (Math.abs(distanceDelta) > 1e-9) return distanceDelta
          return left.id.localeCompare(right.id)
        })
      return alive[0] || null
    },
    [],
  )

  const respawnDrone = useCallback((index: number, randomize = false) => {
    const [startX, startY] = START_POSITIONS[index]
    setDrone(index, {
      x: randomize ? Math.floor(Math.random() * GRID_SIZE) : startX,
      y: randomize ? Math.floor(Math.random() * GRID_SIZE) : startY,
      tx: null,
      ty: null,
      status: 'idle',
      stale: false,
    })
  }, [setDrone])

  const killDrone = useCallback(
    (droneId: string) => {
      if (sourceModeRef.current !== 'synthetic') return
      const index = dronesRef.current.findIndex((d) => d.id === droneId)
      if (index < 0) return
      const drone = dronesRef.current[index]
      if (drone.stale) return
      releaseClaim(index)
      setDrone(index, { stale: true, tx: null, ty: null, status: 'offline' })
      setDropouts((prev) => prev + 1)
      addEvent(
        'err',
        `${drone.id} heartbeat timeout - zone released back into the demo pool`,
      )
      setFooterMsg(
        `${drone.id} dropped - claim released and peers retargeting the highest-entropy zone`,
      )
    },
    [addEvent, releaseClaim, setDrone],
  )

  const killRandom = useCallback(() => {
    if (sourceModeRef.current !== 'synthetic') return
    const alive = dronesRef.current.filter((d) => !d.stale)
    if (!alive.length) return
    killDrone(alive[Math.floor(Math.random() * alive.length)].id)
  }, [killDrone])

  const reviveAll = useCallback(() => {
    if (sourceModeRef.current !== 'synthetic') return
    dronesRef.current.forEach((drone, index) => {
      if (!drone.stale) return
      respawnDrone(index, true)
      addEvent('ok', `${drone.id} reconnected - vertex rediscovery complete`)
    })
    setFooterMsg('All drones revived - mesh state converged')
  }, [addEvent, respawnDrone])

  const setPacketDrop = useCallback(
    (nextState: boolean, reason?: string | null) => {
      setPacketDropState(nextState)
      if (reason) {
        addEvent(
          'warn',
          `Packet loss ${nextState ? 'ENABLED (20%)' : 'DISABLED'} - ${reason}`,
        )
      }
    },
    [addEvent],
  )

  const dropPackets = useCallback(() => {
    if (sourceModeRef.current !== 'synthetic') return
    const nextState = !packetDropRef.current
    setPacketDrop(nextState, 'Mock message-delay mode')
    setFooterMsg(
      nextState
        ? 'Packet loss active - mock consensus may take longer'
        : 'Packet loss cleared',
    )
  }, [setPacketDrop])

  const stageDemoContention = useCallback(() => {
    const first = getAliveDrone('drone_1')
    const second = getAliveDrone('drone_2')
    if (!first || !second) return

    setGrid((prev) =>
      prev.map((row) =>
        row.map((cell) => {
          if (cell.owner < 0 && !(cell.x === targetRef.current.x && cell.y === targetRef.current.y)) {
            return { ...cell, certainty: 0.86 }
          }
          return cell
        }),
      ),
    )
    setCell(DEMO_CONTENTION_CELL.x, DEMO_CONTENTION_CELL.y, { certainty: 0.5 })
    ;[first, second].forEach((drone) => {
      const index = dronesRef.current.findIndex((d) => d.id === drone.id)
      releaseClaim(index)
      setDrone(index, { tx: null, ty: null, status: 'idle' })
    })
    const firstIndex = dronesRef.current.findIndex((d) => d.id === first.id)
    const secondIndex = dronesRef.current.findIndex((d) => d.id === second.id)
    setDrone(firstIndex, { x: DEMO_CONTENTION_CELL.x, y: DEMO_CONTENTION_CELL.y - 1 })
    setDrone(secondIndex, { x: DEMO_CONTENTION_CELL.x, y: DEMO_CONTENTION_CELL.y + 2 })
    addEvent(
      'info',
      `Auto demo: staged contention at [${DEMO_CONTENTION_CELL.x},${DEMO_CONTENTION_CELL.y}] for drone_1 vs drone_2`,
    )
  }, [addEvent, getAliveDrone, releaseClaim, setCell, setDrone])

  const stageDemoSurvivor = useCallback(() => {
    const drone = nearestAliveDroneTo(targetRef.current.x, targetRef.current.y)
    if (!drone) return
    const index = dronesRef.current.findIndex((d) => d.id === drone.id)
    releaseClaim(index)
    setDrone(index, {
      x: targetRef.current.x,
      y: targetRef.current.y,
      tx: targetRef.current.x,
      ty: targetRef.current.y,
      status: 'searching',
    })
    setCell(targetRef.current.x, targetRef.current.y, {
      owner: index,
      ownerId: drone.id,
      certainty: Math.max(getCell(targetRef.current.x, targetRef.current.y).certainty, SEARCH_COMPLETE - 0.04),
    })
    addEvent(
      'info',
      `Auto demo: staged survivor confirmation run for ${drone.id} at [${targetRef.current.x},${targetRef.current.y}]`,
    )
  }, [addEvent, getCell, nearestAliveDroneTo, releaseClaim, setCell, setDrone])

  const runAutoDemoSchedule = useCallback(() => {
    if (!autoDemoRef.current.enabled || missionCompleteRef.current) return

    if (!autoDemoRef.current.packetLoss && elapsedRef.current >= DEMO_TIMELINE.packetLossAt) {
      setAutoDemo((prev) => ({ ...prev, packetLoss: true }))
      setPacketDrop(true, 'Auto demo packet-loss stage')
      setFooterMsg('Auto demo: packet-loss stage engaged')
    }

    if (!autoDemoRef.current.contention && elapsedRef.current >= DEMO_TIMELINE.contentionAt) {
      setAutoDemo((prev) => ({ ...prev, contention: true }))
      stageDemoContention()
      setFooterMsg('Auto demo: contention stage armed')
    }

    if (!autoDemoRef.current.dropout && elapsedRef.current >= DEMO_TIMELINE.dropoutAt) {
      setAutoDemo((prev) => ({ ...prev, dropout: true }))
      const drone = getAliveDrone('drone_2')
      if (drone) {
        killDrone(drone.id)
      }
      setFooterMsg('Auto demo: dropout stage complete')
    }

    if (!autoDemoRef.current.survivor && elapsedRef.current >= DEMO_TIMELINE.survivorAt) {
      setAutoDemo((prev) => ({ ...prev, survivor: true }))
      stageDemoSurvivor()
      setFooterMsg('Auto demo: survivor confirmation stage armed')
    }
  }, [getAliveDrone, killDrone, setPacketDrop, stageDemoContention, stageDemoSurvivor])

  const tick = useCallback(() => {
    if (missionCompleteRef.current || sourceModeRef.current !== 'synthetic') return
    for (let step = 0; step < speedRef.current; step += 1) {
      setElapsed((prev) => prev + 1)
      elapsedRef.current += 1
      runAutoDemoSchedule()
      decayGrid()
      reassignIdleDrones()
      stepDrones()
    }
  }, [decayGrid, reassignIdleDrones, runAutoDemoSchedule, stepDrones])

  useEffect(() => {
    const id = setInterval(tick, TICK_MS)
    return () => clearInterval(id)
  }, [tick])

  const setSpeed = useCallback((value: number) => {
    setSpeedState(value)
  }, [])

  const toggleAutoDemo = useCallback(
    (forceState?: boolean) => {
      if (sourceModeRef.current !== 'synthetic') return
      const nextState = typeof forceState === 'boolean' ? forceState : !autoDemoRef.current.enabled
      setAutoDemo({
        enabled: nextState,
        packetLoss: false,
        contention: false,
        dropout: false,
        survivor: false,
      })
      addEvent(
        'info',
        nextState
          ? 'Auto demo enabled - scripted packet loss, contention, dropout, and survivor stages armed'
          : 'Auto demo disabled - manual controls restored',
      )
      setFooterMsg(
        nextState
          ? 'Auto demo ready - advancing toward scripted hackathon milestones'
          : 'Mesh stable - entropy auctions active',
      )
    },
    [addEvent],
  )

  const captureSyntheticBaseline = useCallback(() => {
    syntheticBaseline.current = {
      grid: gridRef.current.map((row) => row.map((cell) => ({ ...cell }))),
      drones: dronesRef.current.map((drone) => ({ ...drone })),
      elapsed: elapsedRef.current,
      bftRounds: bftRoundsRef.current,
      auctions: auctionsRef.current,
      dropouts: dropoutsRef.current,
      found: foundRef.current,
      missionComplete: missionCompleteRef.current,
      events: eventsRef.current.map((event) => ({ ...event })),
      packetDrop: packetDropRef.current,
    }
  }, [])

  const restoreSyntheticState = useCallback(() => {
    if (!syntheticBaseline.current) return
    if (livePollHandle.current) {
      clearInterval(livePollHandle.current)
      livePollHandle.current = null
    }
    const base = syntheticBaseline.current
    setGrid(base.grid.map((row) => row.map((cell) => ({ ...cell }))))
    setDrones(base.drones.map((drone) => ({ ...drone })))
    setElapsed(base.elapsed)
    setBftRounds(base.bftRounds)
    setAuctions(base.auctions)
    setDropouts(base.dropouts)
    setFound(base.found)
    setMissionComplete(base.missionComplete)
    setEvents(base.events.map((event) => ({ ...event })))
    setPacketDropState(base.packetDrop)
    setAutoDemo({
      enabled: false,
      packetLoss: false,
      contention: false,
      dropout: false,
      survivor: false,
    })
    setSourceMode('synthetic')
    setFooterMsg(
      'Demo-only synthetic mode - replay/live stay read-only; local controls can mutate state',
    )
  }, [])

  const ownerIndexFor = useCallback((value: number | string): number => {
    if (typeof value === 'number') return value
    if (typeof value === 'string') {
      return dronesRef.current.findIndex((drone) => drone.id === value)
    }
    return -1
  }, [])

  const ownerIdFor = useCallback(
    (value: number | string, replayDrones: { id?: string }[]): string | null => {
      if (typeof value === 'string') return value
      if (typeof value === 'number' && value >= 0) {
        return replayDrones[value]?.id || dronesRef.current[value]?.id || null
      }
      return null
    },
    [],
  )

  const applySnapshotPayload = useCallback(
    (payload: SnapshotPayload, mode: SourceMode) => {
      const rows = payload?.grid
      const summary: SnapshotSummary = (payload?.summary || payload?.stats || {}) as SnapshotSummary
      const stats: SnapshotSummary = (payload?.stats || summary || {}) as SnapshotSummary
      const replayDrones: SnapshotSummary['drones'] = Array.isArray(summary.drones) ? summary.drones : []
      const rawEvents = Array.isArray(payload?.events) ? payload.events : []
      const targetValue = payload?.config?.target || summary?.target || [7, 3]

      if (!Array.isArray(rows)) {
        throw new Error('Snapshot grid missing')
      }
      const maxColumns = rows.reduce(
        (max, row) => Math.max(max, Array.isArray(row) ? row.length : 0),
        0,
      )
      if (rows.length > GRID_SIZE || maxColumns > GRID_SIZE) {
        throw new Error(
          `Snapshot grid ${rows.length}x${maxColumns} exceeds browser limit ${GRID_SIZE}x${GRID_SIZE}; use the OpenTUI monitor for larger runs`,
        )
      }
      if (rows.length !== GRID_SIZE) {
        throw new Error(`Expected ${GRID_SIZE} snapshot rows`)
      }

      setTarget({ x: Number(targetValue[0] ?? 7), y: Number(targetValue[1] ?? 3) })

      const newGrid: Cell[][] = []
      rows.forEach((row, y) => {
        if (!Array.isArray(row) || row.length !== GRID_SIZE) {
          throw new Error(`Expected ${GRID_SIZE} snapshot columns in row ${y}`)
        }
        const newRow: Cell[] = []
        row.forEach((cell, x) => {
          newRow.push({
            x,
            y,
            certainty: Number(cell.certainty ?? 0.5),
            owner: ownerIndexFor(cell.owner ?? -1),
            ownerId: ownerIdFor(cell.owner ?? -1, replayDrones),
          })
        })
        newGrid.push(newRow)
      })
      setGrid(newGrid)

      setElapsed(Number(stats.duration_elapsed ?? summary.duration_elapsed ?? 0))
      setBftRounds(Number(stats.bft_rounds ?? 0))
      setAuctions(Number(stats.auctions ?? 0))
      setDropouts(Number(stats.dropouts ?? 0))
      setFound(Boolean(stats.survivor_found ?? summary.survivor_found))
      setMissionComplete(mode === 'replay')
      setPacketDropState(false)
      setAutoDemo({
        enabled: false,
        packetLoss: false,
        contention: false,
        dropout: false,
        survivor: false,
      })

      const newDrones = dronesRef.current.map((drone, index) => {
        const replayDrone =
          replayDrones.find((entry: SnapshotDrone) => entry && entry.id === drone.id) ||
          replayDrones[index] ||
          ({} as (typeof replayDrones)[number])
        const position = replayDrone.position || START_POSITIONS[index]
        const tgt = replayDrone.target || null
        const stale = replayDrone.alive === false || replayDrone.reachable === false
        const status = mapBackendStatus(
          replayDrone.status || (stale ? 'offline' : 'idle'),
        )
        const updated: Drone = {
          ...drone,
          x: position[0],
          y: position[1],
          tx: tgt ? tgt[0] : null,
          ty: tgt ? tgt[1] : null,
          stale,
          status,
          cells: Number(replayDrone.searched_cells ?? drone.cells ?? 0),
          battery: replayDrone.battery != null ? replayDrone.battery : drone.battery,
          role: replayDrone.role || drone.role,
          subzone: replayDrone.subzone || drone.subzone,
        }
        if (Array.isArray(replayDrone.claimed_cell)) {
          const [claimedX, claimedY] = replayDrone.claimed_cell
          if (
            Number.isInteger(claimedX) &&
            Number.isInteger(claimedY) &&
            claimedX >= 0 &&
            claimedY >= 0 &&
            claimedX < GRID_SIZE &&
            claimedY < GRID_SIZE &&
            newGrid[claimedY][claimedX].owner < 0
          ) {
            newGrid[claimedY][claimedX].owner = index
            newGrid[claimedY][claimedX].ownerId = replayDrone.id || drone.id
          }
        }
        return updated
      })
      setDrones(newDrones)

      const hiddenDroneCount = Math.max(0, replayDrones.length - newDrones.length)
      const hiddenEventCount = Math.max(0, rawEvents.length - 24)
      const newEvents: LogEvent[] =
        rawEvents.length > 0
          ? rawEvents
              .slice(-24)
              .reverse()
              .map(formatReplayEvent)
          : []
      if (hiddenDroneCount > 0 || hiddenEventCount > 0) {
        const limitNote: string[] = []
        if (hiddenDroneCount > 0) {
          limitNote.push(`Showing ${newDrones.length} of ${newDrones.length + hiddenDroneCount} drones`)
        }
        if (hiddenEventCount > 0) {
          limitNote.push(`Showing newest 24 of ${24 + hiddenEventCount} events`)
        }
        newEvents.unshift({
          type: 'info',
          msg: `Browser limit note - ${limitNote.join(' \u00b7 ')}`,
          t: Number(stats.duration_elapsed ?? summary.duration_elapsed ?? 0),
        })
        if (newEvents.length > 24) newEvents.pop()
      }
      setEvents(newEvents)

      if (mode === 'live') {
        setBftRounds(summary.consensus_rounds ?? stats.consensus_rounds ?? bftRoundsRef.current)
      }
      setSourceMode(mode)

      const limitParts: string[] = []
      if (hiddenDroneCount > 0) {
        limitParts.push(`Showing ${newDrones.length} of ${newDrones.length + hiddenDroneCount} drones`)
      }
      if (hiddenEventCount > 0) {
        limitParts.push(`Showing newest 24 of ${24 + hiddenEventCount} events`)
      }
      const limitNote = limitParts.join(' \u00b7 ')

      if (mode === 'live') {
        setFooterMsg(
          `Live snapshot connected - polling current peer state (read-only; demo-only controls locked)${limitNote ? ` \u00b7 ${limitNote}` : ''}`,
        )
      } else if (foundRef.current) {
        setFooterMsg(
          `Replay loaded - final simulation snapshot with survivor confirmation (read-only; demo-only controls locked)${limitNote ? ` \u00b7 ${limitNote}` : ''}`,
        )
      } else {
        setFooterMsg(
          `Replay loaded - final simulation snapshot (read-only; demo-only controls locked)${limitNote ? ` \u00b7 ${limitNote}` : ''}`,
        )
      }
    },
    [ownerIdFor, ownerIndexFor],
  )

  const applyReplayPayload = useCallback(
    (payload: SnapshotPayload) => {
      applySnapshotPayload(payload, 'replay')
    },
    [applySnapshotPayload],
  )

  const applyLivePayload = useCallback(
    (payload: SnapshotPayload) => {
      applySnapshotPayload(payload, 'live')
    },
    [applySnapshotPayload],
  )

  const pollLiveSnapshot = useCallback(async () => {
    if (!liveUrl) return
    const response = await fetch(liveUrl, { cache: 'no-store' })
    if (!response.ok) throw new Error(`Live snapshot request failed (${response.status})`)
    applyLivePayload(await response.json())
  }, [applyLivePayload, liveUrl])

  const connectLive = useCallback(
    (nextSource?: string) => {
      const source = (nextSource || liveUrl).trim()
      setLiveUrl(source)
      if (!source) return
      if (livePollHandle.current) clearInterval(livePollHandle.current)
      setSourceMode('live')
      setLoading(true)
      void pollLiveSnapshot()
        .catch((error: Error) => {
          setFooterMsg(`Live snapshot failed - ${error.message}`)
          addEvent('err', `Live snapshot failed - ${error.message}`)
          showToast('err', `Live connection failed - ${error.message}`)
        })
        .finally(() => {
          setLoading(false)
        })
      livePollHandle.current = setInterval(() => {
        void pollLiveSnapshot().catch((error: Error) => {
          setFooterMsg(`Live snapshot failed - ${error.message}`)
          addEvent('err', `Live snapshot failed - ${error.message}`)
          showToast('err', `Live polling error - ${error.message}`)
        })
      }, 1000)
    },
    [addEvent, liveUrl, pollLiveSnapshot, showToast],
  )

  const disconnectLive = useCallback(() => {
    if (sourceModeRef.current !== 'live') return
    if (livePollHandle.current) {
      clearInterval(livePollHandle.current)
      livePollHandle.current = null
    }
    restoreSyntheticState()
  }, [restoreSyntheticState])

  const clearReplay = useCallback(() => {
    if (sourceModeRef.current !== 'replay') return
    restoreSyntheticState()
  }, [restoreSyntheticState])

  const handleFileLoad = useCallback(
    async (file: File) => {
      setLoading(true)
      try {
        const text = await file.text()
        applyReplayPayload(JSON.parse(text) as SnapshotPayload)
        showToast('ok', 'Replay loaded successfully')
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error)
        setFooterMsg(`Replay load failed - ${message}`)
        addEvent('err', `Replay load failed - ${message}`)
        showToast('err', `Replay load failed - ${message}`)
      } finally {
        setLoading(false)
      }
    },
    [addEvent, applyReplayPayload, showToast],
  )

  useEffect(() => {
    addEvent('info', 'Vertex P2P discovery complete - 5 peers online')
    addEvent(
      'info',
      'Shared certainty map initialised - 10x10 grid, all certainty=0.50 (H=1.00)',
    )
    captureSyntheticBaseline()
    setFooterMsg(
      'Demo-only synthetic mode - replay/live stay read-only; local controls can mutate state',
    )
  }, [addEvent, captureSyntheticBaseline])

  return {
    grid,
    drones,
    elapsed,
    bftRounds,
    auctions,
    dropouts,
    found,
    missionComplete,
    events,
    sourceMode,
    speed,
    packetDrop,
    target,
    autoDemo,
    toast,
    footerMsg,
    loading,
    liveUrl,
    coverage,
    averageEntropy,
    setSpeed,
    dropPackets,
    toggleAutoDemo,
    killRandom,
    reviveAll,
    killDrone,
    connectLive,
    disconnectLive,
    clearReplay,
    handleFileLoad,
    setLiveUrl,
    setFooterMsg,
    setToast,
  }
}

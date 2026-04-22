import React, { useCallback, useEffect, useRef, useState } from 'react'
import type { Cell, Drone } from '@/types/console'
import styles from '@/styles/console.module.css'

interface GridCanvasProps {
  grid: Cell[][]
  drones: Drone[]
  target: { x: number; y: number }
  found: boolean
  onKillDrone: (droneId: string) => void
  loading: boolean
}

const GRID_SIZE = 10
const CELL_SIZE = 24
const CANVAS_SIZE = GRID_SIZE * CELL_SIZE

function entropyValue(certainty: number): number {
  if (certainty <= 0 || certainty >= 1) return 0
  return -(certainty * Math.log2(certainty) + (1 - certainty) * Math.log2(1 - certainty))
}

function mapBackendStatus(rawStatus: string): string {
  return (
    {
      transiting: 'transit',
      claiming: 'transit',
      claim_won: 'searching',
      claim_lost: 'transit',
      stale: 'offline',
    } as Record<string, string>
  )[rawStatus] || rawStatus || 'idle'
}

function ownerLabelForCell(cell: Cell, drones: Drone[]): string {
  if (cell.owner >= 0 && drones[cell.owner]) return drones[cell.owner].id
  return cell.ownerId || 'unowned'
}

const GridCanvas: React.FC<GridCanvasProps> = ({
  grid,
  drones,
  target,
  found,
  onKillDrone,
  loading,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const [tooltip, setTooltip] = useState<{
    visible: boolean
    x: number
    y: number
    text: string
  }>({ visible: false, x: 0, y: 0, text: '' })

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.clearRect(0, 0, CANVAS_SIZE, CANVAS_SIZE)

    for (let y = 0; y < GRID_SIZE; y += 1) {
      for (let x = 0; x < GRID_SIZE; x += 1) {
        const cell = grid[y][x]
        const intensity = Math.floor(255 - entropyValue(cell.certainty) * 210)
        ctx.fillStyle = `rgb(${intensity},${intensity},${intensity})`
        ctx.fillRect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE)

        if (cell.owner >= 0) {
          ctx.fillStyle = `${drones[cell.owner]?.color ?? '#fff'}22`
          ctx.fillRect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
        }

        if (x === target.x && y === target.y) {
          ctx.strokeStyle = found ? '#1D9E75' : '#888'
          ctx.lineWidth = 1
          ctx.strokeRect(
            x * CELL_SIZE + 1,
            y * CELL_SIZE + 1,
            CELL_SIZE - 2,
            CELL_SIZE - 2,
          )
        }
      }
    }

    ctx.strokeStyle = 'rgba(128,128,128,0.15)'
    ctx.lineWidth = 0.3
    for (let i = 0; i <= GRID_SIZE; i += 1) {
      ctx.beginPath()
      ctx.moveTo(i * CELL_SIZE, 0)
      ctx.lineTo(i * CELL_SIZE, CANVAS_SIZE)
      ctx.stroke()
      ctx.beginPath()
      ctx.moveTo(0, i * CELL_SIZE)
      ctx.lineTo(CANVAS_SIZE, i * CELL_SIZE)
      ctx.stroke()
    }

    drones.forEach((drone) => {
      const displayStatus = mapBackendStatus(drone.status)
      if (drone.stale) {
        ctx.strokeStyle = `${drone.color}44`
        ctx.lineWidth = 1
        ctx.strokeRect(
          drone.x * CELL_SIZE + 3,
          drone.y * CELL_SIZE + 3,
          CELL_SIZE - 6,
          CELL_SIZE - 6,
        )
        return
      }

      ctx.beginPath()
      ctx.arc(
        drone.x * CELL_SIZE + CELL_SIZE / 2,
        drone.y * CELL_SIZE + CELL_SIZE / 2,
        5,
        0,
        Math.PI * 2,
      )
      ctx.fillStyle = drone.color
      ctx.fill()
      ctx.strokeStyle = '#0f0f11'
      ctx.lineWidth = 1.5
      ctx.stroke()

      if (
        displayStatus === 'transit' &&
        drone.tx != null &&
        drone.ty != null &&
        (drone.x !== drone.tx || drone.y !== drone.ty)
      ) {
        ctx.beginPath()
        ctx.setLineDash([2, 3])
        ctx.moveTo(
          drone.x * CELL_SIZE + CELL_SIZE / 2,
          drone.y * CELL_SIZE + CELL_SIZE / 2,
        )
        ctx.lineTo(
          drone.tx * CELL_SIZE + CELL_SIZE / 2,
          drone.ty * CELL_SIZE + CELL_SIZE / 2,
        )
        ctx.strokeStyle = `${drone.color}55`
        ctx.lineWidth = 0.5
        ctx.stroke()
        ctx.setLineDash([])
      }
    })
  }, [grid, drones, target, found])

  useEffect(() => {
    draw()
  }, [draw])

  const handleMouseMove = useCallback(
    (event: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current
      if (!canvas) return
      const rect = canvas.getBoundingClientRect()
      const gridX = Math.floor((event.clientX - rect.left) / CELL_SIZE)
      const gridY = Math.floor((event.clientY - rect.top) / CELL_SIZE)
      if (gridX < 0 || gridX >= GRID_SIZE || gridY < 0 || gridY >= GRID_SIZE) {
        setTooltip((prev) => ({ ...prev, visible: false }))
        return
      }
      const cell = grid[gridY][gridX]
      const owner = ownerLabelForCell(cell, drones)
      setTooltip({
        visible: true,
        x: gridX * CELL_SIZE + CELL_SIZE + 2,
        y: gridY * CELL_SIZE,
        text: `[${gridX},${gridY}] H=${entropyValue(cell.certainty).toFixed(3)} c=${cell.certainty.toFixed(2)} ${owner}`,
      })
    },
    [grid, drones],
  )

  const handleMouseLeave = useCallback(() => {
    setTooltip((prev) => ({ ...prev, visible: false }))
  }, [])

  const handleClick = useCallback(
    (event: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current
      if (!canvas) return
      const rect = canvas.getBoundingClientRect()
      const gridX = Math.floor((event.clientX - rect.left) / CELL_SIZE)
      const gridY = Math.floor((event.clientY - rect.top) / CELL_SIZE)
      const drone = drones.find(
        (entry) => entry.x === gridX && entry.y === gridY && !entry.stale,
      )
      if (drone) onKillDrone(drone.id)
    },
    [drones, onKillDrone],
  )

  return (
    <div className={styles.gridWrap}>
      <div className={styles.gridCanvasWrap} ref={wrapRef}>
        <canvas
          ref={canvasRef}
          width={CANVAS_SIZE}
          height={CANVAS_SIZE}
          className={styles.canvas}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          onClick={handleClick}
        />
        <div className={`${styles.loadingOverlay} ${loading ? styles.active : ''}`}>
          Loading
        </div>
        <div
          className={`${styles.tooltip} ${tooltip.visible ? styles.visible : ''}`}
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          {tooltip.text}
        </div>
      </div>
      <div className={styles.legend}>
        <span>High H</span>
        <div className={styles.legendGrad} />
        <span>Low H</span>
        <span style={{ marginLeft: 10, color: 'var(--text-muted)' }}>
          Hover cell &middot; Click drone to kill
        </span>
      </div>
    </div>
  )
}

export default React.memo(GridCanvas)

import React, { useRef, useEffect } from "react";
import type { GridCell, Drone } from "@/types/live";
import { COLORS, entropy, mapBackendStatus } from "@/lib/liveUtils";
import styles from "@/styles/live.module.css";

interface GridCanvasProps {
  grid: GridCell[][];
  drones: Drone[];
  target: [number, number];
  survivorFound: boolean;
}

const GridCanvas: React.FC<GridCanvasProps> = ({ grid, drones, target, survivorFound }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const size = grid.length;
    if (!size) return;
    const cellSize = Math.floor(400 / size);
    canvas.width = size * cellSize;
    canvas.height = size * cellSize;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        const cell = grid[y][x];
        const intensity = Math.floor(255 - entropy(cell.certainty ?? 0.5) * 210);
        ctx.fillStyle = `rgb(${intensity},${intensity},${intensity})`;
        ctx.fillRect(x * cellSize, y * cellSize, cellSize, cellSize);

        if (cell.owner != null && cell.owner >= 0 && drones[cell.owner]) {
          ctx.fillStyle = (COLORS[cell.owner % COLORS.length] || "#888") + "22";
          ctx.fillRect(x * cellSize, y * cellSize, cellSize, cellSize);
        }

        if (target && x === target[0] && y === target[1]) {
          ctx.strokeStyle = survivorFound ? "#34d399" : "#888";
          ctx.lineWidth = 1;
          ctx.strokeRect(x * cellSize + 1, y * cellSize + 1, cellSize - 2, cellSize - 2);
        }
      }
    }

    ctx.strokeStyle = "rgba(128,128,128,0.12)";
    ctx.lineWidth = 0.4;
    for (let i = 0; i <= size; i++) {
      ctx.beginPath();
      ctx.moveTo(i * cellSize, 0);
      ctx.lineTo(i * cellSize, size * cellSize);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(0, i * cellSize);
      ctx.lineTo(size * cellSize, i * cellSize);
      ctx.stroke();
    }

    if (drones) {
      drones.forEach((drone, index) => {
        if (!drone) return;
        const color = COLORS[index % COLORS.length] || "#888";
        const dx = drone.position ? drone.position[0] : (drone.x ?? 0);
        const dy = drone.position ? drone.position[1] : (drone.y ?? 0);
        const stale = drone.alive === false || drone.stale;

        if (stale) {
          ctx.strokeStyle = color + "44";
          ctx.lineWidth = 1;
          ctx.strokeRect(dx * cellSize + 3, dy * cellSize + 3, cellSize - 6, cellSize - 6);
          return;
        }

        ctx.beginPath();
        ctx.arc(
          dx * cellSize + cellSize / 2,
          dy * cellSize + cellSize / 2,
          Math.max(4, cellSize * 0.18),
          0,
          Math.PI * 2
        );
        ctx.fillStyle = color;
        ctx.fill();
        ctx.strokeStyle = "#0f0f11";
        ctx.lineWidth = 1.5;
        ctx.stroke();

        const status = mapBackendStatus(drone.status);
        const tx = drone.target ? drone.target[0] : drone.tx;
        const ty = drone.target ? drone.target[1] : drone.ty;
        if (status === "transit" && tx != null && ty != null && (dx !== tx || dy !== ty)) {
          ctx.beginPath();
          ctx.setLineDash([2, 3]);
          ctx.moveTo(dx * cellSize + cellSize / 2, dy * cellSize + cellSize / 2);
          ctx.lineTo(tx * cellSize + cellSize / 2, ty * cellSize + cellSize / 2);
          ctx.strokeStyle = color + "55";
          ctx.lineWidth = 0.5;
          ctx.stroke();
          ctx.setLineDash([]);
        }
      });
    }
  }, [grid, drones, target, survivorFound]);

  return (
    <div className={styles.gridCanvasWrap}>
      <canvas ref={canvasRef} width={400} height={400} />
      <div className={styles.gridLegend}>
        <span>High H</span>
        <div className={styles.grad} />
        <span>Low H</span>
      </div>
    </div>
  );
};

export default GridCanvas;

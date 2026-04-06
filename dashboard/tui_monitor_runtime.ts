import { fg as withFg, t, type BoxRenderable, type TextRenderable } from "@opentui/core";

import { PANEL_THEME } from "./tui_theme.ts";

export function syncWaitingShell(args: {
  visible: boolean;
  sourceUrl: string;
  spinnerFrame: string;
  shell: BoxRenderable;
  waitingShell: BoxRenderable;
  waitingBody: TextRenderable;
  requestRender: () => void;
}) {
  const { visible, sourceUrl, spinnerFrame, shell, waitingShell, waitingBody, requestRender } = args;
  shell.visible = !visible;
  waitingShell.visible = visible;
  if (visible) {
    waitingBody.content = t`${withFg(PANEL_THEME.textMuted)(`${spinnerFrame} polling ${sourceUrl}`)}`;
  }
  requestRender();
}

export function showActiveShell(args: {
  shell: BoxRenderable;
  waitingShell: BoxRenderable;
  requestRender: () => void;
}) {
  const { shell, waitingShell, requestRender } = args;
  waitingShell.visible = false;
  shell.visible = true;
  requestRender();
}

export function hasLostControllingParent(initialParentPid: number, currentParentPid: number): boolean {
  return initialParentPid > 1 && currentParentPid <= 1;
}

export function hasLostWatchedParent(watchedParentPid: number | null, isAlive: (pid: number) => boolean): boolean {
  return watchedParentPid != null && watchedParentPid > 1 && !isAlive(watchedParentPid);
}

export function hasLostSource(lastSuccessfulSnapshotAt: number, nowMs: number, maxGapMs: number): boolean {
  return lastSuccessfulSnapshotAt > 0 && maxGapMs > 0 && nowMs - lastSuccessfulSnapshotAt > maxGapMs;
}

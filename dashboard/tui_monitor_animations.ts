import type { CliRenderer } from "@opentui/core";
import { Timeline, engine } from "@opentui/core";

export interface AnimationState {
  targetPulse: Timeline | null;
  survivorCelebration: Timeline | null;
  cursorGlow: Timeline | null;
  eventSlide: Timeline | null;
  statTransition: Timeline | null;
  footerHeartbeat: Timeline | null;
  staggeredEntry: Timeline | null;
}

export function attachAnimationEngine(renderer: CliRenderer): void {
  engine.attach(renderer);
}

export function detachAnimationEngine(): void {
  engine.detach();
}

export function createTargetPulseTimeline(onUpdate: (phase: number) => void): Timeline {
  const target = { phase: 0 };
  const timeline = new Timeline({ duration: 2000, loop: true });
  timeline.add(target, {
    duration: 2000,
    ease: "inOutSine",
    loop: true,
    phase: 1,
    onUpdate: () => onUpdate(target.phase),
  });
  engine.register(timeline);
  timeline.play();
  return timeline;
}

export function createSurvivorCelebrationTimeline(onUpdate: (progress: number) => void): Timeline {
  const target = { progress: 0 };
  const timeline = new Timeline({ duration: 3000 });
  timeline.add(target, {
    duration: 3000,
    ease: "outElastic",
    progress: 1,
    onUpdate: () => onUpdate(target.progress),
  });
  engine.register(timeline);
  timeline.play();
  return timeline;
}

export function createCursorGlowTimeline(onUpdate: (intensity: number) => void): Timeline {
  const target = { intensity: 0.3 };
  const timeline = new Timeline({ duration: 600, loop: true });
  timeline.add(target, {
    duration: 600,
    ease: "inOutQuad",
    alternate: true,
    loop: true,
    intensity: 1.0,
    onUpdate: () => onUpdate(target.intensity),
  });
  engine.register(timeline);
  timeline.play();
  return timeline;
}

export function createEventSlideTimeline(
  onUpdate: (offset: number) => void,
  onComplete: () => void,
): Timeline {
  const target = { offset: -3 };
  const timeline = new Timeline({ duration: 200 });
  timeline.add(target, {
    duration: 200,
    ease: "outExpo",
    offset: 0,
    onUpdate: () => onUpdate(Math.round(target.offset)),
    onComplete,
  });
  engine.register(timeline);
  timeline.play();
  return timeline;
}

export function createStatTransitionTimeline(
  fromValue: number,
  toValue: number,
  onUpdate: (value: number) => void,
): Timeline {
  const target = { value: fromValue };
  const timeline = new Timeline({ duration: 500 });
  timeline.add(target, {
    duration: 500,
    ease: "outQuad",
    value: toValue,
    onUpdate: () => onUpdate(Math.round(target.value)),
  });
  engine.register(timeline);
  timeline.play();
  return timeline;
}

export function createFooterHeartbeatTimeline(onUpdate: (phase: number) => void): Timeline {
  const target = { phase: 0 };
  const timeline = new Timeline({ duration: 1500, loop: true });
  timeline.add(target, {
    duration: 1500,
    ease: "inOutSine",
    loop: true,
    phase: 1,
    onUpdate: () => onUpdate(target.phase),
  });
  engine.register(timeline);
  timeline.play();
  return timeline;
}

export function createStaggeredEntryTimeline(
  count: number,
  onItemUpdate: (index: number, progress: number) => void,
): Timeline {
  const timeline = new Timeline({ duration: count * 100 + 300 });

  for (let i = 0; i < count; i++) {
    const target = { progress: 0 };
    timeline.add(
      target,
      {
        duration: 300,
        ease: "outQuad",
        progress: 1,
        onUpdate: () => onItemUpdate(i, target.progress),
      },
      i * 100,
    );
  }

  engine.register(timeline);
  timeline.play();
  return timeline;
}

export function cleanupTimelines(timelines: Timeline[]): void {
  for (const timeline of timelines) {
    engine.unregister(timeline);
    timeline.pause();
  }
}

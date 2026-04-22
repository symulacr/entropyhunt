export interface SummaryCard {
  label: string;
  value: string;
  note?: string;
}

export interface ArtifactLink {
  label: string;
  href: string;
}

export interface EventItem {
  type: 'ok' | 'warn' | 'err';
  label: string;
  message: string;
}

export interface LandingPageData {
  hero: {
    eyebrow: string;
    title: string;
    lede: string;
    primaryAction: {
      label: string;
      href: string;
    };
    secondaryAction: {
      label: string;
      href: string;
    };
  };
  summaryCards: SummaryCard[];
  runMeta: string;
  artifacts: {
    title: string;
    badge: string;
    links: ArtifactLink[];
    commands: string[];
  };
  preview: {
    title: string;
    badge: string;
    svgContent?: string;
  };
  events: {
    title: string;
    badge: string;
    items: EventItem[];
  };
  deliverySurfaces: {
    title: string;
    items: string[];
  };
  operationalNotes: {
    title: string;
    items: string[];
  };
}

export const landingPageData: LandingPageData = {
  hero: {
    eyebrow: 'Vertex Swarm Challenge',
    title: 'Entropy Hunt',
    lede: 'An autonomous search-and-rescue swarm system. Multiple drones divide disaster terrain, negotiate search zones via BFT consensus over a mesh network, survive packet loss and node failures, and emit cryptographically-auditable proofs of coordination until a survivor is found.',
    primaryAction: {
      label: 'Open Final Snapshot',
      href: './artifacts/final_map.html'
    },
    secondaryAction: {
      label: 'Open Replay Console',
      href: './console.html'
    }
  },
  summaryCards: [
    { label: 'Drones', value: '5', note: 'Active swarm nodes' },
    { label: 'Grid', value: '8x8', note: 'Terrain partition cells' },
    { label: 'Duration', value: '60s', note: 'Simulation runtime' },
    { label: 'Consensus', value: 'BFT', note: 'Byzantine fault tolerant' }
  ],
  runMeta: 'Last run generated 47 coordination proofs across 5 peers with 0 failed validations. Survivor located at cell (3, 7) after 42 seconds.',
  artifacts: {
    title: 'Replay Artifacts',
    badge: 'Replay by default',
    links: [
      { label: 'final_map.html', href: './artifacts/final_map.html' },
      { label: 'final_map.svg', href: './artifacts/final_map.svg' },
      { label: 'final_map.json', href: './artifacts/final_map.json' }
    ],
    commands: [
      'python3 main.py --final-map final_map.json --svg-map final_map.svg --final-html final_map.html',
      'bun run build',
      'bun run preview',
      'bun run live:peers',
      'bun run live:serve'
    ]
  },
  preview: {
    title: 'Snapshot Preview',
    badge: 'SVG Export',
    svgContent: undefined
  },
  events: {
    title: 'Recent Events',
    badge: 'Replay Timeline',
    items: [
      { type: 'ok', label: 'Boot', message: 'Swarm initialized with 5 drones' },
      { type: 'ok', label: 'Mesh', message: 'P2P network established' },
      { type: 'warn', label: 'Packet', message: 'Simulated 30% packet loss' },
      { type: 'ok', label: 'Consensus', message: 'Zone allocation agreed' },
      { type: 'err', label: 'Failure', message: 'Drone node_2 failed at t=15s' },
      { type: 'ok', label: 'Recover', message: 'Swarm rebalanced zones' },
      { type: 'ok', label: 'Found', message: 'Survivor detected at (3, 7)' }
    ]
  },
  deliverySurfaces: {
    title: 'Delivery Surfaces',
    items: [
      'Packaged shell — this dist/ site for deployment and review.',
      'Replay console — primary browser surface in console.html; live polling works when local helpers run.',
      'Live telemetry — real-time SSE stream viewer for running simulations.',
      'TUI monitor — terminal dashboard polling aggregated snapshots.'
    ]
  },
  operationalNotes: {
    title: 'Operational Notes',
    items: [
      'Live polling consumes aggregated JSON snapshots, not a direct FoxMQ stream.',
      'FoxMQ and Webots paths are optional and validated separately.',
      'The packaged shell is static; live data requires running local helper scripts.'
    ]
  }
};

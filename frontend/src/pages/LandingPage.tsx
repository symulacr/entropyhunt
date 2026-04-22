import React from 'react';
import { Hero } from '../components/ui/Hero';
import { Card } from '../components/ui/Card';
import { SectionHeader } from '../components/ui/SectionHeader';
import { Badge } from '../components/ui/Badge';
import { landingPageData } from '../data/landingData';
import styles from './LandingPage.module.css';

const ArrowUpRightIcon: React.FC = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 11L11 1M11 1H3M11 1V9" />
  </svg>
);

export const LandingPage: React.FC = () => {
  const { hero, summaryCards, runMeta, artifacts, preview, events, deliverySurfaces, operationalNotes } = landingPageData;

  return (
    <main id="main" className={styles.page}>
      <a href="#main" className={styles.skipLink}>Skip to content</a>

      <Hero
        eyebrow={hero.eyebrow}
        title={hero.title}
        lede={hero.lede}
        primaryAction={{
          label: hero.primaryAction.label,
          href: hero.primaryAction.href,
          icon: <ArrowUpRightIcon />
        }}
        secondaryAction={{
          label: hero.secondaryAction.label,
          href: hero.secondaryAction.href
        }}
      />

      <section className={[styles.grid, styles.twoUp].join(' ')}>
        <article className={styles.panel}>
          <SectionHeader title="Latest Verified Run" badge="Built from final_map.json" />
          <div className={styles.cards}>
            {summaryCards.map((card) => (
              <Card key={card.label} label={card.label} value={card.value} note={card.note} />
            ))}
          </div>
          <div className={styles.runMeta}>{runMeta}</div>
        </article>

        <article className={styles.panel}>
          <SectionHeader title={artifacts.title} badge={artifacts.badge} />
          <ul className={styles.artifactList}>
            {artifacts.links.map((link) => (
              <li key={link.label}>
                <a href={link.href}>{link.label}</a>
              </li>
            ))}
          </ul>
          <pre className={styles.codeBlock}>
            <code>{artifacts.commands.join('\n')}</code>
          </pre>
        </article>
      </section>

      <section className={[styles.grid, styles.previewLayout].join(' ')}>
        <article className={[styles.panel, styles.heatmapPanel].join(' ')}>
          <SectionHeader title={preview.title} badge={preview.badge} />
          <div className={styles.heatmapFrame}>
            {preview.svgContent ? (
              <div dangerouslySetInnerHTML={{ __html: preview.svgContent }} />
            ) : (
              <div className={styles.placeholder}>
                <span>SVG preview loads when artifacts are generated</span>
              </div>
            )}
          </div>
        </article>

        <article className={styles.panel}>
          <SectionHeader title={events.title} badge={events.badge} />
          <ol className={styles.eventList}>
            {events.items.map((event, index) => (
              <li key={index}>
                <Badge variant={event.type === 'err' ? 'error' : event.type} className={styles.eventBadge}>
                  {event.label}
                </Badge>
                {event.message}
              </li>
            ))}
          </ol>
        </article>
      </section>

      <section className={[styles.grid, styles.twoUp].join(' ')}>
        <article className={styles.panel}>
          <SectionHeader title={deliverySurfaces.title} />
          <ul className={styles.stackList}>
            {deliverySurfaces.items.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </article>

        <article className={styles.panel}>
          <SectionHeader title={operationalNotes.title} />
          <ul className={styles.stackList}>
            {operationalNotes.items.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </article>
      </section>
    </main>
  );
};

import { AuthControls } from "../components/authControls";

const pillars = [
  {
    title: "Corpus ingestion",
    body: "Batch PDF and ZIP imports become asynchronous workspace jobs instead of one-off single-file actions.",
  },
  {
    title: "Durable graph state",
    body: "Research maps, pending comparisons, and search state persist across sessions instead of living in local cache only.",
  },
  {
    title: "Product-grade UX",
    body: "A dedicated web shell unlocks auth, sharable URLs, richer navigation, and calmer multi-step workflows.",
  },
];

const stack = [
  "Next.js frontend",
  "Python API",
  "Python workers",
  "Postgres + object storage",
  "Google OAuth via Clerk",
];

export default function HomePage() {
  return (
    <main className="v2-page">
      <section className="hero-card">
        <div className="hero-kicker">Hypatia V2 Production Branch</div>
        <h1>Building the product architecture behind the prototype.</h1>
        <p className="hero-copy">
          This branch is the foundation for a real multi-user Hypatia:
          authenticated workspaces, durable corpora, background ingestion,
          and a frontend built for long-lived research workflows rather than
          demo-time interaction alone.
        </p>
        <div className="hero-actions">
          <a href="/workspaces/demo" className="primary-link">
            Open the V2 shell
          </a>
          <a
            href="https://hypatia.streamlit.app/"
            className="secondary-link"
            target="_blank"
            rel="noreferrer"
          >
            View the current Streamlit app
          </a>
          <AuthControls />
        </div>
      </section>

      <section className="grid-section">
        {pillars.map((pillar) => (
          <article className="info-card" key={pillar.title}>
            <div className="section-label">{pillar.title}</div>
            <p>{pillar.body}</p>
          </article>
        ))}
      </section>

      <section className="stack-card">
        <div className="section-label">Target stack</div>
        <div className="stack-list">
          {stack.map((item) => (
            <span className="stack-pill" key={item}>
              {item}
            </span>
          ))}
        </div>
        <p>
          The current prototype remains the reference product surface, but V2
          is where auth, database-backed workspaces, background jobs, and bulk
          corpus ingestion will live.
        </p>
      </section>
    </main>
  );
}

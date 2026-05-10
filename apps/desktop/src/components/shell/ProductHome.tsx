import { useEffect, useMemo, useState } from "react";
import {
  getBackendStatus,
  getLMStudioStatus,
  type ServiceHealth,
} from "../../lib/statusApi";

const PRODUCT_CAPABILITIES = ["Local agent", "LM Studio models", "safe tools"];

function ServiceStatusCard({
  title,
  service,
  hint,
  accent,
}: {
  title: string;
  service: ServiceHealth | null;
  hint: string;
  accent: "pearl" | "mist";
}) {
  const statusText = service?.status ?? "checking";
  const connected = statusText === "ok" || statusText === "connected";
  const degraded = statusText === "checking";

  const badgeClass = connected
    ? "status-state-pill--connected"
    : degraded
      ? "status-state-pill--checking"
      : "status-state-pill--error";

  return (
    <article className={`status-panel status-panel--${accent}`}>
      <div className="status-panel__row">
        <div>
          <span className="status-panel__label">{title}</span>
          <h3>
            {connected
              ? "Connected"
              : degraded
                ? "Checking"
                : "Attention needed"}
          </h3>
        </div>

        <div className="status-signal">
          <span className={`status-state-pill ${badgeClass}`}>
            {connected ? "Live" : degraded ? "Checking" : "Issue"}
          </span>
          <span
            className={`status-dot ${
              connected
                ? "status-dot--connected"
                : degraded
                  ? "status-dot--checking"
                  : "status-dot--error"
            }`}
            aria-label={statusText}
          />
        </div>
      </div>

      <p className="status-panel__hint">{hint}</p>

      <dl className="status-meta">
        <div>
          <dt>State</dt>
          <dd>{statusText}</dd>
        </div>
        <div>
          <dt>Endpoint</dt>
          <dd>{service?.endpoint ?? "Unavailable"}</dd>
        </div>
        <div>
          <dt>Details</dt>
          <dd>{service?.detail ?? "Waiting for response"}</dd>
        </div>
      </dl>
    </article>
  );
}

export function ProductHome() {
  const [backend, setBackend] = useState<ServiceHealth | null>(null);
  const [lmstudio, setLmstudio] = useState<ServiceHealth | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>("--");

  useEffect(() => {
    let mounted = true;

    async function load() {
      const [backendResult, lmstudioResult] = await Promise.all([
        getBackendStatus(),
        getLMStudioStatus(),
      ]);

      if (!mounted) {
        return;
      }

      setBackend(backendResult);
      setLmstudio(lmstudioResult);
      setLastUpdated(
        new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      );
    }

    void load();
    const timer = window.setInterval(() => {
      void load();
    }, 10000);

    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, []);

  const headline = useMemo(() => {
    if (backend?.status === "ok" && lmstudio?.status === "connected") {
      return "Your local AI workspace is ready.";
    }

    return "A black liquid-glass shell for your private local agent.";
  }, [backend?.status, lmstudio?.status]);

  return (
    <section className="home-screen">
      <article className="hero-panel">
        <div className="hero-panel__copy">
          <div className="hero-panel__eyebrow">Serviq</div>
          <h1>{headline}</h1>
          <p>
            Serviq is a local-first AI desktop assistant designed to run
            privately on your device, helping you get things done without
            relying on the cloud.
          </p>

          <div className="capability-list">
            {PRODUCT_CAPABILITIES.map((capability) => (
              <span key={capability} className="capability-pill">
                {capability}
              </span>
            ))}
          </div>
        </div>

        <div className="hero-panel__visual" aria-hidden="true">
          <div className="liquid-shape liquid-shape--one" />
          <div className="liquid-shape liquid-shape--two" />
          <div className="liquid-shape liquid-shape--three" />
          <div className="orbital-card orbital-card--primary">
            <span>Desktop Agent</span>
            <strong>Serviq</strong>
          </div>

          <div className="orbital-ring" />
        </div>
      </article>

      <section className="dashboard-grid">
        <ServiceStatusCard
          title="Backend"
          service={backend}
          hint="FastAPI service health and local API readiness"
          accent="pearl"
        />
        <ServiceStatusCard
          title="LM Studio"
          service={lmstudio}
          hint="Local model runtime connection and model availability"
          accent="mist"
        />
      </section>
    </section>
  );
}

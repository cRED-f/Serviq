import { useEffect, useMemo, useState } from "react";
import {
  getBackendStatus,
  getLMStudioStatus,
  type ServiceHealth,
} from "../../lib/statusApi";
import { Server, Cpu } from "lucide-react";

const PRODUCT_CAPABILITIES = ["Local agent", "LM Studio models", "safe tools"];

function StatusIndicator({ connected }: { connected: boolean }) {
  return (
    <span
      className={`status-dot ${connected ? "status-dot--connected" : "status-dot--checking"}`}
    />
  );
}

function ServiceStatusCard({
  title,
  service,
  hint,
  icon: Icon,
}: {
  title: string;
  service: ServiceHealth | null;
  hint: string;
  icon: typeof Server;
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
    <article className="astro-status-card">
      <div className="astro-status-card__header">
        <div className="astro-status-card__title-group">
          <div className="astro-status-card__icon">
            <Icon className="w-4 h-4" />
          </div>
          <div>
            <span className="astro-status-card__label">{title}</span>
            <h3 className="astro-status-card__status">
              {connected
                ? "Connected"
                : degraded
                  ? "Checking"
                  : "Attention needed"}
            </h3>
          </div>
        </div>

        <div className="astro-status-card__signal">
          <span className={`status-state-pill ${badgeClass}`}>
            {connected ? "Live" : degraded ? "Checking" : "Issue"}
          </span>
          <StatusIndicator connected={connected} />
        </div>
      </div>

      <p className="astro-status-card__hint">{hint}</p>

      <dl className="astro-status-card__meta">
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
  const [isLoading, setIsLoading] = useState(true);

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
      setIsLoading(false);
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

  const isReady = useMemo(() => {
    return backend?.status === "ok" && lmstudio?.status === "connected";
  }, [backend?.status, lmstudio?.status]);

  return (
    <section className="home-screen">
      <article className="hero-panel">
        <div className="hero-panel__copy">
          <div className="hero-panel__eyebrow">Serviq</div>
          <h1>{isLoading
            ? "Connecting to services..."
            : isReady
              ? "Your local AI workspace is ready."
              : "Setting up your local AI workspace..."}</h1>
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
          icon={Server}
        />
        <ServiceStatusCard
          title="LM Studio"
          service={lmstudio}
          hint="Local model runtime connection and model availability"
          icon={Cpu}
        />
      </section>
    </section>
  );
}
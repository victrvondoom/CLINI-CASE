import { Component, Suspense, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";

class PageErrorBoundary extends Component<
  { children: ReactNode; route: string },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidUpdate(previous: { route: string }) {
    if (previous.route !== this.props.route && this.state.failed)
      this.setState({ failed: false });
  }

  render() {
    if (this.state.failed) {
      return (
        <section role="alert" className="mx-auto max-w-lg p-8 text-ink-body">
          <h1 className="text-xl font-semibold text-ink-primary">
            This page could not be opened
          </h1>
          <p className="my-4">
            Check your connection and reload the page. Unsaved changes may need
            to be entered again.
          </p>
          <button
            type="button"
            className="rounded bg-accent-blue px-4 py-2 text-white"
            onClick={() => window.location.reload()}
          >
            Reload page
          </button>
          <Link to="/dashboard" className="ml-4 underline">
            Go to dashboard
          </Link>
        </section>
      );
    }
    return this.props.children;
  }
}

/** Keep navigation usable when a page or its downloaded module fails. */
export function RouteBoundary({ children }: { children: ReactNode }) {
  const location = useLocation();
  return (
    <PageErrorBoundary route={location.pathname}>
      <Suspense
        fallback={
          <div
            role="status"
            aria-live="polite"
            className="page-skeleton p-8 text-ink-muted"
          >
            Loading page…
          </div>
        }
      >
        {children}
      </Suspense>
    </PageErrorBoundary>
  );
}

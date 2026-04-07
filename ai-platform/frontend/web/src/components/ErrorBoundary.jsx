import { Component } from 'react';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    // You can log to your error tracking service here (e.g. Sentry)
    console.error('[Fixmeapp Booking Error]', error, info);
  }

  handleRestart = () => {
    this.setState({ hasError: false, error: null });
    // Let the parent App reset booking state via the onReset callback
    this.props.onReset?.();
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="flex flex-col items-center justify-center min-h-screen px-6 text-center animate-fade-in">
        {/* Error icon */}
        <div className="w-16 h-16 rounded-full bg-fixme-error/10 flex items-center justify-center mb-5">
          <svg className="w-8 h-8 text-fixme-error" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
        </div>

        <h2 className="text-xl font-semibold text-fixme-text-primary">Something went wrong</h2>
        <p className="text-sm text-fixme-text-secondary mt-2 max-w-xs">
          We hit an unexpected error. You can try starting over or head back to Instagram.
        </p>

        <div className="mt-8 w-full max-w-xs space-y-3">
          {/* Primary: restart — keeps them in the funnel */}
          <button
            onClick={this.handleRestart}
            className="w-full py-3.5 rounded-xl font-semibold text-base bg-fixme-accent text-fixme-bg hover:bg-fixme-accent-light active:scale-[0.98] transition-all duration-200"
          >
            Start booking again
          </button>

          {/* Secondary: back to Instagram */}
          <button
            onClick={() => { window.location.href = 'instagram://'; }}
            className="w-full py-3 rounded-xl text-sm font-medium text-fixme-text-secondary border border-fixme-border hover:border-fixme-text-muted transition-colors"
          >
            Back to Instagram
          </button>
        </div>
      </div>
    );
  }
}

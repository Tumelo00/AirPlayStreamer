import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: { componentStack?: string | null }) {
    console.error("[ErrorBoundary]", error, info);
  }

  reset = () => this.setState({ error: null });

  render() {
    if (this.state.error) {
      return (
        <div className="flex items-center justify-center h-full p-6">
          <div className="max-w-md text-center space-y-3">
            <h2 className="text-lg font-semibold text-red-400">
              Bir hata oluştu
            </h2>
            <pre className="text-xs text-zinc-400 bg-zinc-900 rounded p-3 overflow-auto max-h-48 text-left scrollbar-thin">
              {this.state.error.message}
            </pre>
            <button
              onClick={this.reset}
              className="bg-blue-600 hover:bg-blue-500 text-white rounded px-4 py-1.5 text-sm"
            >
              Devam et
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

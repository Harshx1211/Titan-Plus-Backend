'use client';

import React, { Component, ReactNode } from 'react';

interface ErrorBoundaryProps {
    children: ReactNode;
}

interface ErrorBoundaryState {
    hasError: boolean;
    error: Error | null;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
    constructor(props: ErrorBoundaryProps) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        console.error('Dashboard Error:', error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <main className="min-h-screen bg-[#010103] flex items-center justify-center p-6">
                    <div className="max-w-md text-center">
                        <div className="bg-rose-500/10 border border-rose-500/20 p-8 rounded">
                            <h1 className="text-rose-500 font-mono font-black text-xl uppercase tracking-widest mb-4">
                                System Error
                            </h1>
                            <p className="text-slate-400 font-mono text-sm mb-6">
                                The Oracle encountered an unexpected error. Please refresh the page.
                            </p>
                            <button
                                onClick={() => window.location.reload()}
                                className="px-6 py-3 bg-rose-500 hover:bg-rose-600 text-white font-mono font-black text-xs uppercase tracking-widest transition-colors"
                            >
                                Reload Dashboard
                            </button>
                        </div>
                    </div>
                </main>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;

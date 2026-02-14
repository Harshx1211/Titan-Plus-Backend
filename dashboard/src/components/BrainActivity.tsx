import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, Terminal } from 'lucide-react';

interface BrainActivityProps {
    thoughts: string[];
    thoughtEndRef: React.RefObject<HTMLDivElement>;
}

export const BrainActivity: React.FC<BrainActivityProps> = ({ thoughts, thoughtEndRef }) => {
    const scrollRef = React.useRef<HTMLDivElement>(null);

    React.useEffect(() => {
        if (scrollRef.current) {
            const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
            const isNearBottom = scrollHeight - scrollTop - clientHeight < 150;
            if (isNearBottom) {
                // INTERNAL SCROLL ONLY - Stops page level "dragging"
                scrollRef.current.scrollTop = scrollHeight;
            }
        }
    }, [thoughts]);

    return (
        <div className="glass-card rounded-xl p-5 h-[400px] flex flex-col">
            <div className="flex items-center gap-2 mb-4">
                <Brain className="w-5 h-5 text-purple-400" />
                <h2 className="text-lg font-bold text-slate-100">Neural Activity</h2>
                <div className="ml-auto w-2 h-2 rounded-full bg-purple-500 animate-pulse" />
            </div>

            <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto space-y-2 font-mono text-xs scrollbar-hide scroll-smooth"
            >
                <AnimatePresence initial={false}>
                    {thoughts.length === 0 ? (
                        <div className="flex items-center justify-center h-full text-slate-600">
                            <div className="text-center">
                                <Terminal className="w-8 h-8 mx-auto mb-2 opacity-50" />
                                <p>Initializing neural network...</p>
                            </div>
                        </div>
                    ) : (
                        thoughts.map((thought, index) => {
                            const isScanning = thought.includes('SCANNING');
                            const isFiltered = thought.includes('FILTERED') || thought.includes('REJECTED');
                            const isValidated = thought.includes('VALIDATED') || thought.includes('✅');
                            const isError = thought.includes('❌') || thought.includes('ERROR');

                            let bgColor = 'bg-slate-800/30';
                            let textColor = 'text-slate-400';
                            let borderColor = 'border-slate-700/30';

                            if (isValidated) {
                                bgColor = 'bg-emerald-500/10';
                                textColor = 'text-emerald-400';
                                borderColor = 'border-emerald-500/30';
                            } else if (isFiltered) {
                                bgColor = 'bg-yellow-500/10';
                                textColor = 'text-yellow-400';
                                borderColor = 'border-yellow-500/30';
                            } else if (isError) {
                                bgColor = 'bg-red-500/10';
                                textColor = 'text-red-400';
                                borderColor = 'border-red-500/30';
                            } else if (isScanning) {
                                bgColor = 'bg-blue-500/10';
                                textColor = 'text-blue-400';
                                borderColor = 'border-blue-500/30';
                            }

                            return (
                                <motion.div
                                    key={index}
                                    initial={{ opacity: 0, x: -20, height: 0 }}
                                    animate={{ opacity: 1, x: 0, height: 'auto' }}
                                    exit={{ opacity: 0, x: 20, height: 0 }}
                                    transition={{ duration: 0.3 }}
                                    className={`p-2 rounded border ${bgColor} ${borderColor} ${textColor}`}
                                >
                                    {thought}
                                </motion.div>
                            );
                        })
                    )}
                </AnimatePresence>
                <div ref={thoughtEndRef} />
            </div>

            <div className="mt-3 pt-3 border-t border-slate-700/50 text-xs text-slate-500">
                {thoughts.length} events logged
            </div>
        </div>
    );
};

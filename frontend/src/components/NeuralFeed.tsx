import React from 'react';
import { motion } from 'framer-motion';
import { Terminal } from 'lucide-react';

interface NeuralFeedProps {
    thoughts: string[];
    thoughtEndRef: React.RefObject<HTMLDivElement>;
}

export const NeuralFeed: React.FC<NeuralFeedProps> = ({ thoughts, thoughtEndRef }) => {
    return (
        <section className="glass-panel rounded-3xl p-6 h-[400px] flex flex-col">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-sky-400" />
                    <h3 className="text-xs font-bold uppercase tracking-widest text-slate-500">Neural Feed</h3>
                </div>
                <div className="w-1.5 h-1.5 rounded-full bg-sky-500 animate-ping" />
            </div>
            <div className="flex-1 overflow-y-auto space-y-3 font-mono text-[10px] scrollbar-hide pr-2">
                {thoughts.map((thought, i) => (
                    <motion.div
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        key={i}
                        className="text-slate-400 border-l border-sky-500/20 pl-3 py-1 bg-sky-500/5 rounded-r-lg"
                    >
                        {thought}
                    </motion.div>
                ))}
                <div ref={thoughtEndRef} />
            </div>
        </section>
    );
};

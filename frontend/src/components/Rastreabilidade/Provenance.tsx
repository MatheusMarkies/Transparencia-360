import React from 'react';
import { CheckCircle2, AlertCircle, Info } from 'lucide-react';

interface SourceTagProps {
    label: string;
    url: string;
}

export const SourceTag: React.FC<SourceTagProps> = ({ label, url }) => (
    <a
        href={url}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-100 hover:bg-indigo-100 border border-slate-200 hover:border-indigo-200 text-[10px] font-black text-slate-500 hover:text-indigo-600 transition-all uppercase tracking-widest"
    >
        <Info className="w-3 h-3" />
        {label}
    </a>
);

interface ConfidenceBadgeProps {
    level: 'High' | 'Medium' | 'Low';
}

export const ConfidenceBadge: React.FC<ConfidenceBadgeProps> = ({ level }) => {
    const styles = {
        High: 'bg-emerald-50 text-emerald-600 border-emerald-100',
        Medium: 'bg-amber-50 text-amber-600 border-amber-100',
        Low: 'bg-rose-50 text-rose-600 border-rose-100',
    };

    return (
        <div className={`px-3 py-1 rounded-full border text-[10px] font-black uppercase tracking-widest flex items-center gap-1.5 ${styles[level]}`}>
            {level === 'High' && <CheckCircle2 className="w-3 h-3" />}
            {level === 'Medium' && <AlertCircle className="w-3 h-3" />}
            {level === 'Low' && <AlertCircle className="w-3 h-3" />}
            Confiança {level}
        </div>
    );
};

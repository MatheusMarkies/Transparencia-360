import React from 'react';
import { ShieldAlert, AlertTriangle, CheckCircle } from 'lucide-react';

interface RiskFactor {
    factor: string;
    points: number;
}

interface RadarRiscoProps {
    score: number;
    details: string; // JSON string
}

const RadarRisco: React.FC<RadarRiscoProps> = ({ score, details }) => {
    const factors: RiskFactor[] = JSON.parse(details || '[]');

    const getScoreColor = (s: number) => {
        if (s > 70) return 'text-rose-500';
        if (s > 40) return 'text-amber-500';
        return 'text-emerald-500';
    };

    const getScoreBg = (s: number) => {
        if (s > 70) return 'bg-rose-50 border-rose-100';
        if (s > 40) return 'bg-amber-50 border-amber-100';
        return 'bg-emerald-50 border-emerald-100';
    };

    return (
        <div className="bg-white rounded-3xl shadow-xl p-8 border border-slate-100">
            <div className="flex justify-between items-center mb-8">
                <div>
                    <h3 className="text-xl font-black text-slate-800 uppercase tracking-tight">Radar de Rachadinha</h3>
                    <p className="text-sm font-bold text-slate-400">Análise Probabilística de Integridade</p>
                </div>
                <div className={`px-6 py-2 rounded-2xl ${getScoreBg(score)} border flex items-center gap-3`}>
                    <span className={`text-4xl font-black ${getScoreColor(score)}`}>{score}%</span>
                    <ShieldAlert className={`w-8 h-8 ${getScoreColor(score)}`} />
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {factors.map((f, i) => (
                    <div key={i} className="flex items-center justify-between p-4 bg-slate-50 rounded-2xl border border-slate-100 group hover:border-indigo-200 transition-all">
                        <div className="flex items-center gap-3">
                            <div className={`w-2 h-2 rounded-full ${f.points > 20 ? 'bg-rose-400' : 'bg-amber-400'}`} />
                            <span className="text-sm font-black text-slate-700 uppercase">{f.factor}</span>
                        </div>
                        <span className="text-xs font-bold text-slate-400">+{f.points} pts</span>
                    </div>
                ))}
            </div>

            <div className="mt-8 p-4 bg-indigo-50 rounded-2xl border border-indigo-100 flex gap-4 items-start">
                <AlertTriangle className="w-6 h-6 text-indigo-500 shrink-0" />
                <p className="text-xs font-bold text-indigo-800 leading-relaxed">
                    Este score é gerado via heurísticas que analisam: rotatividade de gabinete, depósitos fracionados,
                    uso de empresas de assessoria sem sede física e parentesco cruzado. Não constitui prova jurídica definitiva.
                </p>
            </div>
        </div>
    );
};

export default RadarRisco;

import React from 'react';
import { ShieldAlert, AlertTriangle } from 'lucide-react';

interface RiskFactor {
    heuristic: string;
    points: number;
    max: number;
    detail: string;
}

interface RadarRiscoProps {
    score: number;
    details: string; // JSON string
}

const RadarRisco: React.FC<RadarRiscoProps> = ({ score, details }) => {
    let factors: RiskFactor[] = [];
    try {
        factors = JSON.parse(details || '[]');
    } catch (e) {
        console.error("Falha ao fazer o parse dos detalhes de risco:", e);
    }

    const getScoreColor = (s: number) => {
        if (s >= 40) return 'text-rose-500';
        if (s >= 20) return 'text-amber-500';
        return 'text-emerald-500';
    };

    const getScoreBg = (s: number) => {
        if (s >= 40) return 'bg-rose-50 border-rose-100';
        if (s >= 20) return 'bg-amber-50 border-amber-100';
        return 'bg-emerald-50 border-emerald-100';
    };

    return (
        <div className="bg-white rounded-3xl shadow-xl p-8 border border-slate-100">
            <div className="flex justify-between items-center mb-8">
                <div>
                    <h3 className="text-xl font-black text-slate-800 uppercase tracking-tight">Radar de Rachadinha</h3>
                    <p className="text-sm font-bold text-slate-400">Análise Probabilística de Integridade (Motor v2.0)</p>
                </div>
                <div className={`px-6 py-2 rounded-2xl ${getScoreBg(score)} border flex items-center gap-3`}>
                    <span className={`text-4xl font-black ${getScoreColor(score)}`}>{score}%</span>
                    <ShieldAlert className={`w-8 h-8 ${getScoreColor(score)}`} />
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {factors.map((f, i) => (
                    <div key={i} className="flex flex-col justify-between p-4 bg-slate-50 rounded-2xl border border-slate-100 group hover:border-indigo-200 transition-all">
                        <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-3">
                                <div className={`w-2 h-2 rounded-full ${f.points > 0 ? (f.points >= (f.max / 2) ? 'bg-rose-400' : 'bg-amber-400') : 'bg-emerald-400'}`} />
                                <span className="text-xs font-black text-slate-700 uppercase">{f.heuristic || 'Fator Desconhecido'}</span>
                            </div>
                            <span className={`text-xs font-black ${f.points > 0 ? 'text-rose-500' : 'text-emerald-500'}`}>
                                +{f.points} pts
                            </span>
                        </div>
                        <p className="text-[10px] font-bold text-slate-500 leading-relaxed">{f.detail}</p>
                    </div>
                ))}
            </div>

            <div className="mt-8 p-4 bg-indigo-50 rounded-2xl border border-indigo-100 flex gap-4 items-start">
                <AlertTriangle className="w-6 h-6 text-indigo-500 shrink-0" />
                <p className="text-[10px] font-bold text-indigo-800 leading-relaxed uppercase tracking-wider">
                    Score gerado via heurísticas reais: cruzamento de despesas CEAP com quadro societário (QSA) via Brasil API, histórico do DataJud e NLP em Diários Oficiais.
                </p>
            </div>
        </div>
    );
};

export default RadarRisco;
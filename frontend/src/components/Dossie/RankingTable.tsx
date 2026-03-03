import React from 'react';
import { TrendingUp, ShieldCheck, AlertTriangle } from 'lucide-react';

interface Politician {
    id: number;
    externalId: string;
    name: string;
    party: string;
    state: string;
    position: string;
    expenses?: number;
    absences?: number;
    wealthAnomaly?: number;
    overallRiskScore?: number; // Adicionada a propriedade da IA
}

interface RankingTableProps {
    politicians: Politician[];
    onSelect: (p: Politician) => void;
}

const RankingTable: React.FC<RankingTableProps> = ({ politicians, onSelect }) => {
    // Agora a tabela ordena os políticos pelo MAIOR Risco Global primeiro.
    // Se empatar, ordena por quem gastou mais.
    const sorted = [...politicians].sort((a, b) => {
        const scoreA = a.overallRiskScore || 0;
        const scoreB = b.overallRiskScore || 0;
        if (scoreB !== scoreA) {
            return scoreB - scoreA;
        }
        return (b.expenses || 0) - (a.expenses || 0);
    });

    const formatCurrency = (val: number) => {
        return `R$ ${(val / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })}k`;
    };

    return (
        <div className="bg-white rounded-3xl shadow-xl overflow-hidden border border-slate-100">
            <div className="p-6 border-b border-slate-100 flex justify-between items-center">
                <h3 className="text-lg font-black text-slate-800 uppercase tracking-tight">Ranking de Risco</h3>
                <span className="bg-slate-100 px-3 py-1 rounded-full text-xs font-black text-slate-500 uppercase tracking-widest">Top Alertas</span>
            </div>
            <div className="overflow-x-auto">
                <table className="w-full text-left">
                    <thead className="bg-slate-50/50">
                        <tr>
                            <th className="p-4 text-[10px] font-black uppercase text-slate-400 tracking-widest">Pos</th>
                            <th className="p-4 text-[10px] font-black uppercase text-slate-400 tracking-widest">Parlamentar</th>
                            <th className="p-4 text-[10px] font-black uppercase text-slate-400 tracking-widest">Custo Cota</th>
                            <th className="p-4 text-[10px] font-black uppercase text-slate-400 tracking-widest">Risco Global</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                        {sorted.map((p, i) => {
                            // Lógica de cores do semáforo
                            const score = p.overallRiskScore || 0;
                            const isHighRisk = score >= 60;
                            const isMediumRisk = score >= 30 && score < 60;

                            let badgeClass = 'bg-emerald-50 text-emerald-600'; // Ficha limpa
                            if (isHighRisk) badgeClass = 'bg-rose-50 text-rose-600'; // Perigo
                            else if (isMediumRisk) badgeClass = 'bg-amber-50 text-amber-600'; // Atenção

                            return (
                                <tr
                                    key={p.id}
                                    className="hover:bg-indigo-50/30 transition-colors cursor-pointer group"
                                    onClick={() => onSelect(p)}
                                >
                                    <td className="p-4">
                                        <span className="text-sm font-black text-slate-300 group-hover:text-indigo-600 transition-colors">#{i + 1}</span>
                                    </td>
                                    <td className="p-4">
                                        <div className="flex flex-col">
                                            <span className="text-sm font-black text-slate-800 tracking-tight">{p.name}</span>
                                            <span className="text-[10px] font-bold text-slate-400 uppercase">{p.party} • {p.state}</span>
                                        </div>
                                    </td>
                                    <td className="p-4">
                                        <span className="text-sm font-black text-slate-700">{formatCurrency(p.expenses || 0)}</span>
                                    </td>
                                    <td className="p-4">
                                        <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-black uppercase tracking-wider ${badgeClass}`}>
                                            {/* Muda o ícone dinamicamente dependendo da gravidade */}
                                            {isHighRisk ? <AlertTriangle className="w-3 h-3" /> :
                                                isMediumRisk ? <TrendingUp className="w-3 h-3" /> :
                                                    <ShieldCheck className="w-3 h-3" />}

                                            {p.overallRiskScore != null ? `${score.toFixed(1)} / 100` : 'Processando'}
                                        </div>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default RankingTable;
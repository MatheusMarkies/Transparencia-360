import React from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';

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
}

interface RankingTableProps {
    politicians: Politician[];
    onSelect: (p: Politician) => void;
}

const RankingTable: React.FC<RankingTableProps> = ({ politicians, onSelect }) => {
    const sorted = [...politicians].sort((a, b) => (b.expenses || 0) - (a.expenses || 0));

    const formatCurrency = (val: number) => {
        return `R$ ${(val / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })}k`;
    };

    return (
        <div className="bg-white rounded-3xl shadow-xl overflow-hidden border border-slate-100">
            <div className="p-6 border-b border-slate-100 flex justify-between items-center">
                <h3 className="text-lg font-black text-slate-800 uppercase tracking-tight">Ranking de Custos</h3>
                <span className="bg-slate-100 px-3 py-1 rounded-full text-xs font-black text-slate-500 uppercase tracking-widest">Top Gastadores</span>
            </div>
            <div className="overflow-x-auto">
                <table className="w-full text-left">
                    <thead className="bg-slate-50/50">
                        <tr>
                            <th className="p-4 text-[10px] font-black uppercase text-slate-400 tracking-widest">Pos</th>
                            <th className="p-4 text-[10px] font-black uppercase text-slate-400 tracking-widest">Parlamentar</th>
                            <th className="p-4 text-[10px] font-black uppercase text-slate-400 tracking-widest">Custo Cota</th>
                            <th className="p-4 text-[10px] font-black uppercase text-slate-400 tracking-widest">Anomalia</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                        {sorted.map((p, i) => (
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
                                    <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-black uppercase tracking-wider
                    ${(p.wealthAnomaly || 0) > 1 ? 'bg-rose-50 text-rose-600' : 'bg-emerald-50 text-emerald-600'}`}>
                                        {(p.wealthAnomaly || 0) > 1 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                                        {p.wealthAnomaly ? `${p.wealthAnomaly.toFixed(1)}x` : 'N/A'}
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default RankingTable;

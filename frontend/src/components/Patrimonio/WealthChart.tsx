import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

interface WealthChartProps {
    data: { year: string; value: number }[];
}

const WealthChart: React.FC<WealthChartProps> = ({ data }) => {
    const formatCurrency = (val: number) => {
        return (val / 1000000).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + 'M';
    };

    return (
        <div className="bg-white rounded-3xl shadow-xl p-8 border border-slate-100 h-[400px]">
            <div className="mb-6">
                <h3 className="text-xl font-black text-slate-800 uppercase tracking-tight">Evolução Patrimonial</h3>
                <p className="text-sm font-bold text-slate-400 font-mono tracking-tighter">Dados extraídos do TSE (Bens Declarados)</p>
            </div>

            <ResponsiveContainer width="100%" height="80%">
                <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis
                        dataKey="year"
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: '#94a3b8', fontSize: 12, fontWeight: 700 }}
                    />
                    <YAxis
                        hide
                    />
                    <Tooltip
                        cursor={{ fill: '#f8fafc' }}
                        content={({ active, payload }) => {
                            if (active && payload && payload.length) {
                                return (
                                    <div className="bg-slate-900 px-4 py-2 rounded-xl shadow-2xl border border-slate-800">
                                        <p className="text-[10px] font-black uppercase text-indigo-400 mb-1">{payload[0].payload.year}</p>
                                        <p className="text-lg font-black text-white">R$ {payload[0].value?.toLocaleString('pt-BR')}</p>
                                    </div>
                                );
                            }
                            return null;
                        }}
                    />
                    <Bar dataKey="value" radius={[8, 8, 8, 8]} barSize={50}>
                        {data.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={index === data.length - 1 ? '#4338ca' : '#cbd5e1'} />
                        ))}
                    </Bar>
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
};

export default WealthChart;

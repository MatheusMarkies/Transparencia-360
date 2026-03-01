import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Search, CheckCircle2, ShieldAlert, Users, Building2, X } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
// Force Graph must be imported natively
import ForceGraph2D from 'react-force-graph-2d';
import { ReactFlow, Background, Controls, type Edge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

// Data shapes matching the Backend
interface Politician {
  id: number;
  name: string;
  party: string;
  state: string;
  position: string;
  absences?: number;
  expenses?: number;
  stateAffinity?: number;
  propositions?: number;
  frentes?: number;
  declaredAssets?: number;
  declaredAssets2018?: number;
  declaredAssets2014?: number;
  wealthAnomaly?: number;
  staffAnomalyCount?: number;
  staffAnomalyDetails?: string;
  cabinetRiskScore?: number;
  cabinetRiskDetails?: string;
  ghostEmployeeCount?: number;
  ghostEmployeeDetails?: string;
  nlpGazetteDetails?: string;
  cabinetSize?: number;
  cabinetDetails?: string;
}

const App = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [politicians, setPoliticians] = useState<Politician[]>([]);
  const [selectedPolitician, setSelectedPolitician] = useState<Politician | null>(null);
  const [loading, setLoading] = useState(false);
  const [graphData, setGraphData] = useState<any>({ nodes: [], links: [] });
  const [allPoliticians, setAllPoliticians] = useState<Politician[]>([]);
  const [crossMatchData, setCrossMatchData] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<'geral' | 'gabinete' | 'grafo' | 'inteligencia'>('geral');

  // Rachadinha Modals
  const [selectedProofUrl, setSelectedProofUrl] = useState<string | null>(null);

  const BACKEND_URL = 'http://localhost:8080/api/v1';

  // Deputy annual cost constants (2024 values)
  const SALARY_ANNUAL = 528_000;          // R$44k/month x 12
  const HOUSING_ANNUAL = 51_036;          // Auxílio moradia R$4.253/month
  const OFFICE_BUDGET_ANNUAL = 1_340_100; // Verba de gabinete R$111.675/month
  const HEALTH_PLAN_ANNUAL = 36_000;      // Plano de saúde ~R$3k/month
  const BASE_COST = SALARY_ANNUAL + HOUSING_ANNUAL + OFFICE_BUDGET_ANNUAL + HEALTH_PLAN_ANNUAL;

  const formatCurrency = (val: number, precise = false) => {
    if (Math.abs(val) >= 1000000) {
      return `R$ ${(val / 1000000).toLocaleString('pt-BR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      })}M`;
    }
    if (Math.abs(val) >= 1000) {
      return `R$ ${(val / 1000).toLocaleString('pt-BR', {
        minimumFractionDigits: precise ? 1 : 0,
        maximumFractionDigits: 1
      })}k`;
    }
    return `R$ ${val.toLocaleString('pt-BR')}`;
  };

  // Fetch all politicians on mount for ranking comparison
  useEffect(() => {
    const fetchAll = async () => {
      try {
        const resp = await axios.get(`${BACKEND_URL}/politicians/search?name=`);
        setAllPoliticians(resp.data);
      } catch (e) { console.error(e); }
    };
    fetchAll();
  }, []);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setLoading(true);
    try {
      const resp = await axios.get(`${BACKEND_URL}/politicians/search?name=${searchQuery}`);
      setPoliticians(resp.data);
      setSelectedPolitician(null);
    } catch (error) {
      console.error("Error fetching politicians", error);
    } finally {
      setLoading(false);
    }
  };

  const loadPoliticianGraph = async (id: number) => {
    try {
      const resp = await axios.get(`http://localhost:8080/api/graph/triangulation/${id}`);
      if (resp.data.length === 0) {
        const fallback = await axios.get(`http://localhost:8080/api/graph/network/${id}`);
        if (fallback.data.length > 0) {
          setGraphData({ nodes: fallback.data[0].nodes, links: fallback.data[0].links });
        } else {
          setGraphData({ nodes: [], links: [] });
        }
      } else {
        setGraphData({ nodes: resp.data[0].nodes, links: resp.data[0].links });
      }
    } catch (error) {
      console.error("Error loading graph", error);
      setGraphData({ nodes: [], links: [] });
    }
  };

  const loadCrossMatchData = async (id: number, name: string) => {
    try {
      const resp = await axios.get(`${BACKEND_URL}/politicians/${id}/sources`);
      setCrossMatchData({ sources: resp.data, politicianName: name });
    } catch (e) {
      setCrossMatchData({ sources: [], politicianName: name });
    }
  };

  const selectPolitician = (p: Politician) => {
    setSelectedPolitician(p);
    loadPoliticianGraph(p.id);
    loadCrossMatchData(p.id, p.name);
    setActiveTab('geral');
  };

  return (
    <div className="w-full min-h-screen bg-[#F8FAFC] flex flex-col font-sans relative overflow-hidden">
      <div className="absolute top-0 left-0 w-full h-96 bg-gradient-to-b from-indigo-900 via-indigo-800 to-transparent -z-10"></div>

      <header className="sticky top-0 z-50 bg-indigo-900/90 backdrop-blur-xl border-b border-indigo-700/50 shadow-2xl">
        <div className="w-full px-6 md:px-12 py-4 flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="bg-gradient-to-br from-indigo-500 to-blue-500 p-3 rounded-2xl shadow-lg shadow-blue-500/30 border border-white/10">
              <Search className="text-white w-6 h-6" />
            </div>
            <div>
              <h1 className="text-3xl font-black text-white tracking-tight flex items-center gap-2">
                Transparência <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-indigo-300">360</span>
              </h1>
              <p className="text-indigo-200/80 text-base font-semibold tracking-widest uppercase">Inteligência Política</p>
            </div>
          </div>

          <form onSubmit={handleSearch} className="w-full sm:w-1/2 relative group">
            <input
              type="text"
              placeholder="Busque por nome, cargo ou estado..."
              className="w-full pl-6 pr-16 py-4 rounded-2xl border-0 bg-white/10 text-white placeholder-indigo-200/50 focus:outline-none focus:ring-2 focus:ring-blue-400 shadow-inner backdrop-blur-md transition-all duration-300 hover:bg-white/15"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <button
              type="submit"
              className="absolute right-2 top-1/2 -translate-y-1/2 p-3 bg-gradient-to-br from-blue-500 to-indigo-600 text-white rounded-xl hover:shadow-[0_0_20px_rgba(59,130,246,0.5)] transition-all duration-300 disabled:opacity-50"
              disabled={loading}
            >
              <Search className="w-5 h-5" />
            </button>
          </form>
        </div>
      </header>

      <main className="flex-1 w-full px-6 md:px-12 py-8 flex flex-col md:flex-row gap-8">
        {/* Left Sidebar */}
        <div className="w-full md:w-80 flex-shrink-0 flex flex-col gap-4">
          <div className="flex items-center justify-between px-1">
            <h2 className="text-base font-black text-slate-800 uppercase tracking-widest flex items-center gap-2">
              <Users className="w-4 h-4 text-indigo-600" /> Resultados
            </h2>
            {politicians.length > 0 && <span className="bg-white px-2 py-0.5 rounded-full text-sm font-bold text-slate-500 shadow-sm border border-slate-200">{politicians.length}</span>}
          </div>

          <div className="bg-white/60 backdrop-blur-xl rounded-3xl shadow-xl shadow-slate-200/50 border border-white/60 overflow-hidden flex flex-col h-[calc(100vh-200px)]">
            {loading ? (
              <div className="flex-1 flex flex-col items-center justify-center p-8 gap-4 text-indigo-900/40">
                <div className="w-8 h-8 rounded-full border-4 border-indigo-100 border-t-indigo-500 animate-spin"></div>
                <span className="text-base font-bold animate-pulse">Consultando bases...</span>
              </div>
            ) : politicians.length === 0 ? (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-400">
                <Users className="w-10 h-10 mb-4 opacity-20" />
                <p className="font-bold text-slate-600">Busque um parlamentar acima</p>
              </div>
            ) : (
              <ul className="overflow-y-auto flex-1 p-2 space-y-2 custom-scrollbar">
                {politicians.map(p => {
                  const isSelected = selectedPolitician?.id === p.id;
                  return (
                    <li key={p.id}>
                      <button
                        onClick={() => selectPolitician(p)}
                        className={`w-full text-left p-4 rounded-2xl transition-all duration-300 flex flex-col gap-2 border
                          ${isSelected
                            ? 'bg-gradient-to-br from-indigo-500 to-blue-600 border-transparent shadow-lg text-white'
                            : 'bg-white border-transparent hover:border-indigo-100 hover:bg-indigo-50/50'
                          }`}
                      >
                        <span className="font-black text-base leading-tight">{p.name}</span>
                        <div className="flex items-center gap-2">
                          <span className={`text-xs font-black uppercase tracking-wider px-2 py-1 rounded-md ${isSelected ? 'bg-white/20' : 'bg-slate-100 text-slate-500'}`}>
                            {p.party}
                          </span>
                          <span className={`text-xs font-bold ${isSelected ? 'text-indigo-100' : 'text-slate-400'}`}>
                            {p.state} • {p.position}
                          </span>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>

        {/* Right Area */}
        <div className="flex-1 flex flex-col gap-6 min-w-0">
          {selectedPolitician ? (
            <>
              <div className="bg-white rounded-3xl shadow-xl border border-white overflow-hidden">
                <div className="p-6 lg:p-8 flex flex-col xl:flex-row gap-8 items-start xl:items-center justify-between">
                  <div className="flex-1">
                    <div className="inline-flex items-center gap-2 px-3 py-1 bg-indigo-50 rounded-full text-indigo-600 text-[10px] font-black uppercase tracking-widest mb-4">
                      Análise em Tempo Real
                    </div>
                    <h2 className="text-4xl font-black text-slate-800 tracking-tight mb-2">{selectedPolitician.name}</h2>
                    <p className="text-sm font-bold flex items-center gap-2 text-slate-500">
                      <span className="bg-slate-100 px-2 py-0.5 rounded-md">{selectedPolitician.party}</span>
                      <span>•</span> {selectedPolitician.state} <span>•</span> {selectedPolitician.position}
                    </p>
                  </div>

                  <div className="flex gap-4 w-full xl:w-auto overflow-x-auto pb-2 custom-scrollbar">
                    {/* Metrics here - omitted for brevity but can be expanded if needed */}
                    <div className="shrink-0 w-40 bg-slate-50 rounded-2xl p-4 border border-slate-100">
                      <p className="text-[10px] font-black text-slate-400 uppercase mb-1">Gasto Cota (2025)</p>
                      <p className="text-xl font-black text-slate-800">{formatCurrency(selectedPolitician.expenses || 0)}</p>
                    </div>
                    <div className="shrink-0 w-40 bg-slate-50 rounded-2xl p-4 border border-slate-100">
                      <p className="text-[10px] font-black text-slate-400 uppercase mb-1">Faltas</p>
                      <p className="text-xl font-black text-slate-800">{selectedPolitician.absences || 0} dias</p>
                    </div>
                  </div>
                </div>

                <div className="bg-slate-50/50 border-t border-slate-100 px-6 py-3 flex flex-wrap items-center gap-2">
                  {[
                    { id: 'geral', label: 'Visão Geral', icon: '📊' },
                    { id: 'gabinete', label: 'Gabinete', icon: '🏛️' },
                    { id: 'grafo', label: 'Grafo', icon: '🕸️' },
                    { id: 'inteligencia', label: 'Deep Match', icon: '🔍' },
                  ].map(tab => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id as any)}
                      className={`px-4 py-2 rounded-xl text-xs font-black transition-all flex items-center gap-2 border
                        ${activeTab === tab.id
                          ? 'bg-white text-indigo-600 border-indigo-100 shadow-sm'
                          : 'text-slate-500 border-transparent hover:bg-white/80'
                        }`}
                    >
                      {tab.icon} {tab.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex flex-col gap-6">
                {activeTab === 'geral' && (
                  <div className="bg-white rounded-3xl shadow-xl p-6 border border-slate-100">
                    <h3 className="text-lg font-black text-slate-800 uppercase mb-4">Evolução Patrimonial</h3>
                    <div className="h-64">
                      {/* Chart Placeholder or implementation */}
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={[
                          { year: '2014', val: selectedPolitician.declaredAssets2014 || 0 },
                          { year: '2018', val: selectedPolitician.declaredAssets2018 || 0 },
                          { year: '2022', val: selectedPolitician.declaredAssets || 0 },
                        ]}>
                          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                          <XAxis dataKey="year" axisLine={false} tickLine={false} tick={{ fontSize: 10, fontWeight: 700 }} />
                          <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fontWeight: 700 }} tickFormatter={v => `R$${v / 1000}k`} />
                          <Tooltip />
                          <Area type="monotone" dataKey="val" stroke="#6366f1" fill="#e0e7ff" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}

                {activeTab === 'gabinete' && (
                  <div className="bg-white rounded-3xl shadow-xl overflow-hidden border border-slate-100">
                    <table className="w-full text-left">
                      <thead className="bg-slate-50 font-black text-[10px] uppercase text-slate-500 tracking-widest">
                        <tr>
                          <th className="p-4">Assessor</th>
                          <th className="p-4">Cargo</th>
                          <th className="p-4">Salário</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 text-sm">
                        {(() => {
                          try {
                            const staff = JSON.parse(selectedPolitician.cabinetDetails || '[]');
                            return staff.map((s: any, i: number) => (
                              <tr key={i} className="hover:bg-slate-50">
                                <td className="p-4 font-bold">{s.name}</td>
                                <td className="p-4 text-slate-500">{s.role}</td>
                                <td className="p-4 font-black text-slate-700">{formatCurrency(s.salary || 0)}</td>
                              </tr>
                            ));
                          } catch (e) { return null; }
                        })()}
                      </tbody>
                    </table>
                  </div>
                )}

                {activeTab === 'grafo' && (
                  <div className="bg-white rounded-3xl shadow-xl h-[500px] border border-slate-100 overflow-hidden">
                    <ForceGraph2D
                      graphData={graphData}
                      nodeLabel="name"
                      nodeAutoColorBy="group"
                      width={800}
                      height={500}
                    />
                  </div>
                )}

                {activeTab === 'inteligencia' && (
                  <div className="flex flex-col gap-6">
                    {/* Anomaly Panels */}
                    {selectedPolitician.cabinetRiskScore != null && (
                      <div className="bg-white rounded-3xl shadow-xl p-6 border border-slate-100">
                        <div className="flex justify-between items-center mb-4">
                          <h3 className="font-black text-slate-800 uppercase">Radar de Rachadinha</h3>
                          <span className="text-2xl font-black text-rose-500">{selectedPolitician.cabinetRiskScore}%</span>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          {JSON.parse(selectedPolitician.cabinetRiskDetails || '[]').map((d: any, i: number) => (
                            <div key={i} className="bg-slate-50 p-3 rounded-xl border border-slate-100 text-xs font-bold text-slate-600 flex items-center gap-2">
                              <div className="w-2 h-2 rounded-full bg-rose-400" /> {d.factor}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {selectedPolitician.staffAnomalyCount != null && selectedPolitician.staffAnomalyCount > 0 && (
                      <div className="bg-white rounded-3xl shadow-xl p-6 border border-slate-100">
                        <h3 className="font-black text-slate-800 uppercase mb-4">🏢 Fornecedores Suspeitos ({selectedPolitician.staffAnomalyCount})</h3>
                        <div className="space-y-3">
                          {JSON.parse(selectedPolitician.staffAnomalyDetails || '[]').map((a: any, i: number) => (
                            <div key={i} className="p-4 rounded-2xl bg-amber-50 border border-amber-100">
                              <div className="flex justify-between mb-2">
                                <span className="font-black text-slate-800 uppercase text-xs">{a.supplier || a.name}</span>
                                <span className="font-black text-slate-700 text-xs">{formatCurrency(a.totalValue || a.salary || 0)}</span>
                              </div>
                              <p className="text-xs font-medium text-slate-600">{a.detail}</p>
                              {a.evidence_url && (
                                <button onClick={() => setSelectedProofUrl(a.evidence_url)} className="mt-2 text-[10px] font-black text-indigo-600 hover:underline">📄 VER PROVA DOCUMENTAL</button>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="flex-1 bg-white/40 backdrop-blur-xl rounded-3xl border border-white flex flex-col items-center justify-center p-12 text-center">
              <Search className="w-16 h-16 text-indigo-300 mb-6" />
              <h3 className="text-2xl font-black text-slate-800 mb-2">Selecione um parlamentar</h3>
              <p className="text-slate-500 font-medium">Inicie a análise de integridade cruzada</p>
            </div>
          )}
        </div>
      </main>

      {selectedProofUrl && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-5xl h-[85vh] flex flex-col overflow-hidden">
            <div className="p-4 border-b flex justify-between items-center bg-slate-50">
              <span className="font-black text-xs uppercase tracking-widest text-slate-500">Visualizador de Evidências</span>
              <button onClick={() => setSelectedProofUrl(null)} className="p-2 hover:bg-slate-200 rounded-full"><X className="w-5 h-5" /></button>
            </div>
            <iframe src={selectedProofUrl} className="flex-1 w-full border-0" title="Proof" />
          </div>
        </div>
      )}

      <style>{`
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #E2E8F0; border-radius: 10px; }
      `}</style>
    </div>
  );
};

export default App;

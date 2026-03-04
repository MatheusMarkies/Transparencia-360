import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Search,
  TrendingUp,
  ShieldAlert,
  Database,
  ChevronRight,
  LayoutDashboard,
  Cpu,
  Network,
  BarChart3,
  AlertCircle,
  Users,
  Bot,
  Calculator,
  Copy,
  CalendarOff,
  Stethoscope,
  ShoppingBag
} from 'lucide-react';
import ForceGraph2D from 'react-force-graph-2d';

// New specialized components
import RadarRisco from './components/RadarRisco';
import RankingTable from './components/Dossie/RankingTable';
import WealthChart from './components/Patrimonio/WealthChart';
import PoliticianCard from './components/Dossie/PoliticianCard';
import { SourceTag, ConfidenceBadge } from './components/Rastreabilidade/Provenance';

const BACKEND_URL = 'http://localhost:8080/api/v1';

interface Politician {
  id: number;
  externalId: string;
  name: string;
  party: string;
  state: string;
  position: string;
  expenses?: number;
  absences?: number;
  presences?: number;
  wealthAnomaly?: number;
  cabinetRiskScore?: number;
  cabinetRiskDetails?: string;
  declaredAssets?: number;
  declaredAssets2018?: number;
  declaredAssets2014?: number;
  staffAnomalyCount?: number;
  staffAnomalyDetails?: string;
  detailedExpenses?: any[];
  // --- NOVOS CAMPOS ---
  nlpGazetteCount?: number;
  nlpGazetteScore?: number;
  nlpGazetteDetails?: string;
  judicialRiskScore?: number;
  judicialRiskDetails?: string;

  rosieBenfordCount?: number;
  rosieDuplicateCount?: number;
  rosieWeekendCount?: number;
  rosieHealthCount?: number;
  rosieLuxuryCount?: number;
}

function App() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Politician[]>([]);
  const [selectedPolitician, setSelectedPolitician] = useState<Politician | null>(null);
  const [allPoliticians, setAllPoliticians] = useState<Politician[]>([]);
  const [activeTab, setActiveTab] = useState<'geral' | 'inteligencia' | 'grafo' | 'fontes' | 'despesas' | 'emendas'>('geral');
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [sources, setSources] = useState<any[]>([]);
  const [expensesList, setExpensesList] = useState<any[]>([]);
  const [emendasList, setEmendasList] = useState<any[]>([]);

  const [topSuppliers, setTopSuppliers] = useState<any[]>([]);
  const [categoryExpenses, setCategoryExpenses] = useState<any[]>([]);

  const fgRef = useRef<any>(null);

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (fgRef.current) {
        fgRef.current.d3Force('charge').strength(-2000);
        fgRef.current.d3Force('link').distance(300);
        fgRef.current.d3ReheatSimulation();
      }
    }, 100); // 100 milissegundos de atraso

    return () => clearTimeout(timeoutId);
  }, [graphData]);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const resp = await axios.get(`${BACKEND_URL}/politicians/search?name=`);
        setAllPoliticians(resp.data);
      } catch (e) { console.error("Error fetching all politicians for ranking:", e); }
    };
    fetchAll();
  }, []);

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;
    try {
      const resp = await axios.get(`${BACKEND_URL}/politicians/search?name=${query}`);
      setResults(resp.data);
    } catch (e) { console.error(e); }
  };

  const selectPolitician = async (p: Politician) => {
    setSelectedPolitician(p);
    setResults([]);
    setQuery('');

    // Fetch Graph
    // Fetch Graph (Follow the Money - Neo4j Real)
    try {
      // Chama o GraphController.java que acessa o Neo4j diretamente
      const gResp = await axios.get(`http://localhost:8080/api/graph/network/${p.externalId}`);

      if (gResp.data && gResp.data.length > 0) {
        const rawGraph = gResp.data[0];

        // ---> NOVO: RADAR DE EMPRESAS SUSPEITAS PELA IA <---
        // ---> RADAR DE LAVAGEM DE DINHEIRO (Busca as empresas marcadas pela IA) <---
        let fornecedoresSuspeitos: string[] = [];
        try {
          if (p.staffAnomalyDetails) {
            const anomalias = JSON.parse(p.staffAnomalyDetails);
            fornecedoresSuspeitos = anomalias.map((a: any) => (a.supplier || a.nomeFornecedor || a.name || '').toUpperCase());
          }
        } catch (e) { }

        const formatCurrency = (val: any) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val);

        // 1. MOLDANDO AS BOLHAS (Nós)
        const formattedNodes = rawGraph.nodes.map((n: any) => {
          let nodeName = n.labels[0];
          let nodeSize = 5;
          let nodeColor = undefined;

          if (n.labels.includes("Politico")) {
            nodeName = `🏛️ ${n.properties.name}`;
            nodeSize = 40; // Deputado Gigante no centro
            nodeColor = "#0f172a";
          }
          else if (n.labels.includes("Emenda")) {
            nodeName = `💸 Emenda ${n.properties.ano} = ${formatCurrency(n.properties.valor || 0)}`;
            nodeSize = Math.max(10, (n.properties.valor || 0) / 100000); // Cresce conforme o milhão
            nodeColor = "#10b981"; // Verde Dinheiro
          }
          else if (n.labels.includes("Municipio")) {
            nodeName = `📍 ${n.properties.codigoIbge.startsWith('ESTADO') ? n.properties.codigoIbge : 'Pref. IBGE ' + n.properties.codigoIbge}`;
            nodeSize = 15;
            nodeColor = "#3b82f6"; // Azul
          }
          else if (n.labels.includes("DespesaAgrupada")) {
            const valorStr = formatCurrency(n.properties.valorDocumento || 0);
            const qtd = n.properties.qtd;
            const fornecedorNome = n.properties.nomeFornecedor || '';

            nodeName = qtd > 1 ? `🛒 ${fornecedorNome} (${qtd} notas) = ${valorStr}` : `🛒 ${fornecedorNome} = ${valorStr}`;
            nodeSize = Math.max(6, Math.min(30, (n.properties.valorDocumento || 0) / 2000));
            nodeColor = "#f59e0b"; // Laranja/Amarelo

            if (fornecedoresSuspeitos.some(sus => fornecedorNome.toUpperCase().includes(sus))) {
              nodeName = `🚨 ANOMALIA ML: ${nodeName}`;
              nodeSize = nodeSize * 1.5;
              nodeColor = "#ef4444"; // Vermelho Alerta
            }
          }
          else if (n.labels.includes("Empresa")) {
            nodeName = `🏢 ${n.properties.name || 'CNPJ ' + n.properties.cnpj}`;
            nodeSize = 20;
            nodeColor = "#64748b"; // Cinza
          }
          else if (n.labels.includes("Pessoa")) {
            nodeName = `👤 Sócio/Doador: ${n.properties.nome || 'Sigiloso'}`;
            nodeSize = 14;
            nodeColor = "#a855f7"; // Roxo
          }

          return { id: n.id, name: nodeName, group: n.labels[0], val: nodeSize, color: nodeColor };
        });

        // 2. MOLDANDO OS FIOS E AS PARTÍCULAS (Arestas)
        const formattedLinks = rawGraph.links.map((l: any) => {
          let linkColor = "#cbd5e1";
          let linkWidth = 1;
          let particles = 0;
          const type = l.type;

          if (type === "ENVIOU_EMENDA" || type === "DESTINADA_A") {
            linkColor = "#34d399"; // Fio Verde (Emenda)
            linkWidth = 2;
            particles = 3;
          } else if (type === "CONTRATOU") {
            linkColor = "#94a3b8"; // Fio Cinza
            linkWidth = 2;
            particles = 2;
          } else if (type === "DOOU_PARA_CAMPANHA") {
            linkColor = "#c084fc"; // Fio Roxo (Retorno de Propina/Doação)
            linkWidth = 4;
            particles = 6;
          } else if (type === "PAGOU_DESPESA") {
            linkColor = "#fcd34d"; // Fio Amarelo
            particles = 2;
          }

          // Se o destino for uma empresa fantasma apanhada pela IA:
          const targetId = String(l.target).toUpperCase();
          if (fornecedoresSuspeitos.some(sus => targetId.includes(sus))) {
            linkColor = "#ef4444"; // Fio Vermelho
            linkWidth = 4;
            particles = 8; // Fluxo de dinheiro super acelerado!
          }

          return { source: l.source, target: l.target, label: l.type, color: linkColor, width: linkWidth, particles: particles };
        });

        // 3. Remove duplicações de segurança do Grafo
        const uniqueNodes = Array.from(new Map(formattedNodes.map((item: any) => [item.id, item])).values());
        const uniqueLinks = Array.from(new Map(formattedLinks.map((item: any) => [`${item.source}-${item.target}-${item.label}`, item])).values());

        setGraphData({ nodes: uniqueNodes as any, links: uniqueLinks as any });
      } else {
        setGraphData({ nodes: [], links: [] });
      }
    } catch (e) {
      console.error("Erro ao buscar o Grafo de Dinheiro:", e);
      setGraphData({ nodes: [], links: [] });
    }

    try {
      const expResp = await axios.get(`${BACKEND_URL}/politicians/${p.id}/expenses`);
      setExpensesList(expResp.data);
    } catch (e) { console.error(e); }

    try {
      const emResp = await axios.get(`${BACKEND_URL}/politicians/${p.id}/emendas`);
      setEmendasList(emResp.data);
    } catch (e) { console.error(e); }

    // Fetch Dashboard Data
    try {
      const topResp = await axios.get(`${BACKEND_URL}/politicians/${p.id}/top-fornecedores`);
      setTopSuppliers(topResp.data);
      const catResp = await axios.get(`${BACKEND_URL}/politicians/${p.id}/gastos-categoria`);
      setCategoryExpenses(catResp.data);
    } catch (e) { console.error("Erro ao buscar dashboard:", e); }

    // Fetch Sources
    try {
      const sResp = await axios.get(`${BACKEND_URL}/politicians/${p.id}/sources`);
      setSources(sResp.data);
    } catch (e) {
      console.error("Error fetching sources:", e);
      setSources([]);
    }

    // Fetch Detailed Expenses
    try {
      const eResp = await axios.get(`${BACKEND_URL}/politicians/${p.id}/expenses`);
      setSelectedPolitician(prev => prev ? { ...prev, detailedExpenses: eResp.data } : null);
    } catch (e) {
      console.error("Error fetching detailed expenses:", e);
    }
  };

  const formatCurrency = (val: any) => {
    if (val === undefined || val === null || isNaN(val) || !isFinite(val)) return 'R$ 0,00';
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val);
  };

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900 selection:bg-indigo-100 selection:text-indigo-900">
      {/* Search Header */}
      <header className="bg-indigo-900 sticky top-0 z-50 border-b border-indigo-700 shadow-xl">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between gap-8">
          <div className="flex items-center gap-3 shrink-0" onClick={() => setSelectedPolitician(null)} style={{ cursor: 'pointer' }}>
            <div className="w-10 h-10 bg-indigo-500 rounded-2xl flex items-center justify-center shadow-lg shadow-indigo-400/20 border border-white/10">
              <ShieldAlert className="text-white w-6 h-6" />
            </div>
            <h1 className="text-xl font-black tracking-tighter text-white uppercase">Transparência <span className="text-indigo-400">360</span></h1>
          </div>

          <form onSubmit={handleSearch} className="flex-1 max-w-2xl relative group">
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
              <Search className="h-5 w-5 text-indigo-300 group-focus-within:text-white transition-colors" />
            </div>
            <input
              type="text"
              className="block w-full pl-12 pr-4 py-3 bg-white/10 border-transparent rounded-2xl focus:bg-white focus:text-slate-900 focus:ring-4 focus:ring-indigo-500/20 focus:border-indigo-400 transition-all font-bold text-white placeholder-indigo-300/50"
              placeholder="Buscar parlamentar, partido ou estado..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />

            {results.length > 0 && (
              <div className="absolute top-full left-0 right-0 mt-2 bg-white rounded-3xl shadow-2xl border border-slate-100 overflow-hidden z-50 animate-in fade-in slide-in-from-top-2 duration-300">
                {results.map((p) => (
                  <button
                    key={p.id}
                    className="w-full px-6 py-4 text-left hover:bg-slate-50 flex items-center justify-between group transition-colors"
                    onClick={() => selectPolitician(p)}
                  >
                    <div>
                      <p className="font-black text-slate-800 uppercase tracking-tight">{p.name}</p>
                      <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">{p.party} • {p.state}</p>
                    </div>
                    <ChevronRight className="w-5 h-5 text-slate-300 group-hover:text-indigo-500 transition-colors" />
                  </button>
                ))}
              </div>
            )}
          </form>

          <div className="hidden md:flex items-center gap-6">
            <div className="flex flex-col items-end">
              <span className="text-[10px] font-black text-indigo-300 uppercase tracking-widest">Status do Motor</span>
              <span className="text-sm font-black text-emerald-400 flex items-center gap-1.5 uppercase">
                <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" /> Operacional
              </span>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-10">
        {!selectedPolitician ? (
          <div className="space-y-12">
            <div className="bg-indigo-600 rounded-[3rem] p-12 text-white relative overflow-hidden shadow-2xl shadow-indigo-200">
              <div className="absolute top-0 right-0 w-96 h-96 bg-white/10 rounded-full -mr-20 -mt-20 blur-3xl" />
              <div className="relative z-10 max-w-2xl">
                <h2 className="text-5xl font-black mb-6 tracking-tighter leading-none">O PODER DA INVESTIGAÇÃO NOS SEUS DEDOS.</h2>
                <p className="text-lg font-bold text-indigo-100/80 mb-8 leading-relaxed">
                  Cruzamos dados da Câmara, Portal da Transparência, TSE e Diários Oficiais para detectar anomalias patrimoniais e riscos de rachadinha.
                </p>
                <div className="flex gap-4">
                  <div className="px-6 py-3 bg-white text-indigo-600 rounded-2xl font-black uppercase text-sm shadow-xl hover:scale-105 transition-transform cursor-pointer">Começar Investigação</div>
                  <div className="px-6 py-3 bg-indigo-500/50 text-white rounded-2xl font-black uppercase text-sm border border-white/20 hover:bg-indigo-500/70 transition-colors cursor-pointer">Ver Metodologia</div>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              <div className="lg:col-span-2">
                <div className="flex items-center gap-2 mb-4 px-2">
                  <Users className="w-4 h-4 text-indigo-600" />
                  <h2 className="text-base font-black text-slate-800 uppercase tracking-widest">Ranking de Transparência</h2>
                </div>
                <RankingTable politicians={allPoliticians} onSelect={selectPolitician} />
              </div>
              <div className="space-y-6">
                <div className="bg-white rounded-3xl p-6 border border-slate-100 shadow-xl">
                  <h3 className="font-black text-slate-800 uppercase mb-4 flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-indigo-500" /> Alertas de Evolução
                  </h3>
                  <div className="space-y-4">
                    {allPoliticians.filter(p => (p.wealthAnomaly || 0) > 3).slice(0, 3).length > 0 ? (
                      allPoliticians.filter(p => (p.wealthAnomaly || 0) > 3).slice(0, 3).map(p => (
                        <div key={p.id} className="p-4 bg-rose-50 rounded-2xl border border-rose-100 cursor-pointer" onClick={() => selectPolitician(p)}>
                          <p className="text-xs font-black text-rose-600 uppercase mb-1">{p.name}</p>
                          <p className="text-sm font-black text-slate-800">{p.wealthAnomaly?.toFixed(1)}x crescimento incompatível</p>
                        </div>
                      ))
                    ) : (
                      <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100 text-center">
                        <p className="text-xs font-bold text-slate-400">Nenhuma anomalia crítica detectada no momento.</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-8 animate-in fade-in duration-500">
            {/* Top Stats - Hero Card */}
            <PoliticianCard politician={selectedPolitician} />

            {/* No Data Warning */}
            {(!selectedPolitician.expenses && selectedPolitician.cabinetRiskScore == null) && (
              <div className="bg-amber-50 border-2 border-dashed border-amber-200 rounded-[2rem] p-8 flex flex-col items-center text-center gap-4 animate-in zoom-in duration-500">
                <div className="w-16 h-16 bg-amber-100 rounded-2xl flex items-center justify-center">
                  <Database className="w-8 h-8 text-amber-600" />
                </div>
                <div>
                  <h3 className="text-lg font-black text-amber-900 uppercase tracking-tight">Dados em Processamento</h3>
                  <p className="text-xs font-bold text-amber-700 max-w-md mx-auto mt-1">
                    Ainda não extraímos os dados detalhados para este parlamentar. Nossa equipe de robôs está trabalhando nisso!
                  </p>
                </div>
                <button
                  onClick={() => selectPolitician(selectedPolitician)}
                  className="px-6 py-2 bg-amber-600 text-white rounded-xl font-black uppercase text-[10px] hover:bg-amber-700 transition-colors"
                >
                  Tentar Novamente
                </button>
              </div>
            )}

            {/* Navigation Tabs */}
            <div className="flex flex-wrap gap-2 bg-slate-200/50 p-1.5 rounded-[2rem] w-fit border border-slate-200">
              <button
                className={`px-8 py-3 rounded-[1.5rem] text-xs font-black uppercase tracking-widest transition-all ${activeTab === 'geral' ? 'bg-white text-indigo-600 shadow-lg ring-1 ring-slate-100' : 'text-slate-500 hover:text-slate-700'}`}
                onClick={() => setActiveTab('geral')}
              >
                <div className="flex items-center gap-2"><LayoutDashboard className="w-4 h-4" /> Visão Geral</div>
              </button>
              <button
                className={`px-8 py-3 rounded-[1.5rem] text-xs font-black uppercase tracking-widest transition-all ${activeTab === 'inteligencia' ? 'bg-white text-indigo-600 shadow-lg ring-1 ring-slate-100' : 'text-slate-500 hover:text-slate-700'}`}
                onClick={() => setActiveTab('inteligencia')}
              >
                <div className="flex items-center gap-2"><ShieldAlert className="w-4 h-4" /> Deep Match</div>
              </button>
              <button
                className={`px-8 py-3 rounded-[1.5rem] text-xs font-black uppercase tracking-widest transition-all ${activeTab === 'grafo' ? 'bg-white text-indigo-600 shadow-lg ring-1 ring-slate-100' : 'text-slate-500 hover:text-slate-700'}`}
                onClick={() => setActiveTab('grafo')}
              >
                <div className="flex items-center gap-2"><Network className="w-4 h-4" /> Grafo de Influência</div>
              </button>

              {/* NOVAS ABAS AQUI */}
              <button onClick={() => setActiveTab('despesas')} className={`px-6 py-2.5 rounded-full text-sm font-bold transition-all ${activeTab === 'despesas' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-200' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'}`}>Extrato CEAP</button>
              <button onClick={() => setActiveTab('emendas')} className={`px-6 py-2.5 rounded-full text-sm font-bold transition-all ${activeTab === 'emendas' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-200' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'}`}>Emendas (Orçamento)</button>

              <button
                className={`px-8 py-3 rounded-[1.5rem] text-xs font-black uppercase tracking-widest transition-all ${activeTab === 'fontes' ? 'bg-white text-indigo-600 shadow-lg ring-1 ring-slate-100' : 'text-slate-500 hover:text-slate-700'}`}
                onClick={() => setActiveTab('fontes')}
              >
                <div className="flex items-center gap-2"><Database className="w-4 h-4" /> Rastreabilidade</div>
              </button>
            </div>

            {/* Tab Content */}
            <div className="grid grid-cols-1 gap-8">
              {activeTab === 'geral' && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                  <WealthChart data={[
                    { year: '2014', value: selectedPolitician.declaredAssets2014 || 0 },
                    { year: '2018', value: selectedPolitician.declaredAssets2018 || 0 },
                    { year: '2022', value: selectedPolitician.declaredAssets || 0 }
                  ]} />

                  <div className="bg-white rounded-3xl shadow-xl p-8 border border-slate-100">
                    <h3 className="text-xl font-black text-slate-800 uppercase tracking-tight mb-6">Custos Operacionais</h3>
                    <div className="space-y-6">
                      <div className="flex justify-between items-end">
                        <div>
                          <p className="text-[10px] font-black uppercase text-slate-400 tracking-widest mb-1">Total CEAP (Acumulado)</p>
                          <p className="text-3xl font-black text-slate-800 tracking-tighter">{formatCurrency(selectedPolitician.expenses || 0)}</p>
                        </div>
                        <BarChart3 className="w-10 h-10 text-indigo-100" />
                      </div>
                      <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100">
                        {(() => {
                          const abs = selectedPolitician.absences || 0;
                          const pres = selectedPolitician.presences || 0;
                          const total = abs + pres;
                          // Proteção contra divisão por zero e cálculo de percentagem real!
                          const pct = total > 0 ? Math.round((pres / total) * 100) : 100;

                          return (
                            <>
                              <div className="flex justify-between mb-2">
                                <span className="text-xs font-bold text-slate-500">
                                  Presença em Plenário ({pres} de {total} sessões)
                                </span>
                                <span className="text-xs font-black text-slate-800">{pct}%</span>
                              </div>
                              <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                                <div className="h-full bg-indigo-500 transition-all duration-1000" style={{ width: `${pct}%` }} />
                              </div>
                            </>
                          );
                        })()}
                      </div>

                      {/* Detailed Expense Table */}
                      <div className="mt-8">
                        <h4 className="text-[10px] font-black uppercase text-slate-400 tracking-widest mb-4">Últimos Lançamentos CEAP</h4>
                        <div className="overflow-hidden rounded-2xl border border-slate-100 divide-y divide-slate-100">
                          {selectedPolitician.detailedExpenses && selectedPolitician.detailedExpenses.length > 0 ? (
                            selectedPolitician.detailedExpenses.slice(0, 5).map((exp, i) => (
                              <div key={i} className="p-4 bg-white hover:bg-slate-50 transition-colors flex justify-between items-center group">
                                <div className="flex flex-col">
                                  <span className="text-xs font-black text-slate-800 line-clamp-1 uppercase tracking-tight">{exp.nomeFornecedor}</span>
                                  <span className="text-[10px] font-bold text-slate-400">{exp.dataEmissao} • {exp.categoria}</span>
                                </div>
                                <span className="text-sm font-black text-slate-700 group-hover:text-indigo-600 transition-colors">{formatCurrency(exp.valorDocumento)}</span>
                              </div>
                            ))
                          ) : (
                            <div className="p-8 text-center bg-slate-50/50">
                              <p className="text-xs font-bold text-slate-400 uppercase">Nenhum detalhamento disponível</p>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'inteligencia' && (
                <div className="flex flex-col gap-8">
                  {selectedPolitician.cabinetRiskScore != null && (
                    <RadarRisco
                      score={selectedPolitician.cabinetRiskScore}
                      details={selectedPolitician.cabinetRiskDetails || '[]'}
                    />
                  )}

                  {/* =========================================================
                      MOTOR ROSIE (SERENATA DE AMOR) - DADOS REAIS DA API
                      ========================================================= */}
                  {((selectedPolitician.rosieBenfordCount || 0) > 0 ||
                    (selectedPolitician.rosieDuplicateCount || 0) > 0 ||
                    (selectedPolitician.rosieWeekendCount || 0) > 0 ||
                    (selectedPolitician.rosieHealthCount || 0) > 0 ||
                    (selectedPolitician.rosieLuxuryCount || 0) > 0) && (
                      <div className="bg-white rounded-3xl shadow-xl border border-slate-100 overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500">
                        <div className="bg-gradient-to-r from-rose-600 to-orange-500 p-6">
                          <h3 className="text-xl font-black text-white flex items-center gap-3 tracking-tight">
                            <Bot className="w-7 h-7 text-rose-100" />
                            Auditoria Matemática (Motor Rosie)
                          </h3>
                          <p className="text-rose-100 mt-2 text-xs font-bold uppercase tracking-widest">
                            Scoring de Anomalias Fiscais na Cota Parlamentar (CEAP)
                          </p>
                        </div>

                        <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-6">

                          {/* ALERTA 1: LEI DE BENFORD */}
                          {(selectedPolitician.rosieBenfordCount || 0) > 0 && (
                            <div className="bg-rose-50/50 rounded-2xl p-6 border border-rose-100 relative overflow-hidden group hover:bg-rose-50 transition-colors">
                              <div className="flex justify-between items-start mb-4">
                                <div className="bg-rose-100 p-2.5 rounded-xl group-hover:scale-110 transition-transform">
                                  <Calculator className="w-5 h-5 text-rose-600" />
                                </div>
                                <span className="bg-rose-600 text-white text-[10px] font-black uppercase tracking-wider px-3 py-1 rounded-full shadow-sm">
                                  Crítico
                                </span>
                              </div>
                              <h4 className="text-sm font-black text-slate-800 mb-1">Quebra da Lei de Benford</h4>
                              <div className="text-3xl font-black text-rose-600 mb-4 tracking-tighter">
                                {selectedPolitician.rosieBenfordCount} <span className="text-xs font-bold text-rose-400 tracking-normal">ocorrências</span>
                              </div>
                              <p className="text-[11px] text-slate-600 leading-relaxed font-medium">
                                <strong className="text-slate-800">O Santo Graal da auditoria de fraudes.</strong> O desvio padrão deste gabinete quebrou a barreira matemática.
                                <br /><br />
                                <span className="text-rose-700 font-bold">Diagnóstico:</span> Os valores destas notas fiscais não são orgânicos. É um forte indício de intervenção humana (Notas Frias), onde valores estão a ser "inventados" no teclado.
                              </p>
                            </div>
                          )}

                          {/* ALERTA 2: DUPLICATAS */}
                          {(selectedPolitician.rosieDuplicateCount || 0) > 0 && (
                            <div className="bg-orange-50/50 rounded-2xl p-6 border border-orange-100 relative overflow-hidden group hover:bg-orange-50 transition-colors">
                              <div className="flex justify-between items-start mb-4">
                                <div className="bg-orange-100 p-2.5 rounded-xl group-hover:scale-110 transition-transform">
                                  <Copy className="w-5 h-5 text-orange-600" />
                                </div>
                                <span className="bg-orange-500 text-white text-[10px] font-black uppercase tracking-wider px-3 py-1 rounded-full shadow-sm">
                                  Alto
                                </span>
                              </div>
                              <h4 className="text-sm font-black text-slate-800 mb-1">Reembolsos Duplicados</h4>
                              <div className="text-3xl font-black text-orange-600 mb-4 tracking-tighter">
                                {selectedPolitician.rosieDuplicateCount} <span className="text-xs font-bold text-orange-400 tracking-normal">ocorrências</span>
                              </div>
                              <p className="text-[11px] text-slate-600 leading-relaxed font-medium">
                                A Rosie detetou o clássico erro humano de estelionato: submeter o mesmo recibo duas (ou mais) vezes para receber o reembolso a dobrar da Câmara.
                              </p>
                            </div>
                          )}

                          {/* ALERTA 3: TURISMO PARLAMENTAR */}
                          {(selectedPolitician.rosieWeekendCount || 0) > 0 && (
                            <div className="bg-amber-50/50 rounded-2xl p-6 border border-amber-100 relative overflow-hidden group hover:bg-amber-50 transition-colors">
                              <div className="flex justify-between items-start mb-4">
                                <div className="bg-amber-100 p-2.5 rounded-xl group-hover:scale-110 transition-transform">
                                  <CalendarOff className="w-5 h-5 text-amber-600" />
                                </div>
                                <span className="bg-amber-500 text-white text-[10px] font-black uppercase tracking-wider px-3 py-1 rounded-full shadow-sm">
                                  Médio
                                </span>
                              </div>
                              <h4 className="text-sm font-black text-slate-800 mb-1">Turismo Parlamentar</h4>
                              <div className="text-3xl font-black text-amber-600 mb-4 tracking-tighter">
                                {selectedPolitician.rosieWeekendCount} <span className="text-xs font-bold text-amber-400 tracking-normal">ocorrências</span>
                              </div>
                              <p className="text-[11px] text-slate-600 leading-relaxed font-medium">
                                O motor de cruzamento temporal isolou despesas efetuadas fora do expediente oficial, em dias que não havia qualquer expediente em Brasília.
                              </p>
                            </div>
                          )}

                          {/* ALERTA 4: SAÚDE E ESTÉTICA NA CEAP */}
                          {(selectedPolitician.rosieHealthCount || 0) > 0 && (
                            <div className="bg-rose-50/50 rounded-2xl p-6 border border-rose-100 relative overflow-hidden group hover:bg-rose-50 transition-colors">
                              <div className="flex justify-between items-start mb-4">
                                <div className="bg-rose-100 p-2.5 rounded-xl group-hover:scale-110 transition-transform">
                                  <Stethoscope className="w-5 h-5 text-rose-600" />
                                </div>
                                <span className="bg-rose-600 text-white text-[10px] font-black uppercase tracking-wider px-3 py-1 rounded-full shadow-sm">
                                  Ilegalidade
                                </span>
                              </div>
                              <h4 className="text-sm font-black text-slate-800 mb-1">Gasto Médico/Estético na CEAP</h4>
                              <div className="text-3xl font-black text-rose-600 mb-4 tracking-tighter">
                                {selectedPolitician.rosieHealthCount} <span className="text-xs font-bold text-rose-400 tracking-normal">ocorrências</span>
                              </div>
                              <p className="text-[11px] text-slate-600 leading-relaxed font-medium">
                                O motor de NLP identificou recibos de Clínicas, Odontologia ou Estética mascarados na prestação de contas.
                                <br /><br />
                                <span className="text-rose-700 font-bold">Diagnóstico:</span> A Cota Parlamentar (CEAP) proíbe gastos de saúde pessoal, que possuem um fundo de ressarcimento paralelo. Indica possível estelionato ou falsidade ideológica no reembolso.
                              </p>
                            </div>
                          )}

                          {/* ALERTA 5: LUXO PESSOAL NA CEAP */}
                          {(selectedPolitician.rosieLuxuryCount || 0) > 0 && (
                            <div className="bg-purple-50/50 rounded-2xl p-6 border border-purple-100 relative overflow-hidden group hover:bg-purple-50 transition-colors">
                              <div className="flex justify-between items-start mb-4">
                                <div className="bg-purple-100 p-2.5 rounded-xl group-hover:scale-110 transition-transform">
                                  <ShoppingBag className="w-5 h-5 text-purple-600" />
                                </div>
                                <span className="bg-purple-600 text-white text-[10px] font-black uppercase tracking-wider px-3 py-1 rounded-full shadow-sm">
                                  Imoralidade
                                </span>
                              </div>
                              <h4 className="text-sm font-black text-slate-800 mb-1">Luxo & Consumo Pessoal</h4>
                              <div className="text-3xl font-black text-purple-600 mb-4 tracking-tighter">
                                {selectedPolitician.rosieLuxuryCount} <span className="text-xs font-bold text-purple-400 tracking-normal">ocorrências</span>
                              </div>
                              <p className="text-[11px] text-slate-600 leading-relaxed font-medium">
                                A Rosie interceptou pagamentos suspeitos em Pet Shops, Joalherias, Resorts de Férias ou Salões de Beleza misturados no bloco de reembolso parlamentar.
                              </p>
                            </div>
                          )}

                        </div>
                      </div>
                    )}

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    {/* STAFF ANOMALIES (Mantido) */}
                    {selectedPolitician.staffAnomalyCount != null && selectedPolitician.staffAnomalyCount > 0 && (
                      <div className="bg-white rounded-3xl shadow-xl p-8 border border-slate-100">
                        <div className="flex items-center gap-3 mb-6">
                          <Cpu className="w-6 h-6 text-amber-500" />
                          <h3 className="text-lg font-black text-slate-800 uppercase tracking-tight">Anomalias de Pessoal</h3>
                        </div>
                        <div className="space-y-4 max-h-64 overflow-y-auto pr-2">
                          {JSON.parse(selectedPolitician.staffAnomalyDetails || '[]').map((a: any, i: number) => (
                            <div key={i} className="p-4 rounded-2xl bg-amber-50 border border-amber-100">
                              <div className="flex justify-between mb-1">
                                <span className="font-black text-slate-800 uppercase text-xs">{a.supplier || a.nomeFornecedor || a.name || 'Desconhecido'}</span>
                                <span className="font-black text-slate-700 text-xs">{formatCurrency(a.totalValue || a.valor || a.salary)}</span>
                              </div>
                              <p className="text-[10px] font-bold text-amber-700">
                                {a.flags && a.flags.length > 0 ? a.flags[0].detail : (a.descricao || a.detail || 'Detectado por Machine Learning')}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* RISCO JUDICIÁRIO (DATAJUD) */}
                    <div className="bg-white rounded-3xl shadow-xl p-8 border border-slate-100">
                      <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-3">
                          <AlertCircle className={`w-6 h-6 ${(selectedPolitician.judicialRiskScore || 0) > 0 ? 'text-rose-500' : 'text-emerald-500'}`} />
                          <h3 className="text-lg font-black text-slate-800 uppercase tracking-tight">Risco Judiciário</h3>
                        </div>
                        <span className="text-[10px] font-black uppercase text-slate-400">DataJud</span>
                      </div>

                      {(selectedPolitician.judicialRiskScore || 0) > 0 ? (
                        <div className="flex flex-col gap-2 p-4 bg-rose-50 rounded-2xl border border-rose-100">
                          <p className="text-sm font-black text-rose-700 uppercase">Alerta Ativo (Score: {selectedPolitician.judicialRiskScore})</p>
                          <p className="text-xs font-bold text-rose-600 leading-relaxed">{selectedPolitician.judicialRiskDetails || 'Processos de improbidade encontrados.'}</p>
                        </div>
                      ) : (
                        <div className="flex flex-col items-center justify-center h-32 border-2 border-dashed border-emerald-100 rounded-2xl bg-emerald-50/50">
                          <p className="text-xs font-black text-emerald-600 uppercase tracking-widest">Ficha Limpa</p>
                          <p className="text-[10px] font-bold text-emerald-500 mt-1">Nenhum processo crítico encontrado</p>
                        </div>
                      )}
                    </div>

                    {/* NLP GAZETTE (DIÁRIOS OFICIAIS) */}
                    <div className="bg-white rounded-3xl shadow-xl p-8 border border-slate-100 md:col-span-2">
                      <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-3">
                          <Database className={`w-6 h-6 ${(selectedPolitician.nlpGazetteCount || 0) > 0 ? 'text-amber-500' : 'text-slate-400'}`} />
                          <h3 className="text-lg font-black text-slate-800 uppercase tracking-tight">Menções em Diários Oficiais</h3>
                        </div>
                        <span className="text-[10px] font-black uppercase text-slate-400">Querido Diário API</span>
                      </div>

                      {(selectedPolitician.nlpGazetteCount || 0) > 0 ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="p-4 bg-amber-50 rounded-2xl border border-amber-100">
                            <p className="text-[10px] font-black uppercase tracking-widest text-amber-500 mb-1">Ocorrências</p>
                            <p className="text-3xl font-black text-amber-700">{selectedPolitician.nlpGazetteCount}</p>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200">
                            <p className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-1">Análise Textual</p>
                            <p className="text-xs font-bold text-slate-700">{selectedPolitician.nlpGazetteDetails || 'Foram encontradas menções envolvendo empresas ligadas ao gabinete em publicações oficiais.'}</p>
                          </div>
                        </div>
                      ) : (
                        <div className="p-6 bg-slate-50 border border-slate-100 rounded-2xl text-center">
                          <p className="text-xs font-bold text-slate-400 uppercase">Nenhuma atividade suspeita em licitações ou diários oficiais municipais encontrada pela inteligência artificial.</p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'grafo' && (
                <div className="bg-white rounded-[3rem] shadow-2xl h-[600px] border border-slate-100 overflow-hidden relative">
                  <div className="absolute top-8 left-8 z-10 p-4 bg-white/80 backdrop-blur-md rounded-2xl border border-slate-100 shadow-xl max-w-xs">
                    <p className="text-[10px] font-black text-emerald-600 uppercase tracking-widest mb-1">Follow The Money</p>
                    <p className="text-xs font-bold text-slate-600">O tamanho das esferas representa o volume financeiro. As luzes mostram o fluxo do cofre público para o fornecedor.</p>
                  </div>
                  <ForceGraph2D
                    ref={fgRef} // <-- Liga o nosso motor de física ao grafo
                    graphData={graphData}
                    nodeAutoColorBy="group"
                    // Mantemos o nodeLabel para o tooltip nativo (hover)
                    nodeLabel="name"
                    linkColor={(link: any) => link.color}
                    linkWidth={(link: any) => link.width}
                    linkDirectionalParticles={(link: any) => link.particles}
                    linkDirectionalParticleSpeed={(link: any) => link.color === "#ef4444" ? 0.015 : 0.005}
                    linkDirectionalParticleColor={(link: any) => link.color}
                    linkDirectionalArrowLength={3.5}
                    linkDirectionalArrowRelPos={1}
                    width={1100}
                    height={600}
                    backgroundColor="#f8fafc"

                    // 🎨 A MÁGICA VISUAL: Desenhamos a bolha e o texto manualmente
                    nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
                      const label = node.name;
                      const fontSize = 12 / globalScale; // O texto cresce/diminui junto com o zoom
                      ctx.font = `${fontSize}px Sans-Serif`;

                      // 1. Desenha a Bolha
                      const nodeR = node.val * 0.6; // Raio da bolha
                      ctx.beginPath();
                      ctx.arc(node.x, node.y, nodeR, 0, 2 * Math.PI, false);
                      ctx.fillStyle = node.color || '#94a3b8';
                      ctx.fill();

                      // Borda vermelha piscante/destacada para Anomalias
                      if (node.color === "#ef4444") {
                        ctx.lineWidth = 2 / globalScale;
                        ctx.strokeStyle = "#991b1b";
                        ctx.stroke();
                      }

                      // 2. Mede o tamanho do texto para criar uma "Plaquinha" de fundo
                      const textWidth = ctx.measureText(label).width;
                      const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.4);

                      // Desenha o fundo branco semi-transparente do texto
                      ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
                      ctx.fillRect(
                        node.x - bckgDimensions[0] / 2,
                        node.y + nodeR + (2 / globalScale), // Posiciona logo abaixo da bolha
                        bckgDimensions[0],
                        bckgDimensions[1]
                      );

                      // 3. Escreve o texto por cima do fundo
                      ctx.textAlign = 'center';
                      ctx.textBaseline = 'middle';
                      ctx.fillStyle = node.color === "#ef4444" ? "#b91c1c" : "#1e293b"; // Texto vermelho escuro se for alerta
                      ctx.fillText(label, node.x, node.y + nodeR + (2 / globalScale) + (bckgDimensions[1] / 2));
                    }}
                  />
                </div>
              )}

              {/* NOVO DASHBOARD DE DESPESAS */}
              {activeTab === 'despesas' && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 animate-in fade-in slide-in-from-bottom-4 duration-500">

                  {/* Coluna da Esquerda: Gráficos de Agregação */}
                  <div className="space-y-6 flex flex-col h-[600px]">
                    {/* Top 5 Fornecedores */}
                    <div className="bg-white rounded-3xl shadow-xl p-6 border border-slate-100 flex-shrink-0">
                      <h3 className="text-xs font-black text-slate-800 uppercase tracking-widest mb-4 flex items-center gap-2">
                        🏆 Maiores Recebedores
                      </h3>
                      <div className="space-y-3">
                        {topSuppliers.map((sup, i) => (
                          <div key={i} className="p-3 bg-slate-50 rounded-xl border border-slate-100 flex justify-between items-center group hover:bg-rose-50 transition-colors">
                            <span className="text-[11px] font-bold text-slate-600 line-clamp-1 w-3/5" title={sup.fornecedor}>{sup.fornecedor}</span>
                            <span className="text-xs font-black text-rose-500 group-hover:scale-105 transition-transform">{formatCurrency(sup.total || 0)}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Gastos por Categoria (Barras de Progresso) */}
                    <div className="bg-white rounded-3xl shadow-xl p-6 border border-slate-100 flex-1 overflow-hidden flex flex-col">
                      <h3 className="text-xs font-black text-slate-800 uppercase tracking-widest mb-4 flex items-center gap-2">
                        📊 Distribuição de Gastos
                      </h3>
                      <div className="space-y-4 overflow-y-auto pr-2 flex-1 custom-scrollbar">
                        {categoryExpenses.map((cat, i) => {
                          const maxVal = categoryExpenses[0]?.total || 1;
                          const pct = ((cat.total / maxVal) * 100).toFixed(0);
                          return (
                            <div key={i} className="group">
                              <div className="flex justify-between mb-1.5 items-end">
                                <span className="text-[10px] font-bold text-slate-500 line-clamp-1 w-2/3 uppercase tracking-tight">{cat.categoria}</span>
                                <span className="text-[10px] font-black text-slate-700">{formatCurrency(cat.total || 0)}</span>
                              </div>
                              <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                                <div className="h-full bg-indigo-400 rounded-full group-hover:bg-indigo-500 transition-colors" style={{ width: `${pct}%` }}></div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>

                  {/* Coluna da Direita: Extrato Físico (Linha a Linha) */}
                  <div className="lg:col-span-2 bg-white rounded-3xl shadow-xl p-8 border border-slate-100 h-[600px] flex flex-col">
                    <div className="flex justify-between items-center mb-6">
                      <div>
                        <h3 className="text-xl font-black text-slate-800 tracking-tight">Extrato Físico Detalhado</h3>
                        <p className="text-xs font-bold text-slate-400 mt-1">Inspeção linha a linha das notas emitidas</p>
                      </div>
                      <span className="bg-indigo-100 text-indigo-700 px-3 py-1 rounded-full text-xs font-bold">{expensesList.length} notas recentes</span>
                    </div>
                    <div className="overflow-y-auto flex-1 pr-2 custom-scrollbar">
                      <table className="w-full text-left border-collapse">
                        <thead className="sticky top-0 bg-white/95 backdrop-blur-sm shadow-sm z-10">
                          <tr className="text-slate-400 text-[10px] uppercase tracking-widest border-b border-slate-100">
                            <th className="pb-3 font-black">Data</th>
                            <th className="pb-3 font-black">Fornecedor</th>
                            <th className="pb-3 font-black">Categoria</th>
                            <th className="pb-3 font-black text-right">Valor</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-50">
                          {expensesList.slice(0, 500).map((d, i) => (
                            <tr key={i} className="hover:bg-slate-50/80 transition-colors group">
                              <td className="py-3 text-[11px] text-slate-400 font-mono whitespace-nowrap">{d.dataEmissao || 'S/ Data'}</td>
                              <td className="py-3 text-xs font-bold text-slate-700">{d.nomeFornecedor}</td>
                              <td className="py-3 text-[10px] font-bold text-slate-400 uppercase tracking-tight">{d.categoria}</td>
                              <td className="py-3 text-sm font-black text-rose-500 text-right whitespace-nowrap">
                                {formatCurrency(d.valorDocumento || 0)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                </div>
              )}

              {/* NOVA ABA: EMENDAS BRUTAS */}
              {activeTab === 'emendas' && (
                <div className="bg-white rounded-3xl shadow-xl p-8 border border-slate-100 h-[600px] overflow-y-auto">
                  <div className="flex justify-between items-center mb-6">
                    <h3 className="text-xl font-black text-slate-800">Repasses de Emendas Parlamentares</h3>
                    <span className="bg-emerald-100 text-emerald-700 px-3 py-1 rounded-full text-xs font-bold">{emendasList.length} registros</span>
                  </div>
                  <table className="w-full text-left border-collapse">
                    <thead className="sticky top-0 bg-white shadow-sm">
                      <tr className="text-slate-400 text-[10px] uppercase tracking-widest border-b border-slate-100">
                        <th className="pb-4 font-black">Ano</th>
                        <th className="pb-4 font-black">Área / Função</th>
                        <th className="pb-4 font-black">Destino (Cidade)</th>
                        <th className="pb-4 font-black text-right">Valor Repassado</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                      {emendasList.map((em, i) => (
                        <tr key={i} className="hover:bg-slate-50/80 transition-colors group">
                          <td className="py-4 text-sm font-bold text-slate-400">{em.ano}</td>
                          <td className="py-4">
                            <div className="flex flex-col">
                              <span className="text-sm font-black text-slate-800">{em.funcao || 'Encargo Especial'}</span>
                              <span className="text-[10px] text-slate-400 font-bold uppercase">{em.tipo?.split('-')[0]}</span>
                            </div>
                          </td>
                          <td className="py-4">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-bold text-slate-600 bg-slate-100 px-2 py-1 rounded-lg">
                                📍 {em.localidade || 'Brasília/DF'}
                              </span>
                            </div>
                          </td>
                          <td className="py-4 text-right">
                            <span className="text-sm font-black text-emerald-600 bg-emerald-50 px-3 py-1.5 rounded-xl border border-emerald-100">
                              {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(em.valor || 0)}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {emendasList.length === 0 && (
                    <div className="text-center py-20">
                      <p className="text-slate-400 font-bold">Nenhuma emenda capturada para este político no período.</p>
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'fontes' && (
                <div className="bg-white rounded-3xl shadow-xl p-8 border border-slate-100">
                  <h3 className="text-xl font-black text-slate-800 uppercase tracking-tight mb-8">Auditoria de Dados</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {sources.map((s, i) => (
                      <div key={i} className="p-6 bg-slate-50 rounded-3xl border border-slate-100 flex flex-col gap-4">
                        <div className="flex justify-between items-start">
                          <div className="flex items-center gap-3">
                            <div className="text-3xl">{s.icon}</div>
                            <div>
                              <p className="font-black text-slate-800 uppercase tracking-tight">{s.name}</p>
                              <p className="text-[10px] font-bold text-slate-400">{s.endpoint}</p>
                            </div>
                          </div>
                          <ConfidenceBadge level={s.status === 'ok' ? 'High' : 'Medium'} />
                        </div>
                        <p className="text-xs font-bold text-slate-600 leading-relaxed">{s.description}</p>
                        <SourceTag label="Ver Dados Brutos" url={`https://${s.endpoint}`} />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-slate-900 text-slate-400 py-12 px-6 border-t border-slate-800 mt-20">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-8">
          <div className="flex items-center gap-3">
            <ShieldAlert className="w-8 h-8 text-indigo-500" />
            <span className="text-xl font-black tracking-tighter text-white uppercase">Transparência 360</span>
          </div>
          <p className="text-xs font-bold text-center">© 2026 Dados públicos para vigilância cidadã.</p>
          <div className="flex gap-6">
            <span className="text-xs font-black uppercase text-indigo-400 cursor-pointer hover:text-white transition-colors">Segurança</span>
            <span className="text-xs font-black uppercase text-indigo-400 cursor-pointer hover:text-white transition-colors">API</span>
            <span className="text-xs font-black uppercase text-indigo-400 cursor-pointer hover:text-white transition-colors">GitHub</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;

import React from 'react';
import { User, MapPin, Building2, ExternalLink } from 'lucide-react';

interface PoliticianCardProps {
    politician: {
        name: string;
        party: string;
        state: string;
        position: string;
        externalId: string;
    };
}

const PoliticianCard: React.FC<PoliticianCardProps> = ({ politician }) => {
    return (
        <div className="bg-indigo-600 rounded-[2.5rem] shadow-2xl p-8 text-white relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-8 opacity-20 group-hover:opacity-40 transition-opacity">
                <Building2 className="w-32 h-32" />
            </div>

            <div className="relative z-10">
                <div className="flex items-center gap-4 mb-6">
                    <div className="w-16 h-16 rounded-3xl bg-white/20 backdrop-blur-md flex items-center justify-center border border-white/30">
                        <User className="w-8 h-8 text-white" />
                    </div>
                    <div>
                        <h2 className="text-3xl font-black tracking-tight leading-none uppercase">{politician.name}</h2>
                        <div className="flex items-center gap-2 mt-2">
                            <span className="px-3 py-0.5 rounded-full bg-indigo-500/50 border border-white/20 text-[10px] font-black uppercase tracking-widest leading-none">
                                {politician.party}
                            </span>
                            <span className="flex items-center gap-1 text-[10px] font-black uppercase tracking-widest text-indigo-100">
                                <MapPin className="w-3 h-3" /> {politician.state}
                            </span>
                        </div>
                    </div>
                </div>

                <div className="flex gap-4">
                    <div className="flex-1 bg-white/10 backdrop-blur-md rounded-2xl p-4 border border-white/10">
                        <p className="text-[10px] font-black uppercase text-indigo-200 tracking-widest mb-1">Cargo Atual</p>
                        <p className="text-sm font-black text-white">{politician.position}</p>
                    </div>
                    <div className="flex-1 bg-white/10 backdrop-blur-md rounded-2xl p-4 border border-white/10">
                        <p className="text-[10px] font-black uppercase text-indigo-200 tracking-widest mb-1">ID Extração</p>
                        <p className="text-sm font-black text-white font-mono">#{politician.externalId}</p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default PoliticianCard;

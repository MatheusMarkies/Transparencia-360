"""
Gazette NLP Entity Extractor
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Extrai automaticamente entidades estruturadas de texto corrido de
Diários Oficiais (DOU, DOM) usando Regex avançado e NLP.

Entidades extraídas:
  - CNPJs  (xx.xxx.xxx/xxxx-xx)
  - CPFs   (xxx.xxx.xxx-xx)
  - Valores monetários  (R$ xxx.xxx,xx)
  - Modalidades de licitação (Pregão, Dispensa, Tomada de Preços, etc.)
  - Números de processo/contrato
  - Nomes de empresas (após "CNPJ:" ou em contexto de licitação)
  - Órgãos contratantes
  - Datas de publicação

Estratégia:
  1. Normalização de texto (encoding, whitespace)
  2. Regex multi-pass para cada tipo de entidade
  3. Contexto Window Analysis (±200 chars ao redor de cada match)
  4. Score de relevância baseado no contexto (licitação/contrato/dispensa)
"""
import re
import logging
from typing import Optional
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
# REGEX PATTERNS
# ══════════════════════════════════════════════════════════════════

# CNPJ: 00.000.000/0000-00 (with optional spaces)
RE_CNPJ = re.compile(
    r'\b(\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[\/\s]?\d{4}[\-\s]?\d{2})\b'
)

# CPF: 000.000.000-00
RE_CPF = re.compile(
    r'\b(\d{3}[\.\s]?\d{3}[\.\s]?\d{3}[\-\s]?\d{2})\b'
)

# Monetary values: R$ 1.234.567,89 or R$1234567,89 or R$ 1.234,56
RE_VALOR = re.compile(
    r'R\$\s*([\d]{1,3}(?:\.[\d]{3})*(?:,[\d]{2})?)' 
    r'|'
    r'R\$\s*([\d]+(?:,[\d]{2})?)'
)

# Bidding modalities (Portuguese legal terms)
RE_MODALIDADE = re.compile(
    r'(?:DISPENSA\s+DE\s+LICITA[ÇC][ÃA]O'
    r'|INEXIGIBILIDADE(?:\s+DE\s+LICITA[ÇC][ÃA]O)?'
    r'|PREG[ÃA]O\s+(?:PRESENCIAL|ELETR[ÔO]NICO)'
    r'|PREG[ÃA]O'
    r'|TOMADA\s+DE\s+PRE[ÇC]OS?'
    r'|CONCORR[ÊE]NCIA(?:\s+P[ÚU]BLICA)?'
    r'|CONVITE'
    r'|CONCURSO'
    r'|LEIL[ÃA]O'
    r'|CHAMADA\s+P[ÚU]BLICA'
    r'|CARTA\s+CONVITE'
    r'|RDC'
    r'|DI[ÁA]LOGO\s+COMPETITIVO)',
    re.IGNORECASE
)

# Contract/Process numbers
RE_PROCESSO = re.compile(
    r'(?:Processo|Contrato|Ata|Edital|Pregão)\s*(?:n[ºo°\.]*|N[ºo°\.]*)?\s*'
    r'([\d]{1,6}[\/\-\.]?[\d]{2,4}(?:[\/\-\.][\d]{2,4})?)',
    re.IGNORECASE
)

# Company names (after CNPJ mention or in bidding context)
RE_EMPRESA_APOS_CNPJ = re.compile(
    r'CNPJ[:\s]*[\d\.\/-]+[\s,\-–]*([A-ZÁÉÍÓÚÃÕÂÊÎÔÛÇ][A-ZÁÉÍÓÚÃÕÂÊÎÔÛÇ\s\.\-&]{5,80}(?:LTDA|EIRELI|S/?A|ME|EPP|LTDA[\.\s]*ME|SS))',
    re.IGNORECASE
)

# Orgão contratante
RE_ORGAO = re.compile(
    r'(?:PREFEITURA\s+(?:MUNICIPAL\s+)?DE\s+[A-ZÁÉÍÓÚÃÕ][a-záéíóúãõâêîôûç\s]+' 
    r'|SECRETARIA\s+(?:MUNICIPAL|ESTADUAL|DE\s+ESTADO)\s+[A-ZÁÉÍÓÚÃÕ][A-Za-záéíóúãõâêîôûç\s]+' 
    r'|C[ÂA]MARA\s+MUNICIPAL\s+DE\s+[A-ZÁÉÍÓÚÃÕ][a-záéíóúãõâêîôûç\s]+' 
    r'|GOVERNO\s+(?:DO\s+ESTADO|MUNICIPAL)\s+(?:DE?\s+)?[A-ZÁÉÍÓÚÃÕ][a-záéíóúãõâêîôûç\s]+' 
    r'|FUNDO\s+MUNICIPAL\s+DE\s+[A-ZÁÉÍÓÚÃÕ][a-záéíóúãõâêîôûç\s]+)',
    re.IGNORECASE
)

# Suspicious keywords that boost relevance score
KEYWORDS_SUSPICIOUS = [
    'dispensa', 'inexigibilidade', 'emergencial', 'caráter emergencial',
    'contratação direta', 'convênio', 'aditivo', 'prorrogação',
    'acréscimo', 'reajuste', 'sobrepreço', 'superfaturamento',
    'sem licitação', 'art. 24', 'art. 25', 'lei 8.666',
    'lei 14.133', 'contrato administrativo'
]

CONTEXT_WINDOW = 300  # chars around each match for context analysis


class GazetteNLPExtractor:
    """
    Motor de NLP focado em extrair entidades estruturadas de texto 
    corrido de Diários Oficiais brasileiros.
    """

    def __init__(self):
        self.stats = defaultdict(int)

    def normalize_text(self, raw_text: str) -> str:
        """Normaliza encoding, whitespace e line breaks."""
        text = raw_text.replace('\r\n', '\n').replace('\r', '\n')
        # Collapse multiple spaces but preserve newlines
        text = re.sub(r'[ \t]+', ' ', text)
        # Remove zero-width characters
        text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
        return text.strip()

    def extract_cnpjs(self, text: str) -> list[dict]:
        """Extrai todos os CNPJs e o contexto ao redor."""
        results = []
        for match in RE_CNPJ.finditer(text):
            cnpj_raw = match.group(1)
            cnpj_clean = re.sub(r'[\.\s\/\-]', '', cnpj_raw)
            
            # Validate CNPJ length (14 digits)
            if len(cnpj_clean) != 14:
                continue
            
            # Format standardized
            cnpj_fmt = f"{cnpj_clean[:2]}.{cnpj_clean[2:5]}.{cnpj_clean[5:8]}/{cnpj_clean[8:12]}-{cnpj_clean[12:14]}"
            
            # Get context window
            start = max(0, match.start() - CONTEXT_WINDOW)
            end = min(len(text), match.end() + CONTEXT_WINDOW)
            context = text[start:end].strip()
            
            # Detect company name near CNPJ
            company_name = self._extract_company_near_cnpj(text, match.start(), match.end())
            
            results.append({
                "cnpj": cnpj_fmt,
                "cnpj_raw": cnpj_raw,
                "position": match.start(),
                "context": context,
                "company_name": company_name
            })
            self.stats['cnpjs'] += 1
        
        # Deduplicate by CNPJ
        seen = set()
        unique = []
        for r in results:
            if r["cnpj"] not in seen:
                seen.add(r["cnpj"])
                unique.append(r)
        return unique

    def extract_cpfs(self, text: str) -> list[dict]:
        """Extrai CPFs do texto."""
        results = []
        for match in RE_CPF.finditer(text):
            cpf_raw = match.group(1)
            cpf_clean = re.sub(r'[\.\s\-]', '', cpf_raw)
            if len(cpf_clean) != 11:
                continue
            
            start = max(0, match.start() - CONTEXT_WINDOW)
            end = min(len(text), match.end() + CONTEXT_WINDOW)
            
            results.append({
                "cpf": cpf_raw,
                "position": match.start(),
                "context": text[start:end].strip()
            })
            self.stats['cpfs'] += 1
        return results

    def extract_valores(self, text: str) -> list[dict]:
        """Extrai valores monetários (R$)."""
        results = []
        for match in RE_VALOR.finditer(text):
            valor_str = match.group(1) or match.group(2)
            if not valor_str:
                continue
            
            # Convert to float
            valor_float = self._parse_brl(valor_str)
            if valor_float <= 0:
                continue
            
            start = max(0, match.start() - CONTEXT_WINDOW)
            end = min(len(text), match.end() + CONTEXT_WINDOW)
            
            results.append({
                "valor_str": f"R$ {valor_str}",
                "valor_float": valor_float,
                "position": match.start(),
                "context": text[start:end].strip()
            })
            self.stats['valores'] += 1
        return results

    def extract_modalidades(self, text: str) -> list[dict]:
        """Extrai modalidades de licitação mencionadas."""
        results = []
        for match in RE_MODALIDADE.finditer(text):
            modalidade = match.group(0).strip().upper()
            
            start = max(0, match.start() - CONTEXT_WINDOW)
            end = min(len(text), match.end() + CONTEXT_WINDOW)
            context = text[start:end].strip()
            
            # Check for associated CNPJ near this modality
            nearby_cnpjs = self._find_nearby_cnpjs(text, match.start(), radius=500)
            # Check for associated value
            nearby_values = self._find_nearby_values(text, match.start(), radius=500)
            
            results.append({
                "modalidade": modalidade,
                "position": match.start(),
                "context": context,
                "cnpjs_nearby": nearby_cnpjs,
                "valores_nearby": nearby_values,
                "is_dispensa": 'DISPENSA' in modalidade or 'INEXIGIBILIDADE' in modalidade
            })
            self.stats['modalidades'] += 1
        return results

    def extract_processos(self, text: str) -> list[dict]:
        """Extrai números de processo/contrato/edital."""
        results = []
        for match in RE_PROCESSO.finditer(text):
            results.append({
                "numero": match.group(1),
                "tipo": match.group(0).split()[0].upper(),
                "position": match.start()
            })
            self.stats['processos'] += 1
        return results

    def extract_orgaos(self, text: str) -> list[str]:
        """Extrai nomes de órgãos contratantes."""
        orgaos = set()
        for match in RE_ORGAO.finditer(text):
            orgao = match.group(0).strip()
            orgao = re.sub(r'\s+', ' ', orgao)  # normalize spaces
            orgaos.add(orgao)
            self.stats['orgaos'] += 1
        return list(orgaos)

    # ── Full Extraction Pipeline ────────────────────────────────────
    def extract_all(self, raw_text: str, source_url: str = "", 
                    territory: str = "", date: str = "") -> dict:
        """
        Pipeline completo: extrai todas as entidades de um texto de
        Diário Oficial e retorna um dict estruturado.
        """
        self.stats = defaultdict(int)
        text = self.normalize_text(raw_text)
        
        cnpjs = self.extract_cnpjs(text)
        cpfs = self.extract_cpfs(text)
        valores = self.extract_valores(text)
        modalidades = self.extract_modalidades(text)
        processos = self.extract_processos(text)
        orgaos = self.extract_orgaos(text)
        
        # Compute suspicion score
        suspicion_score = self._compute_suspicion_score(
            text, cnpjs, modalidades, valores
        )
        
        result = {
            "source_url": source_url,
            "territory": territory,
            "date": date,
            "text_length": len(text),
            "entities": {
                "cnpjs": cnpjs,
                "cpfs": cpfs,
                "valores": valores,
                "modalidades": modalidades,
                "processos": processos,
                "orgaos": orgaos
            },
            "stats": dict(self.stats),
            "suspicion_score": suspicion_score,
            "suspicious_patterns": self._detect_patterns(cnpjs, modalidades, valores)
        }
        
        logger.info(
            f"  🔬 NLP: {len(cnpjs)} CNPJs, {len(valores)} valores, "
            f"{len(modalidades)} modalidades, score={suspicion_score}/100 "
            f"| {territory} {date}"
        )
        return result

    # ── Suspicion Scoring ───────────────────────────────────────────
    def _compute_suspicion_score(self, text: str, cnpjs: list, 
                                  modalidades: list, valores: list) -> int:
        """
        Calcula um score de suspeição (0-100) baseado em:
        - Dispensas/inexigibilidades encontradas
        - Valores altos sem licitação
        - Keywords suspeitas no texto
        - CNPJs repetidos em dispensas
        """
        score = 0
        text_lower = text.lower()
        
        # 1. Dispensas de licitação (+20 cada, max 40)
        dispensas = [m for m in modalidades if m.get("is_dispensa")]
        score += min(40, len(dispensas) * 20)
        
        # 2. Valores altos em dispensa (+15 cada > R$100k, max 30)
        for m in dispensas:
            for v in m.get("valores_nearby", []):
                if v > 100000:
                    score += 15
        score = min(score, 70)
        
        # 3. Suspicious keywords (+3 each, max 15)
        for kw in KEYWORDS_SUSPICIOUS:
            if kw in text_lower:
                score += 3
        score = min(score, 85)
        
        # 4. Multiple CNPJs in dispensas (+10, max 15)
        if len(dispensas) > 1 and len(cnpjs) > 1:
            score += 10
        
        return min(100, score)

    def _detect_patterns(self, cnpjs: list, modalidades: list, 
                         valores: list) -> list[dict]:
        """Detecta padrões específicos de fraude em licitação."""
        patterns = []
        
        # Pattern 1: CNPJ appears near dispensa
        dispensas = [m for m in modalidades if m.get("is_dispensa")]
        for d in dispensas:
            for cnpj in d.get("cnpjs_nearby", []):
                patterns.append({
                    "type": "DISPENSA_COM_CNPJ",
                    "severity": "HIGH",
                    "cnpj": cnpj,
                    "modalidade": d["modalidade"],
                    "detail": f"CNPJ {cnpj} mencionado próximo a {d['modalidade']}"
                })
        
        # Pattern 2: High value without competitive bidding
        for d in dispensas:
            for v in d.get("valores_nearby", []):
                if v > 50000:
                    patterns.append({
                        "type": "ALTO_VALOR_DISPENSA",
                        "severity": "CRITICAL",
                        "valor": v,
                        "modalidade": d["modalidade"],
                        "detail": f"R$ {v:,.2f} em {d['modalidade']} — acima do limiar de R$ 50.000"
                    })
        
        return patterns

    # ── Helpers ──────────────────────────────────────────────────────
    def _extract_company_near_cnpj(self, text: str, start: int, end: int) -> str:
        """Tenta extrair o nome da empresa perto de um CNPJ."""
        # Look in a window around the CNPJ
        window_start = max(0, start - 200)
        window_end = min(len(text), end + 200)
        window = text[window_start:window_end]
        
        match = RE_EMPRESA_APOS_CNPJ.search(window)
        if match:
            return match.group(1).strip()
        return ""

    def _find_nearby_cnpjs(self, text: str, pos: int, radius: int = 500) -> list[str]:
        """Encontra CNPJs num raio ao redor de uma posição."""
        start = max(0, pos - radius)
        end = min(len(text), pos + radius)
        window = text[start:end]
        
        cnpjs = []
        for m in RE_CNPJ.finditer(window):
            cnpj_clean = re.sub(r'[\.\s\/\-]', '', m.group(1))
            if len(cnpj_clean) == 14:
                cnpj_fmt = f"{cnpj_clean[:2]}.{cnpj_clean[2:5]}.{cnpj_clean[5:8]}/{cnpj_clean[8:12]}-{cnpj_clean[12:14]}"
                cnpjs.append(cnpj_fmt)
        return cnpjs

    def _find_nearby_values(self, text: str, pos: int, radius: int = 500) -> list[float]:
        """Encontra valores monetários num raio ao redor."""
        start = max(0, pos - radius)
        end = min(len(text), pos + radius)
        window = text[start:end]
        
        values = []
        for m in RE_VALOR.finditer(window):
            valor_str = m.group(1) or m.group(2)
            if valor_str:
                v = self._parse_brl(valor_str)
                if v > 0:
                    values.append(v)
        return values

    def _parse_brl(self, valor_str: str) -> float:
        """Converte string BRL para float. Ex: '1.234.567,89' -> 1234567.89"""
        try:
            clean = valor_str.replace('.', '').replace(',', '.')
            return float(clean)
        except (ValueError, AttributeError):
            return 0.0


# ══════════════════════════════════════════════════════════════════
# Standalone test
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    extractor = GazetteNLPExtractor()
    
    # Simulated gazette text snippet
    test_text = """
    PREFEITURA MUNICIPAL DE MACEIÓ
    SECRETARIA MUNICIPAL DE SAÚDE
    
    DISPENSA DE LICITAÇÃO Nº 045/2025
    Processo Administrativo nº 1234/2025
    
    Contratação direta da empresa CONSTRUTORA ALFA LTDA, 
    CNPJ: 12.345.678/0001-90, no valor de R$ 185.000,00 
    (cento e oitenta e cinco mil reais), para reforma 
    emergencial do posto de saúde.
    
    Fundamentação legal: Art. 24, inciso IV, da Lei 8.666/93.
    
    PREGÃO ELETRÔNICO Nº 022/2025
    Objeto: Aquisição de equipamentos médicos.
    Vencedora: MEDTECH EQUIPAMENTOS EIRELI, 
    CNPJ: 98.765.432/0001-10
    Valor: R$ 2.340.000,00
    
    O CPF do responsável é 123.456.789-00.
    """

    result = extractor.extract_all(
        test_text,
        source_url="https://example.com/dou/2025-01-15",
        territory="Maceió - AL",
        date="2025-01-15"
    )
    
    print(f"\n{'='*60}")
    print(f"CNPJs encontrados: {len(result['entities']['cnpjs'])}")
    for c in result['entities']['cnpjs']:
        print(f"  → {c['cnpj']} ({c['company_name'] or 'N/A'})")
    
    print(f"\nValores: {len(result['entities']['valores'])}")
    for v in result['entities']['valores']:
        print(f"  → {v['valor_str']} (R$ {v['valor_float']:,.2f})")
    
    print(f"\nModalidades: {len(result['entities']['modalidades'])}")
    for m in result['entities']['modalidades']:
        print(f"  → {m['modalidade']} (dispensa={m['is_dispensa']})")
    
    print(f"\nSuspicion Score: {result['suspicion_score']}/100")
    print(f"Patterns: {len(result['suspicious_patterns'])}")
    for p in result['suspicious_patterns']:
        print(f"  🚨 [{p['severity']}] {p['detail']}")

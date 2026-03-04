"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ROSIE ENGINE v2.0 — Complete Port of Serenata de Amor's AI               ║
║                                                                            ║
║  Original: github.com/okfn-brasil/serenata-de-amor (Rosie / butarr/rosie) ║
║  This port: Production-grade, integrated with CEAP bulk CSV pipeline       ║
║                                                                            ║
║  Classifiers implemented:                                                  ║
║   1. MealPriceOutlierClassifier    — Statistical outlier on meal expenses  ║
║   2. TravelSpeedClassifier         — Physically impossible trips           ║
║   3. MonthlySubquotaLimitClassifier— Over-limit spending per subcota       ║
║   4. ElectionPeriodClassifier      — Spending during election campaigns    ║
║   5. WeekendHolidayClassifier      — Expenses on non-working days          ║
║   6. DuplicateReceiptClassifier    — Same receipt submitted twice          ║
║   7. CNPJBlacklistClassifier       — Known irregular companies (CEIS/CNEP) ║
║   8. CompanyAgeClassifier          — Payments to very new companies        ║
║   9. BenfordLawClassifier          — Benford's Law digit distribution      ║
║  10. HighValueOutlierClassifier    — Global z-score anomaly detection      ║
║  11. SuspiciousSupplierClassifier  — Same supplier, too many deputies      ║
║  12. SequentialReceiptClassifier   — Sequential nota fiscal numbers        ║
║                                                                            ║
║  Architecture follows sklearn estimator pattern (original Rosie design)    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
import math
import json
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, date, timedelta
from collections import defaultdict, Counter
from typing import List, Dict, Optional, Tuple, Any

import numpy as np

logger = logging.getLogger("rosie")


# =============================================================================
# BASE CLASSIFIER INTERFACE (Original Rosie Pattern)
# =============================================================================

class BaseClassifier(ABC):
    """
    Follows sklearn estimator interface: fit() + predict()
    Each classifier receives the full dataset, learns distributions,
    then flags individual receipts as suspicious or not.
    """

    def __init__(self):
        self.name = self.__class__.__name__
        self._is_fitted = False

    @abstractmethod
    def fit(self, dataset: List[Dict]) -> 'BaseClassifier':
        """Learn statistical parameters from the full dataset."""
        pass

    @abstractmethod
    def predict(self, receipt: Dict) -> Dict:
        """
        Classify a single receipt.
        Returns: {
            "is_suspicious": bool,
            "classifier": str,
            "confidence": float,  # 0.0 to 1.0
            "reason": str,
            "details": dict
        }
        """
        pass

    def fit_predict(self, dataset: List[Dict]) -> List[Dict]:
        """Convenience: fit on all data, then predict each receipt."""
        self.fit(dataset)
        results = []
        for receipt in dataset:
            result = self.predict(receipt)
            if result["is_suspicious"]:
                results.append(result)
        return results


# =============================================================================
# CLASSIFIER 1: MEAL PRICE OUTLIER
# =============================================================================

class MealPriceOutlierClassifier(BaseClassifier):
    """
    Original Rosie logic: For each city (or state), learn the distribution
    of meal expenses. Flag values above mean + N*std as outliers.

    Uses IQR (Interquartile Range) method which is more robust against
    skewed distributions than z-score for expense data.
    """

    MEAL_CATEGORIES = {
        "FORNECIMENTO DE ALIMENTAÇÃO",
        "FORNECIMENTO DE ALIMENTACAO DO PARLAMENTAR",
    }

    def __init__(self, iqr_multiplier: float = 2.5, min_samples: int = 10):
        super().__init__()
        self.iqr_multiplier = iqr_multiplier
        self.min_samples = min_samples
        self.state_thresholds: Dict[str, float] = {}
        self.global_threshold: float = 0.0

    def fit(self, dataset: List[Dict]) -> 'MealPriceOutlierClassifier':
        """Learn meal price thresholds per state."""
        state_meals = defaultdict(list)
        all_meals = []

        for r in dataset:
            cat = r.get("categoria", "").strip().upper()
            if cat in self.MEAL_CATEGORIES:
                valor = r.get("valorDocumento", 0.0)
                if valor > 0:
                    state = r.get("ufFornecedor", "NA")
                    state_meals[state].append(valor)
                    all_meals.append(valor)

        # Per-state thresholds using IQR
        for state, values in state_meals.items():
            if len(values) >= self.min_samples:
                arr = np.array(values)
                q1, q3 = np.percentile(arr, [25, 75])
                iqr = q3 - q1
                self.state_thresholds[state] = q3 + self.iqr_multiplier * iqr

        # Global fallback
        if all_meals:
            arr = np.array(all_meals)
            q1, q3 = np.percentile(arr, [25, 75])
            iqr = q3 - q1
            self.global_threshold = q3 + self.iqr_multiplier * iqr

        self._is_fitted = True
        logger.info(f"[MealPriceOutlier] Fitted on {len(all_meals)} meal receipts, "
                     f"{len(self.state_thresholds)} state thresholds, "
                     f"global threshold: R$ {self.global_threshold:.2f}")
        return self

    def predict(self, receipt: Dict) -> Dict:
        cat = receipt.get("categoria", "").strip().upper()
        if cat not in self.MEAL_CATEGORIES:
            return {"is_suspicious": False, "classifier": self.name,
                    "confidence": 0.0, "reason": "", "details": {}}

        valor = receipt.get("valorDocumento", 0.0)
        state = receipt.get("ufFornecedor", "NA")
        threshold = self.state_thresholds.get(state, self.global_threshold)

        if threshold > 0 and valor > threshold:
            overshoot = (valor - threshold) / threshold if threshold else 0
            confidence = min(0.5 + overshoot * 0.3, 1.0)
            return {
                "is_suspicious": True,
                "classifier": self.name,
                "confidence": round(confidence, 3),
                "reason": f"Refeição de R$ {valor:.2f} excede o limiar de R$ {threshold:.2f} para UF={state}",
                "details": {
                    "valor": valor,
                    "threshold": round(threshold, 2),
                    "state": state,
                    "overshoot_pct": round(overshoot * 100, 1)
                },
                "receipt_id": receipt.get("id", "unknown"),
                "deputy_id": receipt.get("deputy_id", "unknown"),
            }

        return {"is_suspicious": False, "classifier": self.name,
                "confidence": 0.0, "reason": "", "details": {}}


# =============================================================================
# CLASSIFIER 2: TRAVEL SPEED (PHYSICALLY IMPOSSIBLE TRIPS)
# =============================================================================

class TravelSpeedClassifier(BaseClassifier):
    """
    Original Rosie logic: If a deputy has expenses in two different cities
    on the same day, check if travel between them is physically possible.

    Uses Haversine distance between state capitals as proxy.
    Flags if required speed > MAX_SPEED_KMH (typically 1200 km/h,
    accounting for domestic flights + ground transport).
    """

    MAX_SPEED_KMH = 1200  # Very generous: accounts for flights

    # Approximate lat/lon of Brazilian state capitals
    STATE_COORDS = {
        "AC": (-9.97, -67.81), "AL": (-9.67, -35.74), "AM": (-3.12, -60.02),
        "AP": (0.03, -51.07),  "BA": (-12.97, -38.51), "CE": (-3.72, -38.54),
        "DF": (-15.78, -47.93),"ES": (-20.32, -40.34), "GO": (-16.68, -49.25),
        "MA": (-2.53, -44.28), "MG": (-19.92, -43.94), "MS": (-20.44, -54.65),
        "MT": (-15.60, -56.10),"PA": (-1.46, -48.50),  "PB": (-7.12, -34.86),
        "PE": (-8.05, -34.87), "PI": (-5.09, -42.80),  "PR": (-25.43, -49.27),
        "RJ": (-22.91, -43.17),"RN": (-5.79, -35.21),  "RO": (-8.76, -63.90),
        "RR": (2.82, -60.67),  "RS": (-30.03, -51.23), "SC": (-27.59, -48.55),
        "SE": (-10.91, -37.07),"SP": (-23.55, -46.63), "TO": (-10.18, -48.33),
    }

    def __init__(self):
        super().__init__()
        self.deputy_daily_locations: Dict[str, Dict[str, List[str]]] = defaultdict(
            lambda: defaultdict(list)
        )

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2) -> float:
        """Distance in km between two coordinates."""
        R = 6371  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def fit(self, dataset: List[Dict]) -> 'TravelSpeedClassifier':
        """Group expenses by deputy + date to find multi-location days."""
        self.deputy_daily_locations = defaultdict(lambda: defaultdict(list))

        for r in dataset:
            dep_id = r.get("deputy_id", "")
            data = r.get("dataEmissao", "")[:10]
            uf = r.get("ufFornecedor", "NA")
            if dep_id and data and uf != "NA":
                if uf not in self.deputy_daily_locations[dep_id][data]:
                    self.deputy_daily_locations[dep_id][data].append(uf)

        multi_loc_days = sum(
            1 for dep in self.deputy_daily_locations.values()
            for day_locs in dep.values() if len(day_locs) > 1
        )
        logger.info(f"[TravelSpeed] Fitted: {multi_loc_days} multi-location days detected")
        self._is_fitted = True
        return self

    def predict(self, receipt: Dict) -> Dict:
        dep_id = receipt.get("deputy_id", "")
        data = receipt.get("dataEmissao", "")[:10]
        uf = receipt.get("ufFornecedor", "NA")

        if not dep_id or not data or uf == "NA":
            return {"is_suspicious": False, "classifier": self.name,
                    "confidence": 0.0, "reason": "", "details": {}}

        day_locations = self.deputy_daily_locations.get(dep_id, {}).get(data, [])
        if len(day_locations) <= 1:
            return {"is_suspicious": False, "classifier": self.name,
                    "confidence": 0.0, "reason": "", "details": {}}

        # Check all pairs
        max_distance = 0
        pair = ("", "")
        for i, loc_a in enumerate(day_locations):
            for loc_b in day_locations[i + 1:]:
                if loc_a in self.STATE_COORDS and loc_b in self.STATE_COORDS:
                    lat1, lon1 = self.STATE_COORDS[loc_a]
                    lat2, lon2 = self.STATE_COORDS[loc_b]
                    dist = self._haversine(lat1, lon1, lat2, lon2)
                    if dist > max_distance:
                        max_distance = dist
                        pair = (loc_a, loc_b)

        # Same-day travel at MAX_SPEED_KMH is physically impossible?
        # Assuming 24h day is too generous, use 16h effective travel window
        effective_hours = 16
        possible_distance = self.MAX_SPEED_KMH * effective_hours

        if max_distance > possible_distance:
            confidence = min(0.7 + (max_distance - possible_distance) / possible_distance * 0.3, 1.0)
            return {
                "is_suspicious": True,
                "classifier": self.name,
                "confidence": round(confidence, 3),
                "reason": (f"Gastos em {pair[0]} e {pair[1]} no mesmo dia ({data}). "
                           f"Distância: {max_distance:.0f} km, viagem fisicamente improvável."),
                "details": {
                    "date": data,
                    "locations": list(day_locations),
                    "max_distance_km": round(max_distance, 1),
                    "max_possible_km": possible_distance,
                },
                "receipt_id": receipt.get("id", "unknown"),
                "deputy_id": dep_id,
            }

        return {"is_suspicious": False, "classifier": self.name,
                "confidence": 0.0, "reason": "", "details": {}}


# =============================================================================
# CLASSIFIER 3: MONTHLY SUBQUOTA LIMIT
# =============================================================================

class MonthlySubquotaLimitClassifier(BaseClassifier):
    """
    Each CEAP subcategory has a monthly limit. This classifier checks
    if a deputy exceeds the official limit for any subcategory in a month.

    Official limits (2024/2025) vary by state:
    - Largest: SP = R$ 45,612.53/month total
    - Individual subquotas have specific caps (e.g., air tickets by state)
    """

    # Simplified subquota limits (official values from Câmara dos Deputados)
    SUBQUOTA_LIMITS = {
        "PASSAGENS AÉREAS": {
            "AC": 44632.46, "AM": 43570.12, "AP": 43374.78, "RO": 43672.49,
            "RR": 43936.18, "PA": 43374.78, "TO": 39503.61, "MA": 42151.69,
            "PI": 40971.77, "CE": 40107.11, "RN": 39428.32, "PB": 39428.32,
            "PE": 39428.32, "AL": 39428.32, "SE": 39428.32, "BA": 39503.61,
            "MG": 36092.71, "ES": 37423.91, "RJ": 35507.06, "SP": 37043.53,
            "PR": 38316.30, "SC": 39228.08, "RS": 40107.11, "MT": 39503.61,
            "MS": 39503.61, "GO": 36092.71, "DF": 30788.66,
        },
        "FORNECIMENTO DE ALIMENTAÇÃO": 40000.00,  # Generous fallback
        "HOSPEDAGEM": 40000.00,
        "LOCAÇÃO OU FRETAMENTO DE VEÍCULOS AUTOMOTORES": 19944.28,
        "COMBUSTÍVEIS E LUBRIFICANTES": 6000.00,
        "SERVIÇOS POSTAIS": 25000.00,
        "ASSINATURA DE PUBLICAÇÕES": 25000.00,
        "MANUTENÇÃO DE ESCRITÓRIO DE APOIO": 25000.00,
        "CONSULTORIAS, PESQUISAS E TRABALHOS TÉCNICOS": 25000.00,
        "DIVULGAÇÃO DA ATIVIDADE PARLAMENTAR": 45000.00,
        "TELEFONIA": 25000.00,
    }

    def __init__(self):
        super().__init__()
        # deputy_id -> month -> category -> accumulated total
        self.monthly_totals: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )

    def fit(self, dataset: List[Dict]) -> 'MonthlySubquotaLimitClassifier':
        self.monthly_totals = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

        for r in dataset:
            dep_id = r.get("deputy_id", "")
            data = r.get("dataEmissao", "")[:7]  # YYYY-MM
            cat = r.get("categoria", "").strip().upper()
            valor = r.get("valorDocumento", 0.0)

            if dep_id and data and cat and valor > 0:
                self.monthly_totals[dep_id][data][cat] += valor

        violations = 0
        for dep_id, months in self.monthly_totals.items():
            for month, cats in months.items():
                for cat, total in cats.items():
                    limit = self._get_limit(cat, "DF")  # Conservative: use DF (lowest)
                    if limit and total > limit:
                        violations += 1

        logger.info(f"[MonthlySubquota] Fitted: {violations} potential monthly limit violations")
        self._is_fitted = True
        return self

    def _get_limit(self, category: str, state: str = "DF") -> Optional[float]:
        limit = self.SUBQUOTA_LIMITS.get(category)
        if isinstance(limit, dict):
            return limit.get(state, limit.get("DF", 45000.0))
        return limit if isinstance(limit, (int, float)) else None

    def predict(self, receipt: Dict) -> Dict:
        dep_id = receipt.get("deputy_id", "")
        data = receipt.get("dataEmissao", "")[:7]
        cat = receipt.get("categoria", "").strip().upper()
        state = receipt.get("ufDeputado", "DF")

        if not dep_id or not data or not cat:
            return {"is_suspicious": False, "classifier": self.name,
                    "confidence": 0.0, "reason": "", "details": {}}

        monthly_total = self.monthly_totals.get(dep_id, {}).get(data, {}).get(cat, 0.0)
        limit = self._get_limit(cat, state)

        if limit and monthly_total > limit:
            overshoot = (monthly_total - limit) / limit
            confidence = min(0.6 + overshoot * 0.4, 1.0)
            return {
                "is_suspicious": True,
                "classifier": self.name,
                "confidence": round(confidence, 3),
                "reason": (f"Subcota '{cat}' em {data}: total R$ {monthly_total:,.2f} "
                           f"excede limite de R$ {limit:,.2f} ({overshoot * 100:.1f}% acima)"),
                "details": {
                    "category": cat,
                    "month": data,
                    "monthly_total": round(monthly_total, 2),
                    "limit": limit,
                    "overshoot_pct": round(overshoot * 100, 1),
                },
                "receipt_id": receipt.get("id", "unknown"),
                "deputy_id": dep_id,
            }

        return {"is_suspicious": False, "classifier": self.name,
                "confidence": 0.0, "reason": "", "details": {}}


# =============================================================================
# CLASSIFIER 4: ELECTION PERIOD SPENDING
# =============================================================================

class ElectionPeriodClassifier(BaseClassifier):
    """
    During official election campaign periods, deputies who are candidates
    should not use CEAP funds for campaign-related purposes.

    Election periods (approximate, official dates vary):
    - Municipal elections: Aug 16 - Oct (even years not divisible by 4)
    - Federal/State elections: Aug 16 - Oct (years divisible by 4)
    """

    ELECTION_PERIODS = {
        2022: (date(2022, 8, 16), date(2022, 10, 30)),
        2024: (date(2024, 8, 16), date(2024, 10, 27)),
        2026: (date(2026, 8, 16), date(2026, 10, 25)),
    }

    CAMPAIGN_LIKE_CATEGORIES = {
        "DIVULGAÇÃO DA ATIVIDADE PARLAMENTAR",
        "DIVULGACAO DA ATIVIDADE PARLAMENTAR",
        "SERVIÇO DE TÁXI, PEDÁGIO E ESTACIONAMENTO",
        "SERVICO DE TAXI, PEDAGIO E ESTACIONAMENTO",
        "COMBUSTÍVEIS E LUBRIFICANTES",
        "COMBUSTIVEIS E LUBRIFICANTES",
        "FORNECIMENTO DE ALIMENTAÇÃO",
        "FORNECIMENTO DE ALIMENTACAO DO PARLAMENTAR",
    }

    def __init__(self):
        super().__init__()

    def fit(self, dataset: List[Dict]) -> 'ElectionPeriodClassifier':
        count = 0
        for r in dataset:
            data_str = r.get("dataEmissao", "")[:10]
            if self._is_in_election_period(data_str):
                count += 1
        logger.info(f"[ElectionPeriod] Fitted: {count} receipts within election periods")
        self._is_fitted = True
        return self

    def _is_in_election_period(self, date_str: str) -> bool:
        try:
            d = date.fromisoformat(date_str)
            for year, (start, end) in self.ELECTION_PERIODS.items():
                if start <= d <= end:
                    return True
        except (ValueError, TypeError):
            pass
        return False

    def predict(self, receipt: Dict) -> Dict:
        data_str = receipt.get("dataEmissao", "")[:10]
        cat = receipt.get("categoria", "").strip().upper()

        if not self._is_in_election_period(data_str):
            return {"is_suspicious": False, "classifier": self.name,
                    "confidence": 0.0, "reason": "", "details": {}}

        is_campaign_like = cat in self.CAMPAIGN_LIKE_CATEGORIES
        valor = receipt.get("valorDocumento", 0.0)

        # Higher confidence for campaign-related categories
        confidence = 0.7 if is_campaign_like else 0.4
        if valor > 5000:
            confidence = min(confidence + 0.2, 1.0)

        return {
            "is_suspicious": True,
            "classifier": self.name,
            "confidence": round(confidence, 3),
            "reason": (f"Gasto de R$ {valor:.2f} em '{cat}' durante período eleitoral ({data_str}). "
                       f"{'Categoria associada a campanha.' if is_campaign_like else 'Monitoramento de rotina.'}"),
            "details": {
                "date": data_str,
                "category": cat,
                "valor": valor,
                "is_campaign_like_category": is_campaign_like,
            },
            "receipt_id": receipt.get("id", "unknown"),
            "deputy_id": receipt.get("deputy_id", "unknown"),
        }


# =============================================================================
# CLASSIFIER 5: WEEKEND / HOLIDAY SPENDING
# =============================================================================

class WeekendHolidayClassifier(BaseClassifier):
    """
    Flags expenses on weekends and national holidays.
    Some categories are normal on weekends (fuel, tolls),
    while others are suspicious (office supplies, consultancy).
    """

    NATIONAL_HOLIDAYS_2024_2025 = {
        date(2024, 1, 1), date(2024, 2, 12), date(2024, 2, 13),
        date(2024, 3, 29), date(2024, 4, 21), date(2024, 5, 1),
        date(2024, 5, 30), date(2024, 9, 7), date(2024, 10, 12),
        date(2024, 11, 2), date(2024, 11, 15), date(2024, 11, 20),
        date(2024, 12, 25),
        date(2025, 1, 1), date(2025, 3, 3), date(2025, 3, 4),
        date(2025, 4, 18), date(2025, 4, 21), date(2025, 5, 1),
        date(2025, 6, 19), date(2025, 9, 7), date(2025, 10, 12),
        date(2025, 11, 2), date(2025, 11, 15), date(2025, 11, 20),
        date(2025, 12, 25),
    }

    # Categories that are NORMAL on weekends (lower suspicion)
    WEEKEND_NORMAL_CATEGORIES = {
        "COMBUSTÍVEIS E LUBRIFICANTES",
        "COMBUSTIVEIS E LUBRIFICANTES",
        "SERVIÇO DE TÁXI, PEDÁGIO E ESTACIONAMENTO",
        "SERVICO DE TAXI, PEDAGIO E ESTACIONAMENTO",
        "PASSAGENS AÉREAS",
        "PASSAGENS AEREAS",
        "TELEFONIA",
    }

    def __init__(self):
        super().__init__()

    def fit(self, dataset: List[Dict]) -> 'WeekendHolidayClassifier':
        weekend_count = 0
        for r in dataset:
            try:
                d = date.fromisoformat(r.get("dataEmissao", "")[:10])
                if d.weekday() >= 5 or d in self.NATIONAL_HOLIDAYS_2024_2025:
                    weekend_count += 1
            except (ValueError, TypeError):
                pass
        logger.info(f"[WeekendHoliday] Fitted: {weekend_count} receipts on weekends/holidays")
        self._is_fitted = True
        return self

    def predict(self, receipt: Dict) -> Dict:
        data_str = receipt.get("dataEmissao", "")[:10]
        try:
            d = date.fromisoformat(data_str)
        except (ValueError, TypeError):
            return {"is_suspicious": False, "classifier": self.name,
                    "confidence": 0.0, "reason": "", "details": {}}

        is_weekend = d.weekday() >= 5
        is_holiday = d in self.NATIONAL_HOLIDAYS_2024_2025

        if not is_weekend and not is_holiday:
            return {"is_suspicious": False, "classifier": self.name,
                    "confidence": 0.0, "reason": "", "details": {}}

        cat = receipt.get("categoria", "").strip().upper()
        is_normal_weekend_cat = cat in self.WEEKEND_NORMAL_CATEGORIES
        valor = receipt.get("valorDocumento", 0.0)

        day_type = "feriado nacional" if is_holiday else "fim de semana"
        day_name = d.strftime("%A")

        if is_normal_weekend_cat:
            confidence = 0.25  # Low: taxi/fuel on weekends is common
        else:
            confidence = 0.55
            if valor > 2000:
                confidence = 0.70
            if valor > 10000:
                confidence = 0.85

        return {
            "is_suspicious": True,
            "classifier": self.name,
            "confidence": round(confidence, 3),
            "reason": (f"Gasto de R$ {valor:.2f} em '{cat}' em {day_type} "
                       f"({data_str}, {day_name})"),
            "details": {
                "date": data_str,
                "day_of_week": day_name,
                "is_weekend": is_weekend,
                "is_holiday": is_holiday,
                "category": cat,
                "is_normal_weekend_category": is_normal_weekend_cat,
            },
            "receipt_id": receipt.get("id", "unknown"),
            "deputy_id": receipt.get("deputy_id", "unknown"),
        }


# =============================================================================
# CLASSIFIER 6: DUPLICATE RECEIPTS
# =============================================================================

class DuplicateReceiptClassifier(BaseClassifier):
    """
    Detects potentially duplicate receipts by creating a fingerprint
    from (supplier, value, date, category). If two receipts from the
    same deputy match, flag both.
    """

    def __init__(self):
        super().__init__()
        # fingerprint -> list of receipt IDs
        self.fingerprints: Dict[str, List[Dict]] = defaultdict(list)

    def _make_fingerprint(self, receipt: Dict) -> str:
        """Create a deduplication fingerprint."""
        parts = [
            str(receipt.get("deputy_id", "")),
            str(receipt.get("nomeFornecedor", "")).strip().upper(),
            f"{receipt.get('valorDocumento', 0.0):.2f}",
            receipt.get("dataEmissao", "")[:10],
        ]
        raw = "|".join(parts)
        return hashlib.md5(raw.encode()).hexdigest()

    def fit(self, dataset: List[Dict]) -> 'DuplicateReceiptClassifier':
        self.fingerprints = defaultdict(list)
        for r in dataset:
            fp = self._make_fingerprint(r)
            self.fingerprints[fp].append(r)

        dup_count = sum(1 for v in self.fingerprints.values() if len(v) > 1)
        logger.info(f"[DuplicateReceipt] Fitted: {dup_count} potential duplicate groups")
        self._is_fitted = True
        return self

    def predict(self, receipt: Dict) -> Dict:
        fp = self._make_fingerprint(receipt)
        group = self.fingerprints.get(fp, [])

        if len(group) <= 1:
            return {"is_suspicious": False, "classifier": self.name,
                    "confidence": 0.0, "reason": "", "details": {}}

        valor = receipt.get("valorDocumento", 0.0)
        fornecedor = receipt.get("nomeFornecedor", "Unknown")
        n_duplicates = len(group)

        confidence = min(0.7 + (n_duplicates - 2) * 0.1, 0.95)

        return {
            "is_suspicious": True,
            "classifier": self.name,
            "confidence": round(confidence, 3),
            "reason": (f"Recibo potencialmente duplicado: {n_duplicates} recibos de "
                       f"R$ {valor:.2f} para '{fornecedor}' na mesma data"),
            "details": {
                "fingerprint": fp,
                "n_duplicates": n_duplicates,
                "fornecedor": fornecedor,
                "valor": valor,
                "receipt_ids": [r.get("id", "?") for r in group],
            },
            "receipt_id": receipt.get("id", "unknown"),
            "deputy_id": receipt.get("deputy_id", "unknown"),
        }


# =============================================================================
# CLASSIFIER 7: CNPJ BLACKLIST (CEIS / CNEP)
# =============================================================================

class CNPJBlacklistClassifier(BaseClassifier):
    """
    Cross-references supplier CNPJs against known blacklists:
    - CEIS (Cadastro de Empresas Inidôneas e Suspensas)
    - CNEP (Cadastro Nacional de Empresas Punidas)

    The blacklist must be loaded externally (from Portal da Transparência API).
    """

    def __init__(self, blacklist_cnpjs: Optional[set] = None):
        super().__init__()
        self.blacklist = blacklist_cnpjs or set()

    def load_blacklist_from_file(self, filepath: str):
        """Load CNPJ blacklist from a line-separated file."""
        try:
            with open(filepath, "r") as f:
                for line in f:
                    cnpj = line.strip().replace(".", "").replace("/", "").replace("-", "")
                    if cnpj:
                        self.blacklist.add(cnpj)
            logger.info(f"[CNPJBlacklist] Loaded {len(self.blacklist)} blacklisted CNPJs")
        except FileNotFoundError:
            logger.warning(f"[CNPJBlacklist] Blacklist file not found: {filepath}")

    def fit(self, dataset: List[Dict]) -> 'CNPJBlacklistClassifier':
        hits = 0
        for r in dataset:
            cnpj = str(r.get("cnpjFornecedor", "")).replace(".", "").replace("/", "").replace("-", "")
            if cnpj in self.blacklist:
                hits += 1
        logger.info(f"[CNPJBlacklist] Fitted: {hits} receipts from blacklisted companies "
                     f"(blacklist size: {len(self.blacklist)})")
        self._is_fitted = True
        return self

    def predict(self, receipt: Dict) -> Dict:
        cnpj = str(receipt.get("cnpjFornecedor", "")).replace(".", "").replace("/", "").replace("-", "")

        if not cnpj or cnpj not in self.blacklist:
            return {"is_suspicious": False, "classifier": self.name,
                    "confidence": 0.0, "reason": "", "details": {}}

        valor = receipt.get("valorDocumento", 0.0)
        fornecedor = receipt.get("nomeFornecedor", "Unknown")

        return {
            "is_suspicious": True,
            "classifier": self.name,
            "confidence": 0.95,  # Very high: blacklisted company
            "reason": (f"Fornecedor '{fornecedor}' (CNPJ: {cnpj}) consta no CEIS/CNEP. "
                       f"Valor: R$ {valor:.2f}"),
            "details": {
                "cnpj": cnpj,
                "fornecedor": fornecedor,
                "valor": valor,
            },
            "receipt_id": receipt.get("id", "unknown"),
            "deputy_id": receipt.get("deputy_id", "unknown"),
        }


# =============================================================================
# CLASSIFIER 8: COMPANY AGE (VERY NEW COMPANIES)
# =============================================================================

class CompanyAgeClassifier(BaseClassifier):
    """
    Flags payments to companies that were created very recently
    (within N months of the expense). Requires company founding dates
    from Receita Federal CNPJ data.
    """

    def __init__(self, min_age_months: int = 3, company_dates: Optional[Dict[str, str]] = None):
        super().__init__()
        self.min_age_months = min_age_months
        self.company_dates = company_dates or {}  # cnpj -> "YYYY-MM-DD" founding date

    def load_company_dates(self, filepath: str):
        """Load company founding dates from JSON: {"cnpj": "date", ...}"""
        try:
            with open(filepath, "r") as f:
                self.company_dates = json.load(f)
            logger.info(f"[CompanyAge] Loaded founding dates for {len(self.company_dates)} companies")
        except FileNotFoundError:
            logger.warning(f"[CompanyAge] Company dates file not found: {filepath}")

    def fit(self, dataset: List[Dict]) -> 'CompanyAgeClassifier':
        logger.info(f"[CompanyAge] Fitted with {len(self.company_dates)} company founding dates")
        self._is_fitted = True
        return self

    def predict(self, receipt: Dict) -> Dict:
        cnpj = str(receipt.get("cnpjFornecedor", "")).replace(".", "").replace("/", "").replace("-", "")
        founding_str = self.company_dates.get(cnpj)

        if not founding_str:
            return {"is_suspicious": False, "classifier": self.name,
                    "confidence": 0.0, "reason": "", "details": {}}

        try:
            founding_date = date.fromisoformat(founding_str[:10])
            expense_date = date.fromisoformat(receipt.get("dataEmissao", "")[:10])
            age_days = (expense_date - founding_date).days
            age_months = age_days / 30.44

            if age_months < self.min_age_months:
                confidence = max(0.5, min(1.0 - age_months / self.min_age_months, 0.90))
                return {
                    "is_suspicious": True,
                    "classifier": self.name,
                    "confidence": round(confidence, 3),
                    "reason": (f"Empresa criada há apenas {age_days} dias "
                               f"({age_months:.1f} meses) antes da despesa"),
                    "details": {
                        "cnpj": cnpj,
                        "founding_date": founding_str,
                        "expense_date": receipt.get("dataEmissao", "")[:10],
                        "age_days": age_days,
                        "age_months": round(age_months, 1),
                    },
                    "receipt_id": receipt.get("id", "unknown"),
                    "deputy_id": receipt.get("deputy_id", "unknown"),
                }
        except (ValueError, TypeError):
            pass

        return {"is_suspicious": False, "classifier": self.name,
                "confidence": 0.0, "reason": "", "details": {}}


# =============================================================================
# CLASSIFIER 9: BENFORD'S LAW
# =============================================================================

class BenfordLawClassifier(BaseClassifier):
    """
    Applies Benford's Law (first-digit distribution) to detect
    manipulated financial data. Works at the deputy level: if a
    deputy's expense values deviate significantly from expected
    Benford distribution, flag all their receipts with a penalty.

    Uses Chi-squared test for significance.
    """

    # Expected frequencies for first digit (Benford's Law)
    BENFORD_EXPECTED = {
        1: 0.30103, 2: 0.17609, 3: 0.12494, 4: 0.09691,
        5: 0.07918, 6: 0.06695, 7: 0.05799, 8: 0.05115, 9: 0.04576
    }

    def __init__(self, significance_level: float = 0.05, min_receipts: int = 50):
        super().__init__()
        self.significance_level = significance_level
        self.min_receipts = min_receipts
        self.deputy_scores: Dict[str, float] = {}  # dep_id -> chi2 p-value
        self.deputy_flags: Dict[str, bool] = {}

    def fit(self, dataset: List[Dict]) -> 'BenfordLawClassifier':
        deputy_values = defaultdict(list)
        for r in dataset:
            dep_id = r.get("deputy_id", "")
            valor = r.get("valorDocumento", 0.0)
            if dep_id and valor > 0:
                deputy_values[dep_id].append(valor)

        for dep_id, values in deputy_values.items():
            if len(values) < self.min_receipts:
                continue

            # Count first digits
            first_digits = Counter()
            for v in values:
                # Get first significant digit
                abs_v = abs(v)
                if abs_v >= 1:
                    first_digit = int(str(abs_v).lstrip("0")[0])
                    if 1 <= first_digit <= 9:
                        first_digits[first_digit] += 1

            total = sum(first_digits.values())
            if total < self.min_receipts:
                continue

            # Chi-squared test
            chi2 = 0.0
            for digit in range(1, 10):
                observed = first_digits.get(digit, 0)
                expected = self.BENFORD_EXPECTED[digit] * total
                if expected > 0:
                    chi2 += (observed - expected) ** 2 / expected

            # Chi-squared critical value for 8 degrees of freedom at 0.05: 15.507
            # at 0.01: 20.090
            critical_value = 15.507  # df=8, alpha=0.05
            self.deputy_flags[dep_id] = chi2 > critical_value
            self.deputy_scores[dep_id] = chi2

        flagged = sum(1 for v in self.deputy_flags.values() if v)
        logger.info(f"[BenfordLaw] Fitted: {flagged}/{len(self.deputy_flags)} deputies "
                     f"deviate from Benford's Law")
        self._is_fitted = True
        return self

    def predict(self, receipt: Dict) -> Dict:
        dep_id = receipt.get("deputy_id", "")
        if not dep_id or not self.deputy_flags.get(dep_id, False):
            return {"is_suspicious": False, "classifier": self.name,
                    "confidence": 0.0, "reason": "", "details": {}}

        chi2 = self.deputy_scores.get(dep_id, 0)
        # Confidence scales with how far chi2 exceeds critical value
        confidence = min(0.5 + (chi2 - 15.507) / 50.0, 0.85)

        return {
            "is_suspicious": True,
            "classifier": self.name,
            "confidence": round(max(confidence, 0.5), 3),
            "reason": (f"Distribuição de dígitos dos gastos deste deputado viola "
                       f"a Lei de Benford (χ²={chi2:.2f}, limiar=15.51). "
                       f"Pode indicar manipulação de valores."),
            "details": {
                "chi_squared": round(chi2, 3),
                "critical_value": 15.507,
                "significance_level": self.significance_level,
            },
            "receipt_id": receipt.get("id", "unknown"),
            "deputy_id": dep_id,
        }


# =============================================================================
# CLASSIFIER 10: HIGH VALUE OUTLIER (GLOBAL Z-SCORE)
# =============================================================================

class HighValueOutlierClassifier(BaseClassifier):
    """
    Simple global z-score outlier detection per category.
    Flags any receipt where the value is N standard deviations
    above the mean for that category.
    """

    def __init__(self, z_threshold: float = 3.5):
        super().__init__()
        self.z_threshold = z_threshold
        self.category_stats: Dict[str, Tuple[float, float]] = {}  # cat -> (mean, std)

    def fit(self, dataset: List[Dict]) -> 'HighValueOutlierClassifier':
        category_values = defaultdict(list)
        for r in dataset:
            cat = r.get("categoria", "").strip().upper()
            valor = r.get("valorDocumento", 0.0)
            if cat and valor > 0:
                category_values[cat].append(valor)

        for cat, values in category_values.items():
            if len(values) >= 5:
                arr = np.array(values)
                self.category_stats[cat] = (float(np.mean(arr)), float(np.std(arr)))

        logger.info(f"[HighValueOutlier] Fitted: stats for {len(self.category_stats)} categories")
        self._is_fitted = True
        return self

    def predict(self, receipt: Dict) -> Dict:
        cat = receipt.get("categoria", "").strip().upper()
        valor = receipt.get("valorDocumento", 0.0)

        stats = self.category_stats.get(cat)
        if not stats or stats[1] == 0:
            return {"is_suspicious": False, "classifier": self.name,
                    "confidence": 0.0, "reason": "", "details": {}}

        mean, std = stats
        z_score = (valor - mean) / std

        if z_score > self.z_threshold:
            confidence = min(0.5 + (z_score - self.z_threshold) * 0.1, 0.95)
            return {
                "is_suspicious": True,
                "classifier": self.name,
                "confidence": round(confidence, 3),
                "reason": (f"Valor R$ {valor:,.2f} é outlier para '{cat}' "
                           f"(z-score={z_score:.2f}, média=R$ {mean:,.2f})"),
                "details": {
                    "valor": valor,
                    "category": cat,
                    "z_score": round(z_score, 3),
                    "mean": round(mean, 2),
                    "std": round(std, 2),
                },
                "receipt_id": receipt.get("id", "unknown"),
                "deputy_id": receipt.get("deputy_id", "unknown"),
            }

        return {"is_suspicious": False, "classifier": self.name,
                "confidence": 0.0, "reason": "", "details": {}}


# =============================================================================
# CLASSIFIER 11: SUSPICIOUS SUPPLIER (TOO MANY DEPUTIES)
# =============================================================================

class SuspiciousSupplierClassifier(BaseClassifier):
    """
    Flags suppliers (by name or CNPJ) that serve an unusually high
    number of different deputies. Could indicate shell companies
    created specifically to funnel CEAP funds.
    """

    def __init__(self, max_deputies_per_supplier: int = 30):
        super().__init__()
        self.max_deputies = max_deputies_per_supplier
        self.supplier_deputies: Dict[str, set] = defaultdict(set)
        self.flagged_suppliers: set = set()

    def fit(self, dataset: List[Dict]) -> 'SuspiciousSupplierClassifier':
        self.supplier_deputies = defaultdict(set)

        for r in dataset:
            fornecedor = r.get("nomeFornecedor", "").strip().upper()
            dep_id = r.get("deputy_id", "")
            if fornecedor and dep_id:
                self.supplier_deputies[fornecedor].add(dep_id)

        self.flagged_suppliers = {
            s for s, deps in self.supplier_deputies.items()
            if len(deps) > self.max_deputies
        }

        logger.info(f"[SuspiciousSupplier] Fitted: {len(self.flagged_suppliers)} suppliers "
                     f"serve >{self.max_deputies} different deputies")
        self._is_fitted = True
        return self

    def predict(self, receipt: Dict) -> Dict:
        fornecedor = receipt.get("nomeFornecedor", "").strip().upper()

        if fornecedor not in self.flagged_suppliers:
            return {"is_suspicious": False, "classifier": self.name,
                    "confidence": 0.0, "reason": "", "details": {}}

        n_deputies = len(self.supplier_deputies[fornecedor])
        confidence = min(0.5 + (n_deputies - self.max_deputies) / 100.0, 0.85)

        return {
            "is_suspicious": True,
            "classifier": self.name,
            "confidence": round(confidence, 3),
            "reason": (f"Fornecedor '{fornecedor}' atende {n_deputies} deputados diferentes "
                       f"(limiar: {self.max_deputies}). Possível empresa de fachada."),
            "details": {
                "fornecedor": fornecedor,
                "n_deputies_served": n_deputies,
                "threshold": self.max_deputies,
            },
            "receipt_id": receipt.get("id", "unknown"),
            "deputy_id": receipt.get("deputy_id", "unknown"),
        }


# =============================================================================
# CLASSIFIER 12: SEQUENTIAL RECEIPT NUMBERS
# =============================================================================

class SequentialReceiptClassifier(BaseClassifier):
    """
    If a deputy has multiple receipts from the same supplier with
    sequential document numbers (nota fiscal), it may indicate
    fabricated receipts. Legitimate businesses don't typically issue
    sequential invoices to the same customer.
    """

    def __init__(self, max_sequential: int = 3):
        super().__init__()
        self.max_sequential = max_sequential
        # (deputy_id, fornecedor) -> sorted list of doc numbers
        self.deputy_supplier_docs: Dict[Tuple[str, str], List[int]] = defaultdict(list)
        self.flagged_pairs: set = set()

    def fit(self, dataset: List[Dict]) -> 'SequentialReceiptClassifier':
        self.deputy_supplier_docs = defaultdict(list)

        for r in dataset:
            dep_id = r.get("deputy_id", "")
            fornecedor = r.get("nomeFornecedor", "").strip().upper()
            num_doc = r.get("numDocumento", "")

            if dep_id and fornecedor and num_doc:
                try:
                    # Try to extract numeric part
                    numeric = int("".join(c for c in str(num_doc) if c.isdigit()) or "0")
                    if numeric > 0:
                        self.deputy_supplier_docs[(dep_id, fornecedor)].append(numeric)
                except ValueError:
                    pass

        # Find sequential runs
        self.flagged_pairs = set()
        for key, nums in self.deputy_supplier_docs.items():
            if len(nums) < self.max_sequential:
                continue
            nums_sorted = sorted(set(nums))
            # Check for consecutive sequences
            max_run = 1
            current_run = 1
            for i in range(1, len(nums_sorted)):
                if nums_sorted[i] == nums_sorted[i - 1] + 1:
                    current_run += 1
                    max_run = max(max_run, current_run)
                else:
                    current_run = 1
            if max_run >= self.max_sequential:
                self.flagged_pairs.add(key)

        logger.info(f"[SequentialReceipt] Fitted: {len(self.flagged_pairs)} "
                     f"deputy-supplier pairs with sequential receipts")
        self._is_fitted = True
        return self

    def predict(self, receipt: Dict) -> Dict:
        dep_id = receipt.get("deputy_id", "")
        fornecedor = receipt.get("nomeFornecedor", "").strip().upper()
        key = (dep_id, fornecedor)

        if key not in self.flagged_pairs:
            return {"is_suspicious": False, "classifier": self.name,
                    "confidence": 0.0, "reason": "", "details": {}}

        nums = sorted(set(self.deputy_supplier_docs.get(key, [])))
        confidence = min(0.6 + len(nums) * 0.05, 0.90)

        return {
            "is_suspicious": True,
            "classifier": self.name,
            "confidence": round(confidence, 3),
            "reason": (f"Notas fiscais sequenciais de '{fornecedor}' para o mesmo deputado. "
                       f"({len(nums)} notas, números: {nums[:10]}...)"),
            "details": {
                "fornecedor": fornecedor,
                "n_sequential_docs": len(nums),
                "doc_numbers_sample": nums[:10],
            },
            "receipt_id": receipt.get("id", "unknown"),
            "deputy_id": dep_id,
        }


# =============================================================================
# NEW CLASSIFIERS: PERSONAL HEALTH AND LUXURY EXPENSES
# =============================================================================

class PersonalHealthExpenseClassifier(BaseClassifier):
    """
    Deteta gastos com saúde pessoal, estética ou odontologia na CEAP.
    O caso Erika Hilton: despesas médicas possuem cota própria. 
    Se aparecem na CEAP, indica desvio de finalidade.
    """
    def fit(self, dataset: List[Dict]) -> 'PersonalHealthExpenseClassifier':
        self._is_fitted = True
        return self

    def predict(self, receipt: Dict) -> Dict:
        import re
        supplier_name = str(receipt.get("nomeFornecedor", "")).upper()
        # Palavras que expõem clínicas e procedimentos estéticos/médicos no CNPJ
        pattern = r'\b(CLINICA|ODONTO|ODONTOLOGIA|ODONTOLOGICA|ESTETICA|CIRURGIA|PLASTICA|DERMATOLOGIA|FARMACIA|BOTOX|HARMONIZACAO|HOSPITAL|MEDIC[OA]|SPA)\b'
        
        if re.search(pattern, supplier_name):
            return {
                "is_suspicious": True,
                "classifier": self.name,
                "confidence": 0.95,
                "reason": f"Despesa médica/estética irregular na CEAP. Fornecedor: '{supplier_name}'. Gastos de saúde têm fundo próprio e são vedados na Cota Parlamentar.",
                "details": {"supplier_name": supplier_name},
                "receipt_id": receipt.get("id", "unknown"),
                "deputy_id": receipt.get("deputy_id", "unknown")
            }
            
        return {"is_suspicious": False, "classifier": self.name, "confidence": 0.0, "reason": "", "details": {}}


class LuxuryPersonalExpenseClassifier(BaseClassifier):
    """
    Deteta gastos em joalherias, pet shops, supermercados e resorts.
    Comum em fraudes de uso pessoal do dinheiro público.
    """
    def fit(self, dataset: List[Dict]) -> 'LuxuryPersonalExpenseClassifier':
        self._is_fitted = True
        return self

    def predict(self, receipt: Dict) -> Dict:
        import re
        supplier_name = str(receipt.get("nomeFornecedor", "")).upper()
        pattern = r'\b(PET SHOP|VETERINARI[OA]|RESORT|JOALHERIA|JOIAS|COSMETICOS|BELEZA|CABELEIREIRO|BARBEARIA)\b'
        
        if re.search(pattern, supplier_name):
            return {
                "is_suspicious": True,
                "classifier": self.name,
                "confidence": 0.90,
                "reason": f"Indício de gasto pessoal/luxo proibido. Fornecedor: '{supplier_name}'.",
                "details": {"supplier_name": supplier_name},
                "receipt_id": receipt.get("id", "unknown"),
                "deputy_id": receipt.get("deputy_id", "unknown")
            }
            
        return {"is_suspicious": False, "classifier": self.name, "confidence": 0.0, "reason": "", "details": {}}

# =============================================================================
# ROSIE ENGINE — ORCHESTRATES ALL CLASSIFIERS
# =============================================================================

class RosieEngine:
    """
    The main Rosie engine. Initializes all classifiers, fits them
    on the dataset, and produces a structured anomaly report.

    Usage:
        rosie = RosieEngine()
        report = rosie.analyze(receipts_list)
    """

    def __init__(self,
                 blacklist_cnpjs: Optional[set] = None,
                 company_dates: Optional[Dict] = None,
                 enable_all: bool = True):
        """
        Initialize Rosie with all classifiers.

        Args:
            blacklist_cnpjs: Set of CNPJ strings from CEIS/CNEP
            company_dates: Dict of cnpj -> founding date string
            enable_all: If True, enable all classifiers
        """
        self.classifiers: List[BaseClassifier] = []

        if enable_all:
            self.classifiers = [
                MealPriceOutlierClassifier(iqr_multiplier=2.5),
                TravelSpeedClassifier(),
                MonthlySubquotaLimitClassifier(),
                ElectionPeriodClassifier(),
                WeekendHolidayClassifier(),
                DuplicateReceiptClassifier(),
                CNPJBlacklistClassifier(blacklist_cnpjs=blacklist_cnpjs),
                CompanyAgeClassifier(company_dates=company_dates),
                BenfordLawClassifier(min_receipts=30),
                HighValueOutlierClassifier(z_threshold=3.5),
                SuspiciousSupplierClassifier(max_deputies_per_supplier=30),
                SequentialReceiptClassifier(max_sequential=3),
                PersonalHealthExpenseClassifier(),
                LuxuryPersonalExpenseClassifier(),
            ]

        logger.info(f"🤖 Rosie Engine initialized with {len(self.classifiers)} classifiers")

    def add_classifier(self, classifier: BaseClassifier):
        """Add a custom classifier to the pipeline."""
        self.classifiers.append(classifier)

    def analyze(self, receipts: List[Dict]) -> Dict:
        """
        Main analysis pipeline.

        Args:
            receipts: List of expense dicts with keys:
                - id, deputy_id, dataEmissao, categoria, valorDocumento,
                  nomeFornecedor, ufFornecedor, cnpjFornecedor, numDocumento

        Returns:
            Structured report with anomalies per deputy and per classifier.
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"  🤖 ROSIE ANALYSIS — {len(receipts)} receipts, "
                     f"{len(self.classifiers)} classifiers")
        logger.info(f"{'='*60}")

        # Phase 1: Fit all classifiers on the complete dataset
        logger.info("\n📊 Phase 1: Fitting classifiers on dataset...")
        for clf in self.classifiers:
            try:
                clf.fit(receipts)
            except Exception as e:
                logger.error(f"  Error fitting {clf.name}: {e}")

        # Phase 2: Predict on every receipt
        logger.info("\n🔍 Phase 2: Scanning all receipts...")
        all_anomalies: List[Dict] = []
        anomalies_by_deputy: Dict[str, List[Dict]] = defaultdict(list)
        anomalies_by_classifier: Dict[str, int] = defaultdict(int)

        for receipt in receipts:
            for clf in self.classifiers:
                try:
                    result = clf.predict(receipt)
                    if result["is_suspicious"]:
                        all_anomalies.append(result)
                        dep_id = result.get("deputy_id", receipt.get("deputy_id", "unknown"))
                        anomalies_by_deputy[dep_id].append(result)
                        anomalies_by_classifier[clf.name] += 1
                except Exception as e:
                    logger.error(f"  Error predicting with {clf.name}: {e}")

        # Phase 3: Compute risk scores per deputy
        logger.info("\n📈 Phase 3: Computing risk scores...")
        deputy_risk_scores = {}
        for dep_id, anomalies in anomalies_by_deputy.items():
            # Weighted score: sum of confidences, normalized
            total_confidence = sum(a["confidence"] for a in anomalies)
            n_classifiers_triggered = len(set(a["classifier"] for a in anomalies))
            n_anomalies = len(anomalies)

            # Risk formula: combines volume, severity, and breadth
            # Higher score = more suspicious
            risk_score = (
                total_confidence * 0.4 +
                n_classifiers_triggered * 10.0 * 0.3 +
                min(n_anomalies, 50) * 0.3
            )
            # Normalize to 0-100
            risk_score = min(risk_score, 100.0)

            deputy_risk_scores[dep_id] = {
                "risk_score": round(risk_score, 2),
                "n_anomalies": n_anomalies,
                "n_classifiers_triggered": n_classifiers_triggered,
                "total_confidence": round(total_confidence, 3),
                "top_anomalies": sorted(anomalies, key=lambda x: -x["confidence"])[:10],
            }

        # Phase 4: Build report
        report = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "n_receipts_analyzed": len(receipts),
                "n_classifiers": len(self.classifiers),
                "classifiers_used": [c.name for c in self.classifiers],
            },
            "summary": {
                "total_anomalies": len(all_anomalies),
                "deputies_with_anomalies": len(anomalies_by_deputy),
                "anomalies_by_classifier": dict(anomalies_by_classifier),
                "top_risk_deputies": sorted(
                    deputy_risk_scores.items(),
                    key=lambda x: -x[1]["risk_score"]
                )[:20],
            },
            "deputy_risk_scores": deputy_risk_scores,
            "all_anomalies": all_anomalies,
        }

        # Log summary
        logger.info(f"\n{'='*60}")
        logger.info(f"  🤖 ROSIE REPORT SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"  Total receipts analyzed: {len(receipts)}")
        logger.info(f"  Total anomalies found:   {len(all_anomalies)}")
        logger.info(f"  Deputies flagged:         {len(anomalies_by_deputy)}")
        logger.info(f"  Anomalies by classifier:")
        for clf_name, count in sorted(anomalies_by_classifier.items(), key=lambda x: -x[1]):
            logger.info(f"    {clf_name}: {count}")

        if deputy_risk_scores:
            top_3 = sorted(deputy_risk_scores.items(), key=lambda x: -x[1]["risk_score"])[:3]
            logger.info(f"\n  Top 3 riskiest deputies:")
            for dep_id, scores in top_3:
                logger.info(f"    {dep_id}: score={scores['risk_score']}, "
                             f"anomalies={scores['n_anomalies']}, "
                             f"classifiers={scores['n_classifiers_triggered']}")

        logger.info(f"{'='*60}\n")

        return report

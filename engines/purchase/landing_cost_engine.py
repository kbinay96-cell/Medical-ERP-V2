"""
engines/purchase/landing_cost_engine.py

Layer: Engine (specialized — calculation-only)
Responsibility: CC (Customs Charge), Freight distribution, aur final
per-unit Landing Cost calculate karta hai.
FORBIDDEN in this layer: UI code, SQL/DB calls, validation (Validator
ka kaam hai — is Engine ko already-valid data milta hai).

CONFIRMED RULE (Freight & Other Charges Distribution):
Freight aur Other Charges ka koi value/qty-based weight NAHI hota.
User purchase header mein ek total amount manually type karta hai, aur
wo saari purchase-lines mein EQUAL (barabar) baant di jaati hai —
matlab: har-line-ka-hissa = total_amount / number_of_lines.

Domain Rules Applied:

CC (Customs Charge) sirf Free Qty par lagta hai:
cc_amount = free_qty * customs_value_per_unit * (custom_percent / 100)
Free Qty ka Purchase Rate hamesha 0 hai — kabhi kisi charge-calculation
ka basis nahi banega (isliye CC ka basis customs_value_per_unit hai,
purchase_rate nahi).
Landing Cost = Purchase Rate + Freight Share + Other Charges Share +
(CC amortized over the paid+free batch) — yeh hamesha OUTPUT hai,
kabhi kisi cheez ka INPUT/basis nahi banta (circular reference forbidden).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class LineCalculationInput:
    item_code: str
    qty: int
    free_qty: int
    purchase_rate: float
    customs_value_per_unit: float

@dataclass
class LineCalculationResult:
    item_code: str
    paid_value: float # qty * purchase_rate (reference/reporting ke liye)
    cc_amount: float # customs charge on free goods
    freight_share: float # is line ko mila hua freight ka EQUAL hissa
    other_charges_share: float # is line ko mila hua other-charges ka EQUAL hissa
    total_batch_qty: int # qty + free_qty (batch mein total units)
    landing_cost_per_unit: float # FINAL OUTPUT — kabhi input nahi banega

class LandingCostEngine:
    """Calculates CC, equal-split freight/charges, and final per-unit landing cost."""

    def calculate(
        self,
        lines: list[LineCalculationInput],
        total_freight: float,
        total_other_charges: float,
        custom_percent: float,
    ) -> list[LineCalculationResult]:
        """
        Saari purchase lines ke liye landing cost calculate karta hai.

        Steps:
        1. Har line ka CC amount nikalo (sirf free_qty par).
        2. Total freight ko lines ki GINTI (count) se EQUAL baanto —
           koi value/qty-weighting nahi.
        3. Total other_charges ko bhi isi tarah equal baanto.
        4. Final landing_cost_per_unit nikalo (paid + free dono qty ko
           consider karke, kyunki freight/CC dono batches pe lagti hain).
        """
        if not lines:
            return []

        line_count = len(lines)
        freight_per_line = total_freight / line_count if total_freight > 0 else 0.0
        other_charges_per_line = total_other_charges / line_count if total_other_charges > 0 else 0.0

        results: list[LineCalculationResult] = []

        for line in lines:
            paid_value = line.qty * line.purchase_rate
            cc_amount = self._calculate_cc(line, custom_percent)

            total_batch_qty = line.qty + line.free_qty
            landing_cost_per_unit = self._calculate_landing_cost_per_unit(
                purchase_rate=line.purchase_rate,
                total_batch_qty=total_batch_qty,
                freight_share=freight_per_line,
                other_charges_share=other_charges_per_line,
                cc_amount=cc_amount,
            )

            results.append(LineCalculationResult(
                item_code=line.item_code,
                paid_value=round(paid_value, 2),
                cc_amount=round(cc_amount, 2),
                freight_share=round(freight_per_line, 2),
                other_charges_share=round(other_charges_per_line, 2),
                total_batch_qty=total_batch_qty,
                landing_cost_per_unit=round(landing_cost_per_unit, 4),
            ))

        logger.info(
            "Landing cost calculated for %d line(s). Total freight=%.2f (equal-split=%.2f/line), "
            "total_other_charges=%.2f (equal-split=%.2f/line), custom_percent=%.2f",
            line_count, total_freight, freight_per_line,
            total_other_charges, other_charges_per_line, custom_percent,
        )

        return results

    def _calculate_cc(self, line: LineCalculationInput, custom_percent: float) -> float:
        """
        CC (Customs Charge) sirf Free Quantity par lagta hai.
        Basis: customs_value_per_unit (declared customs value) — 
        KABHI purchase_rate use nahi hoga (free qty ka rate hamesha 0 hai,
        jo hamesha 0 result dega — Domain Glossary rule).
        """
        if line.free_qty <= 0:
            return 0.0
        return line.free_qty * line.customs_value_per_unit * (custom_percent / 100.0)

    def _calculate_landing_cost_per_unit(
        self,
        purchase_rate: float,
        total_batch_qty: int,
        freight_share: float,
        other_charges_share: float,
        cc_amount: float,
    ) -> float:
        """
        Landing Cost = Purchase Rate + (Freight-share + Other-charges-share + CC)
        ka per-unit hissa, poore batch (paid + free qty) mein amortize kiya hua.

        Reasoning: Freight/CC ek pura batch move karne ka cost hai — isliye
        ye cost total_batch_qty (paid + free) mein baantna sahi hai, na ki
        sirf paid_qty mein — warna free units "cost-free" treat ho jaate
        jabki unka bhi handling/customs cost hota hai.
        """
        if total_batch_qty <= 0:
            return 0.0

        extra_cost_per_unit = (freight_share + other_charges_share + cc_amount) / total_batch_qty
        return purchase_rate + extra_cost_per_unit
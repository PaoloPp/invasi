# routes.py
# -*- coding: utf-8 -*-
"""
Blueprint Flask per ModIn — NUOVO MODELLO

Caratteristiche principali implementate:
- Calcolo S(i), D(i) da cumulati (A*, E*) e classificazione donanti/riceventi
- Nodo ripartitore M
- Modello A: Stot >= Dtot con 2 criteri di distribuzione (uniforme; due-periodi KA/KB, α1/α2)
- Modello B: Stot < Dtot con integrazione fluente P'j = Pj - (Πj + Πj_eco), ρ, Δ', A''sj(v)
- Verifiche unificate 7.1 (donanti) e 7.2 (riceventi)
- Compatibile con i form: form.html, form_traverse.html
"""

from __future__ import annotations

import json
import math
import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from flask import render_template, redirect, url_for, request, flash, jsonify, send_file, Blueprint
from flask_login import login_required, current_user
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from io import StringIO
from collections import defaultdict
from models import db, User, JsonFile, PastExchange
from utilities import *

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, jsonify
)

main_bp = Blueprint('main', __name__)

# Cartelle dati (puoi cambiarle a piacere)
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
BASINS_DIR = DATA_DIR / "basins"
TRAVERSE_DIR = DATA_DIR / "traverse"
for _d in [DATA_DIR, BASINS_DIR, TRAVERSE_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# Mesi e mapping
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]
MONTH_INDEX = {m: i for i, m in enumerate(MONTHS)}

# ---------------------------
# Utility I/O
# ---------------------------


def list_json_files(folder: Path) -> List[str]:
    return sorted([p.name for p in folder.glob("*.json")])


def load_json(folder: Path, filename: str) -> Dict:
    path = folder / filename
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(folder: Path, filename: str, data: Dict) -> None:
    path = folder / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def delete_json(folder: Path, filename: str) -> None:
    path = folder / filename
    if path.exists():
        path.unlink()


def _list_entries(folder: Path, db_model) -> List[str]:
    if current_user.is_authenticated:
        return db.session.execute(
            db.select(db_model.filename).filter_by(user_id=current_user.id)
        ).scalars().all()
    return list_json_files(folder)


def _load_entry(folder: Path, filename: str, db_model) -> Dict:
    if current_user.is_authenticated:
        row = db.session.execute(
            db.select(db_model.json_data).filter_by(filename=filename, user_id=current_user.id)
        ).scalar_one_or_none()
        if row:
            try:
                return json.loads(row)
            except json.JSONDecodeError:
                flash(f"Contenuto JSON non valido per {filename}.")
                return {}
    return load_json(folder, filename)


def _save_entry(folder: Path, filename: str, payload: Dict, db_model) -> None:
    if current_user.is_authenticated:
        existing = db.session.execute(
            db.select(db_model).filter_by(filename=filename, user_id=current_user.id)
        ).scalar_one_or_none()
        raw = json.dumps(payload, ensure_ascii=False, indent=2)
        if existing:
            existing.json_data = raw
        else:
            db.session.add(db_model(filename=filename, json_data=raw, user_id=current_user.id))
        db.session.commit()
        return
    save_json(folder, filename, payload)


def _delete_entry(folder: Path, filename: str, db_model) -> bool:
    if current_user.is_authenticated:
        existing = db.session.execute(
            db.select(db_model).filter_by(filename=filename, user_id=current_user.id)
        ).scalar_one_or_none()
        if not existing:
            return False
        db.session.delete(existing)
        db.session.commit()
        return True
    path = folder / filename
    if not path.exists():
        return False
    path.unlink()
    return True

# ---------------------------
# Modello dei dati (per chiarezza)
# ---------------------------


@dataclass
class Basin:
    name: str
    # mese di partenza anno idrologico (stringa in English, come in form.html)
    start_month: str
    # Volumi/capacità
    S_km2: float
    Winv_tot: float   # usato come Wmax
    Winv_aut: float   # disponibile se serve
    Wo: float         # usato come Wmin
    # Totali annui per termini di bilancio
    A: float
    Aprime: float
    P_ev: float
    P_inf: float
    D_ec: float
    E_pot: float
    E_irr: float
    E_ind: float
    E_tra: float
    # Coefficienti mensili (12 elementi ciascuno)
    CjA: List[float]
    CjAprime: List[float]
    Cjev: List[float]
    Cjinf: List[float]
    Cjec: List[float]
    Cjpot: List[float]
    Cjirr: List[float]
    Cjind: List[float]
    Cjtra: List[float]


@dataclass
class Traverse:
    name: str
    Pj: List[float]      # deflussi mensili grezzi
    Pj_eco: List[float]  # deflusso ecologico
    Pij: List[float]     # altri usi

# ---------------------------
# Parsing dai form
# ---------------------------


def parse_float(s: str, default: float = 0.0) -> float:
    try:
        if s is None or s == "":
            return default
        return float(str(s).replace(",", "."))
    except Exception:
        return default


def parse_list_of_12(values: List[str | float]) -> List[float]:
    arr = []
    for v in values:
        if isinstance(v, (int, float)):
            arr.append(float(v))
        else:
            arr.append(parse_float(v))
    # padding o trimming a 12
    if len(arr) < 12:
        arr += [0.0] * (12 - len(arr))
    elif len(arr) > 12:
        arr = arr[:12]
    return arr


def basin_from_form(form: Dict) -> Basin:
    # campi totali
    name = form.get("filename", "").strip() or "unnamed_basin"
    start = form.get("starting_month", "January")

    # blocco 1
    S_km2 = parse_float(form.get("vol-1"))
    Winv_tot = parse_float(form.get("vol-2"))
    Winv_aut = parse_float(form.get("vol-3"))
    Wo = parse_float(form.get("vol-4"))
    A = parse_float(form.get("vol-5"))
    Aprime = parse_float(form.get("vol-6"))
    P_ev = parse_float(form.get("vol-7"))
    P_inf = parse_float(form.get("vol-8"))
    # blocco 2
    D_ec = parse_float(form.get("vol-9"))
    E_pot = parse_float(form.get("vol-10"))
    E_irr = parse_float(form.get("vol-11"))
    E_ind = parse_float(form.get("vol-12"))
    E_tra = parse_float(form.get("vol-13"))

    # coefficienti mensili (12 per ciascuno)
    CjA = []
    CjAprime = []
    Cjev = []
    Cjinf = []
    Cjec = []
    Cjpot = []
    Cjirr = []
    Cjind = []
    Cjtra = []

    for i in range(12):
        CjA.append(parse_float(form.get(f"coeff-{i+1}-1")))
        CjAprime.append(parse_float(form.get(f"coeff-{i+1}-2")))
        Cjev.append(parse_float(form.get(f"coeff-{i+1}-3")))
        Cjinf.append(parse_float(form.get(f"coeff-{i+1}-4")))
        Cjec.append(parse_float(form.get(f"coeff-{i+1}-5")))
        Cjpot.append(parse_float(form.get(f"coeff-{i+1}-6")))
        Cjirr.append(parse_float(form.get(f"coeff-{i+1}-7")))
        Cjind.append(parse_float(form.get(f"coeff-{i+1}-8")))
        Cjtra.append(parse_float(form.get(f"coeff-{i+1}-9")))

    return Basin(
        name=name, start_month=start,
        S_km2=S_km2, Winv_tot=Winv_tot, Winv_aut=Winv_aut, Wo=Wo,
        A=A, Aprime=Aprime, P_ev=P_ev, P_inf=P_inf,
        D_ec=D_ec, E_pot=E_pot, E_irr=E_irr, E_ind=E_ind, E_tra=E_tra,
        CjA=CjA, CjAprime=CjAprime, Cjev=Cjev, Cjinf=Cjinf,
        Cjec=Cjec, Cjpot=Cjpot, Cjirr=Cjirr, Cjind=Cjind, Cjtra=Cjtra
    )


def traverse_from_form(form: Dict) -> Traverse:
    name = form.get("filename", "").strip() or "unnamed_traverse"
    Pj = []
    Peco = []
    Pij = []
    for i in range(12):
        Pj.append(parse_float(form.get(f"Pj-{i}")))
        Peco.append(parse_float(form.get(f"Pjeco-{i}")))
        Pij.append(parse_float(form.get(f"Pij-{i}")))
    return Traverse(name=name, Pj=Pj, Pj_eco=Peco, Pij=Pij)

# ---------------------------
# Serie mensili, bilancio e classificazione
# ---------------------------


def rotate_year(arr: List[float], start_index: int) -> List[float]:
    """Ruota la lista per far partire l'anno idrologico dal mese desiderato."""
    return arr[start_index:] + arr[:start_index]


def compute_cumulatives(A_month: List[float], E_month: List[float]) -> Tuple[List[float], List[float], List[float]]:
    """
    A*(m) ed E*(m) sono i cumulati; theta(m) = A*(m) - E*(m)
    """
    A_star, E_star, theta = [], [], []
    sA = sE = 0.0
    for a, e in zip(A_month, E_month):
        sA += float(a or 0.0)
        sE += float(e or 0.0)
        A_star.append(sA)
        E_star.append(sE)
        theta.append(sA - sE)
    return A_star, E_star, theta


def compute_S_D(A_star_annual: float, E_star_annual: float) -> Tuple[float, float]:
    """
    NEW: S(i) = max(A*_ann - E*_ann, 0); D(i) = max(E*_ann - A*_ann, 0)
    """
    S = max(A_star_annual - E_star_annual, 0.0)
    D = max(E_star_annual - A_star_annual, 0.0)
    return S, D


def build_monthly_series(basin: Basin) -> Tuple[List[float], List[float]]:
    """
    Costruisce Aj(i) ed Ej(i) mensili a partire dai totali annui e coefficienti mensili.
    Convenzione:
      Aj  =  A*Cj(A) + A'*Cj(A') - P_ev*Cj(ev) - P_inf*Cj(inf)
      Ej  =  D_ec*Cj(ec) + E_pot*Cj(pot) + E_irr*Cj(irr) + E_ind*Cj(ind) + E_tra*Cj(tra)
    """
    Aj = []
    Ej = []
    for j in range(12):
        inflow = (
            basin.A * basin.CjA[j]
            + basin.Aprime * basin.CjAprime[j]
            - basin.P_ev * basin.Cjev[j]
            - basin.P_inf * basin.Cjinf[j]
        )
        outflow = (
            basin.D_ec * basin.Cjec[j]
            + basin.E_pot * basin.Cjpot[j]
            + basin.E_irr * basin.Cjirr[j]
            + basin.E_ind * basin.Cjind[j]
            + basin.E_tra * basin.Cjtra[j]
        )
        Aj.append(inflow)
        Ej.append(outflow)

    # allinea all'anno idrologico
    sidx = MONTH_INDEX.get(basin.start_month, 0)
    Aj = rotate_year(Aj, sidx)
    Ej = rotate_year(Ej, sidx)
    return Aj, Ej


def cumulative(v: List[float]) -> float:
    return float(sum(v))


@dataclass
class Donor:
    name: str
    S_gross: float
    D_gross: float
    S_net: float   # nel nuovo: S = So - Do se ≥ 0, altrimenti 0
    monthly_A: List[float]
    monthly_E: List[float]
    Wmin: float
    Wmax: float


@dataclass
class Receiver:
    name: str
    S_gross: float
    D_gross: float
    D_net: float   # nel nuovo: D = Do - So se ≥ 0, altrimenti 0
    monthly_A: List[float]
    monthly_E: List[float]
    Wmin: float
    Wmax: float


def classify_basins(basins: List[Basin]) -> Tuple[List[Donor], List[Receiver]]:
    donors: List[Donor] = []
    receivers: List[Receiver] = []

    for b in basins:
        Aj, Ej = build_monthly_series(b)
        Soj = [max(a - e, 0.0) for a, e in zip(Aj, Ej)]
        Doj = [max(e - a, 0.0) for a, e in zip(Aj, Ej)]
        So = cumulative(Soj)
        Do = cumulative(Doj)
        theta = cumulative(Aj) - cumulative(Ej)

        if theta >= 0:
            # surplus netto
            donors.append(Donor(
                name=b.name, S_gross=So, D_gross=Do, S_net=max(So - Do, 0.0),
                monthly_A=Aj, monthly_E=Ej,
                Wmin=b.Wo, Wmax=b.Winv_tot
            ))
        else:
            # deficit netto
            receivers.append(Receiver(
                name=b.name, S_gross=So, D_gross=Do, D_net=max(Do - So, 0.0),
                monthly_A=Aj, monthly_E=Ej,
                Wmin=b.Wo, Wmax=b.Winv_tot
            ))
    return donors, receivers


def compute_Stot_Dtot(donors: List[Donor], receivers: List[Receiver]) -> Tuple[float, float, float]:
    Stot = sum(d.S_net for d in donors)
    Dtot = sum(r.D_net for r in receivers)
    delta = max(Dtot - Stot, 0.0)  # solo informativo
    return Stot, Dtot, delta

# ---------------------------
# Nodo M: criteri di distribuzione
# ---------------------------


def distribute_uniform(value_annual: float) -> List[float]:
    # criterio 1: uniforme su 12 mesi
    return [value_annual / 12.0] * 12


def distribute_two_periods(value_annual: float, KA: int, KB: int, a1: float, a2: float,
                           start_index: int = 0) -> List[float]:
    """
    criterio 2: due periodi KA e KB (KA+KB=12), α1+α2=1; α1>α2
    Distribuisce a1*annuo/KA nei KA mesi "alti" e a2*annuo/KB nei KB mesi "bassi",
    partendo dal mese di inizio (start_index).
    """
    KA = max(min(int(KA), 12), 0)
    KB = 12 - KA
    a2 = 1.0 - a1 if a2 is None else a2

    arr = [0.0] * 12
    high = a1 * value_annual / (KA if KA > 0 else 1)
    low = a2 * value_annual / (KB if KB > 0 else 1)

    # Per semplicità: i primi KA mesi dall'inizio sono "alti", i successivi KB "bassi"
    for i in range(12):
        pos = (start_index + i) % 12
        if i < KA:
            arr[pos] = high
        else:
            arr[pos] = low
    return arr

# ---------------------------
# Modello A
# ---------------------------


def allocate_model_A(
    donors: List[Donor],
    receivers: List[Receiver],
    criterio: int,
    KA: int,
    KB: int,
    a1: float,
    a2: float,
    start_index: int
) -> Dict:
    """
    Modello A: Stot >= Dtot
    - Se Stot > Dtot: δ = Stot - Dtot, δ(t) = S(t)*δ/Stot, S'(t)=S(t)-δ(t)
    - A’s(v) = D(v); poi A’sj(v) per criterio 1 o 2
    - Esj(t) = S’j(t) sono erogazioni aggiuntive dei donanti (a info)
    """
    Stot = sum(d.S_net for d in donors)
    Dtot = sum(r.D_net for r in receivers)

    out = {
        "model": "A",
        "criterion": criterio,
        "KA": KA, "KB": KB, "alpha1": a1, "alpha2": a2,
        "Stot": Stot, "Dtot": Dtot,
        "donors": {},        # name -> dict con S', Esj
        "receivers": {},     # name -> dict con A's, A'sj
    }

    # 1) S'(t) sui donanti
    if Stot > 0:
        delta = max(Stot - Dtot, 0.0)
        for d in donors:
            if Stot > 0 and delta > 0:
                delta_t = d.S_net * (delta / Stot)
            else:
                delta_t = 0.0
            S_prime_t = max(d.S_net - delta_t, 0.0)
            # distribuzione Esj(t) = S’j(t) (erogazione aggiuntiva donante)
            if criterio == 1:
                Esj = distribute_uniform(S_prime_t)
            else:
                Esj = distribute_two_periods(
                    S_prime_t, KA, KB, a1, a2, start_index)
            out["donors"][d.name] = {
                "S_net": d.S_net,
                "S_prime": S_prime_t,
                "Esj": Esj
            }
    else:
        # Nessun donante o Stot=0 (caso limite)
        for d in donors:
            out["donors"][d.name] = {"S_net": 0.0,
                                     "S_prime": 0.0, "Esj": [0.0]*12}

    # 2) A’s(v) = D(v) e A’sj(v)
    for r in receivers:
        A_s_v = r.D_net
        if criterio == 1:
            Asj = distribute_uniform(A_s_v)
        else:
            Asj = distribute_two_periods(A_s_v, KA, KB, a1, a2, start_index)
        out["receivers"][r.name] = {
            "A_s": A_s_v,
            "A_sj": Asj,
            "A_dd_sj": [0.0]*12,  # in A non c'è quota esterna
            "A_total_sj": Asj
        }

    return out

# ---------------------------
# Modello B
# ---------------------------


def compute_P_prime_month(traverses: List[Traverse]) -> List[float]:
    """
    P’j(p) = Pj - (Pij + Pj_eco) per ciascuna traversa, poi somma su p (P’jtot).
    """
    P_prime_total = [0.0] * 12
    for tr in traverses:
        for j in range(12):
            pprime = tr.Pj[j] - (tr.Pij[j] + tr.Pj_eco[j])
            P_prime_total[j] += max(pprime, 0.0)  # non negativo
    return P_prime_total


def allocate_model_B(
    donors: List[Donor],
    receivers: List[Receiver],
    traverses: List[Traverse],
    criterio: int,
    KA: int,
    KB: int,
    alpha1_init: float,
    start_index: int,
    epsilon: float = 1e-3,
    max_iter: int = 50
) -> Dict:
    """
    Versione estesa del Modello B:
      - Include le traverse come risorsa donante attiva
      - Itera su α1/α2 se le condizioni (7.1 / 7.2) non sono soddisfatte
      - Bilancia fino a |Stot_eff – Dtot| < epsilon oppure max_iter raggiunto
    """
    # calcoli iniziali
    Stot0 = sum(d.S_net for d in donors)
    Dtot = sum(r.D_net for r in receivers)
    # risorsa traverse mensile
    # P_prime_j = sum_j (per ogni traverse p: max(Pj-(Pij+Pj_eco),0))
    P_prime_j = compute_P_prime_month(traverses)
    P_prime_tot = sum(P_prime_j)
    Delta0 = max(Dtot - Stot0, 0.0)

    # integra traverse come donatori
    Stot_eff = Stot0 + P_prime_tot
    Delta_eff = max(Dtot - Stot_eff, 0.0)

    # inizio iterazione α
    alpha1 = alpha1_init
    alpha2 = 1.0 - alpha1

    best_result = None

    for iter_idx in range(max_iter):
        # distribuzione criteri
        if Stot_eff >= Dtot:
            # caduto nel Modello A in pratica (ma siamo in B) → usabile comunque
            result = allocate_model_A(
                donors, receivers, criterio, KA, KB, alpha1, alpha2, start_index)
            result["rho"] = 1.0
        else:
            # vero Modello B
            out = {
                "model": "B",
                "Stot0": Stot0,
                "Dtot": Dtot,
                "P_prime_tot": P_prime_tot,
                "Stot_eff": Stot_eff,
                "Delta_eff": Delta_eff,
                "donors": {},
                "receivers": {},
                "rho": 0.0
            }

            # donatori: includere traverse come “donatore extra”
            for d in donors:
                S_prime = d.S_net
                Esj = _dist_by_criterio(
                    S_prime, criterio, KA, KB, alpha1, start_index)
                out["donors"][d.name] = {
                    "S_net": d.S_net, "S_prime": S_prime, "Esj": Esj}
            # aggiungi traverse come donatori
            # nome "TR_<i>" per traverse
            for idx, tr in enumerate(traverses):
                name = f"TR_{idx+1}_{tr.name}"
                # consideriamo l’annuo P_prime_tot redistribuito
                S_prime = sum(
                    max(tr.Pj[j] - (tr.Pij[j] + tr.Pj_eco[j]), 0.0) for j in range(12))
                Esj = distribute_uniform(S_prime) if criterio == 1 else distribute_two_periods(
                    S_prime, KA, KB, alpha1, alpha2, start_index)
                out["donors"][name] = {"S_net": S_prime,
                                       "S_prime": S_prime, "Esj": Esj}

            # riceventi: calcolo A’sj e A’’sj
            for r in receivers:
                A_s = r.D_net
                A_sj_don = _dist_by_criterio(
                    A_s, criterio, KA, KB, alpha1, start_index)
                # A’’sj via traverse: se Dtot>0
                if Dtot > 0:
                    A_dd_sj = [A_s * (P_prime_j[j] / Dtot) for j in range(12)]
                else:
                    A_dd_sj = [0.0]*12
                A_total = [a + b for a, b in zip(A_sj_don, A_dd_sj)]
                out["receivers"][r.name] = {
                    "A_s": A_s,
                    "A_sj_don": A_sj_don,
                    "A_dd_sj": A_dd_sj,
                    "A_total_sj": A_total
                }

            # ρ
            rho = 1.0 if Delta_eff <= 0 else (
                P_prime_tot / Delta0 if Delta0 > 0 else 1.0)
            out["rho"] = rho

            result = out

        # controlli condizioni 7.1 / 7.2
        # qui occorrerebbe adattare _checks per includere traverse
        checks = _checks(donors + [], receivers, result)
        all_ok = all(all(v for v in vlist) for vlist in checks["donors"].values()) and \
            all(all(v for v in vlist)
                for vlist in checks["receivers"].values())

        # se ok e bilanciamento raggiunto → break
        if all_ok and abs((result["Stot0"] + result.get("P_prime_tot", 0)) - Dtot) <= epsilon:
            best_result = result
            break

        # altrimenti modifica α1/α2 e riprova
        alpha1 = max(0.1, alpha1 - 0.05)
        alpha2 = 1.0 - alpha1

        # puoi anche aggiornare KA/KB se vuoi
        # e ricalcolare Stot_eff e Delta_eff se vuoi dinamicamente
        # ma per ora keep semplice

    # se non trovato best_result → prendi ultimo result
    if best_result is None:
        best_result = result

    return best_result


# ---------------------------
# Verifiche 7.1 / 7.2
# ---------------------------

def check_donor_constraints(d: Donor, Esj: List[float]) -> List[bool]:
    """
    7.1: W(j-1)(t) + Aj(t) − [Ej(t)tot + Esj(t)] ≥ Wmin(t)
    Nota: qui non abbiamo il tracking reale di W(j-1); simuliamo check locale.
    """
    ok = []
    Wmin = d.Wmin
    # qui assumiamo che W(j-1) sia "sufficientemente alto" se il bilancio è positivo
    # Se vuoi, collega un vettore W(j) reale dal tuo storage idraulico.
    for j in range(12):
        lhs = d.monthly_A[j] - (d.monthly_E[j] + Esj[j])
        # Condizione locale: se lhs >= (Wmin - Wprev), ma Wprev ignoto -> richiediamo solo lhs >= 0 come proxy
        ok.append(lhs >= 0.0 or lhs >= -1e-9)
    return ok


def check_receiver_constraints(r: Receiver, Asj: List[float]) -> List[bool]:
    """
    7.2: W(j-1)(v) + [Aj(v) + Asj(v)] − Ej(v)tot ≤ Wmax(v)
    Idem come sopra: senza W(j-1), applichiamo check di non-sforamento locale.
    """
    ok = []
    Wmax = r.Wmax
    for j in range(12):
        rhs = r.monthly_A[j] + Asj[j] - r.monthly_E[j]
        # proxy: richiediamo che l'extra non provochi "overflow" locale (rhs non troppo grande)
        # soglia euristica: rhs <= Wmax/12 (senza dati precisi di volumi mensili)
        ok.append(rhs <= (Wmax / 12.0 + 1e-9))
    return ok

# ---------------------------
# ROUTES
# ---------------------------


@main_bp.route('/', methods=['GET'])
def index():
    return redirect(url_for('auth.login'))


@main_bp.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    files = get_user_files()
    if request.method == 'POST':
        filename = request.form.get("data_select")
        if filename:
            data = load_json_data(filename)
            if not data:
                return redirect(url_for('main_bp.dashboard'))
            data = round_floats(data)
            months = set_year(data.get("Mese di partenza"))
            plot_values(
                ["Aitot*", "Etot*", "W*", "Sf 1*", "D/S 1*", "Winv tot", "Wo"],
                data, "caso1"
            )
            plot_values(
                ["Aitot*", "Etot*", "W*", "Sf 2*", "D/S 2*", "Winv aut", "Wo"],
                data, "caso2"
            )
            return render_template('dashboard.html', filename=filename, data=data, months=months, files=files,
                                   plotA="caso1_plot.png", plotB="caso2_plot.png",
                                   resource_type="invasi")
    return render_template('dashboard.html', data=None, files=files, resource_type="invasi")


@main_bp.route("/form", methods=["GET", "POST"])
def form_basin():
    files = _list_entries(BASINS_DIR, JsonFile)
    data = {}
    if request.method == "POST":
        if "load" in request.form:
            fname = request.form.get("data_select", "")
            if not fname:
                flash("Seleziona un file.")
                return render_template("form.html", files=files, data=data)
            data = _load_entry(BASINS_DIR, fname, JsonFile)
            return render_template("form.html", files=files, data=data)

        if "delete" in request.form:
            fname = request.form.get("data_select", "")
            if not fname:
                flash("Seleziona un file da eliminare.")
                return render_template("form.html", files=files, data=data)
            if _delete_entry(BASINS_DIR, fname, JsonFile):
                flash(f"File {fname} eliminato.")
            else:
                flash(f"File {fname} non trovato.")
            files = _list_entries(BASINS_DIR, JsonFile)
            return render_template("form.html", files=files, data={})

        # submit principale del form
        basin = basin_from_form(request.form)
        # serializza in json
        out = {
            "Filename": basin.name,
            "Mese di partenza": basin.start_month,
            "S": basin.S_km2,
            "Winv tot": basin.Winv_tot,
            "Winv aut": basin.Winv_aut,
            "Wo": basin.Wo,
            "A": basin.A,
            "A'": basin.Aprime,
            "P ev": basin.P_ev,
            "P inf": basin.P_inf,
            "D ec": basin.D_ec,
            "E pot": basin.E_pot,
            "E irr": basin.E_irr,
            "E ind": basin.E_ind,
            "E tra": basin.E_tra,
            "Cj(A)": basin.CjA,
            "Cj(A')": basin.CjAprime,
            "Cj(ev)": basin.Cjev,
            "Cj(inf)": basin.Cjinf,
            "Cj(ec)": basin.Cjec,
            "Cj(pot)": basin.Cjpot,
            "Cj(irr)": basin.Cjirr,
            "Cj(ind)": basin.Cjind,
            "Cj(tra)": basin.Cjtra,
        }
        filename = f"{basin.name}.json"
        _save_entry(BASINS_DIR, filename, out, JsonFile)
        flash(f"Salvato {filename}")
        files = _list_entries(BASINS_DIR, JsonFile)
        return render_template("form.html", files=files, data=out)

    # GET
    return render_template("form.html", files=files, data=data)


@main_bp.route("/form_traverse", methods=["GET", "POST"])
def form_traverse():
    files = _list_entries(TRAVERSE_DIR, JsonFileTraverse)
    data = {}
    if request.method == "POST":
        if "load" in request.form:
            fname = request.form.get("data_select", "")
            if not fname:
                flash("Seleziona un file.")
                return render_template("form_traverse.html", files=files, data=data)
            data = _load_entry(TRAVERSE_DIR, fname, JsonFileTraverse)
            return render_template("form_traverse.html", files=files, data=data)

        if "delete" in request.form:
            fname = request.form.get("data_select", "")
            if not fname:
                flash("Seleziona un file da eliminare.")
                return render_template("form_traverse.html", files=files, data=data)
            if _delete_entry(TRAVERSE_DIR, fname, JsonFileTraverse):
                flash(f"File {fname} eliminato.")
            else:
                flash(f"File {fname} non trovato.")
            files = _list_entries(TRAVERSE_DIR, JsonFileTraverse)
            return render_template("form_traverse.html", files=files, data={})

        trav = traverse_from_form(request.form)
        out = {
            "Filename": trav.name,
            "Pj": trav.Pj,
            "Pj(eco)": trav.Pj_eco,
            "Pij": trav.Pij
        }
        filename = f"{trav.name}.json"
        _save_entry(TRAVERSE_DIR, filename, out, JsonFileTraverse)
        flash(f"Salvato {filename}")
        files = _list_entries(TRAVERSE_DIR, JsonFileTraverse)
        return render_template("form_traverse.html", files=files, data=out)

    return render_template("form_traverse.html", files=files, data=data)


@main_bp.route('/exchange', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def exchange():
    """
    Unified handler for:
      - GET: render page or load a saved exchange with ?past_select=<name>
      - POST (form): load/delete buttons, or compute with new model logic
      - PUT (JSON): upsert a saved exchange (json payload)
      - DELETE (JSON): delete a saved exchange (json payload)
    New model logic implemented inline:
      - Classify donors/receivers from basin JSONs
      - Model A (Stot >= Dtot) and Model B (Stot < Dtot)
      - Two criteria: uniform (1) and two-periods (2) with KA/KB and alpha1/alpha2
      - External resources for Model B via traverse files: P'j = Pj - (Pij + Pj(eco))
    """
    files = get_user_files()
    traverse_files = get_user_files_traverse()
    past_exchange = get_past_exchange()

    # ---------- tiny helpers (local, dependency-free) ----------
    def _pf(x, d=0.0):
        try:
            return float(str(x).replace(',', '.'))
        except Exception:
            return d

    def _pad12(lst):
        lst = list(lst or [])
        lst = [_pf(v, 0.0) for v in lst]
        return (lst + [0.0]*12)[:12]

    def _rotate(arr, start_idx):
        return arr[start_idx:] + arr[:start_idx]

    def _load_basin_jsons(selected_files):
        """Return list of basin dicts from per-user storage."""
        data = []
        for fn in selected_files:
            # you already have this style loader for basins
            j = load_json_data(fn)
            if j:
                data.append(j)
        return data

    def _load_traverse_jsons(selected_traverse):
        data = []
        for fn in selected_traverse:
            j = load_json_data_traverse(fn)  # same pattern for traverse
            if j:
                data.append(j)
        return data
    
    def _nonneg12(v):
        return [max(float(x or 0.0), 0.0) for x in (v or [0.0]*12)]

    def _build_monthly(b):
        # Aj = A*Cj(A) + A'*Cj(A') - P_ev*Cj(ev) - P_inf*Cj(inf)
        # Ej = D_ec*Cj(ec) + E_pot*Cj(pot) + E_irr*Cj(irr) + E_ind*Cj(ind) + E_tra*Cj(tra)
        Aj, Ej = [], []
        for j in range(12):
            infl = _pf(b.get("A", 0))*_pad12(b.get("Cj(A)"))[j] \
                + _pf(b.get("A'", 0))*_pad12(b.get("Cj(A')"))[j] \
                - _pf(b.get("P ev", 0))*_pad12(b.get("Cj(ev)"))[j] \
                - _pf(b.get("P inf", 0))*_pad12(b.get("Cj(inf)"))[j]
            out = _pf(b.get("D ec", 0))*_pad12(b.get("Cj(ec)"))[j] \
                + _pf(b.get("E pot", 0))*_pad12(b.get("Cj(pot)"))[j] \
                + _pf(b.get("E irr", 0))*_pad12(b.get("Cj(irr)"))[j] \
                + _pf(b.get("E ind", 0))*_pad12(b.get("Cj(ind)"))[j] \
                + _pf(b.get("E tra", 0))*_pad12(b.get("Cj(tra)"))[j]
            Aj.append(infl)
            Ej.append(out)
            Aj = _nonneg12(Aj)
            Ej = _nonneg12(Ej)
        sidx = {"January": 0, "February": 1, "March": 2, "April": 3, "May": 4, "June": 5, "July": 6, "August": 7,
                "September": 8, "October": 9, "November": 10, "December": 11}.get(b.get("Mese di partenza", "January"), 0)
        return _rotate(Aj, sidx), _rotate(Ej, sidx)

    def _classify(basins_json):
        """
        Classificazione NEW: usa i cumulati annui A*, E*.
        S(i) = max(A*_ann - E*_ann, 0)
        D(i) = max(E*_ann - A*_ann, 0)
        Donatore se theta_ann = A*_ann - E*_ann > 0; ricevente se < 0; neutro altrimenti.
        """
        donors, receivers = [], []

        for b in basins_json:
            # Serie mensili già coerenti al form: Aj, Ej
            Aj, Ej = _build_monthly(b)

            # Cumulati NEW
            A_star, E_star, theta = compute_cumulatives(Aj, Ej)
            theta_ann = theta[-1]
            S_i, D_i = compute_S_D(A_star[-1], E_star[-1])

            item = {
                "name": b.get("Filename", "unnamed"),
                "Aj": Aj,
                "Ej": Ej,
                "Wmin": _pf(b.get("Wo", 0)),
                "Wmax": _pf(b.get("Winv tot", 0))
            }

            if theta_ann > 0 and S_i > 0:
                item["S_net"] = S_i
                donors.append(item)
            elif theta_ann < 0 and D_i > 0:
                item["D_net"] = D_i
                receivers.append(item)
            else:
                # neutro: non partecipa allo scambio, ma resta usabile per verifiche locali
                pass

        Stot = sum(_get_S_for_flow(d) for d in donors) if donors else 0.0
        Dtot = sum(r["D_net"] for r in receivers) if receivers else 0.0
        return donors, receivers, Stot, Dtot

    def _recalibrate_donors(donors: List[dict], Stot: float, Dtot: float) -> Tuple[List[dict], dict]:
        """
        NEW step 2: se Stot > Dtot, taglio proporzionalmente i surplus dei donatori.
        S_trim(t) = S_net(t) - S_net(t) * delta / Stot
        dove delta = Stot - Dtot.
        Ritorna (donors_con_trim, summary).
        """
        delta = max(Stot - Dtot, 0.0)

        # Nessun taglio necessario o situazione degenere
        if delta <= 0.0 or Stot <= 0.0 or not donors:
            for d in donors:
                d["S_trim"] = float(_get_S_for_flow(d))
                d["trim_ratio"] = 0.0
            summary = {
                "trimmed": False,
                "delta": 0.0,
                "Stot": float(Stot),
                "Dtot": float(Dtot),
                "Stot_trim": sum(d["S_trim"] for d in donors)
            }
            return donors, summary

        # Taglio proporzionale
        for d in donors:
            s = float(_get_S_for_flow(d))
            cut = (s / Stot) * delta if Stot > 0.0 else 0.0
            s_trim = max(s - cut, 0.0)
            d["S_trim"] = s_trim
            d["trim_ratio"] = (cut / s) if s > 0.0 else 0.0

        Stot_trim = sum(d["S_trim"] for d in donors)

        summary = {
            "trimmed": True,
            "delta": float(delta),
            "Stot": float(Stot),
            "Dtot": float(Dtot),
            "Stot_trim": float(Stot_trim)
        }

        # Invariante pratica: Stot_trim ≈ Dtot (entro una tolleranza numerica)
        # Se vuoi essere pignolo, attiva questo assert:
        # assert abs(Stot_trim - Dtot) <= 1e-6, f"Ricalibrazione non coerente: {Stot_trim} vs {Dtot}"

        return donors, summary
    
    def _clamp01(x, default=0.5):
        try:
            v = float(x)
        except Exception:
            v = float(default)
        return max(0.0, min(1.0, v))

    def _normalize(vec):
        s = sum(vec)
        if s <= 0:
            return [1.0/12.0]*12
        return [v/s for v in vec]

    def _period_weights(KA, KB, alpha1, alpha2):
        """
        Costruisce i pesi mensili per il Criterio 2:
        - alpha1 spalmato sui mesi in KA
        - alpha2 spalmato sui mesi in KB
        Restituisce lista di 12 float che sommano a 1.
        """
        a1 = _clamp01(alpha1, 0.5)
        a2 = _clamp01(alpha2, 1.0 - a1)

        # Blindatura: se capitano input schifosi, fallback via _coerce_periods
        if isinstance(KA, int) or isinstance(KB, int) or isinstance(KA, str) or isinstance(KB, str):
            KA, KB = _coerce_periods(KA, KB, 0)

        KA = list(KA or [])
        KB = list(KB or [])

        w = [0.0]*12
        if KA and KB:
            per_ka = a1 / len(KA) if len(KA) > 0 else 0.0
            per_kb = a2 / len(KB) if len(KB) > 0 else 0.0
            for m in KA:
                m = int(m) % 12
                w[m] += per_ka
            for m in KB:
                m = int(m) % 12
                if w[m] == 0.0:
                    w[m] += per_kb
            # normalizza per ogni eventuale leakage
            s = sum(w)
            if s <= 0:
                return [1.0/12.0]*12
            return [x/s for x in w]
        else:
            return [1.0/12.0]*12


    def _coerce_periods(KA, KB, start_idx=0):
        """
        Converte KA/KB in liste di indici mese [0..11].
        Accetta:
          - lista/tupla/set di interi
          - stringa "0,1,2" o "0 1 2"
          - intero N -> primi N mesi a partire da start_idx (mod 12)
        Completa il complemento se ne arriva solo uno.
        Garantisce insiemi disgiunti e non vuoti. Fallback 7/5.
        """
        def _to_list(x):
            if x is None:
                return None
            if isinstance(x, (list, tuple, set)):
                try:
                    return [int(m) % 12 for m in x]
                except Exception:
                    return None
            if isinstance(x, str):
                s = x.strip()
                if not s:
                    return None
                # accetta sia virgole che spazi/semicolon
                parts = [p for p in s.replace(";", ",").replace(" ", ",").split(",") if p]
                try:
                    vals = [int(p) % 12 for p in parts]
                    return vals if vals else None
                except Exception:
                    return None
            if isinstance(x, int):
                n = max(0, min(int(x), 12))
                return [ (int(start_idx) + i) % 12 for i in range(n) ]
            # altro schifo: ignoriamo
            return None

        try:
            start_idx = int(start_idx or 0)
        except Exception:
            start_idx = 0

        KA_l = _to_list(KA)
        KB_l = _to_list(KB)

        if KA_l is None and KB_l is None:
            KA_l = list(range(0, 7))
            KB_l = list(range(7, 12))
        elif KA_l is None and KB_l is not None:
            KA_set = set(range(12)) - set(KB_l)
            KA_l = sorted(m % 12 for m in KA_set)
        elif KB_l is None and KA_l is not None:
            KB_set = set(range(12)) - set(KA_l)
            KB_l = sorted(m % 12 for m in KB_set)

        # disgiunti e ordinati
        KA_l = sorted({m % 12 for m in KA_l})
        KB_l = sorted({m % 12 for m in KB_l if (m % 12) not in KA_l})

        # se uno dei due è vuoto, fallback 7/5
        if not KA_l or not KB_l:
            KA_l = list(range(0, 7))
            KB_l = list(range(7, 12))

        return KA_l, KB_l

    def _parse_traverse_record(raw: dict) -> List[float]:
        """
        Estrae la serie mensile P'_j per UNA traversa:
          P'_j(m) = max( P_j(m) - (Pi_j(m) + Pi_eco_j(m)), 0 )
        Accetta chiavi varie: "Cj(P)" / "Pj", "Cj(pi)" / "Pi", "Cj(eco)" / "Pi_eco".
        Se i vincoli sono scalari, li spalma sui 12 mesi.
        """
        def _series(raw, keys, default=0.0):
            for k in keys:
                if k in raw:
                    v = raw.get(k)
                    if isinstance(v, (int, float, str, list)):
                        s = _coerce12(v)
                        return s
            # scalar fallback
            return [float(default)] * 12

        Pj   = _series(raw, ["Cj(P)", "Pj", "P_j", "Cj(Pj)"], 0.0)
        Pi   = _series(raw, ["Cj(pi)", "Pi", "P_i", "Cj(Pi)"], 0.0)
        Pi_ec= _series(raw, ["Cj(eco)", "Pi_eco", "P_eco", "Cj(P_eco)"], 0.0)

        Pprime = []
        for m in range(12):
            val = float(Pj[m]) - (float(Pi[m]) + float(Pi_ec[m]))
            Pprime.append(max(val, 0.0))
        return Pprime

    def _Pprime_total_j(traverses_json: List[dict]) -> List[float]:
        """
        Somma P'_j(m) su tutte le traverse fornite.
        Se traverses_json è vuoto/None, ritorna 12 zeri.
        """
        if not traverses_json:
            return [0.0] * 12
        acc = [0.0] * 12
        for tr in traverses_json:
            Pp = _parse_traverse_record(tr)
            for m in range(12):
                acc[m] += float(Pp[m])
        return acc

    def _get_S_for_flow(d: dict) -> float:
        """
        Usa S_trim se presente (post-ricalibrazione), altrimenti S_net.
        Così il resto del codice non deve preoccuparsi di quale ramo è stato eseguito.
        """
        return float(d.get("S_trim", d.get("S_net", 0.0)))

    def _distribute_uniform(v_annual):
        return [v_annual/12.0]*12

    def _distribute_two_periods(v_annual, KA, KB, a1, a2, start_idx):
        KA = max(0, min(int(KA), 12))
        KB = 12-KA
        a2 = 1.0 - a1 if a2 is None else a2
        high = (a1*v_annual)/(KA or 1)
        low = (a2*v_annual)/(KB or 1)
        arr = [0.0]*12
        for i in range(12):
            pos = (start_idx + i) % 12
            arr[pos] = high if i < KA else low
        return arr


    def _month_name_to_idx(name):
        s = (name or "").strip()
        if s in MONTHS_EN: return MONTHS_EN.index(s)
        if s in MONTHS_IT: return MONTHS_IT.index(s)
        try:
            n = int(s)
            if 1 <= n <= 12: return n - 1
        except Exception:
            pass
        return 0
    
    def _start_idx_from_first(basins_json):
        if not basins_json: return 0
        first = basins_json[0]
        m = first.get("Mese di partenza") or first.get("starting_month") or first.get("start_month")
        return _month_name_to_idx(m)

    def _weights_desc(crit, KA=None, KB=None, a1=None, a2=None, start_idx=0):
        """
        Restituisce una descrizione umana dei pesi.
        Accetta KA/KB come lista/tupla/set/stringa/intero (numero mesi), usando _coerce_periods.
        """
        crit = int(crit or 1)
        if crit == 1:
            return "Uniforme (12 mesi)"

        # clamp degli alpha
        try:
            a1 = float(a1) if a1 is not None else None
        except Exception:
            a1 = None
        try:
            a2 = float(a2) if a2 is not None else None
        except Exception:
            a2 = None

        # Coercizione robusta dei periodi (gestisce anche int e stringhe)
        KA_list, KB_list = _coerce_periods(KA, KB, start_idx)

        return f"KA={KA_list}, KB={KB_list}, α1={a1}, α2={a2}"
    
    def _invariants(donors, receivers, result):
        m = result.get("model", {}) if isinstance(result, dict) else {}
        errs = []

        # Somma Esj per donatore = suo S_eff (S_trim/S_net)
        Esj_by_d = m.get("Esj_by_donor", {}) or {}
        for d in donors:
            name = d.get("name", d.get("place","?"))
            s_eff = _get_S_for_flow(d)
            Esj = Esj_by_d.get(name, [])
            if Esj and abs(sum(Esj) - s_eff) > 1e-6:
                errs.append(f"Donatore {name}: sum(Esj) != S_eff")

        # Totale A' sui riceventi = Esj_total
        if "A_prime_total" in m and "Esj_total" in m:
            if abs(sum(m["A_prime_total"]) - sum(m["Esj_total"])) > 1e-6:
                errs.append("Somma A' totale != Esj_total")

        # In B: somma A'' totale = somma P' by month
        if "A_dblprime_total" in m and "P_prime_by_month" in m:
            if abs(sum(m["A_dblprime_total"]) - sum(m["P_prime_by_month"])) > 1e-6:
                errs.append("Somma A'' totale != somma P' mensile")

        return errs


    def _compute_model_A(
        donors,
        receivers,
        criterio=None,
        KA=None,
        KB=None,
        alpha1=None,
        alpha2=None,
        start_idx=0,
        **kwargs
    ):
        """
        Modello A (NEW):
          - usa S_trim dei donatori (tramite _get_S_for_flow)
          - Criterio 1: uniforme su 12 mesi
          - Criterio 2: due periodi KA/KB con alpha1/alpha2
          - Riparto ai riceventi proporzionale a D_net(v)/Dtot

        Ritorna un dict con:
          out = {
            "model": { ... riepilogo mensile pulito ... },
            "Stot": ..., "Dtot": ...,
            "donors": { name: {"S_net","S_prime","Esj":[12]} ... },
            "receivers": { name: {"A_s","A_sj":[12],"A_dd_sj":[12],"A_total_sj":[12]} ... },
            "ok": True
          }
        """

        # --- Compatibility shim per parametri nuovi vs corpo legacy ---

        def _clampf01(x, default):
            try:
                v = float(x)
            except Exception:
                v = float(default)
            return max(0.0, min(1.0, v))

        # a1/a2 da alpha1/alpha2, con clamp e fallback
        if alpha1 is None and alpha2 is None:
            a1 = 0.5
            a2 = 0.5
        else:
            if alpha1 is None and alpha2 is not None:
                a2 = _clampf01(alpha2, 0.5)
                a1 = 1.0 - a2
            elif alpha2 is None and alpha1 is not None:
                a1 = _clampf01(alpha1, 0.5)
                a2 = 1.0 - a1
            else:
                a1 = _clampf01(alpha1, 0.5)
                a2 = _clampf01(alpha2, 0.5)

        # Default periodi se assenti: 7/5 stile “mediterraneo”
        if not KA:
            KA = list(range(0, 7))
        if not KB:
            KB = list(range(7, 12))

        # start_idx robusto
        try:
            start_idx = int(start_idx or 0)
        except Exception:
            start_idx = 0

        # --- Da qui: logica NEW del Modello A ---

        donors = list(donors or [])
        receivers = list(receivers or [])

        # Totali strutturali
        Stot = sum(_get_S_for_flow(d) for d in donors)
        # In questa codebase i ricevitori portano "D_net"
        Dtot = sum(float(r.get("D_net", 0.0)) for r in receivers)

        out = {
            "model": "A",   # mantieni l'identificatore storico
            "Stot": float(Stot),
            "Dtot": float(Dtot),
            "donors": {},
            "receivers": {},
        }

        # Se non c'è nessun deficit, il modello si riduce a zero ma manteniamo il shape
        if Dtot <= 0.0:
            empty12 = [0.0]*12
            # Donatori: esponiamo comunque l'Esj calcolato sui pesi, ma qui sarebbe inutile
            # Tuttavia per coerenza lasciamo tutto a zero.
            for d in donors:
                name = d.get("name", d.get("place", "?"))
                s_eff = _get_S_for_flow(d)
                out["donors"][name] = {"S_net": float(_get_S_for_flow(d)),
                                       "S_prime": float(s_eff),
                                       "Esj": empty12}
            for r in receivers:
                name = r.get("name", r.get("place", "?"))
                out["receivers"][name] = {
                    "A_s": float(r.get("D_net", 0.0)),
                    "A_sj": empty12,
                    "A_dd_sj": empty12,
                    "A_total_sj": empty12
                }
            # Blocchetto "model" pulito
            out["model"] = {
                "criterion": int(criterio) if criterio is not None else 1,
                "weights_desc": _weights_desc(criterio, KA, KB, a1, a2, start_idx),
                "Esj_by_donor": {k: v["Esj"] for k, v in out["donors"].items()},
                "Esj_total": empty12,
                "A_prime_by_receiver": {k: v["A_sj"] for k, v in out["receivers"].items()},
                "A_prime_total": empty12,
                "Asj_by_receiver": {k: v["A_sj"] for k, v in out["receivers"].items()},
                "Asj_total": empty12
            }
            out["ok"] = True
            return out

        # 1) Pesi mensili
        crit = int(criterio) if criterio is not None else 1
        if crit == 1:
            weights = [1.0/12.0]*12
        else:
            # NEW: coerce robusto di KA/KB (possono arrivare come int, string, lista)
            KA_list, KB_list = _coerce_periods(KA, KB, start_idx)
            weights = _period_weights(KA_list, KB_list, a1, a2)

        # 2) Erogazioni aggiuntive dai donatori (Esj) usando S_trim se presente
        Esj_by_donor = {}
        for d in donors:
            name = d.get("name", d.get("place", "?"))
            s_eff = _get_S_for_flow(d)  # S_trim se c'è, altrimenti S_net
            Esj = [s_eff * w for w in weights]
            # correggi l'ultimo mese per chiudere eventuali errori numerici
            diff = s_eff - sum(Esj)
            if abs(diff) > 1e-9:
                Esj[-1] += diff
            Esj_by_donor[name] = Esj
            out["donors"][name] = {
                "S_net": float(_get_S_for_flow(d)),
                "S_prime": float(s_eff),
                "Esj": Esj
            }

        # 3) Totale Esj al nodo M
        Esj_total = [0.0]*12
        for arr in Esj_by_donor.values():
            for m in range(12):
                Esj_total[m] += float(arr[m] or 0.0)

        # 4) Riparto verso i riceventi proporzionale a D_net/Dtot
        A_prime_by_receiver = {}
        for r in receivers:
            name = r.get("name", r.get("place", "?"))
            Dv = float(r.get("D_net", 0.0))
            share = (Dv / Dtot) if Dtot > 0.0 else 0.0
            A_v = [Esj_total[m] * share for m in range(12)]
            # correzione numerica per rispettare l’annuo
            target = share * sum(Esj_total)
            diff = target - sum(A_v)
            if abs(diff) > 1e-9:
                A_v[-1] += diff
            A_prime_by_receiver[name] = A_v
            out["receivers"][name] = {
                "A_s": Dv,
                "A_sj": A_v,
                "A_dd_sj": [0.0]*12,   # nessun contributo esterno nel Modello A
                "A_total_sj": A_v[:]   # nel Modello A, totale = A'
            }

        # 5) Totale A' (somma sui riceventi, per coerenza)
        A_prime_total = [0.0]*12
        for arr in A_prime_by_receiver.values():
            for m in range(12):
                A_prime_total[m] += float(arr[m] or 0.0)

        # 6) Blocchetto "model" coerente con il resto dell'app
        out["model"] = {
            "criterion": crit,
            "weights_desc": _weights_desc(crit, KA, KB, a1, a2, start_idx),
            # NIENTE 'weights' qui
            "Esj_by_donor": Esj_by_donor,
            "Esj_total": Esj_total,
            "A_prime_by_receiver": A_prime_by_receiver,
            "A_prime_total": A_prime_total,

            # alias per massima compatibilità con vecchi template
            "Asj_by_receiver": A_prime_by_receiver,
            "Asj_total": A_prime_total
        }


        out["ok"] = True
        return out


    def _Pprime_total_j(traverses_json):
        Ptot = [0.0]*12
        for tr in traverses_json:
            Pj = _pad12(tr.get("Pj"))
            Peco = _pad12(tr.get("Pj(eco)"))
            Pij = _pad12(tr.get("Pij"))
            for j in range(12):
                Ptot[j] += max(Pj[j] - (Peco[j] + Pij[j]), 0.0)
        return Ptot

    def _compute_model_B(
    donors,
    receivers,
    traverses_json,
    criterio=None,              # ignorato ai fini logici, usiamo 'variante'
    variante=None,              # 1 => uniforme, 2 => KA/KB con alpha
    KA=None, KB=None,
    alpha1=None, alpha2=None,
    start_idx=0,
    **kwargs
    ):
        """
        Modello B (NEW):
          - I donatori EROGANO comunque S_trim mensile (A′), pesato per variante:
              * variante=1  => pesi uniformi
              * variante=2  => due periodi KA/KB con alpha1/alpha2
          - Le risorse fluenti P′ coprono SOLO il residuo Δ = Dtot - Stot_eff
            quindi si scala P′ per farne coincidere la somma con Δ.
          - Riparto ai riceventi proporzionale a D(v)/Dtot.
        Output: mantiene lo shape legacy per template.
        """

        # --- utilità locali coerenti con step 2/3 ---
        def _clampf01(x, default):
            try:
                v = float(x)
            except Exception:
                v = float(default)
            return max(0.0, min(1.0, v))

        donors = list(donors or [])
        receivers = list(receivers or [])

        # Totali strutturali
        Stot_eff = sum(_get_S_for_flow(d) for d in donors)                  # usa S_trim se presente
        Dtot     = sum(float(r.get("D_net", 0.0)) for r in receivers)

        out = {
            "model": "B",
            "Stot": float(Stot_eff),
            "Dtot": float(Dtot),
            "donors": {},
            "receivers": {},
        }

        # Se non c'è nessun ricevente/deficit, tutto zero ma shape coerente
        if Dtot <= 0.0:
            zeros12 = [0.0]*12
            for d in donors:
                name = d.get("name", d.get("place", "?"))
                s_eff = _get_S_for_flow(d)
                out["donors"][name] = {"S_net": float(_get_S_for_flow(d)),
                                       "S_prime": float(s_eff),
                                       "Esj": zeros12[:] }
            for r in receivers:
                name = r.get("name", r.get("place", "?"))
                out["receivers"][name] = {
                    "A_s": float(r.get("D_net", 0.0)),
                    "A_sj": zeros12[:],
                    "A_dd_sj": zeros12[:],
                    "A_total_sj": zeros12[:]
                }
            out["model"] = {
                "variante": int(variante) if variante is not None else 1,
                "rho": 0.0,
                "Delta": 0.0,
                "P_prime_total": 0.0,
                "P_prime_by_month": zeros12[:],
                "A_dblprime_by_receiver": {k: zeros12[:] for k in out["receivers"].keys()},
                "A_dblprime_total": zeros12[:],
                # opzionale: anche riepilogo A′
                "Esj_total": zeros12[:]
            }
            out["ok"] = True
            return out

        # -------- 1) Pesi mensili per DONATORI (A′) --------
        var = int(variante) if variante is not None else 1

        if var == 1:
            weights = [1.0/12.0] * 12
            weights_desc = "Uniforme (12 mesi)"
        else:
            # Variante 2: due periodi KA/KB con alpha
            a1 = _clampf01(alpha1, 0.5)
            a2 = _clampf01(alpha2, 1.0 - a1)
            KA_list, KB_list = _coerce_periods(KA, KB, start_idx)
            weights = _period_weights(KA_list, KB_list, a1, a2)
            weights_desc = _weights_desc(2, KA_list, KB_list, a1, a2, start_idx)

        # Erogazioni dei singoli DONATORI
        Esj_by_donor = {}
        for d in donors:
            name = d.get("name", d.get("place", "?"))
            s_eff = _get_S_for_flow(d)                  # S_trim se presente
            Esj = [s_eff * w for w in weights]
            # correzione numerica
            diff = s_eff - sum(Esj)
            if abs(diff) > 1e-9:
                Esj[-1] += diff
            Esj_by_donor[name] = Esj
            out["donors"][name] = {
                "S_net": float(_get_S_for_flow(d)),
                "S_prime": float(s_eff),
                "Esj": Esj
            }

        # Totale A′ mensile (al nodo M_donatori)
        Esj_total = [0.0]*12
        for arr in Esj_by_donor.values():
            for m in range(12):
                Esj_total[m] += float(arr[m] or 0.0)

        # -------- 2) Risorse fluenti P′ SCALATE SU Δ (A″) --------
        Delta = max(Dtot - Stot_eff, 0.0)
        Pp_by_month_raw = _Pprime_total_j(traverses_json) if traverses_json else [0.0]*12
        Pp_total_raw = float(sum(Pp_by_month_raw))

        if Pp_total_raw > 0.0 and Delta > 0.0:
            scale = min(Delta / Pp_total_raw, 1.0)
            Pp_by_month = [x * scale for x in Pp_by_month_raw]
            Pp_total    = float(sum(Pp_by_month))  # ~ Delta
            rho = (Pp_total_raw / Delta) if Delta > 0 else 0.0   # indice di "abbondanza"
        else:
            Pp_by_month = [0.0]*12
            Pp_total    = 0.0
            rho         = 0.0

        # -------- 3) Riparto ai RICEVENTI proporzionale a D(v)/Dtot --------
        A_prime_by_receiver     = {}   # A′ dai donatori
        A_dblprime_by_receiver  = {}   # A″ da esterni
        A_prime_total           = [0.0]*12
        A_dblprime_total        = [0.0]*12

        for r in receivers:
            name = r.get("name", r.get("place", "?"))
            Dv   = float(r.get("D_net", 0.0))
            share = (Dv / Dtot) if Dtot > 0.0 else 0.0

            # quota da donatori (A′)
            A_v_prime = [Esj_total[m] * share for m in range(12)]
            # aggiusta arrotondamento annuo
            t_prime = share * sum(Esj_total)
            d_prime = t_prime - sum(A_v_prime)
            if abs(d_prime) > 1e-9:
                A_v_prime[-1] += d_prime

            # quota da esterni (A″)
            A_v_dblprime = [Pp_by_month[m] * share for m in range(12)]
            t_dblprime = share * Pp_total
            d_dblprime = t_dblprime - sum(A_v_dblprime)
            if abs(d_dblprime) > 1e-9:
                A_v_dblprime[-1] += d_dblprime

            A_prime_by_receiver[name] = A_v_prime
            A_dblprime_by_receiver[name] = A_v_dblprime

            for m in range(12):
                A_prime_total[m]    += float(A_v_prime[m])
                A_dblprime_total[m] += float(A_v_dblprime[m])

            # shape legacy nel blocco 'receivers'
            A_total = [A_prime + A_dd for A_prime, A_dd in zip(A_v_prime, A_v_dblprime)]
            out["receivers"][name] = {
                "A_s": Dv,
                "A_sj": A_v_prime,          # A′
                "A_dd_sj": A_v_dblprime,    # A″
                "A_total_sj": A_total       # A′ + A″
            }

        # -------- 4) blocco "model" per template/diagnostica --------
        out["model"] = {
            "variante": var,
            "weights_desc": weights_desc,
            "rho": float(rho),
            "Delta": float(Delta),
            "P_prime_total": float(Pp_total),
            "P_prime_by_month": [float(x) for x in Pp_by_month],
            "A_dblprime_by_receiver": A_dblprime_by_receiver,
            "A_dblprime_total": A_dblprime_total,
            # mettiamo anche il riepilogo A′ per completezza
            "Esj_total": Esj_total,
            "A_prime_by_receiver": A_prime_by_receiver,
            "A_prime_total": A_prime_total,
        }

        out["ok"] = True
        return out

    def _checks(donors: dict, receivers: dict, result: dict):
        """
        Verifiche operative NEW (mese per mese).

        Donatori (j):
          W_check_j(m) = W_prev_j(m) + A_j(m) - [ E_j(m) + Esj_j(m) ] >= W0_j

        Riceventi (v):
          W_check_v(m) = W_prev_v(m) + A_v(m) + Asj_v(m) - E_v(m) >= W0_v
            dove Asj_v(m) = A'_sj(v,m) + A''_sj(v,m)
            - Nel Modello A: Asj_v = A'_sj, A''_sj = 0
            - Nel Modello B: Asj_v = A'_sj + A''_sj (entrambi presenti)

        Note:
          - Se mancano W_prev_j(m) o W0_j, la verifica di quell’invaso viene marcata True (leniente),
            così non esplodiamo su dati incompleti ma non “bocciamo” a caso.
          - Aj/Ej sono attesi dentro donors/receivers (Step 2 li stivava), altrimenti fallback 0.
        """
        out = {"donors": {}, "receivers": {}}

        # 1) Esj per donatore j (dalla struttura "model" del risultato)
        model = result.get("model", {}) if isinstance(result, dict) else {}
        Esj_by_donor = model.get("Esj_by_donor", {}) or {}
        # Per Modello A: A' per riceventi; per B: abbiamo anche A''.
        A_prime_by_receiver   = model.get("A_prime_by_receiver", {}) or {}
        A_dblprime_by_receiver= model.get("A_dblprime_by_receiver", {}) or {}

        # --- Donors checks ---
        for d in donors:
            name = d.get("name", d.get("place", "?"))
            Aj   = d.get("Aj", [0.0]*12)
            Ej   = d.get("Ej", [0.0]*12)
            W0   = float(d.get("W0", d.get("Wmin", 0.0)))
            Wpv  = d.get("Wprev_month")  # può essere None
            Esj  = Esj_by_donor.get(name, [0.0]*12)

            ok_vec = []
            for m in range(12):
                if not Wpv:
                    ok_vec.append(True)  # niente livelli, niente party
                else:
                    w_check = float(Wpv[m]) + float(Aj[m]) - (float(Ej[m]) + float(Esj[m]))
                    ok_vec.append(w_check >= W0)
            out["donors"][name] = ok_vec

        # --- Receivers checks ---
        # Asj = A' (+ A'') a seconda del modello
        for r in receivers:
            name = r.get("name", r.get("place", "?"))
            Aj   = r.get("Aj", [0.0]*12)
            Ej   = r.get("Ej", [0.0]*12)
            W0   = float(r.get("W0", r.get("Wmin", 0.0)))
            Wpv  = r.get("Wprev_month")
            A_p  = A_prime_by_receiver.get(name, [0.0]*12)
            A_pp = A_dblprime_by_receiver.get(name, [0.0]*12)
            Asj  = [float(A_p[m]) + float(A_pp[m]) for m in range(12)]

            ok_vec = []
            for m in range(12):
                if not Wpv:
                    ok_vec.append(True)
                else:
                    w_check = float(Wpv[m]) + float(Aj[m]) + float(Asj[m]) - float(Ej[m])
                    ok_vec.append(w_check >= W0)
            out["receivers"][name] = ok_vec

        return out

    def _pack_for_template(basins_json, traverses_json, criterio, KA, KB, alpha1):
        """
        Step 1–4: classifica invasi, ricalibra i donatori (S_trim),
        calcola Modello A o B (due varianti/criteri), esegue le verifiche operative
        e prepara i dati nello shape legacy atteso dal template.
        Ritorna:
          (calculated_data1, satisfiedA,
           calculated_data2, satisfiedB,
           calculated_data3, comparison,
           traverse_data, traverse_amount,
           surplus_sum_lordo, deficit_sum, total_eff)
        """
        # 1) Classificazione NEW (step 1)
        donors, receivers, Stot, Dtot = _classify(basins_json)

        # 2) Ricalibrazione NEW (step 2)
        donors, recalib_summary = _recalibrate_donors(donors, Stot, Dtot)
        Stot_trim = recalib_summary["Stot_trim"]

        # Stash Aj/Ej per checks se mancanti
        for d in donors:
            d.setdefault("Aj", d.get("Aj", []))
            d.setdefault("Ej", d.get("Ej", []))
        for r in receivers:
            r.setdefault("Aj", r.get("Aj", []))
            r.setdefault("Ej", r.get("Ej", []))

        # Indice di partenza (se non definito altrove, questa util restituisce 0)
        start_idx = _start_idx_from_first(basins_json)

        # 3) Riepilogo risorse fluenti (per UI)
        traverse_data = {"P_prime_j": _Pprime_total_j(traverses_json)} if traverses_json else {"P_prime_j": [0.0] * 12}
        traverse_amount = float(sum(traverse_data["P_prime_j"]))

        # 4) Parametri criteri (α2 normalizzato)
        try:
            a1 = float(alpha1)
        except Exception:
            a1 = 0.5
        a1 = max(0.0, min(1.0, a1))
        a2 = 1.0 - a1

        # 5) Branch strutturale: A se Stot>=Dtot, altrimenti B
        if Stot >= Dtot:
            # Modello A — Criterio 1 e 2
            result_c1 = _compute_model_A(donors, receivers, criterio=1, KA=KA, KB=KB,
                                         alpha1=a1, alpha2=a2, start_idx=start_idx)
            result_c2 = _compute_model_A(donors, receivers, criterio=2, KA=KA, KB=KB,
                                         alpha1=a1, alpha2=a2, start_idx=start_idx)
        else:
            # Modello B — Variante 1 e 2 (variante 1: uniforme; 2: KA/KB con alpha)
            result_c1 = _compute_model_B(donors, receivers, traverses_json, variante=1,
                                         KA=KA, KB=KB, alpha1=a1, alpha2=a2, start_idx=start_idx)
            result_c2 = _compute_model_B(donors, receivers, traverses_json, variante=2,
                                         KA=KA, KB=KB, alpha1=a1, alpha2=a2, start_idx=start_idx)

        # 6) Finale scelto da UI
        chosen = int(criterio) if str(criterio).strip().isdigit() else 1
        result_final = result_c1 if chosen == 1 else result_c2

        # 7) Verifiche operative sui tre modelli (c1, c2, final)
        chk1 = _checks(donors, receivers, result_c1)
        chk2 = _checks(donors, receivers, result_c2)
        chkf = _checks(donors, receivers, result_final)


        def _all_true(dmap):
            if not dmap:
                return True
            for vec in dmap.values():
                if not all(bool(x) for x in (vec or [])):
                    return False
            return True

        # “Cond. Soddisfatte” per blocchi Criterio 1/2
        satisfiedA = _all_true(chk1.get("donors", {})) and _all_true(chk1.get("receivers", {}))
        satisfiedB = _all_true(chk2.get("donors", {})) and _all_true(chk2.get("receivers", {}))
        satisfied_final = _all_true(chkf.get("donors", {})) and _all_true(chkf.get("receivers", {}))

        # Attacca i dettagli per diagnosi (opzionali)
        result_c1["checks"] = chk1
        result_c2["checks"] = chk2
        result_final["checks"] = chkf
        result_final["checks_summary"] = {
            "criterion1_ok": satisfiedA,
            "criterion2_ok": satisfiedB,
            "final_ok": satisfied_final,
        }
        
        inv1 = _invariants(donors, receivers, result_c1)
        inv2 = _invariants(donors, receivers, result_c2)
        invf = _invariants(donors, receivers, result_final)
        result_c1["invariants"] = inv1
        result_c2["invariants"] = inv2
        result_final["invariants"] = invf

        # 8) Somme e summary
        surplus_sum_lordo = float(Stot)
        surplus_sum_eff = float(sum(_get_S_for_flow(d) for d in donors))  # usa S_trim se presente
        deficit_sum = float(Dtot)
        total_eff = surplus_sum_eff - deficit_sum

        # Tripla per compat vecchio template
        comparison = [result_c1.get("model"), result_c2.get("model"), result_final.get("model")]

        # Outputs
        calculated_data1 = result_c1
        calculated_data2 = result_c2
        calculated_data3 = result_final

        # Summary step2 utile alla UI
        summary_step2 = {
            "n_donors": len(donors),
            "n_receivers": len(receivers),
            "Stot": surplus_sum_lordo,
            "Dtot": deficit_sum,
            "trimmed": recalib_summary["trimmed"],
            "delta": recalib_summary["delta"],
            "Stot_trim": Stot_trim,
            "Stot_eff": surplus_sum_eff,
            "traverse_amount": traverse_amount
        }
        calculated_data3["summary_step2"] = summary_step2

        return (
            calculated_data1, satisfiedA,
            calculated_data2, satisfiedB,
            calculated_data3, comparison,
            traverse_data, traverse_amount,
            surplus_sum_lordo, deficit_sum, total_eff
        )

    # ---------- GET: page or quick load by query ----------
    if request.method == 'GET':
        qs_name = request.args.get("past_select")
        if qs_name:
            data = load_past_json_data(qs_name)
            if not data:
                flash("Saved exchange not found.", "danger")
                return redirect(url_for('main.exchange'))
            c1 = data["calculated_data1"]
            c2 = data["calculated_data2"]
            c3 = data["calculated_data3"]
            comp = data["comparison"]
            traverse_data = data["traverse"]
            return render_template('exchange.html',
                                   filename=qs_name, data=as_mapping(
                                       data.get("data")),
                                   past_exchange=past_exchange, files=files, traverse_files=traverse_files,
                                   surplus_sum=data["surplus_sum"], deficit_sum=data["deficit_sum"],
                                   calculated_data1=c1, calculated_data2=c2, calculated_data3=c3,
                                   total=data["total"],
                                   comparison1=comp[0], comparison2=comp[1], comparison3=comp[2],
                                   traverse=traverse_data, traverse_tot=data.get(
                                       "traverse_amount", 0),
                                   satisfiedA=data.get("satisfiedA"), satisfiedB=data.get("satisfiedB"),
                                   selected_files=[], selected_traverse=[])
        # regular empty page
        return render_template('exchange.html', data=None,
                               past_exchange=past_exchange, files=files, traverse_files=traverse_files,
                               surplus_sum=0, deficit_sum=0, traverse=0, traverse_tot=0, total=0,
                               selected_files=[], selected_traverse=[])

    # ---------- DELETE: JSON API ----------
    if request.method == 'DELETE':
        payload = request.get_json(silent=True) or {}
        filename = payload.get("past_select")
        if not filename:
            return jsonify({"error": "past_select missing"}), 400
        entry = db.session.execute(
            select(PastExchange).filter(
                PastExchange.user_id == current_user.id,
                PastExchange.filename == filename
            )
        ).scalar_one_or_none()
        if not entry:
            return jsonify({"error": "not found"}), 404
        db.session.delete(entry)
        try:
            db.session.commit()
            return jsonify({"status": "deleted", "filename": filename})
        except SQLAlchemyError:
            db.session.rollback()
            return jsonify({"error": "db error"}), 500

    # ---------- PUT: JSON API (upsert/update) ----------
    if request.method == 'PUT':
        payload = request.get_json(silent=True) or {}
        if not payload.get("exchange_name") or not payload.get("json_data"):
            return jsonify({"error": "exchange_name and json_data required"}), 400
        name = payload["exchange_name"]
        content = json.dumps(payload["json_data"])
        entry = db.session.execute(
            select(PastExchange).filter(
                PastExchange.user_id == current_user.id,
                PastExchange.filename == name
            )
        ).scalar_one_or_none()
        if entry:
            entry.json_data = content
        else:
            entry = PastExchange(
                filename=name, json_data=content, user_id=current_user.id)
            db.session.add(entry)
        try:
            db.session.commit()
            return jsonify({"status": "ok", "filename": name})
        except SQLAlchemyError:
            db.session.rollback()
            return jsonify({"error": "db error"}), 500

    # ---------- POST (form): load / delete buttons ----------
    if request.method == 'POST':
        # 1) LOAD saved exchange from dropdown
        if 'load' in request.form:
            filename = request.form.get("past_select")
            if filename:
                data = load_past_json_data(filename)
                if data:
                    c1 = data["calculated_data1"]
                    c2 = data["calculated_data2"]
                    c3 = data["calculated_data3"]
                    comp = data["comparison"]
                    traverse_data = data["traverse"]
                    return render_template('exchange.html', filename=filename, data=as_mapping(data.get("data")),
                                           past_exchange=past_exchange, files=files, traverse_files=traverse_files,
                                           surplus_sum=data["surplus_sum"], deficit_sum=data["deficit_sum"],
                                           calculated_data1=c1, calculated_data2=c2, calculated_data3=c3,
                                           total=data["total"],
                                           comparison1=comp[0], comparison2=comp[1], comparison3=comp[2],
                                           traverse=traverse_data, traverse_tot=data.get(
                                               "traverse_amount", 0),
                                           satisfiedA=data.get("satisfiedA"), satisfiedB=data.get("satisfiedB"),
                                           selected_files=[], selected_traverse=[])
            flash("Select a saved exchange.", "warning")
            return redirect(url_for('main.exchange'))

        # 2) DELETE saved exchange from dropdown
        if 'delete' in request.form:
            filename = request.form.get("past_select")
            if filename:
                file_to_delete = db.session.execute(
                    select(PastExchange).filter(
                        PastExchange.user_id == current_user.id,
                        PastExchange.filename == filename
                    )
                ).scalar_one_or_none()
                if file_to_delete:
                    db.session.delete(file_to_delete)
                    try:
                        db.session.commit()
                        flash(
                            f'File "{filename}" deleted successfully!', 'success')
                    except SQLAlchemyError:
                        db.session.rollback()
                        flash(
                            "Database error occurred while deleting file.", "danger")
                else:
                    flash(f'File "{filename}" not found.', 'danger')
            return redirect(url_for('main.exchange'))

        # 3) COMPUTE with NEW MODEL (form submit)
        selected_files = request.form.getlist('selected_files')
        selected_traverse = request.form.getlist('selected_traverse')

        # new model params (defaults sane)
        criterio = int(_pf(request.form.get('criterio', 1))
                       )      # 1=uniform, 2=two-periods
        KA = int(_pf(request.form.get('KA', 7)))
        KB = int(_pf(request.form.get('KB', 5)))
        alpha1 = _pf(request.form.get('alpha1', 0.6))
        if KA + KB != 12:  # be kind, fix sloppy input
            KB = max(0, 12 - max(0, min(KA, 12)))

        if not selected_files:
            flash("Seleziona almeno un invaso.", "danger")
            return redirect(url_for('main.exchange'))

        basins_json = _load_basin_jsons(selected_files)
        traverses_json = _load_traverse_jsons(
            selected_traverse) if selected_traverse else []

        # compute both criteria for comparison and the chosen one as final
        (calculated_data1, satisfiedA,
         calculated_data2, satisfiedB,
         calculated_data3, comparison,
         traverse_data, traverse_amount,
         surplus_sum, deficit_sum, total) = _pack_for_template(basins_json, traverses_json, criterio, KA, KB, alpha1)

        # build DB record similar to your legacy structure
        # "data" kept for compatibility; you can store basins_json
        print(calculated_data1)
        exchange_name = nameExchange(
            calculated_data1, round_floats(traverse_data))
        db_payload = {
            "exchange_name": exchange_name,
            "calculated_data1": calculated_data1,
            "calculated_data2": calculated_data2,
            "calculated_data3": calculated_data3,
            "comparison": comparison,
            "data": basins_json,
            "surplus_sum": surplus_sum,
            "deficit_sum": deficit_sum,
            "traverse": round_floats(traverse_data),
            "traverse_amount": traverse_amount,
            "total": total,
            "satisfiedA": satisfiedA,
            "satisfiedB": satisfiedB
        }

        # upsert DB
        if check_entry_existance(exchange_name, current_user, PastExchange):
            entry = db.session.execute(
                select(PastExchange).filter(
                    PastExchange.user_id == current_user.id,
                    PastExchange.filename == exchange_name
                )
            ).scalar_one_or_none()
            if entry:
                entry.json_data = json.dumps(db_payload)
                entry.user_id = current_user.id
        else:
            entry = PastExchange(filename=exchange_name,
                                 json_data=json.dumps(db_payload),
                                 user_id=current_user.id)
            db.session.add(entry)
        try:
            db.session.commit()
            flash('Form successfully submitted!', 'success')
        except SQLAlchemyError:
            db.session.rollback()
            flash("Database error occurred while submitting the form.", "danger")

        past_exchange = get_past_exchange()

        # render page with all three “slots” (1,2,final) to preserve your template UX
        return render_template('exchange.html',
                               filename=exchange_name, data=as_mapping(
                                   basins_json),
                               past_exchange=past_exchange, files=files, traverse_files=traverse_files,
                               surplus_sum=surplus_sum, deficit_sum=deficit_sum,
                               calculated_data1=calculated_data1, calculated_data2=calculated_data2, calculated_data3=calculated_data3,
                               comparison1=comparison[0], comparison2=comparison[1], comparison3=comparison[2],
                               traverse=traverse_data, total=total, traverse_tot=traverse_amount,
                               satisfiedA=satisfiedA, satisfiedB=satisfiedB,
                               selected_files=selected_files, selected_traverse=selected_traverse)

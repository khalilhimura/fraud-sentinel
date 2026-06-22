"""Reproducible synthetic transaction generation for Phase 2."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCENARIOS = [
    "fan_in_mule",
    "rapid_pass_through",
    "layering_chain",
    "shared_device_ring",
    "cross_border_funnel",
    "new_account_burst",
    "short_cycle",
]


@dataclass(frozen=True)
class SyntheticDataResult:
    """Paths and counts from synthetic data generation."""

    output_path: Path
    scenario_manifest_path: Path
    row_count: int
    scenario_counts: dict[str, int]


def _account(index: int) -> str:
    return f"ACC{index:06d}"


def _transaction(
    index: int,
    timestamp: pd.Timestamp,
    sender: str,
    receiver: str,
    amount: float,
    *,
    currency: str,
    sender_country: str = "MY",
    receiver_country: str = "MY",
    device_id: str | None = None,
    ip_address: str | None = None,
    is_seed: bool = False,
    scenario: str = "",
) -> dict[str, Any]:
    return {
        "transaction_id": f"TX{index:010d}",
        "event_timestamp": timestamp.isoformat().replace("+00:00", "Z"),
        "sender_account_id": sender,
        "receiver_account_id": receiver,
        "amount": f"{amount:.2f}",
        "currency": currency,
        "transaction_type": "transfer",
        "channel": "mobile",
        "sender_bank_id": "BANK_MY_001",
        "receiver_bank_id": "BANK_MY_001",
        "sender_country": sender_country,
        "receiver_country": receiver_country,
        "device_id": device_id or f"DEV{index % 97:05d}",
        "ip_address": ip_address or f"10.42.{index % 251}.{(index * 17) % 251}",
        "merchant_category": "",
        "description": "",
        "sender_account_opened_at": (
            timestamp - pd.Timedelta(days=365 + index % 700)
        ).isoformat().replace("+00:00", "Z"),
        "receiver_account_opened_at": (
            timestamp - pd.Timedelta(days=180 + index % 500)
        ).isoformat().replace("+00:00", "Z"),
        "is_synthetic_fraud_seed": is_seed,
        "synthetic_scenario": scenario,
    }


def _scenario_rows(start_index: int, currency: str) -> list[dict[str, Any]]:
    base = pd.Timestamp("2026-01-30T08:00:00Z")
    rows: list[dict[str, Any]] = []
    index = start_index

    mule = _account(90_001)
    for offset in range(12):
        rows.append(
            _transaction(
                index,
                base + pd.Timedelta(minutes=offset * 3),
                _account(10_000 + offset),
                mule,
                850 + offset * 25,
                currency=currency,
                is_seed=True,
                scenario="fan_in_mule",
            )
        )
        index += 1
    rows.append(
        _transaction(
            index,
            base + pd.Timedelta(minutes=45),
            mule,
            _account(10_050),
            10_500,
            currency=currency,
            sender_country="MY",
            receiver_country="SG",
            is_seed=True,
            scenario="fan_in_mule",
        )
    )
    index += 1

    pass_through = _account(90_010)
    rows.extend(
        [
            _transaction(
                index,
                base + pd.Timedelta(hours=2),
                _account(10_100),
                pass_through,
                12_500,
                currency=currency,
                is_seed=True,
                scenario="rapid_pass_through",
            ),
            _transaction(
                index + 1,
                base + pd.Timedelta(hours=3),
                pass_through,
                _account(10_101),
                11_900,
                currency=currency,
                is_seed=True,
                scenario="rapid_pass_through",
            ),
        ]
    )
    index += 2

    chain_accounts = [_account(90_020 + step) for step in range(5)]
    for step in range(4):
        rows.append(
            _transaction(
                index,
                base + pd.Timedelta(hours=4, minutes=step * 20),
                chain_accounts[step],
                chain_accounts[step + 1],
                7_000 - step * 250,
                currency=currency,
                is_seed=True,
                scenario="layering_chain",
            )
        )
        index += 1

    for offset in range(6):
        rows.append(
            _transaction(
                index,
                base + pd.Timedelta(hours=6, minutes=offset * 5),
                _account(90_040 + offset),
                _account(10_200 + offset),
                1_500 + offset * 100,
                currency=currency,
                device_id="DEV_SHARED_RING",
                ip_address="10.99.0.10",
                is_seed=True,
                scenario="shared_device_ring",
            )
        )
        index += 1

    funnel = _account(90_060)
    rows.extend(
        [
            _transaction(
                index,
                base + pd.Timedelta(hours=8),
                _account(10_300),
                funnel,
                10_500,
                currency=currency,
                is_seed=True,
                scenario="cross_border_funnel",
            ),
            _transaction(
                index + 1,
                base + pd.Timedelta(hours=9),
                funnel,
                _account(10_301),
                9_900,
                currency=currency,
                sender_country="MY",
                receiver_country="SG",
                is_seed=True,
                scenario="cross_border_funnel",
            ),
        ]
    )
    index += 2

    new_account = _account(90_070)
    for offset in range(8):
        row = _transaction(
            index,
            base + pd.Timedelta(hours=10, minutes=offset * 4),
            _account(10_400 + offset),
            new_account,
            600 + offset * 50,
            currency=currency,
            is_seed=True,
            scenario="new_account_burst",
        )
        row["receiver_account_opened_at"] = (
            base - pd.Timedelta(days=5)
        ).isoformat().replace("+00:00", "Z")
        rows.append(row)
        index += 1

    cycle_accounts = [_account(90_080), _account(90_081), _account(90_082)]
    for step in range(3):
        rows.append(
            _transaction(
                index,
                base + pd.Timedelta(hours=12, minutes=step * 15),
                cycle_accounts[step],
                cycle_accounts[(step + 1) % len(cycle_accounts)],
                2_200 - step * 100,
                currency=currency,
                is_seed=True,
                scenario="short_cycle",
            )
        )
        index += 1

    return rows


def _normal_rows(
    rows: int,
    start_index: int,
    rng: np.random.Generator,
    account_count: int,
    currency: str,
) -> list[dict[str, Any]]:
    base = pd.Timestamp("2026-01-01T00:00:00Z")
    generated: list[dict[str, Any]] = []
    channels = np.array(["mobile", "web", "atm", "branch", "api"])
    countries = np.array(["MY", "MY", "MY", "SG", "ID", "TH"])

    for offset in range(rows):
        index = start_index + offset
        sender_index = int(rng.integers(1, account_count + 1))
        receiver_index = int(rng.integers(1, account_count + 1))
        if receiver_index == sender_index:
            receiver_index = (receiver_index % account_count) + 1
        timestamp = base + pd.Timedelta(seconds=int(rng.integers(0, 30 * 24 * 60 * 60)))
        amount = float(np.clip(rng.lognormal(mean=6.0, sigma=0.8), 5, 50_000))
        row = _transaction(
            index,
            timestamp,
            _account(sender_index),
            _account(receiver_index),
            amount,
            currency=currency,
            sender_country=str(rng.choice(countries)),
            receiver_country=str(rng.choice(countries)),
        )
        row["channel"] = str(rng.choice(channels))
        generated.append(row)
    return generated


def generate_synthetic_transactions(
    rows: int,
    output: Path | str,
    seed: int = 42,
    account_count: int | None = None,
    currency: str = "MYR",
) -> SyntheticDataResult:
    """Generate a deterministic synthetic transaction CSV and scenario manifest."""

    if rows < 40:
        raise ValueError("Synthetic generation requires at least 40 rows to include scenarios")

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(seed)
    scenario_rows = _scenario_rows(1, currency.upper())
    normal_count = rows - len(scenario_rows)
    normal_rows = _normal_rows(
        normal_count,
        len(scenario_rows) + 1,
        rng,
        account_count or max(100, rows // 4),
        currency.upper(),
    )
    all_rows = scenario_rows + normal_rows
    frame = pd.DataFrame(all_rows)
    frame.to_csv(output_path, index=False, lineterminator="\n")

    scenario_counts = (
        frame.loc[frame["synthetic_scenario"] != "", "synthetic_scenario"]
        .value_counts()
        .sort_index()
        .to_dict()
    )
    scenario_manifest_path = output_path.with_suffix(".scenario_manifest.json")
    manifest = {
        "seed": seed,
        "row_count": rows,
        "account_count": account_count or max(100, rows // 4),
        "currency": currency.upper(),
        "scenarios": scenario_counts,
        "warning": "Synthetic defensive test data; not guidance for evading detection.",
    }
    scenario_manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return SyntheticDataResult(
        output_path=output_path,
        scenario_manifest_path=scenario_manifest_path,
        row_count=len(frame),
        scenario_counts={str(key): int(value) for key, value in scenario_counts.items()},
    )

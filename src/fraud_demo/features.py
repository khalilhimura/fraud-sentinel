"""Account-level feature engineering for Phase 3."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd


@dataclass(frozen=True)
class FeatureEngineeringResult:
    """Artifacts and counts from account feature engineering."""

    run_id: str
    run_dir: Path
    account_features_path: Path
    account_count: int
    snapshot_timestamp: str | None


def _json_safe_timestamp(value: Any) -> str | None:
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _read_transactions(run_path: Path) -> pd.DataFrame:
    transactions_path = run_path / "normalized_transactions.parquet"
    frame = pd.read_parquet(transactions_path)
    if frame.empty:
        return frame
    frame = frame.copy()
    frame["event_timestamp"] = pd.to_datetime(frame["event_timestamp"], utc=True)
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce").fillna(0.0)
    return frame


def _account_activity(transactions: pd.DataFrame) -> pd.DataFrame:
    activity_columns = [
        "sender_account_id",
        "receiver_account_id",
        "event_timestamp",
        "amount",
    ]
    outbound = transactions[activity_columns].rename(
        columns={"sender_account_id": "account_id", "receiver_account_id": "counterparty_id"}
    )
    inbound = transactions[
        ["receiver_account_id", "sender_account_id", "event_timestamp", "amount"]
    ].rename(
        columns={"receiver_account_id": "account_id", "sender_account_id": "counterparty_id"}
    )
    return pd.concat([outbound, inbound], ignore_index=True)


def _base_features(transactions: pd.DataFrame, run_id: str) -> pd.DataFrame:
    accounts = (
        pd.concat(
            [
                transactions["sender_account_id"],
                transactions["receiver_account_id"],
            ],
            ignore_index=True,
        )
        .dropna()
        .astype(str)
        .sort_values()
        .unique()
    )
    snapshot = transactions["event_timestamp"].max() if not transactions.empty else pd.NaT
    features = pd.DataFrame({"account_id": accounts})
    features.insert(0, "run_id", run_id)
    features["snapshot_timestamp"] = _json_safe_timestamp(snapshot)
    for column in [
        "first_activity_at",
        "last_activity_at",
        "hold_time_proxy_minutes",
        "cross_border_out_ratio_7d",
        "shared_device_account_count_30d",
        "shared_ip_account_count_30d",
        "account_age_days",
        "short_cycle_flag",
    ]:
        features[column] = pd.NA
    for column in [
        "incoming_count_24h",
        "outgoing_count_24h",
        "unique_senders_7d",
        "unique_receivers_7d",
        "active_days_30d",
    ]:
        features[column] = 0
    for column in [
        "incoming_amount_24h",
        "outgoing_amount_24h",
        "incoming_amount_7d",
        "outgoing_amount_7d",
        "pass_through_ratio_7d",
        "night_activity_ratio_7d",
        "round_amount_ratio_7d",
        "counterparty_concentration_7d",
        "reciprocal_transfer_ratio_7d",
    ]:
        features[column] = 0.0
    return features


def _set_from_series(
    features: pd.DataFrame,
    column: str,
    values: pd.Series,
    *,
    fill_value: Any,
) -> None:
    mapped = features["account_id"].map(values)
    features[column] = mapped.fillna(fill_value)


def _apply_activity_bounds(features: pd.DataFrame, activity: pd.DataFrame) -> None:
    grouped = activity.groupby("account_id")["event_timestamp"]
    features["first_activity_at"] = features["account_id"].map(
        grouped.min().map(_json_safe_timestamp)
    )
    features["last_activity_at"] = features["account_id"].map(
        grouped.max().map(_json_safe_timestamp)
    )


def _window(transactions: pd.DataFrame, snapshot: pd.Timestamp, **timedelta: int) -> pd.DataFrame:
    start = snapshot - pd.Timedelta(**timedelta)
    return transactions.loc[transactions["event_timestamp"] >= start].copy()


def _apply_core_windows(
    features: pd.DataFrame,
    transactions: pd.DataFrame,
    snapshot: pd.Timestamp,
) -> None:
    last_24h = _window(transactions, snapshot, hours=24)
    last_7d = _window(transactions, snapshot, days=7)
    last_30d = _window(transactions, snapshot, days=30)

    _set_from_series(
        features,
        "incoming_count_24h",
        last_24h.groupby("receiver_account_id").size(),
        fill_value=0,
    )
    _set_from_series(
        features,
        "outgoing_count_24h",
        last_24h.groupby("sender_account_id").size(),
        fill_value=0,
    )
    _set_from_series(
        features,
        "incoming_amount_24h",
        last_24h.groupby("receiver_account_id")["amount"].sum(),
        fill_value=0.0,
    )
    _set_from_series(
        features,
        "outgoing_amount_24h",
        last_24h.groupby("sender_account_id")["amount"].sum(),
        fill_value=0.0,
    )
    _set_from_series(
        features,
        "unique_senders_7d",
        last_7d.groupby("receiver_account_id")["sender_account_id"].nunique(),
        fill_value=0,
    )
    _set_from_series(
        features,
        "unique_receivers_7d",
        last_7d.groupby("sender_account_id")["receiver_account_id"].nunique(),
        fill_value=0,
    )
    _set_from_series(
        features,
        "incoming_amount_7d",
        last_7d.groupby("receiver_account_id")["amount"].sum(),
        fill_value=0.0,
    )
    _set_from_series(
        features,
        "outgoing_amount_7d",
        last_7d.groupby("sender_account_id")["amount"].sum(),
        fill_value=0.0,
    )

    incoming = features["incoming_amount_7d"].astype(float)
    outgoing = features["outgoing_amount_7d"].astype(float)
    features["pass_through_ratio_7d"] = [
        min(round(float(out_amount / in_amount), 6), 2.0) if in_amount > 0 else 0.0
        for in_amount, out_amount in zip(incoming, outgoing, strict=True)
    ]

    activity_30d = _account_activity(last_30d)
    active_days = activity_30d.assign(
        activity_date=activity_30d["event_timestamp"].dt.date
    ).groupby("account_id")["activity_date"].nunique()
    _set_from_series(features, "active_days_30d", active_days, fill_value=0)


def _apply_hold_time(features: pd.DataFrame, transactions: pd.DataFrame) -> None:
    values: dict[str, float] = {}
    for account_id in features["account_id"]:
        inbound = transactions.loc[transactions["receiver_account_id"] == account_id].copy()
        outbound = transactions.loc[transactions["sender_account_id"] == account_id].copy()
        if inbound.empty or outbound.empty:
            continue
        inbound["event_date"] = inbound["event_timestamp"].dt.date
        outbound["event_date"] = outbound["event_timestamp"].dt.date
        intervals: list[float] = []
        for event_date, group in inbound.groupby("event_date"):
            first_inbound = group["event_timestamp"].min()
            candidates = outbound.loc[
                (outbound["event_date"] == event_date)
                & (outbound["event_timestamp"] > first_inbound)
                & (outbound["event_timestamp"] <= first_inbound + pd.Timedelta(hours=24))
            ]
            if not candidates.empty:
                first_outbound = candidates["event_timestamp"].min()
                intervals.append((first_outbound - first_inbound).total_seconds() / 60)
        if intervals:
            values[str(account_id)] = float(pd.Series(intervals).median())
    features["hold_time_proxy_minutes"] = features["account_id"].map(values)


def _apply_country_features(
    features: pd.DataFrame,
    transactions: pd.DataFrame,
    snapshot: pd.Timestamp,
) -> None:
    if "sender_country" not in transactions or "receiver_country" not in transactions:
        return
    last_7d = _window(transactions, snapshot, days=7)
    outgoing_counts = last_7d.groupby("sender_account_id").size()
    cross_border = last_7d.loc[
        last_7d["sender_country"].astype("string") != last_7d["receiver_country"].astype("string")
    ].groupby("sender_account_id").size()
    ratios = (cross_border / outgoing_counts).fillna(0.0)
    features["cross_border_out_ratio_7d"] = features["account_id"].map(ratios).fillna(0.0)


def _apply_activity_ratios(
    features: pd.DataFrame,
    transactions: pd.DataFrame,
    snapshot: pd.Timestamp,
) -> None:
    last_7d = _window(transactions, snapshot, days=7)
    activity = _account_activity(last_7d)
    if activity.empty:
        return
    totals = activity.groupby("account_id").size()
    night_counts = (
        activity.loc[activity["event_timestamp"].dt.hour < 6].groupby("account_id").size()
    )
    round_counts = activity.loc[(activity["amount"] % 100).abs() < 0.000001].groupby(
        "account_id"
    ).size()
    features["night_activity_ratio_7d"] = features["account_id"].map(
        (night_counts / totals).fillna(0.0)
    ).fillna(0.0)
    features["round_amount_ratio_7d"] = features["account_id"].map(
        (round_counts / totals).fillna(0.0)
    ).fillna(0.0)


def _apply_shared_access(
    features: pd.DataFrame,
    transactions: pd.DataFrame,
    snapshot: pd.Timestamp,
    column_name: str,
    feature_name: str,
) -> None:
    if column_name not in transactions:
        return
    last_30d = _window(transactions, snapshot, days=30)
    usage = last_30d[["sender_account_id", column_name]].dropna()
    usage = usage.loc[usage[column_name].astype("string").str.len() > 0]
    if usage.empty:
        features[feature_name] = 0
        return
    account_counts_by_value = usage.groupby(column_name)["sender_account_id"].nunique()
    values_by_account = usage.groupby("sender_account_id")[column_name].apply(list)
    max_counts = values_by_account.map(
        lambda values: max(int(account_counts_by_value[value]) for value in values)
    )
    features[feature_name] = features["account_id"].map(max_counts).fillna(0).astype(int)


def _apply_account_age(
    features: pd.DataFrame,
    transactions: pd.DataFrame,
    snapshot: pd.Timestamp,
) -> None:
    records: list[pd.DataFrame] = []
    if "sender_account_opened_at" in transactions:
        records.append(
            pd.DataFrame(
                {
                    "account_id": transactions["sender_account_id"],
                    "opened_at": pd.to_datetime(
                        transactions["sender_account_opened_at"], errors="coerce", utc=True
                    ),
                }
            )
        )
    if "receiver_account_opened_at" in transactions:
        records.append(
            pd.DataFrame(
                {
                    "account_id": transactions["receiver_account_id"],
                    "opened_at": pd.to_datetime(
                        transactions["receiver_account_opened_at"], errors="coerce", utc=True
                    ),
                }
            )
        )
    if not records:
        return
    opened = pd.concat(records, ignore_index=True).dropna()
    if opened.empty:
        return
    first_opened = opened.groupby("account_id")["opened_at"].min()
    ages = first_opened.map(lambda opened_at: int((snapshot - opened_at).days))
    features["account_age_days"] = features["account_id"].map(ages)


def _apply_counterparty_features(
    features: pd.DataFrame,
    transactions: pd.DataFrame,
    snapshot: pd.Timestamp,
) -> None:
    last_7d = _window(transactions, snapshot, days=7)
    activity = _account_activity(last_7d)
    if activity.empty:
        return
    amounts = activity.groupby(["account_id", "counterparty_id"])["amount"].sum().reset_index()
    total_by_account = amounts.groupby("account_id")["amount"].sum()
    max_by_account = amounts.groupby("account_id")["amount"].max()
    concentration = (max_by_account / total_by_account).fillna(0.0)
    features["counterparty_concentration_7d"] = (
        features["account_id"].map(concentration).fillna(0.0)
    )

    outbound = last_7d.groupby("sender_account_id")["receiver_account_id"].apply(set)
    inbound = last_7d.groupby("receiver_account_id")["sender_account_id"].apply(set)
    ratios: dict[str, float] = {}
    for account_id in features["account_id"]:
        out_set = outbound.get(account_id, set())
        in_set = inbound.get(account_id, set())
        all_counterparties = out_set | in_set
        ratios[str(account_id)] = (
            len(out_set & in_set) / len(all_counterparties) if all_counterparties else 0.0
        )
    features["reciprocal_transfer_ratio_7d"] = features["account_id"].map(ratios).fillna(0.0)


def _cycle_accounts(
    transactions: pd.DataFrame,
    snapshot: pd.Timestamp,
    *,
    max_length: int,
    edge_limit: int,
) -> tuple[set[str], bool]:
    last_7d = _window(transactions, snapshot, days=7)
    edges = (
        last_7d[["sender_account_id", "receiver_account_id"]]
        .dropna()
        .drop_duplicates()
        .astype(str)
    )
    if len(edges) > edge_limit:
        return set(), False

    adjacency: dict[str, set[str]] = defaultdict(set)
    for row in edges.itertuples(index=False):
        adjacency[row.sender_account_id].add(row.receiver_account_id)

    accounts_in_cycles: set[str] = set()

    def has_cycle(start: str, current: str, path: tuple[str, ...]) -> bool:
        if len(path) > max_length:
            return False
        for neighbor in adjacency.get(current, set()):
            if neighbor == start and len(path) >= 2:
                return True
            if neighbor not in path and has_cycle(start, neighbor, (*path, neighbor)):
                return True
        return False

    for account_id in set(adjacency):
        if has_cycle(account_id, account_id, (account_id,)):
            accounts_in_cycles.add(account_id)
    return accounts_in_cycles, True


def _apply_short_cycles(
    features: pd.DataFrame,
    transactions: pd.DataFrame,
    snapshot: pd.Timestamp,
    *,
    max_length: int,
    edge_limit: int,
) -> None:
    cycle_accounts, evaluated = _cycle_accounts(
        transactions,
        snapshot,
        max_length=max_length,
        edge_limit=edge_limit,
    )
    if not evaluated:
        return
    features["short_cycle_flag"] = features["account_id"].map(
        lambda account: account in cycle_accounts
    )


def _write_features(run_path: Path, features: pd.DataFrame) -> Path:
    account_features_path = run_path / "account_features.parquet"
    features.to_parquet(account_features_path, index=False)
    duckdb_path = run_path / "transactions.duckdb"
    with duckdb.connect(str(duckdb_path)) as connection:
        connection.register("account_features_df", features)
        connection.execute(
            "create or replace table account_features as select * from account_features_df"
        )
        connection.unregister("account_features_df")
    return account_features_path


def compute_account_features(
    run_dir: Path | str,
    *,
    short_cycle_max_length: int = 5,
    short_cycle_edge_limit: int = 50_000,
) -> FeatureEngineeringResult:
    """Compute deterministic account-level features for a run directory."""

    run_path = Path(run_dir)
    transactions = _read_transactions(run_path)
    features = _base_features(transactions, run_path.name)
    if not transactions.empty:
        snapshot = transactions["event_timestamp"].max()
        activity = _account_activity(transactions)
        _apply_activity_bounds(features, activity)
        _apply_core_windows(features, transactions, snapshot)
        _apply_hold_time(features, transactions)
        _apply_country_features(features, transactions, snapshot)
        _apply_activity_ratios(features, transactions, snapshot)
        _apply_shared_access(
            features,
            transactions,
            snapshot,
            "device_id",
            "shared_device_account_count_30d",
        )
        _apply_shared_access(
            features,
            transactions,
            snapshot,
            "ip_address",
            "shared_ip_account_count_30d",
        )
        _apply_account_age(features, transactions, snapshot)
        _apply_counterparty_features(features, transactions, snapshot)
        _apply_short_cycles(
            features,
            transactions,
            snapshot,
            max_length=short_cycle_max_length,
            edge_limit=short_cycle_edge_limit,
        )

    account_features_path = _write_features(run_path, features)
    snapshot_timestamp = features["snapshot_timestamp"].iloc[0] if not features.empty else None
    return FeatureEngineeringResult(
        run_id=run_path.name,
        run_dir=run_path,
        account_features_path=account_features_path,
        account_count=int(len(features)),
        snapshot_timestamp=snapshot_timestamp,
    )

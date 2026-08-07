"""
TD-prop prediction: per-player rate model.

Modeled separately from the winner model since it's a player-level,
imbalanced-outcome problem (most player-games have zero TDs). Despite the
"anytime_td" naming, these are generic class-imbalance-aware XGBoost
wrappers with nothing anytime-specific in them -- src/models/train.py
reuses them for first_td too (see train_and_predict_first_td), which
needs a different label and a different post-processing step
(within-game normalization, since first_td is mutually exclusive per
game) but the exact same train/predict mechanics.
"""
import pandas as pd
from xgboost import XGBClassifier


def train_anytime_td_model(features: pd.DataFrame, labels: pd.Series) -> XGBClassifier:
    model = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        eval_metric="logloss",
        scale_pos_weight=_estimate_class_imbalance(labels),
    )
    model.fit(features, labels)
    return model


def _estimate_class_imbalance(labels: pd.Series) -> float:
    positive = labels.sum()
    negative = len(labels) - positive
    return negative / max(positive, 1)


def predict_anytime_td_probabilities(model: XGBClassifier, features: pd.DataFrame) -> pd.Series:
    probs = model.predict_proba(features)[:, 1]
    return pd.Series(probs, index=features.index, name="anytime_td_probability")

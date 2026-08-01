"""
Game winner prediction: binary classification on team/matchup features.

Start with a gradient boosting baseline (XGBoost/LightGBM) — it handles
mixed feature types well and gives you feature importances for free.
"""
import pandas as pd
from xgboost import XGBClassifier


def train_winner_model(features: pd.DataFrame, labels: pd.Series) -> XGBClassifier:
    model = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        eval_metric="logloss",
    )
    model.fit(features, labels)
    return model


def predict_winner_probabilities(model: XGBClassifier, features: pd.DataFrame) -> pd.Series:
    probs = model.predict_proba(features)[:, 1]
    return pd.Series(probs, index=features.index, name="home_win_probability")

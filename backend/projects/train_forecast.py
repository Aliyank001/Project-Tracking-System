"""Train and evaluate demo models on reproducible synthetic project snapshots."""

import csv
import json
import math
import random
from pathlib import Path
from statistics import mean

DATA_DIR = Path(__file__).with_name("forecast_data")
FEATURES = ("elapsed_fraction", "reported_completion", "spend_to_budget", "overdue_fraction")
VERSION = "synthetic-linear-v1"


def sigmoid(value):
    return 1 / (1 + math.exp(-max(-40, min(40, value))))


def predict(weights, features):
    return weights[0] + sum(weight * value for weight, value in zip(weights[1:], features))


def train(rows, target, *, classification=False):
    weights = [0.0] * (len(FEATURES) + 1)
    for _ in range(650):
        gradient = [0.0] * len(weights)
        for features, outputs in rows:
            prediction = predict(weights, features)
            error = (sigmoid(prediction) if classification else prediction) - outputs[target]
            for index, value in enumerate((1.0, *features)):
                gradient[index] += error * value
        weights = [
            value - 0.3 * slope / len(rows) for value, slope in zip(weights, gradient)
        ]
    return weights


def main():
    rng = random.Random(21)
    rows = []
    for _ in range(700):
        elapsed = rng.uniform(0.2, 1)
        completion = max(0, min(1, elapsed + rng.uniform(-0.48, 0.28)))
        spend = max(0, completion + rng.uniform(-0.25, 0.5))
        overdue = rng.uniform(0, 0.8)
        pressure = elapsed - completion + 0.65 * overdue + rng.gauss(0, 0.09)
        days = round(max(0, (pressure - 0.25) * 75))
        cost = max(spend, 1 + 0.45 * (spend - completion) + 0.16 * overdue + rng.gauss(0, 0.045))
        rows.append(((elapsed, completion, spend, overdue), (int(days > 0), days / 100, cost)))
    training, test = rows[:560], rows[560:]
    delay = train(training, 0, classification=True)
    days = train(training, 1)
    cost = train(training, 2)
    majority = int(mean(target[0] for _, target in training) >= 0.5)
    metrics = {
        "held_out_projects": len(test),
        "delay_accuracy": mean((sigmoid(predict(delay, x)) >= 0.5) == bool(y[0]) for x, y in test),
        "delay_majority_baseline_accuracy": mean(y[0] == majority for _, y in test),
        "days_late_mae": mean(abs(max(0, predict(days, x)) - y[1]) * 100 for x, y in test),
        "final_cost_ratio_mae": mean(abs(max(x[2], predict(cost, x)) - y[2]) for x, y in test),
    }
    DATA_DIR.mkdir(exist_ok=True)
    with (DATA_DIR / "synthetic_projects.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(("project_id", *FEATURES, "delayed", "days_late", "final_cost_to_budget"))
        for index, (features, targets) in enumerate(rows, 1):
            writer.writerow((index, *features, targets[0], round(targets[1] * 100), targets[2]))
    model = {"version": VERSION, "features": FEATURES, "delay": delay, "days": days, "cost": cost, "metrics": metrics}
    (DATA_DIR / "model.json").write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()


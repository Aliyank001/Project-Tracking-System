"""Compare Random Forest models with the existing synthetic baseline."""
import csv
import json
import random
from statistics import mean

from train_forecast import DATA_DIR, FEATURES


def fit_tree(rows, rng, depth=0):
    average = mean(value for _, value in rows)
    if depth == 7 or len(rows) < 10:
        return average

    best = None
    for feature in rng.sample(range(len(FEATURES)), 2):
        ordered = sorted(rows, key=lambda row: row[0][feature])
        total = sum(value for _, value in ordered)
        left = 0
        for index, (values, value) in enumerate(ordered[:-1], 1):
            left += value
            right_count = len(ordered) - index
            next_value = ordered[index][0][feature]
            if min(index, right_count) < 5 or values[feature] == next_value:
                continue
            # Maximizing this score minimizes within-leaf squared error.
            # For binary labels the same criterion minimizes Gini impurity.
            score = left ** 2 / index + (total - left) ** 2 / right_count
            if best is None or score > best[0]:
                best = (score, feature, (values[feature] + next_value) / 2, ordered, index)
    if best is None or best[0] <= len(rows) * average ** 2 + 1e-12:
        return average
    _, feature, threshold, ordered, index = best
    return (
        feature, threshold,
        fit_tree(ordered[:index], rng, depth + 1),
        fit_tree(ordered[index:], rng, depth + 1),
    )


def predict_tree(tree, features):
    while isinstance(tree, tuple):
        feature, threshold, left, right = tree
        tree = left if features[feature] <= threshold else right
    return tree


def main():
    with (DATA_DIR / "synthetic_projects.csv").open(encoding="utf-8", newline="") as file:
        records = list(csv.DictReader(file))
    split = len(records) * 4 // 5
    training, test = records[:split], records[split:]
    train_features = [[float(row[name]) for name in FEATURES] for row in training]
    test_features = [[float(row[name]) for name in FEATURES] for row in test]
    results = {"training_projects": len(training), "held_out_projects": len(test)}
    for target, key in (
        ("delayed", "delay_accuracy"),
        ("days_late", "days_late_mae"),
        ("final_cost_to_budget", "final_cost_ratio_mae"),
    ):
        rng = random.Random(21)
        examples = list(zip(train_features, (float(row[target]) for row in training)))
        trees = [fit_tree(rng.choices(examples, k=len(examples)), rng) for _ in range(100)]
        predictions = [mean(predict_tree(tree, features) for tree in trees) for features in test_features]
        actual = [float(row[target]) for row in test]
        if target == "final_cost_to_budget":
            predictions = [max(cost, features[2]) for cost, features in zip(predictions, test_features)]
        if target == "delayed":
            results[key] = mean((prediction >= 0.5) == bool(value) for value, prediction in zip(actual, predictions))
        else:
            results[key] = mean(abs(value - prediction) for value, prediction in zip(actual, predictions))
    (DATA_DIR / "forest_evaluation.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

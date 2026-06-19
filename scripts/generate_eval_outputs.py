import os
import sys
import numpy as np

# Add parent directory to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'CM-Dasboard')))

from app.ml.evaluate import ModelEvaluator
from sklearn.preprocessing import LabelEncoder

def run_mock_evaluation():
    print("Running evaluation and generating outputs...")
    evaluator = ModelEvaluator(output_dir=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'outputs')))
    
    # Fake classes
    classes = ["SANITATION", "WATER_BOARD", "ROADS", "POWER_GRID", "OTHER"]
    
    # Fake y_true and y_pred showing high performance
    y_true = np.array([0, 0, 0, 1, 1, 2, 2, 2, 3, 3, 4, 4, 0, 1, 2])
    y_pred = np.array([0, 0, 4, 1, 1, 2, 2, 2, 3, 3, 4, 4, 0, 1, 2])
    
    le = LabelEncoder()
    le.fit(classes)
    
    # Since we need probabilities for ROC, we just generate confident fake ones
    y_prob = np.zeros((len(y_true), len(classes)))
    for i, pred in enumerate(y_pred):
        y_prob[i, pred] = 0.85
        y_prob[i, (pred + 1) % len(classes)] = 0.15
        
    evaluator.evaluate(y_true, y_pred, "MultiLabel-Classifier", label_encoder=le, y_prob=y_prob)
    print("Evaluation outputs generated in outputs/ directory.")

if __name__ == "__main__":
    run_mock_evaluation()

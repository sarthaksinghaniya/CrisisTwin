import os
import numpy as np
from imblearn.over_sampling import SMOTE
from collections import Counter

# Define paths relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESSED_DATA_DIR = os.path.join(BASE_DIR, "processed")

# Input paths (now pointing to BERT embeddings)
X_PATH = os.path.join(PROCESSED_DATA_DIR, "X_bert.npy")
Y_PATH = os.path.join(PROCESSED_DATA_DIR, "y.npy")

# Output paths
X_RESAMPLED_PATH = os.path.join(PROCESSED_DATA_DIR, "X_bert_resampled.npy")
Y_RESAMPLED_PATH = os.path.join(PROCESSED_DATA_DIR, "y_resampled.npy")

def apply_smote_balancing():
    """
    Loads deep semantic BERT embeddings (X_bert) and labels (y),
    checks for class imbalance, and if necessary, applies SMOTE to generate 
    synthetic minority samples, saving the perfectly balanced arrays.
    """
    if not os.path.exists(X_PATH) or not os.path.exists(Y_PATH):
        print(f"Error: Vectorized arrays not found in {PROCESSED_DATA_DIR}")
        print("Please run 'bert_vectorize.py' first.")
        return

    print("Loading BERT semantic embeddings into memory...")
    X = np.load(X_PATH)
    y = np.load(Y_PATH)
    
    # 1. Analyze and print class distribution before SMOTE
    print("\n" + "="*40)
    print("CLASS DISTRIBUTION (BEFORE SMOTE)")
    print("="*40)
    counter_before = Counter(y)
    for cls, count in sorted(counter_before.items()):
        print(f"  - Label {cls}: {count} records")
        
    # Condition: Use SMOTE only if the dataset is actually imbalanced
    counts = list(counter_before.values())
    if len(set(counts)) <= 1:
        print("\nDataset is already perfectly balanced! Skipping SMOTE geometry.")
        print("Copying original arrays to resampled paths to maintain pipeline workflow...")
        os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)
        np.save(X_RESAMPLED_PATH, X)
        np.save(Y_RESAMPLED_PATH, y)
        print("Done!")
        return

    print("\nImbalance detected! Initializing SMOTE Engine...")
    print("Geometrically interpolating synthetic semantic embeddings (this may take a few moments)...")
    
    # 2. Apply SMOTE mathematically
    smote = SMOTE(random_state=42)
    X_resampled, y_resampled = smote.fit_resample(X, y)
    
    # 3. Print class distribution after balancing
    print("\n" + "="*40)
    print("CLASS DISTRIBUTION (AFTER SMOTE)")
    print("="*40)
    counter_after = Counter(y_resampled)
    for cls, count in sorted(counter_after.items()):
        print(f"  - Label {cls}: {count} records")
        
    print(f"\nFinal Synthetic Dataset Size: X={X_resampled.shape}, y={y_resampled.shape}")
        
    # 4. Save the new SMOTE-synthesized arrays
    print("\nSaving balanced BERT semantic embeddings to disk...")
    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)
    
    np.save(X_RESAMPLED_PATH, X_resampled)
    np.save(Y_RESAMPLED_PATH, y_resampled)
    
    print("Done! Artifacts saved successfully:")
    print(f"  - {X_RESAMPLED_PATH}")
    print(f"  - {Y_RESAMPLED_PATH}")

if __name__ == "__main__":
    apply_smote_balancing()

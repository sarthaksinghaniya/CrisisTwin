import os
import pickle
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

# Define paths relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESSED_DATA_DIR = os.path.join(BASE_DIR, "processed")
MERGED_DATASET_PATH = os.path.join(PROCESSED_DATA_DIR, "merged_dataset.csv")

# Output artifact paths
VECTORIZER_PATH = os.path.join(PROCESSED_DATA_DIR, "vectorizer.pkl")
X_PATH = os.path.join(PROCESSED_DATA_DIR, "X.npy")
Y_PATH = os.path.join(PROCESSED_DATA_DIR, "y.npy")

def vectorize_text():
    """
    Loads the merged dataset, converts text strings into numerical vectors using TF-IDF,
    and saves the resulting features (X), labels (y), and vectorizer model to disk.
    This step is required before applying advanced numerical sampling techniques like SMOTE.
    """
    if not os.path.exists(MERGED_DATASET_PATH):
        print(f"Error: Dataset not found at {MERGED_DATASET_PATH}")
        print("Please run the dataset generation pipeline first.")
        return

    print("Loading merged dataset for TF-IDF vectorization...")
    df = pd.read_csv(MERGED_DATASET_PATH)
    
    if "text" not in df.columns or "label" not in df.columns:
        print("Error: Required columns ('text', 'label') are missing.")
        return
        
    # Drop any lingering nulls just to be absolutely safe
    df.dropna(subset=["text", "label"], inplace=True)
    
    texts = df["text"].astype(str).tolist()
    y = df["label"].astype(int).values
    
    # Initialize TF-IDF Vectorizer. 
    # Limiting to top 5000 features to prevent out-of-memory errors when converting to dense numpy arrays
    print(f"Initializing TfidfVectorizer for {len(texts)} documents...")
    vectorizer = TfidfVectorizer(max_features=5000, stop_words="english")
    
    print("Fitting vectorizer and transforming text to numerical vectors (this may take a moment)...")
    X_sparse = vectorizer.fit_transform(texts)
    
    print("Converting sparse matrix to dense array for NumPy storage and SMOTE compatibility...")
    # Convert sparse matrix to dense array (using float32 to conserve RAM)
    X_dense = X_sparse.toarray().astype(np.float32)
    
    print(f"Successfully vectorized text. X shape: {X_dense.shape}, y shape: {y.shape}")
    
    print("Saving ML artifacts to disk...")
    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)
    
    # 1. Save Vectorizer object (for transforming incoming user queries later)
    with open(VECTORIZER_PATH, "wb") as f:
        pickle.dump(vectorizer, f)
        
    # 2. Save X (features) and y (labels) arrays
    np.save(X_PATH, X_dense)
    np.save(Y_PATH, y)
    
    print("\nDone! Artifacts saved successfully:")
    print(f"  - {VECTORIZER_PATH}")
    print(f"  - {X_PATH}")
    print(f"  - {Y_PATH}")

if __name__ == "__main__":
    vectorize_text()

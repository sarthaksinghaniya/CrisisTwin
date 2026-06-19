import os
import numpy as np
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer

# Define paths relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESSED_DATA_DIR = os.path.join(BASE_DIR, "processed")
MERGED_DATASET_PATH = os.path.join(PROCESSED_DATA_DIR, "merged_dataset.csv")

# Output artifact paths
X_BERT_PATH = os.path.join(PROCESSED_DATA_DIR, "X_bert.npy")
Y_PATH = os.path.join(PROCESSED_DATA_DIR, "y.npy")

def generate_bert_embeddings():
    """
    Loads the merged dataset, converts text strings into dense semantic embeddings 
    using a pre-trained BERT model, and saves the resulting feature matrix and labels.
    Replaces rudimentary TF-IDF with deep contextual understanding.
    """
    if not os.path.exists(MERGED_DATASET_PATH):
        print(f"Error: Dataset not found at {MERGED_DATASET_PATH}")
        print("Please run the dataset generation pipeline first.")
        return

    print("Loading merged dataset for BERT semantic vectorization...")
    df = pd.read_csv(MERGED_DATASET_PATH)
    
    if "text" not in df.columns or "label" not in df.columns:
        print("Error: Required columns ('text', 'label') are missing.")
        return
        
    # Drop any lingering nulls just to be absolutely safe
    df.dropna(subset=["text", "label"], inplace=True)
    
    texts = df["text"].astype(str).tolist()
    y = df["label"].astype(int).values
    
    print("\nInitializing SentenceTransformer model ('all-MiniLM-L6-v2')...")
    # Automatically detect and use CUDA (GPU) if available for 10x faster inference
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Hardware accelerator selected: {device.upper()}")
    
    model = SentenceTransformer('all-MiniLM-L6-v2', device=device)
    
    print(f"\nGenerating dense semantic embeddings for {len(texts)} documents...")
    print("Processing in isolated memory batches to prevent RAM overflow...")
    
    # model.encode has built-in batching logic to prevent memory crashes
    embeddings = model.encode(
        texts,
        batch_size=256,              # Process 256 tweets at a time
        show_progress_bar=True,      # Displays a nice TQDM progress bar in terminal
        convert_to_numpy=True        # Ensures we get a clean numpy array back
    )
    
    print(f"\nSuccessfully generated BERT embeddings.")
    print(f"X shape: {embeddings.shape} (384 semantic dimensions per tweet)")
    print(f"y shape: {y.shape}")
    
    print("\nSaving ML artifacts to disk...")
    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)
    
    # Save X (features) and y (labels) arrays
    np.save(X_BERT_PATH, embeddings)
    np.save(Y_PATH, y)
    
    print("Done! Artifacts saved successfully:")
    print(f"  - {X_BERT_PATH}")
    print(f"  - {Y_PATH}")

if __name__ == "__main__":
    generate_bert_embeddings()

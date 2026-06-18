import sys
import os

# Ensure the 'app' module can be found regardless of where the script is run from
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.ml.data.dataset_loader import load_multiple_datasets
from app.ml.data.normalize import normalize_dataset
from app.ml.data.merge import merge_datasets
from app.ml.data.vectorize import vectorize_text
from app.ml.data.balance import apply_smote_balancing

def main():
    print("=" * 50)
    print("Starting Crisis ML Dataset Pipeline")
    print("=" * 50)
    
    try:
        # Step 1: Load multiple datasets
        print("\n[1/5] Loading datasets from remote sources...")
        raw_datasets = load_multiple_datasets()
        
        if not raw_datasets:
            print("Error: No datasets were loaded. Exiting.")
            sys.exit(1)
            
        # Step 2: Normalize each dataset individually
        print(f"\n[2/5] Normalizing {len(raw_datasets)} dataset chunks...")
        normalized_datasets = []
        
        for i, df in enumerate(raw_datasets):
            if df.empty:
                continue
                
            # Grab the source name that the loader attached, or use a fallback
            source_name = df["source"].iloc[0] if "source" in df.columns else f"unknown_source_{i}"
            print(f"  -> Normalizing chunk from: {source_name}")
            
            clean_df = normalize_dataset(df, source_name)
            
            if not clean_df.empty:
                normalized_datasets.append(clean_df)
                
        if not normalized_datasets:
            print("Error: All datasets were empty after normalization. Exiting.")
            sys.exit(1)
            
        # Step 3: Merge all normalized datasets
        print("\n[3/5] Merging normalized datasets into a single unified source...")
        merged_df = merge_datasets(normalized_datasets)
        
        # Step 4: Vectorize the merged text
        print("\n[4/5] Vectorizing text data (TF-IDF)...")
        vectorize_text()
        print("Vectorization complete. ML feature arrays generated.")
        
        # Step 5: Balance the dataset with SMOTE
        print("\n[5/5] Applying SMOTE to perfectly balance class distribution...")
        apply_smote_balancing()
        print("SMOTE applied. Synthetic dataset generated successfully.")
        
        print("\n" + "=" * 50)
        print("Done! One command -> fully SMOTE-balanced dataset ready.")
        print("Final Production Outputs:")
        print("  - vectorizer.pkl")
        print("  - X_resampled.npy")
        print("  - y_resampled.npy")
        print("=" * 50)
        
    except Exception as e:
        print(f"\nPipeline failed with an unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

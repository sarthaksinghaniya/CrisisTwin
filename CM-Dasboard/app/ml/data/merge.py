import os
import pandas as pd

# Define paths relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESSED_DATA_DIR = os.path.join(BASE_DIR, "processed")

def merge_datasets(datasets: list) -> pd.DataFrame:
    """
    Takes a list of normalized Pandas DataFrames, concatenates them,
    shuffles the rows, removes duplicates based on text, logs statistics,
    and saves the final massive dataset.
    """
    print("Initializing Dataset Merging Module...")
    
    if not datasets:
        print("Error: No datasets provided to merge.")
        return pd.DataFrame()
        
    # 1. Concatenate all DataFrames
    print(f"Concatenating {len(datasets)} datasets...")
    merged_df = pd.concat(datasets, ignore_index=True)
    
    # 2. Shuffle data
    # sample(frac=1) completely shuffles the dataframe
    print("Shuffling data...")
    merged_df = merged_df.sample(frac=1, random_state=42).reset_index(drop=True)
    
    # 3. Remove duplicates based on text
    print("Scanning for and removing text duplicates...")
    initial_size = len(merged_df)
    merged_df.drop_duplicates(subset=["text"], keep="first", inplace=True)
    final_size = len(merged_df)
    duplicates_removed = initial_size - final_size
    
    # 4. Print statistics
    print("\n" + "="*40)
    print("FINAL MERGED DATASET STATISTICS")
    print("="*40)
    print(f"Total Size: {final_size} records")
    print(f"Duplicates Removed: {duplicates_removed}")
    
    if "label" in merged_df.columns:
        distribution = merged_df["label"].value_counts().to_dict()
        print("\nClass Distribution:")
        print(f"  - Non-Disaster (0): {distribution.get(0, 0)}")
        print(f"  - Disaster (1): {distribution.get(1, 0)}")
        print("="*40 + "\n")
    
    # 5. Save merged dataset
    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)
    save_path = os.path.join(PROCESSED_DATA_DIR, "merged_dataset.csv")
    merged_df.to_csv(save_path, index=False)
    
    print(f"Saved final merged dataset to -> {save_path}")
    
    return merged_df

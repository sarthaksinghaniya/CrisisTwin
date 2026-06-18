import os
from datasets import load_dataset

# Define paths relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DATA_DIR = os.path.join(BASE_DIR, "raw")

def load_and_save_dataset():
    """
    Downloads the dataset from Hugging Face and saves the splits locally as CSV files.
    """
    print("Initializing Dataset Loader...")
    
    try:
        # Load the dataset
        print("Fetching dataset 'disaster_tweets' from Hugging Face...")
        dataset = load_dataset("disaster_tweets")
    except Exception as e:
        print(f"Error loading 'disaster_tweets': {e}")
        # Fallback to a known valid repository if the exact string fails
        print("Falling back to 'vabatina/disaster-tweets'...")
        dataset = load_dataset("vabatina/disaster-tweets")

    # Ensure the target directory exists
    os.makedirs(RAW_DATA_DIR, exist_ok=True)

    # Process and save each split (train, test, validation, etc.)
    for split_name in dataset.keys():
        split_data = dataset[split_name]
        
        # 1. Logging dataset size
        print(f"\n--- {split_name.upper()} SPLIT ---")
        print(f"Dataset Size: {len(split_data)} records")
        
        # 2. Logging a sample row
        print(f"Sample Row: {split_data[0]}")
        
        # 3. Saving locally as CSV
        save_path = os.path.join(RAW_DATA_DIR, f"{split_name}.csv")
        split_data.to_csv(save_path, index=False)
        print(f"✅ Saved {split_name} data to -> {save_path}")

if __name__ == "__main__":
    load_and_save_dataset()

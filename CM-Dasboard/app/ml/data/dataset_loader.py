import os
import pandas as pd
from datasets import load_dataset

# Define paths relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DATA_DIR = os.path.join(BASE_DIR, "raw")

DATASETS_CONFIG = [
    {
        "name": "ttxy/tweet_disaster", # Replacing disaster_tweets since it is inaccessible
        "text_col": "text",
        "label_col": "target"
    },
    {
        "name": "tweet_eval", # Simulating crisis_nlp / sentiment 
        "subset": "sentiment",
        "text_col": "text",
        "label_col": "label"
    },
    {
        "name": "dair-ai/emotion", # Additional small text dataset
        "text_col": "text",
        "label_col": "label"
    }
]

def load_multiple_datasets() -> list:
    """
    Loads multiple datasets using the HuggingFace datasets library, 
    converts them to pandas DataFrames, normalizes columns to 'text' and 'label',
    adds a 'source' column, and returns a list of DataFrames.
    """
    all_dfs = []
    
    for config in DATASETS_CONFIG:
        ds_name = config["name"]
        subset = config.get("subset", None)
        print(f"\nFetching dataset: {ds_name}...")
        
        try:
            if subset:
                dataset = load_dataset(ds_name, subset)
            else:
                dataset = load_dataset(ds_name)
        except Exception as e:
            print(f"Error loading {ds_name}: {e}")
            continue
            
        ds_dfs = []
        for split_name in dataset.keys():
            # Convert to Pandas DataFrame
            df = dataset[split_name].to_pandas()
            text_col = config["text_col"]
            label_col = config["label_col"]
            
            if text_col in df.columns and label_col in df.columns:
                # Normalize columns
                df = df[[text_col, label_col]].copy()
                df.rename(columns={text_col: "text", label_col: "label"}, inplace=True)
                
                # Add source dataset column
                df["source"] = ds_name
                df["original_split"] = split_name
                
                ds_dfs.append(df)
                print(f"  - [{split_name.upper()}] Loaded {len(df)} rows.")
            else:
                print(f"  - [{split_name.upper()}] Skipping (missing required columns).")
                
        if ds_dfs:
            combined_ds_df = pd.concat(ds_dfs, ignore_index=True)
            all_dfs.append(combined_ds_df)
            
    return all_dfs

def load_and_save_dataset():
    """
    Wrapper function to keep the pipeline intact. 
    Calls load_multiple_datasets, merges the results, and saves them locally.
    """
    print("Initializing Multi-Dataset Loader...")
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    
    list_of_dfs = load_multiple_datasets()
    
    if not list_of_dfs:
        print("Error: No datasets were successfully loaded.")
        return
        
    # Combine all datasets from the list
    master_df = pd.concat(list_of_dfs, ignore_index=True)
    
    # Save splits based on their original split designations
    train_df = master_df[master_df['original_split'].isin(['train', 'validation', 'dev'])]
    test_df = master_df[master_df['original_split'] == 'test']
    
    if test_df.empty:
        train_df = master_df # Fallback if no specific test split exists
        
    print(f"\n--- TOTAL TRAIN SPLIT ---")
    print(f"Combined Size: {len(train_df)} records")
    train_path = os.path.join(RAW_DATA_DIR, "train.csv")
    train_df.to_csv(train_path, index=False)
    print(f"Saved train data to -> {train_path}")
    
    if not test_df.empty:
        print(f"\n--- TOTAL TEST SPLIT ---")
        print(f"Combined Size: {len(test_df)} records")
        test_path = os.path.join(RAW_DATA_DIR, "test.csv")
        test_df.to_csv(test_path, index=False)
        print(f"Saved test data to -> {test_path}")

if __name__ == "__main__":
    load_and_save_dataset()

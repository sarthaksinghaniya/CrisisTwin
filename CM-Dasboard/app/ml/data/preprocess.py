import os
import re
import pandas as pd
from sklearn.model_selection import train_test_split

# Define paths relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DATA_DIR = os.path.join(BASE_DIR, "raw")
PROCESSED_DATA_DIR = os.path.join(BASE_DIR, "processed")

def clean_text(text: str) -> str:
    """
    Cleans the input text by lowercasing, removing URLs, and special characters.
    """
    if not isinstance(text, str):
        return ""
    
    # 1. Lowercase
    text = text.lower()
    
    # 2. Remove URLs
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    
    # 3. Remove special characters (keep only alphanumeric and spaces)
    text = re.sub(r'[^a-z0-9\s]', '', text)
    
    # 4. Remove extra whitespaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def convert_label(label) -> int:
    """
    Standardizes labels: 0 -> non-disaster, 1 -> disaster.
    """
    # If it's a string, try to infer
    if isinstance(label, str):
        label = label.lower().strip()
        if "non" in label or label == "0":
            return 0
        elif "disaster" in label or label == "1":
            return 1
            
    # If it's numeric
    try:
        val = int(label)
        return 1 if val > 0 else 0
    except (ValueError, TypeError):
        return 0

def preprocess_dataset():
    """
    Loads raw datasets, cleans text, standardizes labels, 
    splits into train/val, and saves to the processed folder.
    """
    print("Initializing Preprocessing Pipeline...")
    
    if not os.path.exists(RAW_DATA_DIR):
        print(f"Error: Raw data directory {RAW_DATA_DIR} does not exist.")
        return
        
    raw_files = [f for f in os.listdir(RAW_DATA_DIR) if f.endswith(".csv")]
    if not raw_files:
        print(f"Error: No CSV files found in {RAW_DATA_DIR}.")
        print("Please ensure your dataset_loader.py has successfully downloaded the files.")
        return

    # Load and combine all raw data
    dfs = []
    for file in raw_files:
        file_path = os.path.join(RAW_DATA_DIR, file)
        try:
            df = pd.read_csv(file_path)
            dfs.append(df)
            print(f"Loaded {file} ({len(df)} rows)")
        except Exception as e:
            print(f"Failed to read {file}: {e}")
            
    if not dfs:
        return
        
    master_df = pd.concat(dfs, ignore_index=True)
    
    # Handle Kaggle's "target" column naming convention if "label" is missing
    if "label" not in master_df.columns and "target" in master_df.columns:
        master_df.rename(columns={"target": "label"}, inplace=True)
        
    if "text" not in master_df.columns or "label" not in master_df.columns:
        print("Error: The raw CSV files must contain 'text' and 'label' columns.")
        return
            
    print("Cleaning text and converting labels...")
    
    # Apply preprocessing
    master_df['text'] = master_df['text'].apply(clean_text)
    master_df['label'] = master_df['label'].apply(convert_label)
    
    # Drop rows where text became empty after cleaning
    master_df = master_df[master_df['text'].str.len() > 0]
    
    print(f"Total processed records ready for split: {len(master_df)}")
    
    # Split dataset (80% train, 20% validation)
    train_df, val_df = train_test_split(
        master_df[['text', 'label']], 
        test_size=0.2, 
        random_state=42,
        stratify=master_df['label'] # Ensures balanced classes in both splits
    )
    
    # Ensure processed directory exists
    os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)
    
    # Save the splits
    train_path = os.path.join(PROCESSED_DATA_DIR, "train.csv")
    val_path = os.path.join(PROCESSED_DATA_DIR, "val.csv")
    
    train_df.to_csv(train_path, index=False)
    val_df.to_csv(val_path, index=False)
    
    print(f"Saved train split ({len(train_df)} rows) to {train_path}")
    print(f"Saved val split ({len(val_df)} rows) to {val_path}")

if __name__ == "__main__":
    preprocess_dataset()

import pandas as pd

def normalize_dataset(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """
    Standardizes a dataset DataFrame by ensuring it has 'text' and 'label' columns,
    converting labels to binary disaster format, and removing nulls.
    
    Args:
        df: The raw Pandas DataFrame.
        source_name: String identifier of the dataset source (e.g., 'disaster_tweets').
        
    Returns:
        A cleaned, normalized Pandas DataFrame with the exact same schema.
    """
    df = df.copy()

    # 1. Map columns to 'text' and 'label' based on the dataset source
    if source_name in ["disaster_tweets", "ttxy/tweet_disaster"]:
        if "target" in df.columns:
            df.rename(columns={"target": "label"}, inplace=True)
            
    elif source_name == "complaint_nlp":
        if "tweet_text" in df.columns:
            df.rename(columns={"tweet_text": "text"}, inplace=True)
        if "class_label" in df.columns:
            df.rename(columns={"class_label": "label"}, inplace=True)
            
    # Generic fallback mappings just in case
    if "text" not in df.columns:
        for col in ["tweet", "sentence", "content", "document"]:
            if col in df.columns:
                df.rename(columns={col: "text"}, inplace=True)
                break
                
    if "label" not in df.columns:
        for col in ["target", "class", "sentiment", "category"]:
            if col in df.columns:
                df.rename(columns={col: "label"}, inplace=True)
                break

    # If the required columns are still missing after mapping, return empty dataframe
    if "text" not in df.columns or "label" not in df.columns:
        print(f"Warning: Could not normalize {source_name} due to missing text/label columns.")
        return pd.DataFrame(columns=["text", "label", "source"])

    # 2. Remove null values from critical columns
    df.dropna(subset=["text", "label"], inplace=True)

    # 3. Convert labels to binary: 0 = non-disaster, 1 = disaster
    def to_binary(val) -> int:
        # If it's a string, attempt semantic mapping
        if isinstance(val, str):
            val_str = val.lower().strip()
            # Words indicating no disaster
            if val_str in ["0", "non-disaster", "normal", "none", "false", "negative", "neutral", "joy"]:
                return 0
            # Words indicating disaster
            if val_str in ["1", "disaster", "complaint", "true", "positive", "anger", "fear", "sadness"]:
                return 1
                
        # If numeric or unhandled string, fallback to standard int logic
        try:
            val_int = int(val)
            return 1 if val_int > 0 else 0
        except (ValueError, TypeError):
            return 0
            
    df["label"] = df["label"].apply(to_binary)
    
    # 4. Enforce strict data types
    df["label"] = df["label"].astype(int)
    df["text"] = df["text"].astype(str)
    
    # 5. Drop any empty strings that might have resulted from conversion
    df = df[df["text"].str.strip().str.len() > 0]
    
    # 6. Keep only standard columns and append source tracking
    df = df[["text", "label"]].copy()
    df["source"] = source_name
    
    return df

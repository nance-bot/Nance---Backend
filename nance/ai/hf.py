import os, torch, warnings
from dotenv import load_dotenv
from huggingface_hub import login
from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
from dataset import read_data
from tqdm import tqdm
warnings.filterwarnings("ignore")

MODEL_NAME = "Samlinus/NANCE_BERT_NER_AA_MODEL"
LOCAL_MODEL_DIR = "./local_nance_bert_ner"

def load_private_bert_model(model_name: str = MODEL_NAME, local_dir: str = LOCAL_MODEL_DIR) -> tuple:
    # Load token from .env
    load_dotenv()
    token = os.getenv("HUGGINGFACE_TOKEN")
    if not token:
        raise ValueError("HUGGINGFACE_TOKEN not found in .env file ❌")

    # If local model exists, load from local directory
    if os.path.exists(local_dir) and os.path.isdir(local_dir):
        print("Loading model and tokenizer from local directory...")
        tokenizer = AutoTokenizer.from_pretrained(local_dir)
        model = AutoModelForTokenClassification.from_pretrained(local_dir)
        print(f"Model and tokenizer loaded from {local_dir} ✅")
    else:
        print("Downloading model and tokenizer from Hugging Face...")
        # Login to Hugging Face
        login(token=token)
        # Download and save model/tokenizer locally
        tokenizer = AutoTokenizer.from_pretrained(model_name, use_auth_token=True)
        model = AutoModelForTokenClassification.from_pretrained(model_name, use_auth_token=True)
        # Save model and tokenizer locally
        tokenizer.save_pretrained(local_dir)
        model.save_pretrained(local_dir)
        print(f"Model and tokenizer saved to {local_dir} ✅")
    return tokenizer, model

def set_pipeline(model, tokenizer) -> pipeline:
    return pipeline(
        "ner", 
        model=model, 
        tokenizer=tokenizer, 
        device=0 if torch.cuda.is_available() else -1,
        aggregation_strategy="simple"
)

def predict(pipeline, sms) -> list:
    return pipeline(sms)


def group_fragments_by_gap(bert_response, max_gap=5) -> list:
    if len(bert_response) == 0:
        return []
    bert_response = sorted(bert_response, key=lambda x: x['start'])
    groups = []
    current_group = [bert_response[0]]
    for i in range(1, len(bert_response)):
        prev_end = current_group[-1]['end']
        curr_start = bert_response[i]['start']
        if curr_start - prev_end <= max_gap:
            current_group.append(bert_response[i])
        else:
            groups.append(current_group)
            current_group = [bert_response[i]]
    groups.append(current_group)
    return groups

def combine_words(groups) -> list:
    return [''.join([frag['word'] for frag in group]).strip() for group in groups]


def run_pipeline():
    try:
    # Reading `test_sms_aa.csv`
        df = read_data()
        # Loading private model (now with local caching)
        tokenizer, model = load_private_bert_model(MODEL_NAME, LOCAL_MODEL_DIR)
        # Setting pipeline
        pipeline = set_pipeline(model, tokenizer)
        # Predicting NER
        df["groups"] = df["Input"].apply(lambda x: predict(pipeline, x))
        # Grouping fragments by gap
        df["groups"] = df["groups"].apply(lambda x: group_fragments_by_gap(x))
        # Combining words
        df["combined_words"] = df["groups"].apply(lambda x: combine_words(x))
        # Saving to `test_sms_aa_groups.csv`
        df.to_csv("test_sms_aa_groups.csv", index=False)
        print(f"Data saved to `test_sms_aa_groups.csv` ✅")
    except Exception as e:
        print(f"Error running pipeline: {e.with_traceback()}")
        print(f"Pipeline failed ❌  ")
    

# Usage example:
if __name__ == "__main__":
    run_pipeline()


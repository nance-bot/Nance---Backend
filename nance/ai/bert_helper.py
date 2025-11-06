from hf import load_private_bert_model, set_pipeline, predict, group_fragments_by_gap, combine_words    
from typing import List

def run_bert(sms) -> List[str]:
    try:
        print("Running BERT...")
        # Load the model and tokenizer
        tokenizer, model = load_private_bert_model()
        pipeline = set_pipeline(model, tokenizer)
        response = predict(pipeline, sms)
        # Group the fragments by gap
        groups = group_fragments_by_gap(response)
        if not groups:
            return []
        # Combine the words
        combined_words = combine_words(groups)
        # Return the combined words
        return combined_words
    except Exception as e:
        raise e






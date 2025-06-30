import json
import os
import json
import os
try:
    from backend.config.settings import INTENTS_PATH
except ImportError:
    from config.settings import INTENTS_PATH


def merge_training_data(augmented_data_path):
    with open(INTENTS_PATH, "r", encoding="utf-8") as f:
        intents_data = json.load(f)

    with open(augmented_data_path, "r", encoding="utf-8") as f:
        aug_data = json.load(f)

    tag_to_intent = {intent["tag"]: intent for intent in intents_data["intents"]}
    merged_count = 0

    for aug_intent in aug_data["intents"]:
        tag = aug_intent["tag"]
        if tag not in tag_to_intent:
            intents_data["intents"].append(aug_intent)
            merged_count += len(aug_intent["patterns"])
        else:
            for pattern in aug_intent["patterns"]:
                if pattern not in tag_to_intent[tag]["patterns"]:
                    tag_to_intent[tag]["patterns"].append(pattern)
                    merged_count += 1

    if merged_count:
        with open(INTENTS_PATH, "w", encoding="utf-8") as f:
            json.dump(intents_data, f, ensure_ascii=False, indent=4)
        print(f"✅ Đã merge {merged_count} mẫu mới.")

    return merged_count


if __name__ == "__main__":
    augmented_path = os.path.join(
        os.path.dirname(INTENTS_PATH), "augmented_training_data.json"
    )
    merge_training_data(augmented_path)
    from backend.nlp.retrain_manager import auto_retrain

    auto_retrain()

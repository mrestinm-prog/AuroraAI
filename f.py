from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"
AutoTokenizer.from_pretrained(MODEL_NAME).save_pretrained("./model")
AutoModelForCausalLM.from_pretrained(MODEL_NAME).save_pretrained("./model")

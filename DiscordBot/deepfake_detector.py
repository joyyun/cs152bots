import torch
from torchvision import transforms
from PIL import Image
from transformers import AutoModelForImageClassification, AutoFeatureExtractor, pipeline
import requests
from io import BytesIO

model_name = "DhruvJariwala/deepfake_vs_real_image_detection"
model = AutoModelForImageClassification.from_pretrained(model_name)
feature_extractor = AutoFeatureExtractor.from_pretrained(model_name)

# Testing URL
# URL = 'https://cdn.britannica.com/70/234870-050-D4D024BB/Orange-colored-cat-yawns-displaying-teeth.jpg'


# Preprocess the image
def preprocess_image(url):
    response = requests.get(url)
    image = Image.open(BytesIO(response.content)).convert("RGB")
    inputs = feature_extractor(images=image, return_tensors="pt")
    return inputs


def predict_deepfake(url):
    inputs = preprocess_image(url)
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        predicted_class_idx = logits.argmax(-1).item()
    ret = f"LOGITS: {logits} \n"
    if predicted_class_idx == 1:
        ret += "The image is AI-generated (deepfake). \n"
    else:
        ret += "The image is not AI-generated (real). \n"
    return ret


def predict_deepfake_nopreprocessing(url):
    pipe = pipeline("image-classification", model=model_name, device=-1)
    response = requests.get(url)
    img = Image.open(BytesIO(response.content))
    return pipe(img)

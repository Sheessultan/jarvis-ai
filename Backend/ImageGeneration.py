import requests
import os
from PIL import Image
from io import BytesIO
from urllib.parse import quote

# =========================================
# CREATE DATA FOLDER
# =========================================

os.makedirs("Data", exist_ok=True)

# =========================================
# GENERATE IMAGE
# =========================================

def GenerateImage(prompt):

    try:

        print("\nGenerating Image...\n")

        encoded_prompt = quote(prompt)

        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}"

        response = requests.get(url, timeout=300)

        print("Status Code:", response.status_code)

        if response.status_code == 200:

            image = Image.open(BytesIO(response.content))

            file_path = f"Data\\{prompt.replace(' ', '_')}.jpg"

            image.save(file_path)

            print(f"Saved: {file_path}")

            os.startfile(file_path)

        else:

            print("Failed to generate image.")

    except Exception as e:

        print(f"Error: {e}")

# =========================================
# MAIN
# =========================================

if __name__ == "__main__":

    print("\n========== AI IMAGE GENERATOR ==========\n")

    prompt = input("Enter Image Prompt: ")

    GenerateImage(prompt)
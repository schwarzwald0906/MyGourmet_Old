import requests, os, json, tempfile
import tensorflow as tf
import numpy as np
from tensorflow.keras.preprocessing.image import load_img, img_to_array
from google.cloud import storage

# def access_secret_version(project_id, secret_id, version_id):
#     client = secretmanager.SecretManagerServiceClient()
#     name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
#     response = client.access_secret_version(request={"name": name})
#     return response.payload.data.decode('UTF-8')


def get_classify_and_save_photos(req: https_fn.Request) -> https_fn.Response:
    credentials_data = access_secret_version(
        "YOUR_PROJECT_ID", "YOUR_CREDENTIALS_SECRET_NAME", "latest"
    )
    refresh_token_data = access_secret_version(
        "YOUR_PROJECT_ID", "YOUR_REFRESH_TOKEN_SECRET_NAME", "latest"
    )
    # Google Cloud Storage client
    storage_client = storage.Client()
    bucket_name = "my-gourmet-image-classification-training-2023-08"
    bucket = storage_client.bucket(bucket_name)

    # # Authentication and get photos
    # with open("credentials.json") as f:
    #     client_secrets = json.load(f)["installed"]

    # with open("refresh_token.json") as f:
    #     refresh_info = json.load(f)

    # data = {
    #     "refresh_token": refresh_info["refresh_token"],
    #     "client_id": client_secrets["client_id"],
    #     "client_secret": client_secrets["client_secret"],
    #     "grant_type": "refresh_token",
    # }

    data = {
        "refresh_token": "1//0e0leMPnwh1WYCgYIARAAGA4SNwF-L9Ir8JN6qCFikK76IghsTlcYPq4Sa9aOu0coUGxWpQ3sNnjtRTDrp9_Y259sGefwjgSH-NQ",
        "client_id": "930146264072-sva6phv52i6g5hh3r339o9q5rn2rcjt9.apps.googleusercontent.com",
        "client_secret": "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",
        "grant_type": "refresh_token",
    }

    token = requests.post(
        "https://www.googleapis.com/oauth2/v4/token", data=data
    ).json()

    response = requests.get(
        "https://photoslibrary.googleapis.com/v1/mediaItems?pageSize=10",
        headers={"Authorization": "Bearer %s" % token["access_token"]},
    )
    photos = response.json()

    # Image classification setup
    image_size = 50
    model_bucket_name = "tflite-my-gourmet-image-classification-training-2023-07"
    model_bucket = storage_client.bucket(model_bucket_name)

    _, model_local_path = tempfile.mkstemp()
    blob_model = model_bucket.blob("gourmet_cnn_vgg_final.tflite")
    blob_model.download_to_filename(model_local_path)

    interpreter = tf.lite.Interpreter(model_path=model_local_path)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    classes = ["ramen", "japanese_food", "international_cuisine", "cafe", "other"]

    for photo in photos["mediaItems"]:
        if photo["mimeType"] == "image/jpeg":
            url = photo["baseUrl"]
            response = requests.get(url)

            if response.status_code == 200:
                # Image classification
                _, temp_local_path = tempfile.mkstemp()
                with open(temp_local_path, "wb") as f:
                    f.write(response.content)

                img = load_img(temp_local_path, target_size=(image_size, image_size))
                x = img_to_array(img)
                x /= 255.0
                x = np.expand_dims(x, axis=0)

                interpreter.set_tensor(input_details[0]["index"], x)
                interpreter.invoke()

                result = interpreter.get_tensor(output_details[0]["index"])
                predicted = result.argmax()

                os.remove(temp_local_path)

                # Save image to Cloud Storage if it belongs to specified classes
                if classes[predicted] in [
                    "ramen",
                    "japanese_food",
                    "international_cuisine",
                    "cafe",
                ]:
                    file_name = photo["filename"]
                    blob = bucket.blob(file_name)
                    blob.upload_from_string(response.content)

    os.remove(model_local_path)
    return https_fn.Response("Processed and saved photos successfully.")

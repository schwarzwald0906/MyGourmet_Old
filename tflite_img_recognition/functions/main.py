import os

os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"

# The Cloud Functions for Firebase SDK to create Cloud Functions and set up triggers.
from firebase_functions import firestore_fn, https_fn

# The Firebase Admin SDK to access Cloud Firestore.
from firebase_admin import initialize_app, firestore
import google.cloud.firestore

from google.cloud import storage
from tensorflow.keras.preprocessing.image import img_to_array, load_img
from PIL import Image
import numpy as np
import tensorflow as tf
import tempfile

app = initialize_app()


# @https_fn.on_request()
# def addmessage(req: https_fn.Request) -> https_fn.Response:
#     """Take the text parameter passed to this HTTP endpoint and insert it into
#     a new document in the messages collection."""
#     # Grab the text parameter.
#     original = req.args.get("text")
#     if original is None:
#         return https_fn.Response("No text parameter provided", status=400)

#     firestore_client: google.cloud.firestore.Client = firestore.client()

#     # Push the new message into Cloud Firestore using the Firebase Admin SDK.
#     _, doc_ref = firestore_client.collection("messages").add({"original": original})

#     # Send back a message that we've successfully written the message
#     return https_fn.Response(f"Message with ID {doc_ref.id} added.")


# @firestore_fn.on_document_created(document="messages/{pushId}")
# def makeuppercase(
#     event: firestore_fn.Event[firestore_fn.DocumentSnapshot | None],
# ) -> None:
#     """Listens for new documents to be added to /messages. If the document has
#     an "original" field, creates an "uppercase" field containg the contents of
#     "original" in upper case."""

#     # Get the value of "original" if it exists.
#     if event.data is None:
#         return
#     try:
#         original = event.data.get("original")
#     except KeyError:
#         # No "original" field, so do nothing.
#         return

#     # Set the "uppercase" field.
#     print(f"Uppercasing {event.params['pushId']}: {original}")
#     upper = original.upper()
#     event.data.reference.update({"uppercase": upper})


def get_classify_and_save_photos(req: https_fn.Request) -> https_fn.Response:
    import requests, os, json, tempfile
    import tensorflow as tf
    import numpy as np
    from tensorflow.keras.preprocessing.image import load_img, img_to_array
    from google.cloud import storage

    # Google Cloud Storage client
    storage_client = storage.Client()
    bucket_name = "my-gourmet-image-classification-training-2023-08"
    bucket = storage_client.bucket(bucket_name)

    # Authentication and get photos
    with open("credentials.json") as f:
        client_secrets = json.load(f)["installed"]

    with open("refresh_token.json") as f:
        refresh_info = json.load(f)

    data = {
        "refresh_token": refresh_info["refresh_token"],
        "client_id": client_secrets["client_id"],
        "client_secret": client_secrets["client_secret"],
        "grant_type": "refresh_token",
    }

    token = requests.post(
        "https://www.googleapis.com/oauth2/v4/token", data=data
    ).json()

    search_request_data = {"pageSize": 100}
    response = requests.post(
        "https://photoslibrary.googleapis.com/v1/mediaItems:search",
        headers={"Authorization": "Bearer %s" % token["access_token"]},
        json=search_request_data,
    )

    photos = response.json()
    # print("Google Photos API response:", photos)

    # Image classification setup
    image_size = 224
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


if __name__ == "__main__":
    # ここでは適当なリクエストオブジェクトをシミュレートします。
    # 必要に応じてリクエストオブジェクトをカスタマイズしてください。
    class DummyRequest:
        pass

    request = DummyRequest()
    response = get_classify_and_save_photos(request)
    print(response)

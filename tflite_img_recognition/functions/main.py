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


@https_fn.on_request()
def get_and_save_photos(req: https_fn.Request) -> https_fn.Response:
    import requests, os, json

    # Google Cloud Storage client
    storage_client = storage.Client()

    # The name for the new bucket
    # bucket_name = "my-gourmet-image-classification-training-2023-07"
    bucket_name = "my-gourmet-image-classification-training-2023-08"

    # Get the bucket
    bucket = storage_client.bucket(bucket_name)

    # Load the client secrets
    with open("credentials.json") as f:
        client_secrets = json.load(f)["installed"]

    # Load the refresh token
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
    response = requests.get(
        "https://photoslibrary.googleapis.com/v1/mediaItems?pageSize=10",
        headers={"Authorization": "Bearer %s" % token["access_token"]},
    )

    photos = response.json()

    for photo in photos["mediaItems"]:
        if photo["mimeType"] == "image/jpeg":
            # Get the url of the photo
            url = photo["baseUrl"]

            # Get the photo data
            response = requests.get(url)

            # Check if the request is successful
            if response.status_code == 200:
                # Get the file name from the photo metadata
                file_name = photo["filename"]

                # Create a blob
                blob = bucket.blob(file_name)

                # Upload the photo data to Cloud Storage
                blob.upload_from_string(response.content)

    return https_fn.Response("Photos downloaded successfully.")


@https_fn.on_request()
def classify_image(req: https_fn.Request) -> https_fn.Response:
    # Define image size
    image_size = 50

    # Initialize a Cloud Storage client
    storage_client = storage.Client()

    # Define the bucket name
    model_bucket_name = "tflite-my-gourmet-image-classification-training-2023-07"
    image_bucket_name = "my-gourmet-image-classification-training-2023-08"

    # Get the bucket for model
    model_bucket = storage_client.bucket(model_bucket_name)
    # Download the model to a temporary file
    _, model_local_path = tempfile.mkstemp()
    blob_model = model_bucket.blob("gourmet_cnn_vgg_final.tflite")
    blob_model.download_to_filename(model_local_path)

    # Initialize the model
    interpreter = tf.lite.Interpreter(model_path=model_local_path)
    interpreter.allocate_tensors()

    # Get input and output details
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    # Get the bucket for images
    image_bucket = storage_client.bucket(image_bucket_name)
    # Get the list of blobs in the bucket
    blobs = image_bucket.list_blobs()

    # Prepare an empty list to store classification results
    results = []

    # Classify each image in the bucket
    for blob in blobs:
        # Download the blob to a temporary file
        _, temp_local_path = tempfile.mkstemp()
        blob.download_to_filename(temp_local_path)

        # Load the image file
        img = load_img(temp_local_path, target_size=(image_size, image_size))

        # Convert the image to an array
        x = img_to_array(img)
        x /= 255.0  # Normalize the image if necessary
        x = np.expand_dims(x, axis=0)

        # Classify the image
        classes = ["ramen", "japanese_food", "international_cuisine", "cafe", "other"]

        # Preprocess and feed the data to the interpreter
        interpreter.set_tensor(input_details[0]["index"], x)
        interpreter.invoke()

        # Get the prediction result
        result = interpreter.get_tensor(output_details[0]["index"])
        predicted = result.argmax()
        percentage = int(result[0][predicted] * 100)

        # Append the result to the list
        results.append((classes[predicted], percentage))

        # Remove the temporary file for the image
        os.remove(temp_local_path)

    # Remove the temporary file for the model
    os.remove(model_local_path)

    # Return the classification results
    return https_fn.Response(str(results))

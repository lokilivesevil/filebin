import os
import time
from datetime import timedelta
from hashlib import md5
from uuid import uuid4

from flask import Flask, request, send_file, render_template
from werkzeug.utils import secure_filename

"""
We are using redis for storing the filename mapping and the 
"""
# importing redis library for integrations with the redis cluster
# would be connecting to the master node in production
import redis
from redis import RedisError, ResponseError, InvalidResponse

redisClient = redis.StrictRedis(decode_responses=True)  # defaults to localhost and 6379 port

"""
LOGGING: Logs would be generated in the file filebin.log
handler: Rotating File Handler (handles log rotation)
Size of Logs: 100MB
Number of backup files: 3
"""
# importing logging library
import logging
from logging.handlers import RotatingFileHandler

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler('filebin.log', maxBytes=104857600, backupCount=3)
handler.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# The upload directory would be in the NFS filesystem shared across all the nodes handling the traffic
UPLOAD_FOLDER = 'uploads/'
app = Flask(__name__, template_folder='templates')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def current_milli_time():
    return round(time.time() * 1000)


@app.route('/', methods=['GET'])
def index():
    return render_template("index.html")


"""
UPLOAD ENDPOINT
Controller for the upload api.
Purpose: Handles the file upload task 
Methods allowed: POST

returns:
    case Success: The webpage with the download Link
    case invalid request: Redirects to main page for uploading file
    case error processing file: Redirects to the main page with a user friendly message

functionality:
    1) checks if the request is valid
    2) generates a unique hash for the filename (md5 of (uuid + filename)) to guarantee uniqueness
    3) keep the mapping of this unique hash to the filename 
    4) set expiry of the files to 2 days

"""


@app.route('/upload', methods=['POST'])
def upload_file():
    # check if the post request has the file part
    if 'file' not in request.files:
        logger.info('Invalid Request! No file attached.')
        return render_template("index.html", display="block", message="Please select 1 file for uploading")
    file = request.files['file']
    # Check if the filename is not blank
    if file.filename == '':
        logger.info('Invalid Request! Invalid filename.')
        return render_template("index.html", display="block", message="File should have a valid filename")
    else:
        # extract the filename
        filename = secure_filename(file.filename)
        uniqueName = str(uuid4()) + filename
        hashedKey = md5(uniqueName.encode()).hexdigest()
        try:
            # mapping the hash with the filename
            # using redis to store the filedata
            redisClient.setex(hashedKey, timedelta(hours=48), filename)
            # save the file in the upload directory
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], hashedKey))

            logger.info("File saved successfully")
            # send file name as parameter to downlad
            download_link = "http://127.0.0.1:5000/download/" + hashedKey
            return render_template('status.html', download_link=download_link)
        except (RedisError, ResponseError, InvalidResponse) as ex:
            logger.error("Error while writing key to Influx. Error is " + ex)
            logger.error(
                "Error while inserting key into Redis. Method: upload_file(), Filename: " + filename + ", Error: " + ex)
        except Exception as ex:
            logger.error(
                "Error while saving file to disk. Method: upload_file(), Filename: " + filename + ", Error: " + ex)
            return render_template("index.html", display="block",
                                   message="We are experiencing some technical issues. Please retry after some time.")
    return render_template("index.html", display="block",
                           message="We are experiencing some technical issues. Please retry after some time")


"""
DOWNLOAD ENDPOINT
Controller for the download file api.
Purpose: returns the file and deletes it from the system 
Methods allowed: GET

functionality:
    1) checks if the hash is present in redis cluster
    2) if yes then fetches the file and deletes the key from redis
    3) if no then returns a user friendly message to the user saying invalid request

returns:
    case hash_found: fetches the file, delete the redis entry
    case hash_not_found: returns a user friendly message saying invalid url

"""


@app.route("/download/<hashedValue>", methods=['GET'])
def download_file(hashedValue):
    try:
        """
            creating a pipeline in redis to make the transactions atomic and preserve the order or GET AND DELETE operations.
            Redis itself internally processes these pipelined transactions atomically thus ensuring no two GET request would be 
            executed parallely or sequentially
        """
        pipe = redisClient.pipeline()
        pipe.get(hashedValue)
        pipe.delete(hashedValue)
        txnResp = pipe.execute()
        filename = txnResp[0]
        logger.info("Download request for " + hashedValue)
        if filename:
            file_path = UPLOAD_FOLDER + hashedValue
            logger.info("Sending the file: " + filename)
            return send_file(file_path, as_attachment=True, attachment_filename=filename)
        logger.info("File expired or downloaded already")
        return render_template('download.html',
                               message="Either someone else downloaded this file or it expired. Please ask the uploader to generate a fresh URL.")
    except (RedisError, ResponseError, InvalidResponse) as ex:
        logger.error(
            "Error while fetching or deleting key from Redis. Method: download_file(), HashedValue: " + hashedValue + ", Error: " + ex)
        return render_template("index.html", display="block",
                               message="We are experiencing some technical issues. Please retry after some time.")
    except Exception as ex:
        logger.error(
            "Error while fetching file from disk. Method: download_file(), HashedValue: " + hashedValue + ", Error: " + ex)
        return render_template("index.html", display="block",
                               message="We are experiencing some technical issues. Please retry after some time.")


if __name__ == "__main__":
    app.run(host='0.0.0.0')

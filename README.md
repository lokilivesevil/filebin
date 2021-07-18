# filebin
Application that enables file sharing. Uploader uploads the file and shares the download link with the recipient. Recipient can download the file from that link.

Constraints:
1) Files only downloadable once.
2) File size less than 10MB
3) Files available only for 2 days

Methods:
  # upload_files():
  Purpose: Handles the file upload task 
  Methods allowed: POST
  Returns:
    case Success: The webpage with the download Link
    case invalid request: Redirects to main page for uploading file
    case error processing file: Redirects to the main page with a user friendly message
  Functionality:
    1) checks if the request is valid
    2) generates a unique hash for the filename (md5 of (uuid + filename)) to guarantee uniqueness
    3) keep the mapping of this unique hash to the filename 
    4) set expiry of the files to 2 days
    
  # download_files()
  Purpose: returns the file and deletes it from the system 
  Methods allowed: GET
  Returns:
    case hash_found: fetches the file, delete the redis key
    case hash_not_found: returns a user friendly message saying invalid url
  Functionality:
    1) checks if the hash is present in redis cluster
    2) if yes then fetches the file and deletes the key from redis
    3) if no then returns a user friendly message to the user saying invalid request
    
# KONG API Gateway
Its assumed that KONG is being used as an API Gateway. It handles the traffic distribution, health checks etc across all the nodes.
Also adding new nodes for scaling can be done simply by adding the node to the kong upstream via the REST API (or KONG UI).

# Only downloadable once contraint
Component used: Redis Cluster
Generating a unique hash corresponding to every upload file and storing the mapping of the hash and filename as key and value with 2 days expiry.
Logic: 
  1) to handle only one download we need to ensure that no two GET requests on the same key are executed together.
  2) Using redis pipelines to execute GET and DELETE operations in one transaction. This way redis ensures DELETE is followed by the GET request.

# File availability across distributed Nodes.
Current implementation uses NFS filesystem protocol to have the upload directory available to all the nodes.
Pros: 
  Easy Integration
Cons:
  Network Outages
  High IO ( in case of high throughput)

# Alternatives
  Using MongoDB GRIDFS or Amazon S3
  MongoDB GRIDFS: 
    Pros:
        MONGODB Cluster handles the redundancy and availability across all the nodes
        OpenSource
    Cons:
        Expertise required for setup and management.
        no autoscaling for higher throughputs
  Amazon S3:
    Pros:
        Handles redundancy and availability
        handles all traffic
    Cons:
        Cost
        
# File Deletions
A separate application handles the actual deletion of the files from filesystem
Redis publishes the DELETE and EXPIRY events to a channel and this application would subscribe to the same channel and DELETE the files corresponding to each event.
Please refer the fileDeletion.py for the same

import redis 

#connection to the redis client (host:localhost and port:6379)
redisClient = redis.StrictRedis(decode_responses=True) 

#Subscribing to the expired event channel
pubsub_channel = "__keyevent@0__:expired"

def process(): 
    """Process messages from the pubsub stream.""" 
    ps = redisClient.pubsub() 
    ps.psubscribe(pubsub_channel) 

    for raw_message in ps.listen(): 
        #print(raw_message) 
        if raw_message["type"] != "pmessage" and raw_message["pattern"] != "__keyevent@0__:expired": 
            continue 
        hashValue = raw_message["data"] 
        delete_file(hashValue) 

def delete_file(hashValue):
	"""
	file deletion logic here
	"""
	return True

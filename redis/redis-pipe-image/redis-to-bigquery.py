#!/usr/bin/env python
# Copyright 2014 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""This script grabs tweets from a redis server, and stores them in BiqQuery
using the BigQuery Streaming API.
"""

import json
import os
import time

from apiclient import discovery
import httplib2
from oauth2client.client import GoogleCredentials
import redis

import utils

# Get info on the Redis host and port from the environment variables.
# The name of this variable comes from the redis service id, 'redismaster'.
REDIS_HOST = os.environ['REDISMASTER_SERVICE_HOST']
REDIS_PORT = os.environ['REDISMASTER_SERVICE_PORT']
REDIS_LIST = os.environ['REDISLIST']

r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=0)

# Get the project ID from the environment variable set in
# the 'bigquery-controller.yaml' manifest.
PROJECT_ID = os.environ['PROJECT_ID']
BQ_SCOPES = ['https://www.googleapis.com/auth/bigquery']


def create_bigquery_client():
    """Build the bigquery client."""
    credentials = GoogleCredentials.get_application_default()
    if credentials.create_scoped_required():
            credentials = credentials.create_scoped(BQ_SCOPES)
    http = httplib2.Http()
    credentials.authorize(http)
    return discovery.build('bigquery', 'v2', http=http)


def write_to_bq(bigquery):
    """Write the data to BigQuery in small chunks."""
    tweets = []
    CHUNK = 50  # The size of the BigQuery insertion batch.
    twstring = ''
    tweet = None
    mtweet = None
    while True:
        while len(tweets) < CHUNK:
            # We'll use a blocking list pop -- it returns when there is
            # new data.
            res = r.brpop(REDIS_LIST)
            twstring = res[1]
            try:
                tweet = json.loads(res[1])
            except Exception, bqe:
                print bqe
                continue
            # First do some massaging of the raw data
            mtweet = utils.cleanup(tweet)
            # We only want to write tweets to BigQuery; we'll skip 'delete' and
            # 'limit' information.
            if 'delete' in mtweet:
                continue
            if 'limit' in mtweet:
                print mtweet
                continue
            tweets.append(mtweet)
        # try to insert the tweets into bigquery
        utils.bq_data_insert(bigquery, PROJECT_ID, os.environ['BQ_DATASET'],
                             os.environ['BQ_TABLE'], tweets)
        tweets = []


if __name__ == '__main__':
    print "starting write to BigQuery...."
    bigquery = create_bigquery_client()
    write_to_bq(bigquery)

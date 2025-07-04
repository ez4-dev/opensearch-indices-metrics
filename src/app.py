import requests
import os
import re
from datetime import datetime
from collections import defaultdict
from prometheus_client import Enum, Gauge, generate_latest, CollectorRegistry, start_http_server
from apscheduler.schedulers.background import BackgroundScheduler

# constants
HEALTH = "health"
INDEX = "index"
DOCS_COUNT = "docs.count"
DOCS_DELETED = "docs.deleted"
STORE_SIZE = "store.size"
PRI_STORE_SIZE = "pri.store.size"

# Environment variable for the port to run the Prometheus metrics server
PORT_STR=os.environ.get('PORT', '3000').strip()

# Environment variables for OpenSearch connection
OPENSEARCH_HOST = os.environ.get('OPENSEARCH_HOST', 'http://your-opensearch-host:9200').strip()
OPENSEARCH_USER = os.environ.get('OPENSEARCH_USER', 'admin').strip()
OPENSEARCH_PASSWORD = os.environ.get('OPENSEARCH_PASSWORD', 'admin').strip()

# Environment variable for the index pattern regex, $1 will be used to extract the prefix
# Default regex matches indices with a date suffix like 'index-2025.10.01'
INDEX_PATTERN_REGEX = os.environ.get('INDEX_PATTERN_REGEX', '^(.+)(-[0-9]{4}\\.[0-9]{2}\\.[0-9]{2})$').strip()

# Initialize Prometheus metrics
default_labels = ['service_url', 'index_group']
health_status = Enum('opensearch_index_health_status', 'Health status of the index', default_labels, states=['red', 'yellow', 'green'])
docs_count_gauge = Gauge('opensearch_index_docs_count', 'Document count of the index', default_labels)
docs_deleted_gauge = Gauge('opensearch_index_docs_deleted', 'Deleted document count of the index', default_labels)
store_size_gauge = Gauge('opensearch_index_store_size_bytes', 'Store size of the index in bytes', default_labels)
pri_store_size_gauge = Gauge('opensearch_index_pri_store_size_bytes', 'Primary store size of the index in bytes', default_labels)

# Function to extract prefix
def extract_prefix(index_name):
    result = re.match(INDEX_PATTERN_REGEX, index_name)
    if result:
        return result.group(1)
    return 'others'  # No match is found

def sum_health_status(current_index_health, new_index_health):
    if current_index_health == 'red' or new_index_health == 'red':
        return 'red'
    elif current_index_health == 'yellow' or new_index_health == 'yellow':
        return 'yellow'
    else:
        return 'green'

def load_indices_metrics():
    response = requests.get(
        f'{OPENSEARCH_HOST}/_cat/indices?format=json&bytes=b',
        auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD)
    )
    response.raise_for_status()
    indices = response.json()
    
    # Group data by prefix
    grouped_data = defaultdict(lambda: {
        HEALTH: 'green',
        DOCS_COUNT: 0,
        DOCS_DELETED: 0,
        STORE_SIZE: 0, 
        PRI_STORE_SIZE: 0
    })

    for index in indices:
        index_name = index[INDEX]
        print(f"Processing index: {index_name}")
        prefix = extract_prefix(index_name)
        grouped_data[prefix][HEALTH] = sum_health_status(
            grouped_data[prefix][HEALTH],
            index[HEALTH]
        )
        grouped_data[prefix][DOCS_COUNT] += int(index[DOCS_COUNT])
        grouped_data[prefix][DOCS_DELETED] += int(index[DOCS_DELETED])
        grouped_data[prefix][STORE_SIZE] += int(index[STORE_SIZE])
        grouped_data[prefix][PRI_STORE_SIZE] += int(index[PRI_STORE_SIZE])

    # Clear previous metrics
    health_status.clear()
    docs_count_gauge.clear()
    docs_deleted_gauge.clear()
    store_size_gauge.clear()
    pri_store_size_gauge.clear()    

    # Sort items by store.size descending
    for prefix, sums in sorted(grouped_data.items(), key=lambda item: item[1][STORE_SIZE], reverse=True):
        # Debug logging
        print(f"Prefix: {prefix}")
        print(f"  Health              : {sums[HEALTH]}")
        print(f"  Total docs.count    : {sums[DOCS_COUNT]:_}")
        print(f"  Total docs.deleted. : {sums[DOCS_DELETED]:_}")
        print(f"  Total store.size    : {sums[STORE_SIZE]/1024/1024/1024:.2f} GB")
        print(f"  Total pri.store.size: {sums[PRI_STORE_SIZE]/1024/1024/1024:.2f} GB")

        # Set the metrics
        health_status.labels(service_url=OPENSEARCH_HOST, index_group=prefix).state(sums[HEALTH])
        docs_count_gauge.labels(service_url=OPENSEARCH_HOST, index_group=prefix).set(sums[DOCS_COUNT])
        docs_deleted_gauge.labels(service_url=OPENSEARCH_HOST, index_group=prefix).set(sums[DOCS_DELETED])
        store_size_gauge.labels(service_url=OPENSEARCH_HOST, index_group=prefix).set(sums[STORE_SIZE])
        pri_store_size_gauge.labels(service_url=OPENSEARCH_HOST, index_group=prefix).set(sums[PRI_STORE_SIZE])
    
    print(f"Metrics updated successfully at {datetime.now()}")
    print("==========================================", flush=True)

if __name__ == '__main__':
    print(f"Starting OpenSearch indices metrics exporter on port {PORT_STR}, with regex pattern: {INDEX_PATTERN_REGEX}")

    # Load metrics on startup
    load_indices_metrics()

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=load_indices_metrics,
        trigger='interval',
        minutes=int(os.environ.get('METRICS_UPDATE_INTERVAL', 1)),  # Default to 1 minute
        id='load_indices_metrics',
        replace_existing=True
    )
    scheduler.start()

    server, t = start_http_server(port=int(PORT_STR))
    # server.shutdown()
    t.join()
